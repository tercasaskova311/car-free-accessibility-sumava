# Main script to run the MTB trail center planner
#loads data, builds network, performs spatial analysis, and creates interactive map

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
from network_layer import OptimizedNetworkBuilder



def stats(study_area, rides, network, candidates=None):
    print("stats")
    
    # ========== RIDE DATA ==========
    print(f"RIDE DATA:")
    print(f"Total Rides:{len(rides):,}")
    print(f"Total Distance:{rides['distance_km'].sum():.1f} km (sum of all rides)")
    print(f"Average Ride:{rides['distance_km'].mean():.1f} km")
    print(f"Median Ride:{rides['distance_km'].median():.1f} km")
    print(f"Longest Ride:{rides['distance_km'].max():.1f} km")
    
    
    # ========== USAGE PATTERNS: 
    # simple traffic categories based on ride counts per segment, plus mean/median rides per segment for context

    print(f"USAGE PATTERNS:")
    high_traffic = len(network[network['ride_count'] >= 5])
    medium_traffic = len(network[(network['ride_count'] >= 3) & (network['ride_count'] < 5)])
    low_traffic = len(network[network['ride_count'] < 3])

    print(f"High-traffic trails (≥5 rides):{high_traffic:3d} segments ({high_traffic/len(network)*100:.1f}%)")
    print(f"Medium-traffic trails (3-4 rides):{medium_traffic:3d} segments ({medium_traffic/len(network)*100:.1f}%)")
    print(f"Low-traffic trails (1-2 rides):{low_traffic:3d} segments ({low_traffic/len(network)*100:.1f}%)")
    print(f"Mean rides per segment:{network['ride_count'].mean():.1f}")
    print(f"Median rides per segment:{network['ride_count'].median():.0f}")
    
    # ========== QUALITY CHECKS ==========
    # Check the ratio of total ride-segment intersections to total rides
    # gives a sense of how well the network captures the routes without over-segmenting or under-segmenting

    print(f"QUALITY CHECKS:")
    count_ratio = network['ride_count'].sum() / len(rides)
    print(f"Ride-to-segment ratio: {count_ratio:.2f}x")

    if count_ratio > 3.0:
        print(f"High ratio: Each ride crosses ~{count_ratio:.1f} segments on average")
        print(f"(This is expected for long rides on interconnected networks)")
    elif count_ratio > 2.0:
        print(f"Moderate ratio: Typical for complex trail networks")
    else:
        print(f"Low ratio: Good segmentation quality")
    
    # ========== CANDIDATE LOCATION ==========
    # If candidates were identified = print details and the global Moran's I statistic for spatial autocorrelation of trail usage

    if candidates is not None and len(candidates) > 0:
        from pathlib import Path
        import geopandas as gpd
        
        candidates_path = Path('maps/candidate_locations.gpkg')
        if candidates_path.exists():
            candidates = gpd.read_file(candidates_path)
            
            print(f"SPATIAL ANALYSIS:")
            print(f"Candidates Found: {len(candidates)}")
            
            if hasattr(candidates, 'attrs') and 'global_morans_i' in candidates.attrs:
                gm = candidates.attrs['global_morans_i']
                print(f"Global Moran's I:{gm['morans_i']:.4f} (p={gm['p_value']:.4f})")
                print(f"Interpretation:{gm['interpretation']}")
            
            best = candidates.iloc[0]
            second = candidates.iloc[1] if len(candidates) > 1 else None
            third = candidates.iloc[2] if len(candidates) > 2 else None
            print(f"TOP CANDIDATE LOCATIONS:")

            top_k = min(3, len(candidates))

            for i in range(top_k):
                row = candidates.iloc[i]

                print(f"\n#{int(row['rank'])} CANDIDATE")
                print(f"Coordinates:{row.geometry.y:.4f}°N, {row.geometry.x:.4f}°E")
                print(f"Suitability Score:{row['suitability_score']:.1f}/100")
                print(f"Local Moran's I:{row.get('mean_local_morans_i', 0):.3f}")
                print(f"Trail Access (5km radius):")
                print(f"• Segments:{int(row['trail_count'])}")
                print(f"• Total Rides:{int(row['total_rides'])}")
                print(f"Hotspot Segments:{int(row.get('hotspot_segments', 0))}")
                print(f"Protected Zone:{row['zone_type']} "
                    f"{'PROHIBITED' if row['in_prohibited_zone'] else 'PERMITTED'}")

def main():
    study_area, rides = DataLoader.load_data(Config.STUDY_AREA, Config.STRAVA_RIDES)

    rides = DataLoader.clean_ride_names(rides)
    rides = DataLoader.calculate_km(rides)

    # === BUILD OR LOAD NETWORK ===
    if Config.TRAIL_NETWORK.exists():
        print(f"Loading existing network from {Config.TRAIL_NETWORK}")
        network = gpd.read_file(Config.TRAIL_NETWORK)
        print("Re-mapping rides to network segments...")
        network = NetworkBuilder.map_rides_to_segments_vectorized(
            network,
            rides,
            buffer_distance=Config.INTERSECTION_BUFFER
        )
    else:
        print("\n Building trail network from scratch...")
        network = NetworkBuilder.create_network_grid_based(rides)
        network = NetworkBuilder.map_rides_to_segments_vectorized(network, rides, buffer_distance=Config.INTERSECTION_BUFFER)
        NetworkBuilder.save_network(network, Config.TRAIL_NETWORK)
    

    # SPATIAL AUTOCORRELATION ANALYSIS
    protected_zones_file = Path('data/sumava_zones_2.geojson')
    protected_zones = gpd.read_file(protected_zones_file) if protected_zones_file.exists() else None

    print("SPATIAL AUTOCORRELATION ANALYSIS")
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

   
    # Analysis is done on FULL network, but HTML shows SAMPLE (fast loading times)    
    print("OPTIMIZING DATA FOR HTML RENDERING")
    
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
    
    #CREATE INTERACTIVE MAP ===
    print("CREATING INTERACTIVE MAP")

    bounds = study_area.total_bounds
    center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
    print(f"   Map center: {center}")

    m = BaseLayers.create_base_map(center, Config.DEFAULT_ZOOM)
    print(f"Base map created")

    # Study area boundary
    BaseLayers.add_study_area(m, study_area)
    print(f"Study area added")

    # Protected zones
    if protected_zones is not None:
        TrailsLayers.add_protected_zones(m, protected_zones)

    # Trail network (using OPTIMIZED sample)
    print(f"Adding trail network ({len(network_map)} segments)...")
    TrailsLayers.add_trail_net(m, network_map)

    TrailsLayers.trails_in_hh(m, network_with_lisa.to_crs(network.crs))
    print(f"Highlighted High-High LISA clusters")
    
    # Heatmap (will be subsampled inside the function)
    print(f"Adding heatmap...")
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

    # === STEP 7: PRINT SUMMARY ===
    stats(study_area, rides_full, network_full)


if __name__ == "__main__":
    main()