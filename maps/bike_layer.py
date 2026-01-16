import folium
from folium.plugins import MarkerCluster, HeatMap, MiniMap, Fullscreen
import geopandas as gpd
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import Config
from folium import FeatureGroup


class BikeLayers: 
    @staticmethod
    def add_clickable_rides(m, rides):    
        # Group rides by route type
        for route_type in rides['route_type'].unique():
            type_rides = rides[rides['route_type'] == route_type]
            
            for idx, ride in type_rides.iterrows():

                popup_html = f"""
                <div style='font-family: Arial; min-width: 200px;'>
                    <p style='margin: 3px 0; font-size: 13px;'>
                        <b>Type:</b> {ride['route_type']}<br>
                        <b>Distance:</b> {ride['distance_km']:.1f} km<br>
                        <b>Activity ID:</b> {ride['activity_id']}
                    </p>
                </div>
                """
                
                # Choose color based on route type
                color_map = {
                    'Ride': '#5c4033'
                }
                color = color_map.get(route_type, '#5c4033')
                
                # Add ride geometry - control=False prevents it from showing in layer control!
                folium.GeoJson(
                    ride.geometry,
                    style_function=lambda x, c=color: {
                        'color': c,
                        'weight': 3,
                        'opacity': 1
                    },
                    highlight_function=lambda x: {
                        'weight': 5,
                        'opacity': 1.0
                    },
                    popup=folium.Popup(popup_html, max_width=300),
                    tooltip=f"({ride['distance_km']:.1f} km)",
                    control=False  # THIS IS THE KEY - hides from layer control!
                ).add_to(m)
        
        print(f"✓ Added {len(rides)} clickable rides to map (hidden from layer control)")

    @staticmethod
    def add_rides_by_length(m, rides):

        # length cat - important for later...
        rides['length_category'] = pd.cut(
            rides['distance_km'],
            bins=[0, 25, 50, float('inf')],
            labels=['Short (0-25 km)', 'Medium (25-50km)', 
                    'Long (50+)']
        )
        
        colors_by_length = {
            'Short (0-25 km)': '#9b59b6',    # light purple
            'Medium (25–50 km)': '#8e44ad',  # strong purple
            'Very Long (50+)': '#5e3370'     # dark violet
        }
        
        for category in rides['length_category'].dropna().unique():
            subset = rides[rides['length_category'] == category]

            layer = folium.FeatureGroup(
                name=f'{category} ({len(subset)})',
                show=False
            )

            # all rides in category as single GeoJson - in order to speedup
            folium.GeoJson(
                subset[['geometry', 'activity_id', 'distance_km']],
                style_function=lambda x, c=colors_by_length[category]: {
                    'color': c,
                    'weight': 3,
                    'opacity': 0.7
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=['activity_id', 'distance_km'],
                    aliases=['Ride:', 'Distance (km):']
                )
            ).add_to(layer)
            
            layer.add_to(m)
        
        print("Added length-based layers")  
    
    @staticmethod
    def add_start_points(m, rides):
        layer = folium.FeatureGroup(name='Start Points', show=False)
        cluster = MarkerCluster().add_to(layer)
        
        valid_starts = rides[rides['start_point'].notna()].copy()
        
        for idx, (_, ride) in enumerate(valid_starts.iterrows()):
            coords = ride['start_point']

            folium.Marker(
                location=[coords[1], coords[0]],
                popup=(
                    f"<b>Ride {ride.name}</b><br>"
                    f"Distance: {ride['distance_km']:.1f} km<br>"
                    f"Type: {ride['route_type']}",
                ),
                icon=folium.Icon(color='blue', icon='bicycle', prefix='fa')
            ).add_to(cluster)
            
            # Progress
            if (idx + 1) % 100 == 0:
                print(f"   Added {idx + 1}/{len(valid_starts)} markers...")
        
        layer.add_to(m)
        print(f"Added {len(valid_starts)} start points")

