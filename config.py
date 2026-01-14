from pathlib impot Path

class Config:

    DATA_DIR = Path('data')
    STRAVA_DIR = DATA_DIR / 'strava'
    SUMAVA_DIR = DATA_DIR / 'sumava_data'
    OUTPUT_DIR = Path('maps')

    STUDY_AREA = 'data/sumava_data/sumava_aoi.gpkg'
    STRAVA_RIDES = 'data/strava/strava_routes_sumava.gpkg'

    CLEANED_RIDES = STRAVA_DIR / 'rides_cleaned.gpkg'
    TRAIL_NETWORK = STRAVA_DIR / 'trail_network.gpkg'
    OUTPUT_MAP = OUTPUT_DIR / 'mtb_planner.html'
    
    # Map settings
    DEFAULT_ZOOM = 11
    MIN_ZOOM = 8
    MAX_ZOOM = 
    
    # === NETWORK SETTINGS ===
    SNAP_TOLERANCE = 50  # meters - merge lines within this distance
    SIMPLIFY_TOLERANCE = 10  # meters
    INTERSECTION_BUFFER = 100  # meters - for mapping rides to segments
    CLUSTER_DISTANCE = 2000  # meters - for grouping nearby rides
    
    # Colors
    COLORS = {
        # Network traffic levels
        'no_traffic': '#95a5a6',    # Gray
        'low_traffic': '#3498db',    # Blue
        'medium_traffic': '#f39c12', # Orange
        'high_traffic': '#e74c3c',   # Red
        
        # Route types
        'loop': '#2ecc71',           # Green
        'point_to_point': '#3498db', # Blue
        'out_and_back': '#9b59b6',   # Purple
        
        # General
        'study_area': '#e74c3c',
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