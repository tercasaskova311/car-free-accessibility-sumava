import pandas as pd
import matplotlib.pyplot as plt
import geopandas as gpd
import numpy as np
from datetime import datetime

rides = gpd.read_file('data/strava/strava_route_sample.geojson')

# ============================================
# TEMPORAL ANALYSIS
# ============================================
rides['date'] = pd.to_datetime(rides['date'])
rides['year'] = rides['date'].dt.year
rides['month'] = rides['date'].dt.month
rides['day_of_week'] = rides['date'].dt.dayofweek  # 0=Monday, 6=Sunday
rides['season'] = rides['month'].apply(lambda x: 
    'Winter' if x in [12, 1, 2] else
    'Spring' if x in [3, 4, 5] else
    'Summer' if x in [6, 7, 8] else 'Fall'
)

print("="*60)
print("TEMPORAL DISTRIBUTION")
print("="*60)
print("\nRides per year:")
print(rides.groupby('year').size())

print("\nRides per season:")
print(rides.groupby('season').size().sort_values(ascending=False))

print("\nRides per day of week:")
day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
dow_counts = rides.groupby('day_of_week').size()
for day, count in dow_counts.items():
    print(f"  {day_names[day]}: {count}")

# ============================================
# RIDE CHARACTERISTICS
# ============================================
print("\n" + "="*60)
print("RIDE CHARACTERISTICS")
print("="*60)

print(f"\nDistance statistics:")
print(f"  Mean: {rides['distance_km'].mean():.1f} km")
print(f"  Median: {rides['distance_km'].median():.1f} km")
print(f"  Std dev: {rides['distance_km'].std():.1f} km")
print(f"  Range: {rides['distance_km'].min():.1f} - {rides['distance_km'].max():.1f} km")

print(f"\nElevation gain statistics:")
print(f"  Mean: {rides['elevation_gain_m'].mean():.0f} m")
print(f"  Median: {rides['elevation_gain_m'].median():.0f} m")
print(f"  Std dev: {rides['elevation_gain_m'].std():.0f} m")
print(f"  Range: {rides['elevation_gain_m'].min():.0f} - {rides['elevation_gain_m'].max():.0f} m")

# Calculate climbing intensity (m elevation per km)
rides['climb_intensity'] = rides['elevation_gain_m'] / rides['distance_km']
print(f"\nClimbing intensity (elevation gain per km):")
print(f"  Mean: {rides['climb_intensity'].mean():.1f} m/km")
print(f"  Median: {rides['climb_intensity'].median():.1f} m/km")

# Categorize rides by difficulty
rides['difficulty'] = pd.cut(
    rides['climb_intensity'],
    bins=[0, 20, 40, 60, np.inf],
    labels=['Easy (<20 m/km)', 'Moderate (20-40 m/km)', 
            'Hard (40-60 m/km)', 'Very Hard (>60 m/km)']
)
print(f"\nRide difficulty distribution:")
print(rides['difficulty'].value_counts().sort_index())

# ============================================
# ACTIVITY PATTERNS
# ============================================
print("\n" + "="*60)
print("ACTIVITY PATTERNS")
print("="*60)

# Cumulative stats
total_distance = rides['distance_km'].sum()
total_elevation = rides['elevation_gain_m'].sum()
total_days = (rides['date'].max() - rides['date'].min()).days
active_months = rides.groupby([rides['year'], rides['month']]).size().count()

print(f"\nCumulative statistics (2017-2024):")
print(f"  Total rides: {len(rides):,}")
print(f"  Total distance: {total_distance:,.0f} km")
print(f"  Total elevation: {total_elevation:,.0f} m")
print(f"  Study period: {total_days} days ({total_days/365:.1f} years)")
print(f"  Active months: {active_months} out of {total_days//30} possible")
print(f"  Average rides per month: {len(rides)/active_months:.1f}")
print(f"  Average distance per ride: {total_distance/len(rides):.1f} km")

# Find the most productive month/year
most_rides_month = rides.groupby([rides['year'], rides['month']]).size().idxmax()
print(f"\nMost active month: {most_rides_month[0]}-{most_rides_month[1]:02d} "
      f"({rides.groupby([rides['year'], rides['month']]).size().max()} rides)")

# ============================================
# DATA QUALITY
# ============================================
print("\n" + "="*60)
print("DATA QUALITY METRICS")
print("="*60)

# Check for anomalies
short_rides = (rides['distance_km'] < 5).sum()
long_rides = (rides['distance_km'] > 50).sum()
low_elevation = (rides['elevation_gain_m'] < 100).sum()
high_elevation = (rides['elevation_gain_m'] > 1500).sum()

print(f"\nPotential anomalies:")
print(f"  Very short rides (<5 km): {short_rides} ({short_rides/len(rides)*100:.1f}%)")
print(f"  Very long rides (>50 km): {long_rides} ({long_rides/len(rides)*100:.1f}%)")
print(f"  Low elevation (<100 m): {low_elevation} ({low_elevation/len(rides)*100:.1f}%)")
print(f"  High elevation (>1500 m): {high_elevation} ({high_elevation/len(rides)*100:.1f}%)")

# Check data completeness
missing_distance = rides['distance_km'].isna().sum()
missing_elevation = rides['elevation_gain_m'].isna().sum()
print(f"\nData completeness:")
print(f"  Missing distance values: {missing_distance}")
print(f"  Missing elevation values: {missing_elevation}")
print(f"  Complete records: {len(rides) - max(missing_distance, missing_elevation)} ({(len(rides) - max(missing_distance, missing_elevation))/len(rides)*100:.1f}%)")

# ============================================
# ENHANCED VISUALIZATIONS
# ============================================
fig = plt.figure(figsize=(16, 10))

