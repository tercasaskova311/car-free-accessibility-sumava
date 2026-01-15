#getting insights from uploaded rides - mainly heatmap - which is later used to answear the research question
import folium
from folium.plugins import MarkerCluster, HeatMap, MiniMap, Fullscreen
import geopandas as gpd
import pandas as pd
from pathlib import Path
from sklearn.cluster import DBSCAN
import numpy as np
from shapely.geometry import Point

class HeatMapLayer:
    @staticmethod
    def add_heatmap(m, rides):
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
            layer = folium.FeatureGroup(name='Density Heatmap', show=False)
            HeatMap(
                heat_data,
                min_opacity=0.3,
                radius=15,
                blur=20,
                gradient={0.0: 'blue', 0.5: 'lime', 0.7: 'yellow', 1.0: 'red'}
            ).add_to(layer)
            layer.add_to(m)
            print(f"add heatmap layer")
    
    @staticmethod
    def add_route_clusters(m, rides, distance_threshold=1000):
        """
        Cluster rides by start-point proximity with CLEAR popularity labels
        """
        # Keep only rides with valid start points
        rides_valid = rides[rides["start_point"].notna()].copy()
        if rides_valid.empty:
            print("⚠️ No valid start points for clustering")
            return

        # Convert to GeoSeries
        start_points = gpd.GeoSeries(
            [Point(p) for p in rides_valid["start_point"]],
            crs=rides.crs
        )

        # Project to meters for accurate distance calculation
        start_points_proj = start_points.to_crs("EPSG:32633")

        # Extract coordinates
        coords = np.column_stack([
            start_points_proj.x,
            start_points_proj.y
        ])

        # DBSCAN clustering
        db = DBSCAN(
            eps=distance_threshold,
            min_samples=3,
            metric="euclidean"
        ).fit(coords)

        rides_valid["cluster"] = db.labels_
        rides["cluster"] = rides_valid["cluster"]

        # Get cluster popularity ranking
        cluster_counts = rides_valid[rides_valid["cluster"] != -1]["cluster"].value_counts()
        
        # Map cluster IDs to popularity labels
        cluster_labels = {}
        sorted_clusters = cluster_counts.sort_values(ascending=False).index.tolist()
        
        popularity_names = ["Most popular rides", "Popular", "Moderate", " Enjoy trails for yourself"]
        
        for rank, cluster_id in enumerate(sorted_clusters):
            count = cluster_counts[cluster_id]
            if rank < len(popularity_names):
                label = popularity_names[rank]
            else:
                label = f"Zone {rank + 1}"
            
            cluster_labels[cluster_id] = {
                'name': label,
                'count': count,
                'rank': rank + 1
            }

        # Visualization colors
        colors = [
            "#e74c3c",  # Red - hottest
            "#f39c12",  # Orange
            "#3498db",  # Blue
            "#2ecc71",  # Green
            "#9b59b6",  # Purple
            "#1abc9c"   # Teal
        ]

        for cluster_id in sorted_clusters:
            subset = rides_valid[rides_valid["cluster"] == cluster_id]
            
            label_info = cluster_labels[cluster_id]
            layer_name = f"{label_info['name']} ({label_info['count']} rides)"
            
            layer = folium.FeatureGroup(
                name=layer_name,
                show=False  # Hidden by default to avoid clutter
            )

            color = colors[label_info['rank'] - 1] if label_info['rank'] <= len(colors) else colors[-1]

            for _, ride in subset.iterrows():
                folium.GeoJson(
                    ride.geometry,
                    style_function=lambda _, c=color: {
                        "color": c,
                        "weight": 3,
                        "opacity": 0.7
                    },
                    tooltip=f"{label_info['name']} - {ride.get('distance_km', 0):.1f}km"
                ).add_to(layer)

            layer.add_to(m)

        print(f"✓ Created {len(sorted_clusters)} popularity zones from {len(rides_valid)} rides")