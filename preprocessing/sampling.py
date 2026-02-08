# scripts/00_sample_dataset.py
"""
Random sampling of GPS rides to reduce computational load
Original dataset: 9,000 rides
Target sample: 3,045 rides (33.8%)
"""

import geopandas as gpd
import numpy as np
from pathlib import Path

# Set random seed for reproducibility
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)

# Paths
INPUT_FILE = 'data/strava/strava_routes_sumava_FULL.geojson'  # Original 9k
OUTPUT_FILE = 'data/strava/strava_routes_sumava.geojson'      # Sampled 3k

# Load full dataset
print("Loading full dataset...")
full_rides = gpd.read_file(INPUT_FILE)
print(f"Full dataset: {len(full_rides)} rides")

# Calculate statistics BEFORE sampling (for validation)
print("\nFull dataset statistics:")
print(f"  Mean distance: {full_rides['distance_km'].mean():.1f} km")
print(f"  Mean elevation: {full_rides['elevation_gain_m'].mean():.0f} m")
print(f"  Date range: {full_rides['date'].min()} to {full_rides['date'].max()}")

# Random sample (33.8%)
SAMPLE_SIZE = 3045
sample_indices = np.random.choice(full_rides.index, size=SAMPLE_SIZE, replace=False)
sampled_rides = full_rides.loc[sample_indices].copy()

# Calculate statistics AFTER sampling (for validation)
print(f"\nSampled dataset ({SAMPLE_SIZE} rides):")
print(f"  Mean distance: {sampled_rides['distance_km'].mean():.1f} km")
print(f"  Mean elevation: {sampled_rides['elevation_gain_m'].mean():.0f} m")
print(f"  Date range: {sampled_rides['date'].min()} to {sampled_rides['date'].max()}")

# Compare distributions
print("\nDistribution comparison:")
print(f"  Distance difference: {abs(full_rides['distance_km'].mean() - sampled_rides['distance_km'].mean()):.1f} km")
print(f"  Elevation difference: {abs(full_rides['elevation_gain_m'].mean() - sampled_rides['elevation_gain_m'].mean()):.0f} m")

# Save sampled dataset
sampled_rides.to_file(OUTPUT_FILE, driver='GeoJSON')
print(f" Sampled dataset saved to {OUTPUT_FILE}")
print(f"   Random seed: {RANDOM_SEED} (for reproducibility)")