# 1. Rides per year
ax1 = plt.subplot(2, 3, 1)
rides.groupby('year').size().plot(kind='bar', ax=ax1, color='steelblue')
ax1.set_title('Rides per Year', fontsize=12, fontweight='bold')
ax1.set_xlabel('Year')
ax1.set_ylabel('Number of Rides')
ax1.grid(axis='y', alpha=0.3)

# 2. Rides per month (all years combined)
ax2 = plt.subplot(2, 3, 2)
month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
               'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
monthly = rides.groupby('month').size()
ax2.bar(range(1, 13), [monthly.get(i, 0) for i in range(1, 13)], color='coral')
ax2.set_xticks(range(1, 13))
ax2.set_xticklabels(month_names, rotation=45)
ax2.set_title('Rides per Month (All Years)', fontsize=12, fontweight='bold')
ax2.set_ylabel('Number of Rides')
ax2.grid(axis='y', alpha=0.3)

# 3. Rides by season
ax3 = plt.subplot(2, 3, 3)
season_order = ['Spring', 'Summer', 'Fall', 'Winter']
season_counts = rides.groupby('season').size().reindex(season_order)
colors = ['#90EE90', '#FFD700', '#FF8C00', '#87CEEB']
ax3.bar(season_order, season_counts, color=colors)
ax3.set_title('Rides by Season', fontsize=12, fontweight='bold')
ax3.set_ylabel('Number of Rides')
ax3.grid(axis='y', alpha=0.3)

# 4. Distance distribution
ax4 = plt.subplot(2, 3, 4)
ax4.hist(rides['distance_km'], bins=30, color='mediumseagreen', edgecolor='black', alpha=0.7)
ax4.axvline(rides['distance_km'].mean(), color='red', linestyle='--', 
            label=f'Mean: {rides["distance_km"].mean():.1f} km')
ax4.axvline(rides['distance_km'].median(), color='orange', linestyle='--', 
            label=f'Median: {rides["distance_km"].median():.1f} km')
ax4.set_title('Distance Distribution', fontsize=12, fontweight='bold')
ax4.set_xlabel('Distance (km)')
ax4.set_ylabel('Frequency')
ax4.legend()
ax4.grid(axis='y', alpha=0.3)

# 5. Elevation gain distribution
ax5 = plt.subplot(2, 3, 5)
ax5.hist(rides['elevation_gain_m'], bins=30, color='slateblue', edgecolor='black', alpha=0.7)
ax5.axvline(rides['elevation_gain_m'].mean(), color='red', linestyle='--', 
            label=f'Mean: {rides["elevation_gain_m"].mean():.0f} m')
ax5.axvline(rides['elevation_gain_m'].median(), color='orange', linestyle='--', 
            label=f'Median: {rides["elevation_gain_m"].median():.0f} m')
ax5.set_title('Elevation Gain Distribution', fontsize=12, fontweight='bold')
ax5.set_xlabel('Elevation Gain (m)')
ax5.set_ylabel('Frequency')
ax5.legend()
ax5.grid(axis='y', alpha=0.3)

# 6. Climbing intensity vs distance scatter
ax6 = plt.subplot(2, 3, 6)
scatter = ax6.scatter(rides['distance_km'], rides['elevation_gain_m'], 
                     c=rides['climb_intensity'], cmap='YlOrRd', 
                     alpha=0.6, s=20)
ax6.set_title('Distance vs Elevation Gain', fontsize=12, fontweight='bold')
ax6.set_xlabel('Distance (km)')
ax6.set_ylabel('Elevation Gain (m)')
cbar = plt.colorbar(scatter, ax=ax6)
cbar.set_label('Climb Intensity (m/km)', rotation=270, labelpad=15)
ax6.grid(alpha=0.3)

plt.tight_layout()
plt.savefig('preprocessing/comprehensive_eda_2.png', dpi=300, bbox_inches='tight')
print(f"\n✅ Visualization saved to preprocessing/comprehensive_eda.png")

# ============================================
# ADDITIONAL INSIGHTS FOR REPORT
# ============================================
print("\n" + "="*60)
print("KEY INSIGHTS FOR REPORT")
print("="*60)

# Weekend vs weekday
rides['is_weekend'] = rides['day_of_week'].isin([5, 6])
weekend_pct = rides['is_weekend'].sum() / len(rides) * 100
print(f"\nWeekend vs Weekday:")
print(f"  Weekend rides: {rides['is_weekend'].sum()} ({weekend_pct:.1f}%)")
print(f"  Weekday rides: {(~rides['is_weekend']).sum()} ({100-weekend_pct:.1f}%)")

# Peak usage period
peak_year = rides['year'].value_counts().idxmax()
peak_season = rides['season'].value_counts().idxmax()
print(f"\nPeak activity:")
print(f"  Most active year: {peak_year} ({rides[rides['year']==peak_year].shape[0]} rides)")
print(f"  Most active season: {peak_season} ({rides[rides['season']==peak_season].shape[0]} rides)")

# "Epic rides" (>40km with >1000m elevation)
epic_rides = rides[(rides['distance_km'] > 40) & (rides['elevation_gain_m'] > 1000)]
print(f"\n'Epic rides' (>40 km, >1000 m elevation): {len(epic_rides)} ({len(epic_rides)/len(rides)*100:.1f}%)")

# Data collection consistency
rides_per_year = rides.groupby('year').size()
print(f"\nData collection consistency:")
print(f"  Min rides/year: {rides_per_year.min()}")
print(f"  Max rides/year: {rides_per_year.max()}")
print(f"  Coefficient of variation: {rides_per_year.std()/rides_per_year.mean():.2f}")

print("\n" + "="*60)
print("✅ Analysis complete!")
print("="*60)