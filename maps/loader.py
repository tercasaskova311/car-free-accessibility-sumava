import folium
from folium.plugins import MarkerCluster, HeatMap, MiniMap, Fullscreen
import geopandas as gpd
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import Config
from bike_layer import BikeLayers
from analysis_layer import AnalysisLayers

class DataLoader:
    
    @staticmethod
    def load_data(study_area_path, rides_path):
        
        study_area = gpd.read_file(study_area_path)
        rides = gpd.read_file(rides_path)
        
        # Ensure matching CRS
        if study_area.crs != rides.crs:
            rides = rides.to_crs(study_area.crs)
        
        print(f"   ✓ Loaded {len(rides)} rides")
        return study_area, rides

    @staticmethod
    def clean_ride_names(rides):
        """
        Remove ride name / description column entirely
        """
        print("🧹 Removing ride names column...")

        if 'name' in rides.columns:
            rides = rides.drop(columns=['name'])
            print("   ✓ 'name' column removed")
        else:
            print("   ⚠️  No 'name' column found")

        return rides
    
    @staticmethod
    def calculate_km(rides):
        # Calculate length in km
        rides_proj = rides.to_crs("EPSG:32633")
        rides["length_km"] = rides_proj.geometry.length / 1000
        
        # Helper functions for start/end extraction
        def get_start_point(geom):
            from shapely.geometry import LineString, MultiLineString
            if geom is None or geom.is_empty:
                return None
            try:
                if isinstance(geom, LineString):
                    return geom.coords[0]
                elif isinstance(geom, MultiLineString):
                    return list(geom.geoms[0].coords)[0]
                else:
                    # Fallback for other geometry types
                    coords = list(geom.coords)
                    return coords[0] if coords else None
            except:
                return None
        
        def get_end_point(geom):
            from shapely.geometry import LineString, MultiLineString
            if geom is None or geom.is_empty:
                return None
            try:
                if isinstance(geom, LineString):
                    return geom.coords[-1]
                elif isinstance(geom, MultiLineString):
                    return list(geom.geoms[-1].coords)[-1]
                else:
                    # Fallback for other geometry types
                    coords = list(geom.coords)
                    return coords[-1] if coords else None
            except:
                return None
        
        # Extract start/end points
        rides['start_point'] = rides.geometry.apply(get_start_point)
        rides['end_point'] = rides.geometry.apply(get_end_point)
        
        # Classify route type
        def classify_route(row):
            if not row['start_point'] or not row['end_point']:
                return 'Unknown'
            
            from shapely.geometry import Point
            start = Point(row['start_point'])
            end = Point(row['end_point'])
            dist = start.distance(end)
            
            if dist < 0.001:  # ~100m
                return 'Loop'
            elif row.geometry.length / dist < 1.5:
                return 'Point-to-Point'
            else:
                return 'Out-and-Back'
        
        rides['route_type'] = rides.apply(classify_route, axis=1)
        
        print(f"   ✓ Enriched {len(rides)} rides")
        return rides

