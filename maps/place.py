import geopandas as gpd
import numpy as np
from shapely.geometry import Point
from sklearn.cluster import DBSCAN
import pandas as pd
from pathlib import Path
import sys
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import Config

class SuitabilityAnalyzer:
    
    def __init__(self, network, rides, study_area, protected_zones=None):
        self.network = network
        self.rides = rides
        self.study_area = study_area
        self.protected_zones = protected_zones
        
        # Project to UTM for accurate distance calculations
        self.network_proj = network.to_crs("EPSG:32633")
        self.rides_proj = rides.to_crs("EPSG:32633")
        self.study_area_proj = study_area.to_crs("EPSG:32633")
        
        if protected_zones is not None:
            self.protected_zones_proj = protected_zones.to_crs("EPSG:32633")
        else:
            self.protected_zones_proj = None
    
    def identify_high_traffic_zones(self, min_traffic=5):
        """Find areas with high trail usage"""
        high_traffic = self.network_proj[
            self.network_proj['ride_count'] >= min_traffic
        ].copy()
        
        print(f"✓ Identified {len(high_traffic)} high-traffic segments (≥{min_traffic} rides)")
        return high_traffic
    
    def find_trail_centroids(self, high_traffic_segments):
        """
        Use DBSCAN to find clusters of high-traffic trails
        Returns cluster centroids as candidate locations
        """
        # Extract centroids of high-traffic segments
        centroids = high_traffic_segments.geometry.centroid
        coords = np.column_stack([centroids.x, centroids.y])
        
        # Cluster nearby segments (2km radius)
        db = DBSCAN(eps=2000, min_samples=3).fit(coords)
        
        high_traffic_segments['cluster'] = db.labels_
        
        # Calculate cluster centroids
        candidates = []
        for cluster_id in set(db.labels_):
            if cluster_id == -1:  # Skip noise
                continue
            
            cluster_segments = high_traffic_segments[
                high_traffic_segments['cluster'] == cluster_id
            ]
            
            # Weighted centroid by traffic
            weights = cluster_segments['ride_count'].values
            weighted_coords = np.average(
                np.column_stack([
                    cluster_segments.geometry.centroid.x,
                    cluster_segments.geometry.centroid.y
                ]),
                axis=0,
                weights=weights
            )
            
            candidates.append({
                'cluster_id': cluster_id,
                'geometry': Point(weighted_coords),
                'segments_count': len(cluster_segments),
                'total_traffic': cluster_segments['ride_count'].sum(),
                'avg_traffic': cluster_segments['ride_count'].mean()
            })
        
        candidates_gdf = gpd.GeoDataFrame(
            candidates, 
            crs="EPSG:32633"
        ).to_crs(self.network.crs)
        
        print(f"✓ Found {len(candidates_gdf)} candidate zones")
        return candidates_gdf
    
    def calculate_environmental_impact(self, candidates, buffer_m=500):
        """
        Calculate environmental impact score for each candidate
        Lower score = better (less impact on protected zones)
        """
        if self.protected_zones_proj is None:
            print("⚠️ No protected zones data - skipping environmental analysis")
            return pd.DataFrame({
                'candidate_id': candidates.index,
                'protected_overlap_m2': [0] * len(candidates),
                'distance_to_zone_a': [float('inf')] * len(candidates),
                'in_protected_zone': [False] * len(candidates)
            })
        
        candidates_proj = candidates.to_crs("EPSG:32633")
        
        env_scores = []
        for idx, candidate in candidates_proj.iterrows():
            # Create buffer around candidate site
            site_buffer = candidate.geometry.buffer(buffer_m)
            
            # Check overlap with protected zones
            overlap_area = 0
            min_distance = float('inf')
            in_protected = False
            
            for _, zone in self.protected_zones_proj.iterrows():
                # Check if candidate is inside protected zone
                if zone.geometry.contains(candidate.geometry):
                    in_protected = True
                
                # Calculate overlap
                if site_buffer.intersects(zone.geometry):
                    overlap = site_buffer.intersection(zone.geometry).area
                    overlap_area += overlap
                
                # Calculate distance to zone
                distance = candidate.geometry.distance(zone.geometry)
                min_distance = min(min_distance, distance)
            
            env_scores.append({
                'candidate_id': idx,
                'protected_overlap_m2': overlap_area,
                'distance_to_protected': min_distance,
                'in_protected_zone': in_protected
            })
        
        return pd.DataFrame(env_scores)
    
    def calculate_trail_accessibility(self, candidates, radius_m=5000):
        """
        For each candidate, calculate:
        - Number of trail segments within 5km
        - Total trail length within 5km
        - Average trail traffic within 5km
        """
        candidates_proj = candidates.to_crs("EPSG:32633")
        
        scores = []
        for idx, candidate in candidates_proj.iterrows():
            buffer = candidate.geometry.buffer(radius_m)
            
            # Find intersecting trail segments
            nearby_segments = self.network_proj[
                self.network_proj.geometry.intersects(buffer)
            ]
            
            # Calculate metrics
            total_length_km = nearby_segments['distance_km'].sum()
            num_segments = len(nearby_segments)
            avg_traffic = nearby_segments['ride_count'].mean() if num_segments > 0 else 0
            total_traffic = nearby_segments['ride_count'].sum()
            
            scores.append({
                'candidate_id': idx,
                'trail_segments_5km': num_segments,
                'trail_length_5km': total_length_km,
                'avg_segment_traffic': avg_traffic,
                'total_traffic_5km': total_traffic
            })
        
        scores_df = pd.DataFrame(scores)
        return candidates.join(scores_df.set_index('candidate_id'))
    
    def calculate_ride_accessibility(self, candidates, radius_m=5000):
        """
        Count how many ride start points are within 5km of each candidate
        (Indicates existing user base nearby)
        """
        candidates_proj = candidates.to_crs("EPSG:32633")
        rides_with_starts = self.rides_proj[
            self.rides_proj['start_point'].notna()
        ].copy()
        
        # Convert start points to geometries
        start_geoms = gpd.GeoSeries(
            [Point(p) for p in rides_with_starts['start_point']],
            crs="EPSG:32633"
        )
        
        ride_access = []
        for idx, candidate in candidates_proj.iterrows():
            buffer = candidate.geometry.buffer(radius_m)
            nearby_starts = start_geoms[start_geoms.within(buffer)]
            
            ride_access.append({
                'candidate_id': idx,
                'ride_starts_5km': len(nearby_starts)
            })
        
        return pd.DataFrame(ride_access)
    
    def calculate_suitability_scores(self, candidates_enriched):
        """
        Combine metrics into a weighted suitability score
        Higher = better location
        Environmental penalty applied for protected zone overlap
        """
        df = candidates_enriched.copy()
        
        # Normalize each metric to 0-100 scale
        def normalize(series):
            if series.max() == series.min():
                return pd.Series([50] * len(series))
            return ((series - series.min()) / (series.max() - series.min())) * 100
        
        # Positive factors (higher is better)
        df['score_trail_count'] = normalize(df['trail_segments_5km'])
        df['score_trail_length'] = normalize(df['trail_length_5km'])
        df['score_traffic'] = normalize(df['total_traffic_5km'])
        df['score_ride_starts'] = normalize(df['ride_starts_5km'])
        
        # Environmental factor (invert - higher distance is better)
        if 'distance_to_protected' in df.columns:
            df['score_environmental'] = normalize(df['distance_to_protected'])
        else:
            df['score_environmental'] = 50
        
        # Weighted average
        weights = {
            'score_trail_count': 0.20,
            'score_trail_length': 0.20,
            'score_traffic': 0.30,
            'score_ride_starts': 0.10,
            'score_environmental': 0.20  # Environmental consideration
        }
        
        df['suitability_score'] = (
            df['score_trail_count'] * weights['score_trail_count'] +
            df['score_trail_length'] * weights['score_trail_length'] +
            df['score_traffic'] * weights['score_traffic'] +
            df['score_ride_starts'] * weights['score_ride_starts'] +
            df['score_environmental'] * weights['score_environmental']
        )
        
        # Apply penalty for being inside protected zones
        if 'in_protected_zone' in df.columns:
            df.loc[df['in_protected_zone'], 'suitability_score'] *= 0.5
            df['penalty_applied'] = df['in_protected_zone']
        
        # Rank candidates
        df['rank'] = df['suitability_score'].rank(ascending=False, method='dense')
        
        return df.sort_values('suitability_score', ascending=False)
    
    def analyze(self):
        """Run full suitability analysis"""
        print("\n" + "="*60)
        print("TRAIL CENTER SUITABILITY ANALYSIS")
        print("="*60)
        
        # Step 1: Find high-traffic zones
        high_traffic = self.identify_high_traffic_zones(min_traffic=5)
        
        # Step 2: Identify candidate locations
        candidates = self.find_trail_centroids(high_traffic)
        
        if len(candidates) == 0:
            print("❌ No suitable candidate locations found")
            return None
        
        # Step 3: Calculate environmental impact
        print("\nAnalyzing environmental constraints...")
        env_scores = self.calculate_environmental_impact(candidates, buffer_m=500)
        candidates = candidates.join(
            env_scores.set_index('candidate_id')
        )
        
        # Step 4: Calculate trail accessibility
        print("Calculating trail accessibility...")
        candidates = self.calculate_trail_accessibility(candidates, radius_m=5000)
        
        # Step 5: Calculate ride start accessibility
        print("Calculating ride start proximity...")
        ride_access = self.calculate_ride_accessibility(candidates, radius_m=5000)
        candidates = candidates.join(
            ride_access.set_index('candidate_id')
        )
        
        # Step 6: Calculate final scores
        print("Computing suitability scores...")
        results = self.calculate_suitability_scores(candidates)
        
        return results
    
    def print_results(self, results):
        """Print analysis results in readable format"""
        print("\n" + "="*60)
        print("TOP CANDIDATE LOCATIONS")
        print("="*60)
        
        for idx, row in results.head(5).iterrows():
            print(f"\n🏆 RANK {int(row['rank'])}: Candidate {idx}")
            print(f"   Location: {row.geometry.y:.6f}°N, {row.geometry.x:.6f}°E")
            print(f"   Suitability Score: {row['suitability_score']:.1f}/100")
            
            if row.get('in_protected_zone', False):
                print(f"   ⚠️  WARNING: Inside protected zone (penalty applied)")
            
            print(f"\n   Trail Access (5km radius):")
            print(f"     • {int(row['trail_segments_5km'])} trail segments")
            print(f"     • {row['trail_length_5km']:.1f} km total trails")
            print(f"     • {row['total_traffic_5km']:.0f} total rides recorded")
            print(f"     • {int(row['ride_starts_5km'])} ride start points nearby")
            
            if 'distance_to_protected' in row and row['distance_to_protected'] != float('inf'):
                print(f"\n   Environmental:")
                print(f"     • {row['distance_to_protected']:.0f}m from protected zones")
                print(f"     • {row['protected_overlap_m2']:.0f}m² overlap with buffer")
        
        print("\n" + "="*60)
    
    def save_results(self, results, output_path):
        """Save candidate locations to file"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Keep essential columns
        save_cols = [
            'rank', 'suitability_score', 'geometry',
            'trail_segments_5km', 'trail_length_5km',
            'total_traffic_5km', 'ride_starts_5km'
        ]
        
        # Add environmental columns if they exist
        if 'distance_to_protected' in results.columns:
            save_cols.extend(['distance_to_protected', 'in_protected_zone', 'protected_overlap_m2'])
        
        results[save_cols].to_file(output_path, driver='GPKG')
        print(f"\n💾 Results saved to: {output_path}")
    
    def visualize_results(self, results, output_path=None):
        """Create visualization of candidate locations"""
        fig, ax = plt.subplots(figsize=(15, 12))
        
        # Plot study area
        self.study_area.plot(ax=ax, facecolor='none', edgecolor='red', 
                            linewidth=2, label='Study Area')
        
        # Plot protected zones if available
        if self.protected_zones is not None:
            self.protected_zones.plot(ax=ax, facecolor='lightcoral', 
                                     edgecolor='darkred', alpha=0.3,
                                     linewidth=1, label='Protected Zones')
        
        # Plot trail network (light gray)
        self.network.plot(ax=ax, color='lightgray', linewidth=0.5, alpha=0.5)
        
        # Plot high-traffic trails
        high_traffic = self.network[self.network['ride_count'] >= 5]
        high_traffic.plot(ax=ax, column='ride_count', cmap='YlOrRd',
                         linewidth=1.5, legend=True, alpha=0.7,
                         legend_kwds={'label': 'Trail Traffic'})
        
        # Plot candidate locations
        results_proj = results.to_crs(self.study_area.crs)
        results_proj.plot(ax=ax, column='rank', cmap='RdYlGn_r',
                         markersize=200, alpha=0.8, edgecolor='black',
                         linewidth=2, legend=True,
                         legend_kwds={'label': 'Candidate Rank'})
        
        # Add labels
        for idx, row in results_proj.iterrows():
            ax.annotate(f"#{int(row['rank'])}", 
                       xy=(row.geometry.x, row.geometry.y),
                       xytext=(5, 5), textcoords='offset points',
                       fontsize=12, fontweight='bold',
                       bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
        
        ax.set_title('MTB Trail Center Suitability Analysis', fontsize=16, fontweight='bold')
        ax.legend(loc='upper right')
        plt.tight_layout()
        
        if output_path:
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            print(f"📊 Visualization saved to: {output_path}")
        
        plt.show()


def main():
    """Run analysis"""
    Config.ensure_directories()
    
    # Load data
    print("📂 Loading data...")
    study_area = gpd.read_file(Config.STUDY_AREA)
    rides = gpd.read_file(Config.STRAVA_RIDES)
    network = gpd.read_file(Config.TRAIL_NETWORK)
    
    # Load protected zones if available
    zones_path = Path('data/sumava_zones_2.geojson')
    protected_zones = None
    
    if zones_path.exists():
        print("🌲 Loading protected zones...")
        zones = gpd.read_file(zones_path)
        
        # Filter for zones A and B (most protected)
        if 'ZONA' in zones.columns:
            protected_zones = zones[zones['ZONA'].isin(['A', 'B'])].copy()
            print(f"   ✓ Found {len(protected_zones)} protected zones (A & B)")
        else:
            print("   ⚠️ Warning: 'ZONA' column not found in zones file")
            print(f"   Available columns: {zones.columns.tolist()}")
            protected_zones = zones  # Use all zones
    else:
        print(f"   ⚠️ Protected zones file not found: {zones_path}")
        print("   Running analysis WITHOUT environmental constraints")
    
    # Run analysis
    analyzer = SuitabilityAnalyzer(network, rides, study_area, protected_zones)
    results = analyzer.analyze()
    
    if results is not None:
        analyzer.print_results(results)
        
        # Save results
        output_path = Config.OUTPUT_DIR / 'candidate_locations.gpkg'
        analyzer.save_results(results, output_path)
        
        # Create visualization
        viz_path = Config.OUTPUT_DIR / 'suitability_analysis.png'
        analyzer.visualize_results(results, viz_path)
        
        return results
    
    return None


if __name__ == "__main__":
    results = main()