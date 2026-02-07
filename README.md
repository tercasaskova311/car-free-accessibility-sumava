# 🚵 MTB Trail Center Planner for Šumava National Park

Find the best location for a mountain bike trail center using GPS data and spatial analysis.

## 📍 What This Does

This project analyzes 7 years of mountain biking GPS data (3,045 rides) to find the optimal location for a trail center in Šumava National Park, Czech Republic.

**[🗺️ View Interactive Map](https://tercasaskova311.github.io/mtb-ride-planner/maps/mtb_planner.html)**

## Results

- **Best Location**: 49.09°N, 13.61°E (Score: 80/100)
- **Zone**: II (development permitted)

## How It Works

1. **Collects GPS rides** from personal activities
2. **Builds trail network** by merging overlapping rides
3. **Finds hotspots** using spatial statistics (Moran's I)
4. **Ranks locations** based on trail access and usage
5. **Checks regulations** (avoids protected zones)


## Sections

- **Interactive map** with trail network, heatmaps, and candidate locations
- **Spatial analysis** identifying high-traffic areas
- **Environmental compliance** checking protected zones

## Structure

```
mtb-ride-planner/
├── data/                      # GPS data and boundaries
│   ├── strava/                # Your ride data
│   └── sumava_zones_2.geojson # Protected zones
├── maps/                      # Analysis scripts
│   ├── main.py                # Run this!
│   └── mtb_planner.html       # Output map
├── preprocessing/             # Data download tools
└── requirements.txt           # Dependencies
```
## Features

- ✅ Automated trail network construction
- ✅ Statistical hotspot detection (Moran's I)
- ✅ Multi-criteria location ranking
- ✅ Environmental constraint checking
- ✅ Interactive web map visualization

## Methods

- **Network Building**: Grid-based spatial indexing (1000m cells)
- **Hotspot Detection**: Local Moran's I analysis
- **Clustering**: DBSCAN (ε = 2 km)
- **Scoring**: Weighted by accessibility (30%), usage (30%), clustering (40%)





  