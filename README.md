# 🚵 MTB Trail Center Site Selection for Šumava National Park

**Evidence-based trail center location analysis using GPS activity data and spatial autocorrelation.**

**[View Interactive Map](https://tercasaskova311.github.io/mtb-ride-planner/maps/mtb_planner.html)**

---

## Overview

This project analyzes 7 years of mountain biking GPS data (2017–2024, 3,045 rides, 112,276 km) to identify optimal trail center locations in Šumava National Park, Czech Republic, using spatial autocorrelation analysis (Moran's I) and environmental constraints.

**Key Result:** Location at 49.09°N, 13.61°E (Zone II, Score: 80/100) provides access to 1,537 high-traffic trail segments within 5 km radius.

---

## Reproducibility

### Prerequisites

- **Python:** 3.9+
- **Memory:** 8 GB RAM minimum (16 GB recommended)
- **Disk Space:** 2 GB

### Installation

```bash
# 1. Clone repository
git clone https://github.com/tercasaskova311/mtb-ride-planner.git
cd mtb-ride-planner

# 2. Install dependencies
pip install -r requirements.txt
```

### Execution

**Option 1: Run complete analysis (recommended)**

```bash
python maps/main.py
```

This single script executes the full pipeline:
1. Loads GPS rides and study area boundary
2. Builds trail network using grid-based aggregation
3. Performs Global and Local Moran's I analysis
4. Identifies candidate locations via DBSCAN clustering
5. Calculates suitability scores with environmental constraints
6. Generates interactive map at `maps/mtb_planner.html`

**Expected runtime:** ~15 min. 
**Expected output:** 20,023 trail segments + candidate locations

**Option 2: Download new GPS data (optional)**

```bash
# Requires Strava API credentials as environment variables
export STRAVA_CLIENT_ID="your_id"
export STRAVA_CLIENT_SECRET="your_secret"
export CODE="your_code"

python preprocessing/strava_data.py
```

---

##  Structure

```
mtb-ride-planner/
│
├── data/                              # Input datasets (gitignored)
│   ├── strava/
│   │   ├── strava_routes_sumava.geojson       # 3,045 GPS rides
│   │   └── strava_start_points_sumava.geojson
│   ├── sumava_data/
│   │   └── sumava_aoi.geojson                 # Study area boundary
│   ├── sumava_zones_2.geojson                 # Protected zones (I-IV)
│   └── AIO/                                   # Area of interest files
│
├── maps/                              # Analysis pipeline + outputs
│   ├── main.py                        # ⭐ Master script (run this!)
│   ├── loader.py                      # Data loading utilities
│   ├── network_layer.py               # Grid-based network construction
│   ├── spatial_analysis.py            # Moran's I + candidate selection
│   ├── base_map.py                    # Folium base map creation
│   ├── trails_layer.py                # Trail/zone/candidate layers
│   ├── heatmap.py                     # Density heatmap generation
│   ├── mtb_planner.html               # 🗺️ Interactive output map
│   ├── candidate_locations.gpkg       # Analysis results
│   └── network_with_lisa.gpkg         # Network with LISA statistics
│
├── preprocessing/                     # Data collection (optional)
│   ├── strava_data.py                 # Strava API downloader
│   └── aio_download.py                # Study area boundary downloader
│
├── config.py                          # Configuration parameters
├── requirements.txt                   # Python dependencies
├── README.md                          # This file
└── .github/workflows/static.yml       # GitHub Pages deployment
```

---

## Methodology 

### 1. Network Construction (`network_layer.py`)
- **Grid-based aggregation:** 1000m × 1000m cells
- **Douglas-Peucker simplification:** 15m tolerance
- **Snapping tolerance:** 100m (GPS error compensation)
- **Minimum segment length:** 300m
- **Output:** 20,023 segments from 3,045 rides (~0.2x compression)

### 2. Spatial Autocorrelation (`spatial_analysis.py`)
- **Global Moran's I:** I = 0.0793 (p < 0.001) → significant clustering
- **Local Moran's I (LISA):** Identifies 1,537 High-High hotspots
- **Distance threshold:** 2000m (spatial weights)

### 3. Candidate Selection
- **DBSCAN clustering:** ε = 2km, min_samples = 2
- **Service radius:** 5 km (IMBA guidelines)
- **Weighted centroid:** Local Moran's I as weights

### 4. Suitability Scoring
- **Accessibility:** 30% (unique trail length within 5 km)
- **Usage:** 30% (total rides intersecting buffer)
- **Clustering:** 40% (mean Local Moran's I)
- **Constraint:** Zone I (core protection) = score 0

---

## Interactive Map Features

Access at: https://tercasaskova311.github.io/mtb-ride-planner/maps/mtb_planner.html

- **Trail Network:** 300 segments (traffic-weighted sample)
- **Heatmap:** Kernel density (15,000 points, 1,000 rides sampled)
- **High-High Clusters:** Top 10 statistically significant hotspots
- **Candidate Locations:** Top 3 sites with detailed pop-ups
- **Protected Zones:** Zones I-IV with opacity-coded restriction levels
- **Base Maps:** OpenStreetMap, Satellite, Topographic
- **Layer Controls:** Toggle visibility

---

## License & Privacy

- **Data:** Personal GPS data from 3 anonymized users with informed consent
- **Map tiles:** © OpenStreetMap contributors

---

## Links

- **Interactive Map:** https://tercasaskova311.github.io/mtb-ride-planner/maps/mtb_planner.html
- **GitHub Repository:** https://github.com/tercasaskova311/mtb-ride-planner

