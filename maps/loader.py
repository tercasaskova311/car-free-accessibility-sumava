import geopandas as gpd
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import Config

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
        if 'name' in rides.columns:
            rides = rides.drop(columns=['name'])
            print("'name' column removed")
        else:
            print("No 'name' column found")
        return rides

    @staticmethod
    def calculate_km(rides):
        # Calculate length in km
        rides_proj = rides.to_crs("EPSG:32633")
        rides["distance_km"] = rides_proj.geometry.length / 1000

        print("Calculated ride distances in km")
        return rides

