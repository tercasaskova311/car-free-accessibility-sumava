import geopandas as gpd
import numpy as np
from shapely.geometry import Point
from libpysal.weights import DistanceBand
from esda.moran import Moran, Moran_Local
import pandas as pd
from pathlib import Path

class SpatialAutocorrelation: 
#Uses Moran's I to identify statistically significant clustering => Spatial autocorrelation analysis for trail network hotspots.
    
    @staticmethod
    def calculate_global_morans_i(network_proj, attribute='ride_count', distance_threshold=2000):

        #Test for global spatial autocorrelation in trail usage.
    
        centroids = network_proj.geometry.centroid #Create spatial weights matrix based on distance
        coords = np.column_stack([centroids.x, centroids.y])
        
        w = DistanceBand.from_array(coords, threshold=distance_threshold, binary=True) #Distance-based weights

        w.transform = 'r'  # Row-standardized
        
        y = network_proj[attribute].values # Calculate Global Moran's I

        moran = Moran(y, w)
        
        result = {
            'morans_i': moran.I,
            'expected_i': moran.EI,
            'p_value': moran.p_sim,
            'z_score': moran.z_sim,
            'significant': moran.p_sim < 0.05,
            'interpretation': SpatialAutocorrelation._interpret_global_moran(moran)
        }
        
        print(f"global moran's I")
        print(f"Moran's I: {result['morans_i']:.4f}")
        print(f"Expected I: {result['expected_i']:.4f}")
        print(f"Z-score: {result['z_score']:.4f}")
        print(f"P-value: {result['p_value']:.4f}")
        print(f"Interpretation: {result['interpretation']}")
        
        return result
    
    @staticmethod
    def _interpret_global_moran(moran):
        if moran.p_sim >= 0.05:
            return "No significant spatial clustering detected (random distribution)"
        elif moran.I > moran.EI:
            return "Significant positive autocorrelation (high-traffic trails cluster together)"
        else:
            return "Significant negative autocorrelation (high/low trails are dispersed)"
    
    @staticmethod
    def calculate_local_morans_i(network_proj, attribute='ride_count', distance_threshold=2000):
        #local hotspots/coldspots using Local Moran's I (LISA).
    
        centroids = network_proj.geometry.centroid
        coords = np.column_stack([centroids.x, centroids.y])
        
        # Create spatial weights
        w = DistanceBand.from_array(coords, threshold=distance_threshold, binary=True)
        w.transform = 'r'
        
        # Calculate Local Moran's I
        y = network_proj[attribute].values
        lisa = Moran_Local(y, w)
        
        # Add results to network
        network_with_lisa = network_proj.copy()
        network_with_lisa['local_i'] = lisa.Is
        network_with_lisa['p_value'] = lisa.p_sim
        network_with_lisa['z_score'] = lisa.z_sim
        network_with_lisa['significant'] = lisa.p_sim < 0.05
        
        # Classify into quadrants
        network_with_lisa['cluster_type'] = SpatialAutocorrelation._classify_lisa_quadrants(
            lisa, network_proj[attribute].values
        )
        
        # Summary statistics
        hotspots = network_with_lisa[
            (network_with_lisa['cluster_type'] == 'High-High') & 
            (network_with_lisa['significant'] == True)
        ]
        
        print(f"local moran's I")
        print(f"Total segments analyzed: {len(network_with_lisa)}")
        print(f"Significant hotspots (High-High): {len(hotspots)}")
        print(f"Mean Local I (hotspots): {hotspots['local_i'].mean():.4f}")
        
        return network_with_lisa
    
    @staticmethod
    def _classify_lisa_quadrants(lisa, y):

        classifications = []
        y_mean = y.mean()
        
        for i, (local_i, is_sig) in enumerate(zip(lisa.Is, lisa.p_sim)):
            if not is_sig or lisa.p_sim[i] >= 0.05:
                classifications.append('Not Significant')
                continue
            
            if y[i] > y_mean and lisa.q[i] == 1:  # HH
                classifications.append('High-High')
            elif y[i] < y_mean and lisa.q[i] == 3:  # LL
                classifications.append('Low-Low')
            elif y[i] > y_mean and lisa.q[i] == 2:  # LH
                classifications.append('High-Low')
            elif y[i] < y_mean and lisa.q[i] == 4:  # HL
                classifications.append('Low-High')
            else:
                classifications.append('Not Significant')
        
        return classifications


