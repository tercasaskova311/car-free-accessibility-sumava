from pathlib import Path

class Config:

    DATA_DIR = Path('data')
    STRAVA_DIR = DATA_DIR / 'strava'
    SUMAVA_DIR = DATA_DIR / 'sumava_data'
    OUTPUT_DIR = Path('maps')

    STUDY_AREA = 'data/AIO/sumava_aoi.geojson'
    STRAVA_RIDES = 'data/strava/strava_route_sample.geojson'

    CLEANED_RIDES = STRAVA_DIR / 'rides_cleaned.gpkg'
    TRAIL_NETWORK = STRAVA_DIR / 'trail_network.gpkg'
    OUTPUT_MAP = OUTPUT_DIR / 'mtb_planner.html'
    
    # Map settings
    DEFAULT_ZOOM = 11
    MIN_ZOOM = 8
    MAX_ZOOM = 18  # FIX: was 1, swapped with MIN_ZOOM
    
    # === NETWORK SETTINGS ===
    SNAP_TOLERANCE = 10  # meters - merge lines within this distance
    SIMPLIFY_TOLERANCE = 5  # meters
    INTERSECTION_BUFFER = 100  # meters - for mapping rides to segments
    CLUSTER_DISTANCE = 2000  # meters - for grouping nearby rides
    
    # Colors
    COLORS = {
        # Network traffic levels
        'no_traffic': "#FCE512",    # brown
        'low_traffic': "#0a0a09",    # Orange
        'medium_traffic': '#FF9966', # Light red
        'high_traffic': '#CC0000',   # Red
        
        # Route types
        'loop': '#2ecc71',           # Green
        'point_to_point': '#3498db', # Blue
        'out_and_back': '#9b59b6',   # Purple
        
        # General
        'study_area': '#FCE512',
        'highlight': '#f39c12',
        'default': '#3498db'
    }
    
    # Traffic thresholds (number of rides)
    TRAFFIC_THRESHOLDS = {
        'low': 3,
        'medium': 7
    }

    # Clustering
    CLUSTER_DISTANCE = 2000  # meters
    INTERSECTION_BUFFER = 100  # meters

    # === HEATMAP SETTINGS ===
    HEATMAP_POINTS_PER_ROUTE = 30
    HEATMAP_RADIUS = 15
    HEATMAP_BLUR = 20
    
    @classmethod
    def ensure_directories(cls):
        """Create output directories if they don't exist"""
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.STRAVA_DIR.mkdir(parents=True, exist_ok=True)

    
    # Performance tuning for large datasets
    SIMPLIFY_GEOMETRIES = True  # Set to False for max detail
    MAX_RIDES_IN_POPUP = 10     # Limit popup content
    SAMPLE_HEATMAP = True       # Use subset for heatmap
    HEATMAP_SAMPLE_SIZE = 0.5   # Use 50% of rides

    # === RENDERING PERFORMANCE ===
    # Subsample rides for the base trail layer to keep HTML manageable
    # With 9500+ rides, rendering all of them individually kills the browser
    BASE_TRAIL_SAMPLE_SIZE = 500   # max rides to show on base trail layer
    # Simplify geometry tolerance (meters) applied before writing to HTML
    RENDER_SIMPLIFY_M = 10