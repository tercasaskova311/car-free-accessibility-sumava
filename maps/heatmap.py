#heatmap layer - add heatmap of ride density to the map, with configurable parameters for point density, radius, blur, and color gradient
import folium
from folium.plugins import HeatMap
import geopandas as gpd
import numpy as np
from shapely.geometry import Point
from sklearn.cluster import DBSCAN
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import Config


class HeatMapLayer:
    @staticmethod
    def add_heatmap(m, rides):
        MAX_HEAT_POINTS = 15_000 # Cap total heatmap points to prevent browser overload
        points_per_route = Config.HEATMAP_POINTS_PER_ROUTE  # 30 - more points for smoother heatmap, fewer for performance

        # How many rides do we need to stay under the cap? - max 5000 points
        max_rides = max(1, MAX_HEAT_POINTS // points_per_route)

        if len(rides) > max_rides:
            rides_sample = rides.sample(n=max_rides, random_state=42)
            print(f"Heatmap subsampled: {len(rides)} → {max_rides} rides")
        else:
            rides_sample = rides

        heat_data = []

        #ride - interpolate points along the route -heatmap 
        for _, ride in rides_sample.iterrows():
            if ride.geometry is None or ride.geometry.is_empty:
                continue
            length = ride.geometry.length
            for i in range(points_per_route):
                try:
                    point = ride.geometry.interpolate(i / points_per_route * length)
                    heat_data.append([point.y, point.x])
                except Exception:
                    continue

        if heat_data:
            layer = folium.FeatureGroup(name='Density Heatmap', show=False)
            HeatMap(
                heat_data,
                min_opacity=0.3,
                radius=Config.HEATMAP_RADIUS,
                blur=Config.HEATMAP_BLUR,
                gradient={0.0: 'white', 0.5: 'lime', 0.7: 'yellow', 1.0: 'red'}
            ).add_to(layer)
            layer.add_to(m)
            print(f" Heatmap layer added ({len(heat_data)} points)")

     