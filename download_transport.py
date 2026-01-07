import osmnx as ox
import geopandas as gpd
import pandas as pd
import os
from shapely.ops import unary_union
import requests
import time
from shapely.geometry import Point, box
import json

os.makedirs('data/raw', exist_ok=True)
os.makedirs('data/processed', exist_ok=True)
'''
# ============================================
# STUDY AREA
# ============================================

# Czech side
jihocesky = ox.geocode_to_gdf('Jihočeský kraj, Czechia')
plzensky = ox.geocode_to_gdf('Plzeňský kraj, Czechia')

# German side
freyung_grafenau = ox.geocode_to_gdf('Landkreis Freyung-Grafenau, Germany')
regen = ox.geocode_to_gdf('Landkreis Regen, Germany')

# Combine all regions
study_area_gdf = gpd.GeoDataFrame(
    pd.concat([jihocesky, plzensky, freyung_grafenau, regen], ignore_index=True),
    crs='EPSG:4326'
)

# Create unified boundary
study_area_unified = gpd.GeoDataFrame(
    {'geometry': [study_area_gdf.unary_union]},
    crs='EPSG:4326'
)

study_area_unified.to_file('data/raw/00_study_area.gpkg', driver='GPKG')
print(f"✅ Study area saved: {study_area_unified.total_bounds}")

# ============================================
# ROADS
# ============================================

try:
    G = ox.graph_from_polygon(
        study_area_unified.geometry.iloc[0],
        network_type='drive', 
        simplify=True
    )
    
    nodes, edges = ox.graph_to_gdfs(G)
    edges.to_file('data/raw/01_road_network.gpkg', driver='GPKG')
    print(f"✅ Roads saved: {len(edges)} segments")
except Exception as e:
    print(f"❌ Road download failed: {e}")

# ============================================
# BUS STOPS
# ============================================

try:
    bus_stops = ox.features_from_polygon(
        study_area_unified.geometry.iloc[0],
        tags={'highway': 'bus_stop'}
    )
    bus_stops.to_file('data/raw/02_bus_stops.gpkg', driver='GPKG')
    print(f"✅ Bus stops: {len(bus_stops)}")
except Exception as e:
    print(f"❌ Bus stops failed: {e}")

# ============================================
# TRAIN STATIONS
# ============================================

try:
    train_stations = ox.features_from_polygon(
        study_area_unified.geometry.iloc[0],
        tags={
            'railway': ['station', 'halt', 'tram_stop'],
            'public_transport': 'station'
        }
    )
    train_stations.to_file('data/raw/02_train_stations.gpkg', driver='GPKG')
    print(f"✅ Train stations: {len(train_stations)}")
except Exception as e:
    print(f"❌ Train stations failed: {e}")

# ============================================
# PARKING
# ============================================

try:
    parking = ox.features_from_polygon(
        study_area_unified.geometry.iloc[0],
        tags={
            'amenity': ['parking', 'parking_space'],
            'parking': True
        }
    )
    parking.to_file('data/raw/04_parking.gpkg', driver='GPKG')
    print(f"✅ Parking: {len(parking)}")
except Exception as e:
    print(f"❌ Parking failed: {e}")
'''
import osmnx as ox
import geopandas as gpd
import pandas as pd
import os
from shapely.ops import unary_union
import time
from shapely.geometry import Point, box

os.makedirs('data/raw', exist_ok=True)
os.makedirs('data/processed', exist_ok=True)

OUTPUT_PATH = 'data/raw/03_tourism_pois.gpkg'

ox.settings.timeout = 300
ox.settings.max_query_area_size = 50 * 1000 * 1000 * 50

print("\n" + "="*60)
print("DOWNLOADING TOURISM POIs (OPTIMIZED)")
print("="*60)

# ============================================
# STRATEGY: Download ONLY the national parks, not entire regions!
# ============================================

def download_pois_by_place(place_name, tags):
    """Download POIs for a specific place"""
    print(f"\n📍 Downloading: {place_name}")
    
    try:
        # Use place name directly - much faster!
        pois = ox.features_from_place(place_name, tags=tags)
        print(f"   ✅ Found {len(pois)} POIs")
        return pois
    except Exception as e:
        print(f"   ⚠️ Failed: {str(e)[:100]}")
        return None

# Simplified tags
tags_focused = {
    'tourism': ['attraction', 'viewpoint', 'alpine_hut', 'wilderness_hut'],
    'natural': ['peak', 'waterfall', 'lake', 'cave_entrance'],
    'amenity': ['shelter']
}

all_pois = []

# ============================================
# Download only from the ACTUAL PARKS (much smaller areas)
# ============================================

places = [
    'Národní park Šumava, Czechia',
    'Nationalpark Bayerischer Wald, Germany'
]

for place in places:
    pois = download_pois_by_place(place, tags_focused)
    if pois is not None and len(pois) > 0:
        all_pois.append(pois)
    time.sleep(2)  # Be nice to OSM servers

# ============================================
# Combine results
# ============================================

