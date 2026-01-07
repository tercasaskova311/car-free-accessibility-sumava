"""
Step-by-step GTFS exploration
Let's understand what's in the data BEFORE building complex networks
"""

import pandas as pd
import geopandas as gpd
import zipfile
from pathlib import Path

# ============================================
# STEP 1: EXTRACT AND LOOK AT THE DATA
# ============================================

def explore_gtfs(gtfs_path):
    """Look at what's inside GTFS"""
    
    print(f"\n{'='*60}")
    print(f"EXPLORING: {gtfs_path}")
    print(f"{'='*60}")
    
    with zipfile.ZipFile(gtfs_path) as z:
        print(f"\n📂 Files in this GTFS:")
        for filename in z.namelist():
            print(f"   - {filename}")
        
        # ============================================
        # TABLE 1: STOPS (Where buses stop)
        # ============================================
        print(f"\n\n🚏 STOPS.TXT - Where buses stop")
        print("-" * 60)
        
        stops = pd.read_csv(z.open('stops.txt'))
        print(f"Total stops: {len(stops)}")
        print(f"\nColumns: {list(stops.columns)}")
        print(f"\nFirst 3 stops:")
        print(stops[['stop_id', 'stop_name', 'stop_lat', 'stop_lon']].head(3))
        
        # ============================================
        # TABLE 2: ROUTES (What bus lines exist)
        # ============================================
        print(f"\n\n🚌 ROUTES.TXT - What bus/train lines exist")
        print("-" * 60)
        
        routes = pd.read_csv(z.open('routes.txt'))
        print(f"Total routes: {len(routes)}")
        print(f"\nColumns: {list(routes.columns)}")
        print(f"\nFirst 3 routes:")
        print(routes[['route_id', 'route_short_name', 'route_long_name', 'route_type']].head(3))
        
        # Route types explained
        print(f"\nRoute types in this GTFS:")
        route_types = {
            0: 'Tram', 1: 'Subway', 2: 'Rail', 3: 'Bus',
            4: 'Ferry', 5: 'Cable car', 6: 'Gondola', 7: 'Funicular'
        }
        type_counts = routes['route_type'].value_counts()
        for route_type, count in type_counts.items():
            print(f"   {route_types.get(route_type, 'Unknown')}: {count}")
        
        # ============================================
        # TABLE 3: TRIPS (Specific journeys)
        # ============================================
        print(f"\n\n🚍 TRIPS.TXT - Specific journeys")
        print("-" * 60)
        
        trips = pd.read_csv(z.open('trips.txt'))
        print(f"Total trips: {len(trips)}")
        print(f"\nColumns: {list(trips.columns)}")
        print(f"\nFirst 3 trips:")
        print(trips[['trip_id', 'route_id', 'service_id']].head(3))
        
        # ============================================
        # TABLE 4: STOP_TIMES (The actual schedule!)
        # ============================================
        print(f"\n\n⏰ STOP_TIMES.TXT - The actual timetable")
        print("-" * 60)
        
        stop_times = pd.read_csv(z.open('stop_times.txt'))
        print(f"Total scheduled stops: {len(stop_times)}")
        print(f"\nColumns: {list(stop_times.columns)}")
        print(f"\nFirst 5 entries (one trip):")
        first_trip = stop_times[stop_times['trip_id'] == stop_times['trip_id'].iloc[0]]
        print(first_trip[['trip_id', 'stop_id', 'arrival_time', 'departure_time', 'stop_sequence']].head(5))
        
        # ============================================
        # TABLE 5: CALENDAR (Which days does it run?)
        # ============================================
        print(f"\n\n📅 CALENDAR.TXT - Which days services run")
        print("-" * 60)
        
        calendar = pd.read_csv(z.open('calendar.txt'))
        print(f"Total service patterns: {len(calendar)}")
        print(f"\nColumns: {list(calendar.columns)}")
        print(f"\nFirst 3 service patterns:")
        print(calendar[['service_id', 'monday', 'tuesday', 'wednesday', 'thursday', 
                       'friday', 'saturday', 'sunday', 'start_date', 'end_date']].head(3))
        
        return {
            'stops': stops,
            'routes': routes,
            'trips': trips,
            'stop_times': stop_times,
            'calendar': calendar
        }

# ============================================
# RUN EXPLORATION
# ============================================

print("Let's explore your GTFS files!\n")

# Explore Czech GTFS
czech_data = explore_gtfs('data/czech_gtfs.zip')

# Explore German GTFS
german_data = explore_gtfs('data/german_gtfs.zip')