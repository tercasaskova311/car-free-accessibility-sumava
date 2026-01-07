import pandas as pd
import geopandas as gpd
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from shapely.geometry import LineString

ANALYSIS_DATE = datetime(2026, 6, 7)   # Sunday, June 7, 2026
STUDY_AREA_PATH = 'data/raw/00_study_area.gpkg'
GTFS_FILES = [
    {'path': 'data/czech_gtfs.zip', 'region': 'Czech', 'color': '#1f77b4'},
    {'path': 'data/german_gtfs', 'region': 'German', 'color': '#2ca02c'}
]
OUTPUT_GPKG = 'data/processed/gtfs_layers.gpkg'

class GTFSLayerBuilder:    
    def __init__(self, gtfs_path, region_name, region_color, analysis_date, source_type=None):
        self.gtfs_path = gtfs_path
        self.region = region_name
        self.color = region_color
        self.analysis_date = analysis_date
        self.source_type = 'zip' if str(gtfs_path).endswith('.zip') else 'folder'
        self.tables = {}
        
    def load_tables(self):
        print(f"\n Loading {self.region} GTFS from {self.gtfs_path}")
        
        required = ['stops', 'routes', 'trips', 'stop_times', 'calendar']
        
        if self.source_type == 'zip':
            with zipfile.ZipFile(self.gtfs_path) as z:
                for table in required:
                    filename = f'{table}.txt'
                    if filename in z.namelist():
                        self.tables[table] = pd.read_csv(z.open(filename), dtype=str)
                        print(f"   {table}: {len(self.tables[table])} rows")
                    else:
                        print(f"   Missing: {table}")
        else:
            for table in required:
                filepath = Path(self.gtfs_path) / f'{table}.txt'
                if filepath.exists():
                    self.tables[table] = pd.read_csv(filepath, dtype=str)
                    print(f"   {table}: {len(self.tables[table])} rows")
                else:
                    print(f"   Missing: {table}")        
        # Standardize column names
        self._standardize_columns()
                    
    def _standardize_columns(self):        
        # Stops: ensure we have stop_id, stop_name, stop_lat, stop_lon
        if 'stops' in self.tables:
            stops = self.tables['stops']
            # Convert lat/lon to float
            stops['stop_lat'] = pd.to_numeric(stops['stop_lat'], errors='coerce')
            stops['stop_lon'] = pd.to_numeric(stops['stop_lon'], errors='coerce')
            # Remove rows with missing coordinates
            stops = stops.dropna(subset=['stop_lat', 'stop_lon'])
            self.tables['stops'] = stops
        
        # Routes: ensure route_id, route_short_name, route_long_name, route_type
        if 'routes' in self.tables:
            routes = self.tables['routes']
            if 'route_short_name' not in routes.columns and 'route_name' in routes.columns:
                routes['route_short_name'] = routes['route_name']
            routes['route_type'] = pd.to_numeric(routes['route_type'], errors='coerce').fillna(3).astype(int)
            self.tables['routes'] = routes
        
        if 'calendar' in self.tables:
            calendar = self.tables['calendar']
            for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
                if day in calendar.columns:
                    calendar[day] = pd.to_numeric(calendar[day], errors='coerce').fillna(0).astype(int)
            self.tables['calendar'] = calendar
    
    def get_active_services(self):
        calendar = self.tables['calendar'].copy()        
        calendar['start_date'] = pd.to_datetime(calendar['start_date'], format='%Y%m%d', errors='coerce')
        calendar['end_date'] = pd.to_datetime(calendar['end_date'], format='%Y%m%d', errors='coerce')
        calendar = calendar.dropna(subset=['start_date', 'end_date'])
        weekday = self.analysis_date.weekday()
        day_col = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'][weekday]
        
        active = calendar[
            (calendar['start_date'] <= self.analysis_date) &
            (calendar['end_date'] >= self.analysis_date) &
            (calendar[day_col] == 1)
        ]['service_id'].tolist()
        
        print(f"{len(active)} services active on {self.analysis_date.strftime('%A, %Y-%m-%d')}")
        return active
    
    def create_stops_layer(self):
        print(f"\n Creating stops layer for {self.region}...")
        
        stops = self.tables['stops'].copy()        
        stops_gdf = gpd.GeoDataFrame(
            stops,
            geometry=gpd.points_from_xy(stops.stop_lon, stops.stop_lat),
            crs='EPSG:4326'
        )        
        stops_gdf['region'] = self.region
        stops_gdf['color'] = self.color        
        stop_times = self.tables['stop_times']
        trips = self.tables['trips']
        
        st_with_routes = stop_times.merge(trips[['trip_id', 'route_id']], on='trip_id', how='left')
        
        routes_per_stop = st_with_routes.groupby('stop_id')['route_id'].nunique().reset_index()
        routes_per_stop.columns = ['stop_id', 'num_routes']
        
        stops_gdf = stops_gdf.merge(routes_per_stop, on='stop_id', how='left')
        stops_gdf['num_routes'] = stops_gdf['num_routes'].fillna(0).astype(int)
        
        essential_cols = ['stop_id', 'stop_name', 'stop_lat', 'stop_lon', 'num_routes', 'region', 'color', 'geometry']
        cols_to_keep = [col for col in essential_cols if col in stops_gdf.columns]
        stops_gdf = stops_gdf[cols_to_keep]
        
        print(f"{len(stops_gdf)} stops")
        return stops_gdf
    
    def create_routes_layer(self):
        """Create route lines layer"""
        print(f"\n Creating routes layer for {self.region}...")
        
        stops = self.tables['stops']
        stop_times = self.tables['stop_times']
        trips = self.tables['trips']
        routes = self.tables['routes']
        
        # Create stop coordinates lookup
        stop_coords = stops.set_index('stop_id')[['stop_lon', 'stop_lat']].to_dict('index')
        
        # Get active services
        active_services = self.get_active_services()
        active_trips = trips[trips['service_id'].isin(active_services)]
        
        route_geometries = []
        
        # Sample trips to avoid too many lines (use one trip per route)
        print(f"  Processing {active_trips['route_id'].nunique()} unique routes...")
        
        for route_id in active_trips['route_id'].unique():
            # Get one representative trip for this route
            route_trips = active_trips[active_trips['route_id'] == route_id]
            trip_id = route_trips['trip_id'].iloc[0]
            
            # Get stops for this trip
            trip_stops = stop_times[stop_times['trip_id'] == trip_id].copy()
            trip_stops['stop_sequence'] = pd.to_numeric(trip_stops['stop_sequence'], errors='coerce')
            trip_stops = trip_stops.dropna(subset=['stop_sequence']).sort_values('stop_sequence')
            
            # Build coordinate list
            coords = []
            for stop_id in trip_stops['stop_id']:
                if stop_id in stop_coords:
                    coords.append((
                        stop_coords[stop_id]['stop_lon'],
                        stop_coords[stop_id]['stop_lat']
                    ))
            
            if len(coords) >= 2:
                route_info = routes[routes['route_id'] == route_id].iloc[0]
                
                route_name = route_info.get('route_short_name', route_info.get('route_long_name', 'Unknown'))
                if pd.isna(route_name) or route_name == '':
                    route_name = f"Route {route_id}"
                
                route_geometries.append({
                    'route_id': str(route_id),
                    'route_name': str(route_name),
                    'route_type': int(route_info['route_type']),
                    'route_type_name': self._route_type_name(int(route_info['route_type'])),
                    'num_stops': len(coords),
                    'geometry': LineString(coords)
                })
        
        if len(route_geometries) == 0:
            print(f"  ⚠️ No routes created for {self.region}")
            return gpd.GeoDataFrame(columns=['route_id', 'route_name', 'route_type', 'route_type_name', 'num_stops', 'region', 'color', 'geometry'], crs='EPSG:4326')
        
        routes_gdf = gpd.GeoDataFrame(route_geometries, crs='EPSG:4326')
        routes_gdf['region'] = self.region
        routes_gdf['color'] = self.color
        
        print(f"  ✅ {len(routes_gdf)} routes")
        print(f"     Types: {routes_gdf['route_type_name'].value_counts().to_dict()}")
        
        return routes_gdf
    
    def create_timetable_layer(self):
        """Create timetable with actual departure times"""
        print(f"\n Creating timetable layer for {self.region}...")
        
        stops = self.tables['stops']
        stop_times = self.tables['stop_times']
        trips = self.tables['trips']
        routes = self.tables['routes']
        
        # Get active services
        active_services = self.get_active_services()
        active_trips = trips[trips['service_id'].isin(active_services)]
        
        print(f"  Processing {len(active_trips)} active trips...")
        
        # Filter stop_times to active trips
        timetable = stop_times[stop_times['trip_id'].isin(active_trips['trip_id'])].copy()
        
        # Sample to reduce size (every 10th stop_time to avoid huge files)
        # Comment this line out if you want the complete timetable
        timetable = timetable.sample(min(len(timetable), len(timetable) // 10))
        
        # Merge with trip and route info
        timetable = timetable.merge(trips[['trip_id', 'route_id', 'service_id']], on='trip_id', how='left')
        timetable = timetable.merge(
            routes[['route_id', 'route_short_name', 'route_long_name', 'route_type']], 
            on='route_id', 
            how='left'
        )
        timetable = timetable.merge(
            stops[['stop_id', 'stop_name', 'stop_lon', 'stop_lat']], 
            on='stop_id', 
            how='left'
        )
        
        # Remove rows with missing coordinates
        timetable = timetable.dropna(subset=['stop_lat', 'stop_lon'])
        
        # Parse times
        def parse_gtfs_time(time_str):
            """Convert GTFS time to datetime"""
            if pd.isna(time_str):
                return None
            try:
                h, m, s = map(int, str(time_str).split(':'))
                days = h // 24
                h = h % 24
                return self.analysis_date + timedelta(days=days, hours=h, minutes=m, seconds=s)
            except:
                return None
        
        timetable['departure_dt'] = timetable['departure_time'].apply(parse_gtfs_time)
        timetable['arrival_dt'] = timetable['arrival_time'].apply(parse_gtfs_time)
        
        # Remove rows with invalid times
        timetable = timetable.dropna(subset=['departure_dt'])
        
        # Add hour for filtering
        timetable['departure_hour'] = timetable['departure_dt'].dt.hour
        
        # Create geometry
        timetable_gdf = gpd.GeoDataFrame(
            timetable,
            geometry=gpd.points_from_xy(timetable.stop_lon, timetable.stop_lat),
            crs='EPSG:4326'
        )
        
        # Add metadata
        timetable_gdf['region'] = self.region
        timetable_gdf['route_name'] = timetable_gdf['route_short_name'].fillna(timetable_gdf['route_long_name']).fillna('Unknown')
        timetable_gdf['route_type_name'] = timetable_gdf['route_type'].apply(self._route_type_name)
        
        # Select useful columns
        columns_to_keep = [
            'stop_id', 'stop_name', 'trip_id', 'route_id', 'route_name', 
            'route_type', 'route_type_name', 'stop_sequence',
            'arrival_time', 'departure_time', 'departure_hour',
            'region', 'geometry'
        ]
        # Only keep columns that exist
        cols_to_keep = [col for col in columns_to_keep if col in timetable_gdf.columns]
        timetable_gdf = timetable_gdf[cols_to_keep]
        
        print(f"   {len(timetable_gdf)} scheduled stops (sampled)")
        print(f"     Trips: {timetable_gdf['trip_id'].nunique()}")
        
        if len(timetable_gdf) > 0:
            print(f"     Departures by hour:")
            hourly = timetable_gdf.groupby('departure_hour').size().to_dict()
            # Show only hours with departures
            for hour in sorted(hourly.keys()):
                print(f"       {hour:02d}:00 - {hourly[hour]} departures")
        
        return timetable_gdf
    
    def create_frequency_layer(self):
        """Create layer showing service frequency per stop"""
        print(f"\n📊 Creating frequency layer for {self.region}...")
        
        stops = self.tables['stops']
        stop_times = self.tables['stop_times']
        trips = self.tables['trips']
        
        # Get active services
        active_services = self.get_active_services()
        active_trips = trips[trips['service_id'].isin(active_services)]
        
        # Filter to active trips
        schedule = stop_times[stop_times['trip_id'].isin(active_trips['trip_id'])].copy()
        
        # Count departures per stop
        departures_per_stop = schedule.groupby('stop_id').size().reset_index(name='daily_departures')
        
        # Merge with stop info
        frequency = stops.merge(departures_per_stop, on='stop_id', how='left')
        frequency['daily_departures'] = frequency['daily_departures'].fillna(0).astype(int)
        
        # Create GeoDataFrame
        frequency_gdf = gpd.GeoDataFrame(
            frequency,
            geometry=gpd.points_from_xy(frequency.stop_lon, frequency.stop_lat),
            crs='EPSG:4326'
        )
        
        frequency_gdf['region'] = self.region
        frequency_gdf['color'] = self.color
        
        # Categorize service level
        frequency_gdf['service_level'] = pd.cut(
            frequency_gdf['daily_departures'],
            bins=[0, 5, 20, 50, float('inf')],
            labels=['Very Low (0-5)', 'Low (6-20)', 'Medium (21-50)', 'High (50+)']
        )
        
        # Keep only essential columns
        essential_cols = ['stop_id', 'stop_name', 'stop_lat', 'stop_lon', 'daily_departures', 'service_level', 'region', 'color', 'geometry']
        cols_to_keep = [col for col in essential_cols if col in frequency_gdf.columns]
        frequency_gdf = frequency_gdf[cols_to_keep]
        
        print(f"Service frequency calculated")
        if 'service_level' in frequency_gdf.columns:
            print(f"     {frequency_gdf['service_level'].value_counts().to_dict()}")
        
        return frequency_gdf
    
    @staticmethod
    def _route_type_name(route_type):
        """Convert route type code to name"""
        types = {
            0: 'Tram', 1: 'Subway', 2: 'Rail', 3: 'Bus',
            4: 'Ferry', 5: 'Cable car', 6: 'Gondola', 7: 'Funicular'
        }
        return types.get(int(route_type) if not pd.isna(route_type) else 3, 'Unknown')

# ============================================
# MAIN PROCESSING
# ============================================

def prepare_all_gtfs_layers():

    print(f"Analysis Date: {ANALYSIS_DATE.strftime('%A, %B %d, %Y')}")    
    study_area = gpd.read_file(STUDY_AREA_PATH)
    if len(study_area) > 1:
        study_area = study_area.dissolve()
    study_area = study_area.to_crs('EPSG:4326')
    
    print(f"\n Study area bounds: {study_area.total_bounds}")
    
    # Initialize collectors
    all_stops = []
    all_routes = []
    all_timetables = []
    all_frequencies = []
    
    # Process each GTFS feed
    for gtfs_config in GTFS_FILES:
        if not Path(gtfs_config['path']).exists():
            print(f"\n⚠️ Skipping {gtfs_config['region']}: file not found")
            continue
        
        try:
            builder = GTFSLayerBuilder(
                gtfs_config['path'],
                gtfs_config['region'],
                gtfs_config['color'],
                ANALYSIS_DATE
            )
            
            builder.load_tables()
            
            # Create layers
            stops = builder.create_stops_layer()
            routes = builder.create_routes_layer()
            timetable = builder.create_timetable_layer()
            frequency = builder.create_frequency_layer()
            
            # Clip to study area
            print(f"\n✂️ Clipping to study area...")
            stops_clipped = gpd.clip(stops, study_area)
            routes_clipped = gpd.clip(routes, study_area)
            timetable_clipped = gpd.clip(timetable, study_area)
            frequency_clipped = gpd.clip(frequency, study_area)
            
            print(f"  Before clipping: {len(stops)} stops, {len(routes)} routes")
            print(f"  After clipping: {len(stops_clipped)} stops, {len(routes_clipped)} routes")
            
            # Only add if we have data after clipping
            if len(stops_clipped) > 0:
                all_stops.append(stops_clipped)
            if len(routes_clipped) > 0:
                all_routes.append(routes_clipped)
            if len(timetable_clipped) > 0:
                all_timetables.append(timetable_clipped)
            if len(frequency_clipped) > 0:
                all_frequencies.append(frequency_clipped)
                
        except Exception as e:
            print(f"\n Error processing {gtfs_config['region']}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # ============================================
    # COMBINE AND SAVE
    # ============================================
    
    if not all_stops:
        print("\n No data to save - check your study area and GTFS files")
        return
    
    print("\n" + "="*60)
    print("SAVING LAYERS")
    print("="*60)
    
    # Combine all regions
    combined_stops = pd.concat(all_stops, ignore_index=True)
    combined_routes = pd.concat(all_routes, ignore_index=True) if all_routes else gpd.GeoDataFrame()
    combined_timetable = pd.concat(all_timetables, ignore_index=True) if all_timetables else gpd.GeoDataFrame()
    combined_frequency = pd.concat(all_frequencies, ignore_index=True) if all_frequencies else gpd.GeoDataFrame()
    
    # Create output directory
    Path(OUTPUT_GPKG).parent.mkdir(parents=True, exist_ok=True)
    
    # Save to GeoPackage (multiple layers in one file)
    combined_stops.to_file(OUTPUT_GPKG, layer='stops', driver='GPKG')
    print(f" Saved 'stops' layer: {len(combined_stops)} features")
    
    if len(combined_routes) > 0:
        combined_routes.to_file(OUTPUT_GPKG, layer='routes', driver='GPKG')
        print(f" Saved 'routes' layer: {len(combined_routes)} features")
    
    if len(combined_timetable) > 0:
        combined_timetable.to_file(OUTPUT_GPKG, layer='timetable', driver='GPKG')
        print(f"Saved 'timetable' layer: {len(combined_timetable)} features")
    
    if len(combined_frequency) > 0:
        combined_frequency.to_file(OUTPUT_GPKG, layer='frequency', driver='GPKG')
        print(f" Saved 'frequency' layer: {len(combined_frequency)} features")
    
    # Also save study area for reference
    study_area.to_file(OUTPUT_GPKG, layer='study_area', driver='GPKG')
    print(f" Saved 'study_area' layer")
    
    print("\n" + "="*60)
    print(" ALL LAYERS SAVED TO:", OUTPUT_GPKG)
    print("="*60)
    print("\nLayers available:")
    print(f"  - stops: {len(combined_stops)} transit stops")
    print(f"  - routes: {len(combined_routes)} route lines")
    print(f"  - timetable: {len(combined_timetable)} scheduled stops")
    print(f"  - frequency: {len(combined_frequency)} stops with service frequency")
    print("  - study_area: Your boundary")
    print("\nNext steps:")
    print("  1. Open in QGIS to visualize")
    print("  2. Load in Python: gpd.read_file(OUTPUT_GPKG, layer='layer_name')")
    print("  3. Combine with tourism POIs and other layers")

# ============================================
# RUN
# ============================================

if __name__ == "__main__":
    prepare_all_gtfs_layers()