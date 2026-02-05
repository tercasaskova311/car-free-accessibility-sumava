from loader import DataLoader
from network_layer import NetworkBuilder
from base_map import BaseLayers
from trails_layer import TrailsLayers
from heatmap import HeatMapLayer
from spatial_analysis import LocationAnalyzer, SpatialAutocorrelation
from render_optimizer import RenderOptimizer  # ← NEW
import sys
from pathlib import Path
import folium
import geopandas as gpd
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import Config


def stats(study_area, rides, network):
    """Print summary statistics"""
    print("\n" + "="*70 )
    print("ANALYSIS SUMMARY")
    print("="*70)
    print(f"\n DATA:")
    print(f"   Total Rides:     {len(rides):,}")
    print(f"   Total Distance:  {rides['distance_km'].sum():.1f} km")
    print(f"   Average Ride:    {rides['distance_km'].mean():.1f} km")
    print(f"   Longest Ride:    {rides['distance_km'].max():.1f} km")

    print(f"\nNETWORK:")
    print(f"   Total Segments:  {len(network):,}")
    print(f"   Total Length:    {network['distance_km'].sum():.1f} km")
    print(f"   Avg Segment:     {network['distance_km'].mean()*1000:.0f} m")
    print(f"   Most Popular:    {network['ride_count'].max()} rides on one segment")
    
    # Quality check
    print(f"\nQUALITY CHECKS:")
    count_ratio = network['ride_count'].sum() / len(rides)
    print(f"   Ride count ratio: {count_ratio:.2f}x")
    if count_ratio > 3.0:
        print(f"WARNING: High double-counting detected!")
        print(f"Each ride counted ~{count_ratio:.1f} times")
        print(f"Consider: reducing INTERSECTION_BUFFER or rebuilding network")
    elif count_ratio > 2.0:
        print(f"Moderate double-counting (acceptable for complex routes)")
    else:
        print(f"Minimal double-counting - good quality!")
    
    tiny_segments = (network['distance_km'] < 0.2).sum()
    tiny_pct = tiny_segments / len(network) * 100
    print(f"   Segments < 200m: {tiny_segments:,} ({tiny_pct:.1f}%)")
    if tiny_pct > 30:
        print(f"High fragmentation - consider increasing SNAP_TOLERANCE")
    else:
        print(f"Good segmentation")

    # Spatial analysis results
    candidates_path = Config.OUTPUT_DIR / 'candidate_locations.gpkg'
    if candidates_path.exists():
        candidates = gpd.read_file(candidates_path)
        print(f"\n SPATIAL ANALYSIS:")
        print(f"   Candidates Found: {len(candidates)}")

        if hasattr(candidates, 'attrs') and 'global_morans_i' in candidates.attrs:
            gm = candidates.attrs['global_morans_i']
            print(f"   Global Moran's I: {gm['morans_i']:.4f} (p={gm['p_value']:.4f})")
            print(f"   {gm['interpretation']}")

        best = candidates.iloc[0]
        print(f"\n🏆 OPTIMAL LOCATION:")
        print(f"   Coordinates:  {best.geometry.y:.4f}°N, {best.geometry.x:.4f}°E")
        print(f"   Score:        {best['suitability_score']:.1f}/100")
        print(f"   Local I:      {best.get('mean_local_morans_i', 0):.3f}")
        print(f"   Trail Access: {int(best['trail_count'])} segments ({best['trail_length_km']:.1f} km)")
        print(f"   Zone:         {best['zone_type']} "
              f"{'❌ PROHIBITED' if best['in_prohibited_zone'] else '✅ PERMITTED'}")

    print(f"\n📄 Output: {Config.OUTPUT_MAP}")
    print("="*70)


