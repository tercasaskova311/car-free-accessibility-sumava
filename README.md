# 🚵 MTB Trail Center Site Selection for Šumava National Park

**Evidence-based trail center location analysis using GPS activity data and spatial autocorrelation.**

**[View Interactive Map](https://tercasaskova311.github.io/mtb-ride-planner/maps/mtb_planner.html)**

---

## Overview

This project analyzes 7 years of mountain biking GPS data (2017–2024, 3,045 rides, 62 919.8 km) to identify optimal trail center locations in Šumava National Park, Czech Republic, using spatial autocorrelation analysis (Moran's I) and environmental constraints.

**Key Result:** Location at 49.09°N, 13.61°E (Zone C, Score: 80/100) provides access to 2575 high-traffic trail segments within 5 km radius.

---

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
│   │   └── strava_sample.geojson       #small sample 
│   ├── AIO/
│   │   └── sumava_aoi.geojson                 # Study area boundary
│   ├── sumava_zones_2.geojson                 # Protected zones 
│
├── maps/                              
│   ├── main.py                        # Master script (run this!)
│   ├── loader.py                      # Data loading utilities
│   ├── network_layer.py               # Grid-based network construction
│   ├── spatial_analysis.py            # Moran's I + candidate selection
│   ├── base_map.py                    # Folium base map creation
│   ├── trails_layer.py                # Trail/zone/candidate layers
│   ├── heatmap.py                     # Density heatmap generation
│   ├── mtb_planner.html               # Interactive output map
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

## Interactive Map Features

Access at: https://tercasaskova311.github.io/mtb-ride-planner/maps/mtb_planner.html

- **Trail Network:** 300 segments (traffic-weighted sample)
- **Heatmap:** Kernel density (15,000 points, 1,000 rides sampled)
- **High-High Clusters:** Top 10 statistically significant hotspots
- **Candidate Locations:** Top 2 sites with pop-ups
- **Protected Zones:** Zones & restrictions
- **Base Maps:** OpenStreetMap, Satellite, Topographic

---

## Links

- **Interactive Map:** https://tercasaskova311.github.io/mtb-ride-planner/maps/mtb_planner.html