class LocationAnalyzer:
    #location suitability analysis using spatial statistics.
    
    @staticmethod
    def find_candidate_locations(network_proj, min_traffic=5):
        #candidate locations from High-High hotspot clusters.

        #statistically significant hotspots
        hotspots = network_proj[
            (network_proj['cluster_type'] == 'High-High') & 
            (network_proj['significant'] == True) &
            (network_proj['ride_count'] >= min_traffic)
        ].copy()
        
        if len(hotspots) == 0:
            print("️no significant hotspots found")
            return None
        
        # Group hotspots
        from sklearn.cluster import DBSCAN
        centroids = hotspots.geometry.centroid
        coords = np.column_stack([centroids.x, centroids.y])
        
        # Use DBSCAN to group hotspots into zones
        db = DBSCAN(eps=2000, min_samples=2).fit(coords)
        hotspots['spatial_group'] = db.labels_
        
        #candidate from each group
        candidates = []
        for group_id in set(db.labels_):
            if group_id == -1:  # Skip noise points
                continue
            
            group_segs = hotspots[hotspots['spatial_group'] == group_id]
            
            # Weighted centroid by Local Moran's I strength
            weights = group_segs['local_i'].values
            center = np.average(
                np.column_stack([group_segs.geometry.centroid.x, 
                               group_segs.geometry.centroid.y]),
                axis=0, weights=weights
            )
            
            candidates.append({
                'geometry': Point(center),
                'hotspot_segments': len(group_segs),
                'total_rides': group_segs['ride_count'].sum(),
                'mean_local_morans_i': group_segs['local_i'].mean(),
                'clustering_strength': group_segs['local_i'].sum()  # Higher = stronger cluster
            })
        
        print(f"identified {len(candidates)} candidate zones from {len(hotspots)} hotspot segments")
        
        return gpd.GeoDataFrame(candidates, crs="EPSG:32633", geometry='geometry')
    
    @staticmethod
    def calculate_trail_access(candidates, network_proj, radius_m=5000):
        #trail accessibility metrics within buffer radius - radius 5km based by international standards for trail building
        for col in ['trail_count', 'trail_length_km', 'total_rides']:
            candidates[col] = 0
        
        for idx, candidate in candidates.iterrows():
            buffer = candidate.geometry.buffer(radius_m)
            nearby = network_proj[network_proj.geometry.intersects(buffer)]
            
            candidates.at[idx, 'trail_count'] = len(nearby)
            candidates.at[idx, 'trail_length_km'] = nearby['distance_km'].sum()
            candidates.at[idx, 'total_rides'] = nearby['ride_count'].sum()
        
        return candidates
    
    @staticmethod
    def check_environmental_constraints(candidates, zones_proj):
        #check if candidates fall in protected = prohibited zones 
        if zones_proj is None:
            candidates['in_prohibited_zone'] = False
            candidates['zone_type'] = 'Unknown'
            return candidates
        
        joined = gpd.sjoin(candidates, zones_proj[['ZONA', 'geometry']], 
                          how='left', predicate='within')
        
        candidates['zone_type'] = joined['ZONA'].fillna('None')
        candidates['in_prohibited_zone'] = (candidates['zone_type'] == 'A')
        
        return candidates
    
    @staticmethod
    def calculate_composite_scores(candidates):
        #final score for choosing the trail center location: 
        #Trail accessibility (30%), Usage intensity (30%), Clustering strength (Local Moran's I) (40%), Environmental compliance (Zone A = disqualified)
    
        df = candidates.copy()
        
        # Normalize metrics to 0-100
        def normalize(series):
            if series.max() == series.min():
                return pd.Series([50] * len(series))
            return ((series - series.min()) / (series.max() - series.min())) * 100
        
        # Composite score with spatial statistics weight
        df['accessibility_score'] = normalize(df['trail_count'])
        df['usage_score'] = normalize(df['total_rides'])
        df['clustering_score'] = normalize(df['mean_local_morans_i'])
        
        df['suitability_score'] = (
            df['accessibility_score'] * 0.30 +
            df['usage_score'] * 0.30 +
            df['clustering_score'] * 0.40
        )
        
        # Zone A penalty (complete disqualification)
        df.loc[df['in_prohibited_zone'], 'suitability_score'] = 0
        
        # Rank by score
        df['rank'] = df['suitability_score'].rank(ascending=False, method='dense').astype(int)
        
        return df.sort_values('suitability_score', ascending=False)
    
    @staticmethod
    def analyze(network, rides, study_area, protected_zones=None):
        """
        Complete spatial analysis workflow with Moran's I.
        
        Pipeline:
        1. Calculate Global Moran's I (test for overall clustering)
        2. Calculate Local Moran's I (identify specific hotspots)
        3. Extract candidate locations from High-High clusters
        4. Calculate accessibility metrics
        5. Check environmental constraints
        6. Compute composite suitability scores
        """
        # Project to metric CRS
        network_proj = network.to_crs("EPSG:32633")
        zones_proj = protected_zones.to_crs("EPSG:32633") if protected_zones is not None else None
        
        # STEP 1: Global spatial autocorrelation
        global_moran = SpatialAutocorrelation.calculate_global_morans_i(
            network_proj, 
            attribute='ride_count',
            distance_threshold=2000
        )
        
        # STEP 2: Local hotspot identification
        network_with_lisa = SpatialAutocorrelation.calculate_local_morans_i(
            network_proj,
            attribute='ride_count',
            distance_threshold=2000
        )
        
        # STEP 3: Find candidate locations from hotspots
        candidates = LocationAnalyzer.find_candidate_locations(
            network_with_lisa, 
            min_traffic=5
        )
        
        if candidates is None:
            print("no suitable candidates found")
            return None
        
        # STEP 4: Calculate trail accessibility
        candidates = LocationAnalyzer.calculate_trail_access(
            candidates, 
            network_proj, 
            radius_m=5000
        )
        
        # STEP 5: Environmental constraints
        candidates = LocationAnalyzer.check_environmental_constraints(
            candidates, 
            zones_proj
        )
        
        # STEP 6: Composite scoring
        results = LocationAnalyzer.calculate_composite_scores(candidates)
        
        # Store global statistics for reporting
        results.attrs['global_morans_i'] = global_moran
        
        # Convert back to original CRS
        return results.to_crs(network.crs)
    
    @staticmethod
    def save_results(results, output_path):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Select columns for export
        export_cols = [
            'rank', 'suitability_score', 'geometry',
            'trail_count', 'trail_length_km', 'total_rides',
            'mean_local_morans_i', 'clustering_strength',
            'in_prohibited_zone', 'zone_type',
            'hotspot_segments'
        ]
        
        results[export_cols].to_file(output_path, driver='GPKG')
        print(f"✓ Results saved to {output_path}")
        
        # Print summary
        print(f"candidates")
        for idx, row in results.head(5).iterrows():
            print(f"\n{row['rank']}. Location ({row.geometry.y:.4f}°N, {row.geometry.x:.4f}°E)")
            print(f"   Suitability Score: {row['suitability_score']:.1f}/100")
            print(f"   Clustering Strength (Local I): {row['mean_local_morans_i']:.3f}")
            print(f"   Trail Access: {int(row['trail_count'])} segments, {row['trail_length_km']:.1f}km")
            print(f"   Zone: {row['zone_type']} {'ROHIBITED' if row['in_prohibited_zone'] else '✓'}")