def main():
    Config.ensure_directories()
    Config.print_settings()  # ← Show current settings

    # === STEP 1: LOAD BASE DATA ===
    print("\n" + "="*70)
    print("MTB TRAIL CENTER PLANNER - SPATIAL ANALYSIS")
    print("="*70)

    study_area, rides = DataLoader.load_data(Config.STUDY_AREA, Config.STRAVA_RIDES)

    # === STEP 2: CLEAN & ENRICH RIDES ===
    rides = DataLoader.clean_ride_names(rides)
    rides = DataLoader.calculate_km(rides)

    # === STEP 3: BUILD OR LOAD NETWORK ===
    if Config.TRAIL_NETWORK.exists():
        print(f"\n Loading existing network from {Config.TRAIL_NETWORK}")
        network = gpd.read_file(Config.TRAIL_NETWORK)
        print("   Re-mapping rides to network segments...")
        network = NetworkBuilder.map_rides_to_segments(
            network,
            rides,
            buffer_distance=Config.INTERSECTION_BUFFER
        )
    else:
        print("\n Building trail network from scratch...")
        network = NetworkBuilder.create_network_sequential(
            rides,
            tolerance=Config.SIMPLIFY_TOLERANCE,
            snap_tolerance=Config.SNAP_TOLERANCE
        )
        network = NetworkBuilder.map_rides_to_segments(
            network,
            rides,
            buffer_distance=Config.INTERSECTION_BUFFER
        )
        NetworkBuilder.save_network(network, Config.TRAIL_NETWORK)

    # === STEP 4: SPATIAL AUTOCORRELATION ANALYSIS ===
    protected_zones_file = Path('data/sumava_zones_2.geojson')
    protected_zones = gpd.read_file(protected_zones_file) if protected_zones_file.exists() else None

    print("\n" + "="*70)
    print("SPATIAL AUTOCORRELATION ANALYSIS")
    print("="*70)
    results = LocationAnalyzer.analyze(network, rides, study_area, protected_zones)

    candidates_file = Config.OUTPUT_DIR / 'candidate_locations.gpkg'
    LocationAnalyzer.save_results(results, candidates_file)

    # Save network with LISA for reference
    network_proj = network.to_crs("EPSG:32633")
    network_with_lisa = SpatialAutocorrelation.calculate_local_morans_i(
        network_proj,
        attribute='ride_count',
        distance_threshold=2000
    )
    network_lisa_file = Config.OUTPUT_DIR / 'network_with_lisa.gpkg'
    network_with_lisa.to_crs(network.crs).to_file(network_lisa_file, driver='GPKG')
    print(f"✓ Network with LISA statistics saved to {network_lisa_file}")

    # =========================================================================
    # STEP 5: OPTIMIZE DATA FOR HTML RENDERING
    # =========================================================================
    # KEY CONCEPT: Analysis is done on FULL network, but HTML shows SAMPLE
    # This gives you accurate results with fast loading times
    # =========================================================================
    
    print("\n" + "="*70)
    print("OPTIMIZING DATA FOR HTML RENDERING")
    print("="*70)
    
    # Keep full network for statistics in the info panel
    network_full = network.copy()
    rides_full = rides.copy()
    
    # Optimize for rendering using RenderOptimizer
    #network_optimized, rides_optimized = RenderOptimizer.optimize_for_render(
    #    network=network,
    #    rides=rides,
    #    max_network=Config.BASE_TRAIL_SAMPLE_SIZE,
    #    max_rides=Config.MAX_TOTAL_RIDES_RENDER,
    #    simplify_tolerance=Config.RENDER_SIMPLIFY_M,
    #    sampling_strategy=Config.TRAIL_RENDER_STRATEGY
    #)
    
    # Drop problematic columns that crash Folium
    network_map = network.drop(columns=['rides'], errors='ignore')
    rides_map = rides.drop(
        columns=['start_point', 'end_point'],
        errors='ignore'
    )
    
    #print(f"\n✅ Data sanitized for rendering:")
    #print(f"   network_map columns: {list(network_map.columns)}")
    #print(f"   rides_map columns:   {list(rides_map.columns)}")

    # === STEP 6: CREATE INTERACTIVE MAP ===
    print("\n" + "="*70)
    print("CREATING INTERACTIVE MAP")
    print("="*70)

    bounds = study_area.total_bounds
    center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
    print(f"   Map center: {center}")

    m = BaseLayers.create_base_map(center, Config.DEFAULT_ZOOM)
    print(f"   ✓ Base map created")

    # Study area boundary
    BaseLayers.add_study_area(m, study_area)
    print(f"   ✓ Study area added")

    # Protected zones
    if protected_zones is not None:
        TrailsLayers.add_protected_zones(m, protected_zones)

    # Trail network (using OPTIMIZED sample)
    print(f"   Adding trail network ({len(network_map)} segments)...")
    TrailsLayers.add_trail_net(m, network_map)

    # Rides by length (using OPTIMIZED sample)
    print(f"   Adding rides by length...")
    TrailsLayers.add_rides_by_length(m, rides_map)

    # Heatmap (will be subsampled inside the function)
    print(f"   Adding heatmap...")
    HeatMapLayer.add_heatmap(m, rides_map)

    # Candidate markers
    candidates = gpd.read_file(candidates_file)
    TrailsLayers.add_candidate_locations(m, candidates, protected_zones)

    # Info panel - USE FULL NETWORK for accurate statistics!
    BaseLayers.add_description(m, network_full, candidates)

    # Layer control
    print(f"   Adding layer control...")
    folium.LayerControl(position='topright', collapsed=False).add_to(m)

    # Save
    BaseLayers.save_map(m, Config.OUTPUT_MAP)
    
    # Check file size
    html_size_mb = Path(Config.OUTPUT_MAP).stat().st_size / (1024 * 1024)
    print(f"\n📄 HTML file size: {html_size_mb:.1f} MB")
    if html_size_mb > 50:
        print(f"   ⚠️  WARNING: File is large, may be slow to load")
        print(f"      Consider reducing BASE_TRAIL_SAMPLE_SIZE or RENDER_SIMPLIFY_M")
    elif html_size_mb > 30:
        print(f"   ⚠️  File is moderately large")
    else:
        print(f"   ✅ File size is good for fast loading")

    # === STEP 7: PRINT SUMMARY ===
    stats(study_area, rides_full, network_full)


if __name__ == "__main__":
    main()