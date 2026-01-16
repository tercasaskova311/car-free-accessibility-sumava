# MTB Trail Center Planner for Šumava National Park
**Geospatial Analysis of Mountain Bike Routes Using Personal Strava Data**


Using 7 years of personal GPS tracking data from Strava (2017-2024), this analysis:
- Identifies high-traffic trail networks through spatial clustering (DBSCAN)
- Evaluates candidate trail center locations based on accessibility metrics
- Performs environmental constraint analysis using protected zone classifications
- Generates an interactive map with multiple analytical layers

**[View Live Interactive Map](maps/mtb_planner_map.html)** (download and open in browser)

---

## Study Area

**Šumava National Park (Národní park Šumava) and Protected Landscape Area (CHKO Šumava)**
- Location: Czech Republic-Germany border
- Total area: ~1,630 km² (NP + CHKO)

---

## Quick Start

### Prerequisites
- (Optional) Strava account for downloading custom data

### Installation

```bash
# Clone repository
git clone https://github.com/tercasaskova311/mtb-ride-planner
cd mtb-ride-planner
pip install -r requirements.txt

#Option 1: Use Sample Data (Quick Demo)
python maps/testing.py

#Option 2: Download Your Own Strava Data
#Requirements = Active Strava account with GPS activities

#1.Get Strava API Credentials:**
   - Go to https://www.strava.com/settings/api
   - Create a new application
   - Note your `Client ID` and `Client Secret`

#2.Set Environment Variables:
   export STRAVA_CLIENT_ID="your_client_id"
   export STRAVA_CLIENT_SECRET="your_client_secret"
   export CODE="your_authorization_code"

#3.Download Data:   
   python preprocessing/strava_data.py

#4.Run Analysis

python maps/main.py
```

## STEPS ##
1. Load and clean ride data
2. Build unified trail network from overlapping GPS tracks
3. Map rides to network segments
4. Perform DBSCAN clustering on high-traffic areas
5. Calculate suitability scores for candidate locations
6. Check environmental constraints (protected zones)
7. Generate interactive map with all layers

---

## Interactive Map Features

Open `maps/mtb_planner_map.html` in web browser.

### Base Layers
-  **OpenStreetMap** - Default street map
-  **Satellite Imagery** - Esri World Imagery
-  **Topographic Map** - OpenTopoMap with contours

### Analysis Layers
| Layer | Description | Visibility |
|-------|-------------|------------|
| **Study Area Boundary** | Red dashed outline of NP + CHKO | Always on |
| **Protected Zones** | Green gradient (darker = stricter) | On by default |
| **Trail Network** | Color by popularity:<br>🟡 Low (1-2 rides)<br>🟠 Medium (3-6 rides)<br>🔴 High (7+ rides) | On by default |
| **Candidate Locations** | Numbered markers (1-8), sized by rank | On by default |
| **Density Heatmap** | Red-yellow GPS point concentration | Off by default |
| **Ride Clusters** | Grouped by start point proximity | Off by default |
| **Rides by Length** | Short/Medium/Long categories | Off by default |

---

## Project Structure

```
mtb-ride-planner/
│
├── data/
│   ├── strava/                    # Strava GPS data
│   │   ├── strava_routes_sumava.geojson
│   │   ├── trail_network.gpkg
│   │   └── rides_cleaned.gpkg
│   │
│   ├── sumava_data/               # Protected area boundaries
│   │   ├── sumava_np.geojson
│   │   ├── sumava_chko.geojson
│   │   └── sumava_aoi.gpkg        # Combined AOI
│   │
│   └── sumava_zones_2.geojson     # Official zone classifications
│
├── maps/                          # Analysis scripts
│   ├── main.py                    # Main pipeline
│   ├── analysis.py                # Suitability analysis
│   ├── network_layer.py           # Trail network construction
│   ├── base_map.py                # Base map creation
│   ├── bike_layer.py              # Trail visualization layers
│   ├── heatmap.py                 # Density heatmap
│   ├── loader.py                  # Data loading utilities
│   ├── testing.py                 # Quick test with sample data
│   └── mtb_planner_map.html       # OUTPUT: Interactive map
│
├── preprocessing/
│   ├── aio_download.py            # Download protected areas
│   └── strava_data.py             # Download Strava activities
│
├── analysis/
│   └── visualization_zones.py     # Zone classification analysis
│
├── config.py                      # Configuration parameters
├── requirements.txt               # Python dependencies
└── README.md                      # This file
```

---

## Methodology

### 1. Trail Network Construction
- **Input:** 147 overlapping GPS tracks
- **Method:** Shapely `unary_union` + `linemerge`
- **Output:** 324 distinct trail segments

### 2. Popularity Analysis
- **Method:** Buffer-based spatial join (100m tolerance)
- **Result:** Each segment tagged with ride count

### 3. Candidate Identification
- **Algorithm:** DBSCAN clustering (eps=2000m, min_samples=3)
- **Filtering:** High-traffic segments (≥5 rides)
- **Output:** 8 candidate clusters

### 4. Accessibility Scoring
- **Metric:** Trail count/length/traffic within 5km radius
- **Weights:** Frequency (40%), Traffic (40%), Length (20%)

### 5. Environmental Constraints
- **Method:** Point-in-polygon spatial join with zone classifications
- **Penalty:** Zone A (core protection) → Score = 0

---



  