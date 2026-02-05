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
    
    # ============================================================
    # ULTRA-MINIMAL SETTINGS FOR 548 RIDES
    # ============================================================
    
    # Network building - create FEWER, LONGER segments
    SNAP_TOLERANCE = 50          # ← VERY LARGE (was 25)
    MIN_SEGMENT_LENGTH = 500     # ← VERY LARGE (was 200)
    SIMPLIFY_TOLERANCE = 10      # ← More aggressive
    INTERSECTION_BUFFER = 30     # ← VERY SMALL (was 50)
    
    # Rendering - show MINIMAL data in HTML
    BASE_TRAIL_SAMPLE_SIZE = 100      # ← Only 100 segments (was 300)
    RENDER_SIMPLIFY_M = 30            # ← Very aggressive (was 20)
    TRAIL_RENDER_STRATEGY = 'top_traffic'  # Show only busiest trails
    
    # Heatmap - MINIMAL
    HEATMAP_POINTS_PER_ROUTE = 10     # ← Reduced from 20
    HEATMAP_RADIUS = 12
    HEATMAP_BLUR = 15
    MAX_HEAT_POINTS = 3000            # ← Reduced from 8000
    
    # Rides by length - MINIMAL
    MAX_RIDES_PER_LENGTH_CATEGORY = 50   # ← Only 50 per category
    MAX_TOTAL_RIDES_RENDER = 150         # ← Total 150 rides shown
    
    # Colors
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
        'low': 2,      # ← Lower thresholds for small dataset
        'medium': 5
    }
    
    CLUSTER_DISTANCE = 2000
    SIMPLIFY_GEOMETRIES = True
    SAMPLE_HEATMAP = True
    HEATMAP_SAMPLE_SIZE = 0.3  # Use only 30% for heatmap
    
    @classmethod
    def ensure_directories(cls):
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.STRAVA_DIR.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def print_settings(cls):
        print("\n" + "="*70)
        print("ULTRA-MINIMAL CONFIG (548 rides)")
        print("="*70)
        print("\nNETWORK BUILDING:")
        print(f"  SNAP_TOLERANCE:     {cls.SNAP_TOLERANCE}m (creates ~50-150 segments)")
        print(f"  MIN_SEGMENT_LENGTH: {cls.MIN_SEGMENT_LENGTH}m (filters tiny segments)")
        print("\nHTML RENDERING:")
        print(f"  Segments shown:     {cls.BASE_TRAIL_SAMPLE_SIZE}")
        print(f"  Rides shown:        {cls.MAX_TOTAL_RIDES_RENDER}")
        print(f"  Heatmap points:     {cls.MAX_HEAT_POINTS}")
        print(f"  Expected HTML:      ~5-10 MB")
        print("="*70 + "\n")