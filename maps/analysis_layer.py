import folium
from folium.plugins import MarkerCluster, HeatMap, MiniMap, Fullscreen
import geopandas as gpd
import pandas as pd
from pathlib import Path

class AnalysisLayers:
    """Create analysis and heatmap layers"""
    
    @staticmethod
    def add_heatmap(m, rides):
        """Add density heatmap"""
        heat_data = []
        
        for _, ride in rides.iterrows():
            if ride.geometry:
                # Sample points along route
                length = ride.geometry.length
                for i in range(30):
                    try:
                        point = ride.geometry.interpolate(i / 30 * length)
                        heat_data.append([point.y, point.x])
                    except:
                        continue
        
        if heat_data:
            layer = folium.FeatureGroup(name='🔥 Density Heatmap', show=False)
            HeatMap(
                heat_data,
                min_opacity=0.3,
                radius=15,
                blur=20,
                gradient={0.0: 'blue', 0.5: 'lime', 0.7: 'yellow', 1.0: 'red'}
            ).add_to(layer)
            layer.add_to(m)
            print(f"   ✓ Added heatmap layer")
    
    @staticmethod
    def add_route_clusters(m, rides, distance_threshold=2000):
        """Group and visualize route clusters"""
        rides_proj = rides.to_crs('EPSG:32633')
        
        # Simple clustering
        clusters = {}
        cluster_id = 0
        assigned = set()
        
        for i, row1 in rides_proj.iterrows():
            if i in assigned or not row1['start_point']:
                continue
            
            from shapely.geometry import Point
            start1 = Point(row1['start_point'])
            cluster_members = [i]
            assigned.add(i)
            
            for j, row2 in rides_proj.iterrows():
                if i == j or j in assigned or not row2['start_point']:
                    continue
                
                start2 = Point(row2['start_point'])
                if start1.distance(start2) < distance_threshold:
                    cluster_members.append(j)
                    assigned.add(j)
            
            for member in cluster_members:
                clusters[member] = cluster_id
            cluster_id += 1
        
        rides['cluster'] = rides.index.map(clusters)
        
        # Visualize clusters
        colors = ['#3498db', '#2ecc71', '#f39c12', '#e74c3c', '#9b59b6', '#1abc9c']
        
        for cluster_num in rides['cluster'].unique():
            if pd.isna(cluster_num):
                continue
            
            subset = rides[rides['cluster'] == cluster_num]
            layer = folium.FeatureGroup(
                name=f'📍 Area {chr(65 + int(cluster_num))} ({len(subset)} rides)',
                show=False
            )
            
            color = colors[int(cluster_num) % len(colors)]
            
            for _, ride in subset.iterrows():
                if ride.geometry:
                    folium.GeoJson(
                        ride.geometry,
                        style_function=lambda x, c=color: {
                            'color': c,
                            'weight': 3,
                            'opacity': 0.7
                        }
                    ).add_to(layer)
            
            layer.add_to(m)
        
        print(f"   ✓ Added {cluster_id} route clusters")
