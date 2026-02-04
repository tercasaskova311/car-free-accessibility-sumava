# MTB Trail Center Planner for Šumava National Park
**Geospatial Analysis of Mountain Bike Routes Using Personal Strava Data**


Using personal GPS tracking data from Garmin device (2017-2024), this analysis:
- Identifies high-traffic trail networks through spatial analysis (Moran's I)
- Evaluates candidate trail center locations based on accessibility metrics
- Performs environmental constraint analysis using protected zone classifications
- Generates an interactive map with multiple analytical layers

**[View Live Interactive Map](....)

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

#Download Your Own Strava Data
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
4. Perform Moran's I global and local spacial analysis
5. Calculate suitability scores for candidate locations
6. Check environmental constraints (protected zones)
7. Generate interactive map with all layers

---

## Interactive Map Features

Open (...)

### Base Layers
-  **OpenStreetMap** - Default street map
-  **Satellite Imagery** - Esri World Imagery
-  **Topographic Map** - OpenTopoMap with contours

### Analysis Layers
| Layer | Description | Visibility |
|-------|-------------|------------|
| **Study Area Boundary** | Red dashed outline of NP + CHKO | Always on |
| **Protected Zones** | Green gradient (darker = stricter) | On by default |
| **Trail Network** | .....|
| **Candidate Location** | 1 choosen location marked by circle | On by default |
| **Density Heatmap** | Red-yellow GPS point concentration | Off by default |
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
│   │   └── sumava_aoi.gpkg        # Combined AOI
│   │
│   └── sumava_zones_2.geojson     # Official zone classifications
│
├── maps/                          # Analysis scripts
│   ├── main.py                    # Main pipeline
│   ├── spatial_analysis.py        # Suitability analysis
│   ├── network_layer.py           # Trail network construction
│   ├── base_map.py                # Base map creation
│   ├── bike_layer.py              # Trail visualization layers
│   ├── heatmap.py                 # Density heatmap
│   ├── loader.py                  # Data loading utilities
│   └── mtb_planner_map.html       # OUTPUT: Interactive map
│
├── preprocessing/
│   ├── aio_download.py            # Download protected areas
│   └── strava_data.py             # Download Strava activities
│
├── config.py                      # Configuration parameters
├── requirements.txt               
└── README.md                      
```

---

## Methodology

### 1. Trail Network Construction
- **Input:**  overlapping GPS tracks
- **Method:** Shapely `unary_union` + `linemerge`
- **Output:** distinct trail segments

### 2. Popularity Analysis
- **Method:** Buffer-based spatial join (100m tolerance)
- **Result:** Each segment tagged with ride count

### 3. Candidate Identification
- **Algorithm:** Moran's I local + global
- **Filtering:** High-traffic segments 
- **Output:** 1 candidate 

### 4. Accessibility Scoring
- **Metric:** Trail count/length/traffic within 5km radius
- **Weights:** Frequency (40%), Traffic (40%), Length (20%)

### 5. Environmental Constraints
- **Method:** Point-in-polygon spatial join with zone classifications
- **Penalty:** Zone A (core protection) → Score = 0

---



  