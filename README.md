# Car-Free Tourism Accessibility Analysis
## Šumava & Bavarian Forest National Parks

### Project Overview
Geospatial analysis evaluating public transport accessibility to tourism destinations 
in cross-border protected areas. Interactive web map showing car-free travel 
feasibility using OSM data, GTFS schedules, and network analysis.

## Phase 1: Data Collection 
**Goal:** Download all necessary spatial layers

### 1.1 Base Layers (OSM via OSMnx)
- [x] Study area boundary (Jihočeský kraj, Plzeňský kraj, Freyung-Grafenau, Regen)
- [x] Road network (drive network type)
- [x] Bus stops & train stations
- [x] Parking locations
- [x] Tourism POIs (peaks, lakes, viewpoints, alpine huts, attractions)

**Output:** `data/raw/*.gpkg` files

### 1.2 Public Transport Data (GTFS)
- [x] Czech GTFS (Jihočeský & Plzeňský kraj)
- [x] German GTFS (Bayern)
- [x] Processed transit stops, routes, timetables, frequency

**Processing script:** `prepare_gtfs_layers.py`
**Output:** `data/processed/gtfs_layers.gpkg` (multi-layer)
  - stops (10,832 features)
  - routes (550 features) 
  - timetable (scheduled departures)
  - frequency (service levels)
