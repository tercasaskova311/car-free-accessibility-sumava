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
    MAX_ZOOM = 18
    
    SNAP_TOLERANCE = 100           # Cluster distance (4x buffer for similar routes)
    MIN_SEGMENT_LENGTH = 300       # Filter segments shorter than 300m
    SIMPLIFY_TOLERANCE = 15        # Simplify geometry by 15m tolerance
    INTERSECTION_BUFFER = 100      # Ride-to-segment mapping tolerance
    BASE_TRAIL_SAMPLE_SIZE = 300        # Show top 300 segments (traffic-weighted)
    RENDER_SIMPLIFY_M = 25              # Simplify coordinates for HTML
    TRAIL_RENDER_STRATEGY = 'traffic_weighted'  # Prioritize busy trails
    HEATMAP_POINTS_PER_ROUTE = 15       # 15 points per route
    HEATMAP_RADIUS = 12                 # Heatmap radius
    HEATMAP_BLUR = 15                   # Blur amount
    MAX_HEAT_POINTS = 5000              # Cap total points at 5000

    MAX_RIDES_PER_LENGTH_CATEGORY = 100   # 100 per category (short/medium/long)
    MAX_TOTAL_RIDES_RENDER = 300          # Total 300 rides in HTML
    
    COLORS = {
        'no_traffic': "#1f77b4",
        'low_traffic': "#ff7f0e",
        'medium_traffic': '#FF9966',
        'high_traffic': '#d62728',
        'loop': '#2ecc71',
        'point_to_point': '#3498db',
        'out_and_back': '#9b59b6',
        'study_area': "#790101",
        'highlight': '#f39c12',
        'default': '#3498db'
    }
    
    TRAFFIC_THRESHOLDS = {
        'low': 5,       # 5+ rides = low traffic
        'medium': 10    # 10+ rides = medium traffic
    }
    
    # Legacy settings (not used with optimized approach)
    CLUSTER_DISTANCE = 2000
    SIMPLIFY_GEOMETRIES = True
    SAMPLE_HEATMAP = True
    HEATMAP_SAMPLE_SIZE = 0.3
    
    @classmethod
    def ensure_directories(cls):
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.STRAVA_DIR.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def print_settings(cls):
        print("OPTIMIZED CONFIG FOR 3,000 RIDES")
        print("\nNETWORK BUILDING:")
        print(f"  SNAP_TOLERANCE:       {cls.SNAP_TOLERANCE}m (clustering distance)")
        print(f"  MIN_SEGMENT_LENGTH:   {cls.MIN_SEGMENT_LENGTH}m (minimum segment)")
        print(f"  SIMPLIFY_TOLERANCE:   {cls.SIMPLIFY_TOLERANCE}m (geometry simplification)")
        print(f"  INTERSECTION_BUFFER:  {cls.INTERSECTION_BUFFER}m (mapping tolerance)")
        print(f"\n  Expected output:      400-700 segments")
        print(f"  Expected time:        30-60 seconds")
        
        print("\nHTML RENDERING:")
        print(f"  Segments shown:       {cls.BASE_TRAIL_SAMPLE_SIZE} (traffic-weighted sample)")
        print(f"  Rides shown:          {cls.MAX_TOTAL_RIDES_RENDER} (balanced categories)")
        print(f"  Heatmap points:       {cls.MAX_HEAT_POINTS}")
        print(f"  Simplification:       {cls.RENDER_SIMPLIFY_M}m")
