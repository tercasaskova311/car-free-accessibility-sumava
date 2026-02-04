from loader import DataLoader
from network_layer import NetworkBuilder
from base_map import BaseLayers
from trails_layer import TrailsLayers
from heatmap import HeatMapLayer
from spatial_analysis import LocationAnalyzer, SpatialAutocorrelation
import sys
from pathlib import Path
import folium
import geopandas as gpd
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import Config


def stats(study_area, rides, network):
    print("\n========== SUMMARY ==========")
    print(f"Total Rides:     {len(rides)}")
    print(f"Average Ride:    {rides['distance_km'].mean():.1f} km")
    print(f"Longest Ride:    {rides['distance_km'].max():.1f} km")

    print(f"\nNetwork:")
    print(f"  Total km of trails in the study area:  {network['distance_km'].sum():.1f} km")
    print(f"  Most Popular:  {network['ride_count'].max()} rides on given one segment")

    candidates_path = Config.OUTPUT_DIR / 'candidate_locations.gpkg'
    if candidates_path.exists():
        candidates = gpd.read_file(candidates_path)
        print(f"\n=== SPATIAL ANALYSIS RESULTS ===")
        print(f"Trail Center Candidates: {len(candidates)} locations")

        if hasattr(candidates, 'attrs') and 'global_morans_i' in candidates.attrs:
            gm = candidates.attrs['global_morans_i']
            print(f"\nGlobal Moran's I: {gm['morans_i']:.4f} (p={gm['p_value']:.4f})")
            print(f"Interpretation: {gm['interpretation']}")

        best = candidates.iloc[0]
        print(f"\n🏆 OPTIMAL LOCATION:")
        print(f"  Coordinates:  {best.geometry.y:.4f}°N, {best.geometry.x:.4f}°E")
        print(f"  Score:        {best['suitability_score']:.1f}/100")
        print(f"  Local I:      {best.get('mean_local_morans_i', 0):.3f}")
        print(f"  Zone:         {best['zone_type']} "
              f"{'❌ PROHIBITED' if best['in_prohibited_zone'] else '✓ PERMITTED'}")

    print(f"\nOutput: {Config.OUTPUT_MAP}")


def main():
    Config.ensure_directories()

    # === STEP 1: LOAD BASE DATA ===
    print("MTB TRAIL CENTER PLANNER - SPATIAL AUTOCORRELATION ANALYSIS")

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
        print("\n Building trail network...")
        network = NetworkBuilder.create_network_sequential(
            rides,
            tolerance=Config.SNAP_TOLERANCE
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

    print("\nRUNNING SPATIAL AUTOCORRELATION ANALYSIS")
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
    # STEP 5: SANITISE DATA BEFORE PASSING TO MAP LAYERS
    # =========================================================================
    # network['rides'] is a column of Python lists (avg 670 dicts each).
    # rides['start_point'] / ['end_point'] are tuples.
    # Folium serialises everything in the GeoDataFrame to GeoJSON → HTML.
    # These columns alone would bloat the file by hundreds of MB.
    # Keep a reference copy for popup lookups, then drop from the main frames.
    # =========================================================================

    # Drop the 'rides' column completely before passing to map layers
    network_map = network.drop(columns=['rides'], errors='ignore').copy()

    # Ensure we keep only the columns needed for rendering
    essential_network_cols = ['segment_id', 'geometry', 'ride_count', 'distance_km']
    network_map = network_map[essential_network_cols].copy()

    # For rides, drop problematic columns
    rides_map = rides.drop(
        columns=['start_point', 'end_point'],
        errors='ignore'
    ).copy()

    print(f"\n  ✓ Sanitized data:")
    print(f"     network_map: {len(network_map)} segments with columns: {list(network_map.columns)}")
    print(f"     rides_map: {len(rides_map)} rides with columns: {list(rides_map.columns)}")
        # === STEP 6: CREATE INTERACTIVE MAP ===
    print("\n  Creating interactive map...")

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

    # Trail network coloured by popularity  (pass lookup dict for popups)
    print(f"   Adding trail network ({len(network_map)} segments)...")
    TrailsLayers.add_trail_net(m, network_map)

    # Rides by length (subsampled inside the function)
    print(f"   Adding rides by length...")
    TrailsLayers.add_rides_by_length(m, rides_map)

    # Heatmap (subsampled inside the function)
    print(f"   Adding heatmap...")
    HeatMapLayer.add_heatmap(m, rides_map)

    # Candidate markers
    candidates = gpd.read_file(candidates_file)
    TrailsLayers.add_candidate_locations(m, candidates, protected_zones)

    # Info panel
    BaseLayers.add_description(m, network_map, candidates)

    # Layer control
    print(f"   Adding layer control...")
    folium.LayerControl(position='topright', collapsed=False).add_to(m)

    # Save
    BaseLayers.save_map(m, Config.OUTPUT_MAP)

    # === STEP 7: PRINT SUMMARY ===
    stats(study_area, rides, network)


if __name__ == "__main__":
    main()