if not all_pois:
    print("\n❌ No POIs found")
    
    # FALLBACK: Manual list of key destinations
    print("\n💡 Using manual list of key destinations instead...")
    
    destinations = [
        # Czech - Lakes
        {'name': 'Černé jezero', 'lat': 48.9850, 'lon': 13.5825, 'category': 'Lake'},
        {'name': 'Čertovo jezero', 'lat': 49.1681, 'lon': 13.4856, 'category': 'Lake'},
        {'name': 'Plešné jezero', 'lat': 48.7775, 'lon': 13.8661, 'category': 'Lake'},
        {'name': 'Prášilské jezero', 'lat': 49.0706, 'lon': 13.3975, 'category': 'Lake'},
        
        # Czech - Peaks
        {'name': 'Plechý', 'lat': 48.7736, 'lon': 13.8597, 'category': 'Mountain Peak', 'ele': '1378'},
        {'name': 'Boubín', 'lat': 49.0272, 'lon': 13.8097, 'category': 'Mountain Peak', 'ele': '1362'},
        {'name': 'Třístoličník', 'lat': 48.7067, 'lon': 13.8050, 'category': 'Mountain Peak', 'ele': '1312'},
        {'name': 'Jezerní hora', 'lat': 49.1667, 'lon': 13.4833, 'category': 'Mountain Peak', 'ele': '1343'},
        
        # Czech - Huts & Info
        {'name': 'Kvilda', 'lat': 49.0297, 'lon': 13.5764, 'category': 'Mountain Hut'},
        {'name': 'Modrava', 'lat': 49.0300, 'lon': 13.4969, 'category': 'Mountain Hut'},
        {'name': 'Churáňov', 'lat': 49.0719, 'lon': 13.6164, 'category': 'Tourist Attraction'},
        
        # German - Peaks
        {'name': 'Großer Arber', 'lat': 49.1094, 'lon': 13.1347, 'category': 'Mountain Peak', 'ele': '1456'},
        {'name': 'Rachel', 'lat': 49.0453, 'lon': 13.3878, 'category': 'Mountain Peak', 'ele': '1453'},
        {'name': 'Lusen', 'lat': 48.9542, 'lon': 13.5036, 'category': 'Mountain Peak', 'ele': '1373'},
        {'name': 'Kleiner Arber', 'lat': 49.1275, 'lon': 13.1117, 'category': 'Mountain Peak', 'ele': '1384'},
        
        # German - Attractions
        {'name': 'Baumwipfelpfad', 'lat': 48.9194, 'lon': 13.4622, 'category': 'Tourist Attraction'},
        {'name': 'Tierfreigelände', 'lat': 49.0550, 'lon': 13.3608, 'category': 'Tourist Attraction'},
        {'name': 'Rachelsee', 'lat': 49.0444, 'lon': 13.3917, 'category': 'Lake'},
        
        # Border area
        {'name': 'Třístoličník (Dreisesselberg)', 'lat': 48.7067, 'lon': 13.8050, 'category': 'Mountain Peak', 'ele': '1312'},
    ]
    
    pois_clean = gpd.GeoDataFrame(
        destinations,
        geometry=[Point(d['lon'], d['lat']) for d in destinations],
        crs='EPSG:4326'
    )
    
else:
    # Combine OSM downloads
    combined = pd.concat(all_pois, ignore_index=True)
    
    # Remove duplicates
    id_cols = []
    if 'osmid' in combined.columns:
        id_cols.append('osmid')
    if 'element_type' in combined.columns:
        id_cols.append('element_type')
    
    if id_cols:
        combined = combined.drop_duplicates(subset=id_cols)
    else:
        combined = combined.drop_duplicates(subset=['geometry'])
    
    print(f"\n✅ Total unique POIs: {len(combined)}")
    
    # Categorize
    def categorize_poi(row):
        if pd.notna(row.get('natural')):
            if row.get('natural') == 'peak':
                return 'Mountain Peak'
            elif row.get('natural') in ['waterfall', 'spring']:
                return 'Water Feature'
            elif row.get('natural') == 'lake':
                return 'Lake'
            elif row.get('natural') == 'cave_entrance':
                return 'Cave'
        
        if pd.notna(row.get('tourism')):
            if row.get('tourism') in ['alpine_hut', 'wilderness_hut']:
                return 'Mountain Hut'
            elif row.get('tourism') == 'viewpoint':
                return 'Viewpoint'
            elif row.get('tourism') == 'attraction':
                return 'Tourist Attraction'
        
        if pd.notna(row.get('amenity')) and row.get('amenity') == 'shelter':
            return 'Shelter'
        
        return 'Other'
    
    combined['category'] = combined.apply(categorize_poi, axis=1)
    
    print("\n📊 POIs by category:")
    print(combined['category'].value_counts())
    
    # Clean up columns
    essential_cols = ['name', 'category', 'natural', 'tourism', 'amenity', 
                      'ele', 'wikipedia', 'geometry']
    cols_to_keep = [col for col in essential_cols if col in combined.columns]
    pois_clean = combined[cols_to_keep]

# ============================================
# Save
# ============================================

pois_clean.to_file(OUTPUT_PATH, driver='GPKG')

print(f"\n{'='*60}")
print(f"✅ SAVED: {OUTPUT_PATH}")
print(f"   Total POIs: {len(pois_clean)}")
print(f"{'='*60}")

if 'category' in pois_clean.columns:
    print("\n📊 Final breakdown:")
    for category, count in pois_clean['category'].value_counts().items():
        print(f"   {category}: {count}")

print("\n🎉 Done! POIs ready for analysis")
