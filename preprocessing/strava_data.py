import json
import time
from pathlib import Path
from datetime import datetime
import geopandas as gpd
from shapely.geometry import LineString, MultiLineString, Point
from stravalib import Client
import polyline
import os

STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
CODE = os.getenv("CODE")

if not STRAVA_CLIENT_ID or not STRAVA_CLIENT_SECRET or not CODE:
    raise RuntimeError("STRAVA_CLIENT_ID / STRAVA_CLIENT_SECRET not set")


# ============================================
# CONFIG
# ============================================

TOKEN_FILE = 'data/.strava_token.json'
OUTPUT_DIR = Path('data/strava')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_GEOJSON = OUTPUT_DIR / 'strava_routes_sumava.geojson'
START_POINTS_GEOJSON = OUTPUT_DIR / 'strava_start_points_sumava.geojson'
AIO = 'data/sumava_data/sumava_aoi.geojson'

ACTIVITY_TYPE = 'Ride'
MIN_DATE = datetime(2017, 1, 1)
REQUEST_DELAY = 5  # seconds between requests

# ============================================
# HELPERS
# ============================================

def load_token():
    if not Path(TOKEN_FILE).exists():
        raise FileNotFoundError(f"Token file not found: {TOKEN_FILE}")
    with open(TOKEN_FILE) as f:
        return json.load(f)

def refresh_token_if_needed(token_data):
    if token_data["expires_at"] > time.time():
        return token_data  # still valid

    print(" Token expired, refreshing...")

    client = Client()
    new_token = client.refresh_access_token(
        client_id=STRAVA_CLIENT_ID,
        client_secret=STRAVA_CLIENT_SECRET,
        code=CODE
    )

    with open(TOKEN_FILE, "w") as f:
        json.dump(new_token, f, indent=2)

    print("Token refreshed")
    return new_token

def decode_polyline_to_linestring(polyline_str):
    if not polyline_str:
        return None
    try:
        coords = polyline.decode(polyline_str)
        coords_swapped = [(lon, lat) for lat, lon in coords]
        return LineString(coords_swapped)
    except Exception:
        return None

def get_start_point(geom):
    if geom is None:
        return None
    if isinstance(geom, LineString):
        return Point(geom.coords[0])
    elif isinstance(geom, MultiLineString):
        return Point(list(geom.geoms[0].coords)[0])
    else:  # GeometryCollection or other
        for g in geom.geoms:
            if isinstance(g, LineString):
                return Point(g.coords[0])
    return None

def save_routes_geojson(gdf, path):
    if len(gdf) > 0:
        gdf.to_file(path, driver='GeoJSON')
        print(f"Saved {len(gdf)} records → {path}")

# ============================================
# MAIN DOWNLOAD FUNCTION
# ============================================
def download_strava_routes_incremental():
    print("Loading Strava token...")

    token_data = load_token()
    token_data = refresh_token_if_needed(token_data)

    client = Client(access_token=token_data["access_token"])

    athlete = client.get_athlete()
    print(f"👤 Athlete: {athlete.firstname} {athlete.lastname}")

    # Load AOI
    aio_gdf = gpd.read_file(AIO)[['geometry']]
    aio_gdf = aio_gdf.to_crs(epsg=4326)

    # Resume from existing file
    if OUTPUT_GEOJSON.exists():
        routes_gdf = gpd.read_file(OUTPUT_GEOJSON)
        processed_ids = set(routes_gdf['activity_id'])
        routes_list = routes_gdf.to_dict('records')
        print(f"Resuming, {len(routes_list)} activities already saved")
    else:
        routes_list = []
        processed_ids = set()

    count = 0
    batch_save = 10  # save after every 10 rides

    for activity in client.get_activities(after=MIN_DATE):
        if activity.type != ACTIVITY_TYPE or activity.id in processed_ids:
            continue

        # Retry activity download
        retries = 3
        for attempt in range(retries):
            try:
                detailed = client.get_activity(activity.id)
                break
            except Exception as e:
                wait = 2 ** attempt
                print(f" Error downloading activity {activity.id}: {e}. Retrying in {wait}s...")
                time.sleep(wait)
        else:
            print(f" Failed to download activity {activity.id}, skipping...")
            continue

        geom = decode_polyline_to_linestring(
            detailed.map.summary_polyline if detailed.map else None
        )
        if geom is None:
            continue

        record = {
            'activity_id': detailed.id,
            'name': detailed.name,
            'date': detailed.start_date_local,
            'distance_km': float(detailed.distance) / 1000 if detailed.distance else 0,
            'elevation_gain_m': float(detailed.total_elevation_gain) if detailed.total_elevation_gain else 0,
            'geometry': geom
        }

        routes_list.append(record)
        processed_ids.add(detailed.id)
        count += 1

        # Save batch every N rides
        if count % batch_save == 0:
            gdf_tmp = gpd.GeoDataFrame(routes_list, crs='EPSG:4326')

            # Clip to AOI to keep only rides in Sumava
            sumava_routes = gpd.overlay(gdf_tmp, aio_gdf, how='intersection')
            save_routes_geojson(sumava_routes, OUTPUT_GEOJSON)

            # Save start points
            start_points = sumava_routes.copy()
            start_points['geometry'] = start_points['geometry'].apply(get_start_point)
            save_routes_geojson(start_points, START_POINTS_GEOJSON)

        time.sleep(REQUEST_DELAY)

    # Save final batch
    gdf_tmp = gpd.GeoDataFrame(routes_list, crs='EPSG:4326')
    sumava_routes = gpd.overlay(gdf_tmp, aio_gdf, how='intersection')
    save_routes_geojson(sumava_routes, OUTPUT_GEOJSON)

    start_points = sumava_routes.copy()
    start_points['geometry'] = start_points['geometry'].apply(get_start_point)
    save_routes_geojson(start_points, START_POINTS_GEOJSON)

    print(f" Done! Total new activities processed this run: {count}")
    return gpd.read_file(OUTPUT_GEOJSON)


if __name__ == "__main__":
    download_strava_routes_incremental()
