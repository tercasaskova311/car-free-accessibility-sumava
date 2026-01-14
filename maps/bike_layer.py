import folium
from folium.plugins import MarkerCluster, HeatMap, MiniMap, Fullscreen
import geopandas as gpd
import pandas as pd
from pathlib import Path
# ============================================================================
# RIDE LAYERS
# ============================================================================

class RideLayers:
    """Create ride visualization layers"""
    
    @staticmethod
    def add_all_rides(m, rides):
        """Add simple all-rides layer"""
        layer = folium.FeatureGroup(name='🚴 All Rides', show=True)
        
        for _, ride in rides.iterrows():
            if ride.geometry:
                popup_html = f"""
                <b>{ride.get('name', 'Unnamed Ride')}</b><br>
                Distance: {ride['length_km']:.1f} km<br>
                Type: {ride['route_type']}
                """
                
                folium.GeoJson(
                    ride.geometry,
                    style_function=lambda x: {
                        'color': Config.COLORS['default'],
                        'weight': 3,
                        'opacity': 0.6
                    },
                    popup=folium.Popup(popup_html, max_width=250),
                    tooltip=ride.get('name', 'Ride')
                ).add_to(layer)
        
        layer.add_to(m)
        print(f"   ✓ Added all rides layer")
    
    @staticmethod
    def add_rides_by_length(m, rides):
        """Add rides grouped by length"""
        # Define length categories
        rides['length_category'] = pd.cut(
            rides['length_km'],
            bins=[0, 10, 25, 50, 100, float('inf')],
            labels=['Short (<10km)', 'Medium (10-25km)', 
                   'Long (25-50km)', 'Very Long (50-100km)', 
                   'Ultra (>100km)']
        )
        
        colors_by_length = {
            'Short (<10km)': '#27ae60',
            'Medium (10-25km)': '#3498db',
            'Long (25-50km)': '#f39c12',
            'Very Long (50-100km)': '#e74c3c',
            'Ultra (>100km)': '#8e44ad'
        }
        
        for category in rides['length_category'].unique():
            if pd.isna(category):
                continue
                
            subset = rides[rides['length_category'] == category]
            layer = folium.FeatureGroup(
                name=f'📏 {category} ({len(subset)})',
                show=False
            )
            
            for _, ride in subset.iterrows():
                if ride.geometry:
                    folium.GeoJson(
                        ride.geometry,
                        style_function=lambda x, c=colors_by_length[category]: {
                            'color': c,
                            'weight': 3,
                            'opacity': 0.7
                        },
                        tooltip=f"{ride.get('name', 'Ride')} - {ride['length_km']:.1f}km"
                    ).add_to(layer)
            
            layer.add_to(m)
        
        print(f"   ✓ Added length-based layers")
    
 
    @staticmethod
    def add_heatmap(m, rides):
        """Add density heatmap layer"""
        print("🔥 Creating heatmap...")
        
        heat_data = []
        
        for _, ride in rides.iterrows():
            if ride.geometry:
                length = ride.geometry.length
                for i in range(Config.HEATMAP_POINTS_PER_ROUTE):
                    try:
                        point = ride.geometry.interpolate(i / Config.HEATMAP_POINTS_PER_ROUTE * length)
                        heat_data.append([point.y, point.x])
                    except:
                        continue
        
        if heat_data:
            layer = folium.FeatureGroup(name='🔥 Density Heatmap', show=False)
            HeatMap(
                heat_data,
                min_opacity=0.3,
                radius=Config.HEATMAP_RADIUS,
                blur=Config.HEATMAP_BLUR,
                gradient={0.0: 'blue', 0.5: 'lime', 0.7: 'yellow', 1.0: 'red'}
            ).add_to(layer)
            layer.add_to(m)
            print(f"   ✓ Added heatmap with {len(heat_data)} points")
    
    @staticmethod
    def add_start_points(m, rides):
        """Add clustered start points"""
        layer = folium.FeatureGroup(name='📍 Start Points', show=False)
        cluster = MarkerCluster().add_to(layer)
        
        for _, ride in rides.iterrows():
            if ride['start_point']:
                coords = ride['start_point']
                folium.Marker(
                    location=[coords[1], coords[0]],
                    popup=f"<b>{ride.get('name', 'Ride')}</b><br>"
                          f"Distance: {ride['length_km']:.1f} km<br>"
                          f"Type: {ride['route_type']}",
                    icon=folium.Icon(color='blue', icon='bicycle', prefix='fa')
                ).add_to(cluster)
        
        layer.add_to(m)
        print(f"   ✓ Added start points layer")

