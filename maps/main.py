from loader import DataLoader
from network_layer import NetworkBuilder
from base_map import BaseLayers
from bike_layer import BikeLayers
from heatmap import HeatMapLayer
import sys
from pathlib import Path
import folium
import geopandas as gpd
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import Config


def print_summary(study_area, rides, network):
    print("sumary")
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

    if candidates_path and Path(candidates_path).exists():
        candidates = gpd.read_file(candidates_path)
        print(f"\n🎯 Trail Center Candidates:")
        print(f"   • {len(candidates)} suitable locations identified")
        best = candidates.iloc[0]
        print(f"   • Best location: {best.geometry.y:.4f}°N, {best.geometry.x:.4f}°E")
        print(f"   • Suitability Score: {best['suitability_score']:.1f}/100")
    
    print(f"\n Output saved to: {Config.OUTPUT_MAP}")


def add_candidate_locations(m, candidates_path, protected_zones_path=None):
    """Add candidate trail center locations to map with environmental overlay"""
    if not Path(candidates_path).exists():
        print("⚠️ No candidate locations found. Run analysis first.")
        return
    
    # Add protected zones layer if available
    if protected_zones_path and Path(protected_zones_path).exists():
        print("   Adding protected zones layer...")
        zones = gpd.read_file(protected_zones_path)
        
        folium.GeoJson(
            zones,
            name='🌲 Protected Zones (A & B)',
            style_function=lambda x: {
                'fillColor': '#d63031',
                'color': '#c0392b',
                'weight': 2,
                'fillOpacity': 0.2,
                'dashArray': '5, 5'
            },
            tooltip='Ecologically Sensitive Zone - Avoid'
        ).add_to(m)
    
    candidates = gpd.read_file(candidates_path)
    
    # Create layer
    layer = folium.FeatureGroup(name='🎯 Candidate Trail Centers', show=True)
    
    # Color scale for ranks
    rank_colors = {
        1: '#2ecc71',  # Green - best
        2: '#3498db',  # Blue
        3: '#f39c12',  # Orange
        4: '#e74c3c',  # Red
        5: '#95a5a6'   # Gray
    }
    
    for idx, candidate in candidates.iterrows():
        rank = int(candidate['rank'])
        color = rank_colors.get(rank, '#95a5a6')
        
        # Create popup
        popup_html = f"""
        <div style="font-family: Arial; min-width: 250px;">
            <h4 style="margin: 0 0 10px 0; color: {color};">
                {'🥇' if rank == 1 else '🥈' if rank == 2 else '🥉' if rank == 3 else f'#{rank}'} 
                Candidate Location
            </h4>
            <p style="margin: 5px 0; font-size: 14px;">
                <b>Suitability Score:</b> {candidate['suitability_score']:.1f}/100
            </p>
            <hr style="margin: 10px 0;">
            <p style="font-size: 12px; margin: 5px 0;">
                <b>Trail Access (5km):</b><br>
                • {int(candidate['trail_segments_5km'])} segments<br>
                • {candidate['trail_length_5km']:.1f} km trails<br>
                • {int(candidate['total_traffic_5km'])} recorded rides<br>
                • {int(candidate['ride_starts_5km'])} start points nearby
            </p>
        </div>
        """
        
        # Add marker
        folium.CircleMarker(
            location=[candidate.geometry.y, candidate.geometry.x],
            radius=15 if rank <= 3 else 10,
            color=color,
            fill=True,
            fillColor=color,
            fillOpacity=0.7,
            weight=3,
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"Rank #{rank} - Score: {candidate['suitability_score']:.0f}/100"
        ).add_to(layer)
        
        # Add 5km radius circle
        folium.Circle(
            location=[candidate.geometry.y, candidate.geometry.x],
            radius=5000,
            color=color,
            fill=False,
            weight=2,
            opacity=0.3,
            dashArray='5, 5'
        ).add_to(layer)
    
    layer.add_to(m)
    print(f"✓ Added {len(candidates)} candidate locations")


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

    # Calculate map center
    bounds = study_area.total_bounds
    center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
    
    # Create base map
    m = BaseLayers.create_base_map(center, Config.DEFAULT_ZOOM)
    
    # Add layers
    BaseLayers.add_study_area(m, study_area)   
   
    BikeLayers.add_all_rides(m, rides)
    BikeLayers.add_rides_by_length(m, rides)

    HeatMapLayer.add_route_clusters(m, rides, Config.CLUSTER_DISTANCE)
    HeatMapLayer.add_heatmap(m, rides)

    candidates_file = Config.OUTPUT_DIR / 'candidate_locations.gpkg'
    protected_zones_file = Path('data/sumava_zones_2.geojson')
    
    # Check if protected zones exist
    zones_path = protected_zones_file if protected_zones_file.exists() else None
    add_candidate_locations(m, candidates_file, zones_path)

    BaseLayers.add_instructions(m) 
    BaseLayers.add_trail_network_analysis(m, network)
    
    BikeLayers.add_clickable_rides(m, rides)
        
    # Add layer control
    folium.LayerControl(position='topright', collapsed=False).add_to(m)
    
    # Save map
    BaseLayers.save_map(m, Config.OUTPUT_MAP)
    
    # === STEP 5: PRINT SUMMARY ===
    print_summary(study_area, rides, network)


if __name__ == "__main__":
    import folium
    main()