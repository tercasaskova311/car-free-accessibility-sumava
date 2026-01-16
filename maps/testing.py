from loader import DataLoader
from network_layer import NetworkBuilder
from base_map import BaseLayers
from bike_layer import BikeLayers
from heatmap import HeatMapLayer
from analysis import SuitabilityAnalyzer
import sys
from pathlib import Path
import folium
import geopandas as gpd
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import Config


def stats(study_area, rides, network):
    print("sumary:")
    print(f"   Total Rides: {len(rides)}")
    print(f"   Total Distance: {rides['distance_km'].sum():.1f} km")
    print(f"   Average Ride: {rides['distance_km'].mean():.1f} km")
    print(f"   Longest Ride: {rides['distance_km'].max():.1f} km")
    
    print(f"\n  Network:")
    print(f"   Segments: {len(network)}")
    print(f"   Total Length: {network['distance_km'].sum():.1f} km")
    print(f"   Most Popular: {network['ride_count'].max()} rides on one segment")
    
    print(f"\n Route Types:")
    for route_type, count in rides['route_type'].value_counts().items():
        print(f"   {route_type}: {count}")
    
    candidates_path = Config.OUTPUT_DIR / 'candidate_locations.gpkg'

    if candidates_path and Path(candidates_path).exists():
        candidates = gpd.read_file(candidates_path)
        print(f"\n Trail Center Candidates:")
        print(f"   • {len(candidates)} suitable locations identified")
        best = candidates.iloc[0]
        print(f"   • Best location: {best.geometry.y:.4f}°N, {best.geometry.x:.4f}°E")
        print(f"   • Suitability Score: {best['suitability_score']:.1f}/100")
    
    print(f"\n Output saved to: {Config.OUTPUT_MAP}")


def main():    
    Config.ensure_directories()
    
    study_area, rides = DataLoader.load_data(
        Config.STUDY_AREA,
        Config.STRAVA_RIDES
    )
     # === STEP 2: CLEANING ===
    rides = DataLoader.clean_ride_names(rides)
    rides = DataLoader.calculate_km(rides)

    # === STEP 3: BUILDING NETWORK ===
    network = NetworkBuilder.create_network(
        rides,
        tolerance=Config.SNAP_TOLERANCE
    )

    network = NetworkBuilder.map_rides_to_segments(
        network,
        rides,
        buffer_distance=Config.INTERSECTION_BUFFER
    )

    NetworkBuilder.save_network(network, Config.TRAIL_NETWORK)

    protected_zones_file = Path('data/sumava_zones_2.geojson')
    protected_zones = gpd.read_file(protected_zones_file)

    results = SuitabilityAnalyzer.analyze(
        network=network,
        rides=rides,
        study_area=study_area,
        protected_zones=protected_zones
    )
    
    # Print and save results
    if results is not None:
        SuitabilityAnalyzer.print_results(results, top_n=5)
        
        candidates_file = 'maps/candidate_locations.gpkg'
        SuitabilityAnalyzer.save_results(results, candidates_file)
    
    # Calculate map center
    bounds = study_area.total_bounds
    center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
    
    # Create base map
    m = BaseLayers.create_base_map(center, Config.DEFAULT_ZOOM)
    
    # Add layers
    BaseLayers.add_study_area(m, study_area)   
   
    BikeLayers.add_rides_by_length(m, rides)

    HeatMapLayer.add_route_clusters(m, rides, Config.CLUSTER_DISTANCE)
    HeatMapLayer.add_heatmap(m, rides)
    
    candidates_path = Config.OUTPUT_DIR / 'candidate_locations.gpkg'
    protected_zones_file = Path('data/sumava_zones_2.geojson')
    SuitabilityAnalyzer.add_candidate_locations(m, candidates_path, protected_zones_file)


    candidates = gpd.read_file(candidates_path)
    BaseLayers.add_analysis_summary(m, network, candidates)  

    BaseLayers.add_instructions(m) 
    

    # Add layer control
    folium.LayerControl(position='topright', collapsed=False).add_to(m)
    
    # Save map
    BaseLayers.save_map(m, Config.OUTPUT_MAP)
    
    # === STEP 5: PRINT SUMMARY ===
    stats(study_area, rides, network)


if __name__ == "__main__":
    import folium
    main()