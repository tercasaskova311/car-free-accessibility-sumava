#Spatial autocorrelation analysis for trail network hotspots + location suitability
import geopandas as gpd
import numpy as np
from shapely.geometry import Point
from shapely.ops import unary_union
from libpysal.weights import DistanceBand
from esda.moran import Moran, Moran_Local
import pandas as pd
from pathlib import Path
from sklearn.cluster import DBSCAN

class SpatialAutocorrelation: 
    
    @staticmethod
    def calculate_global_morans_i(network_proj, attribute='ride_count', distance_threshold=2000):
        #spatial autocorrelation in trail usage = test whether high-traffic trails cluster together

        #projected trail network => number of rides per segment
        centroids = network_proj.geometry.centroid 

        #array of x and y coords =>calculate distances between them
        coords = np.column_stack([centroids.x, centroids.y])

        w = DistanceBand.from_array(coords, threshold=distance_threshold, binary=True)
        
        # compare segments with different numbers of neighbors
        w.transform = 'r'  
        y = network_proj[attribute].values
        moran = Moran(y, w)

        result = {
            'morans_i':      moran.I,
            'expected_i':    moran.EI,
            'p_value':       moran.p_sim,
            'z_score':       moran.z_sim,
            'significant':   moran.p_sim < 0.05,
            'interpretation': SpatialAutocorrelation._interpret_global_moran(moran)
        }

        print("global moran's I")
        print(f"  Moran's I:      {result['morans_i']:.4f}")
        print(f"  Expected I:     {result['expected_i']:.4f}")
        print(f"  Z-score:        {result['z_score']:.4f}")
        print(f"  P-value:        {result['p_value']:.4f}")
        print(f"  Interpretation: {result['interpretation']}")

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

        #project trails to crs (m)
        centroids = network_proj.geometry.centroid
        #stack xy within array
        coords = np.column_stack([centroids.x, centroids.y])

        #create weight matrix: neighbors within threshold distance
        #this is crucial for trails with varying number of neighbors
        #the goal is to compare segments with different numbers of neighbors
        w = DistanceBand.from_array(coords, threshold=distance_threshold, binary=True)
        w.transform = 'r'

        y = network_proj[attribute].values
        lisa = Moran_Local(y, w)

        network_with_lisa = network_proj.copy()
        network_with_lisa['local_i']     = lisa.Is
        network_with_lisa['p_value']     = lisa.p_sim
        network_with_lisa['z_score']     = lisa.z_sim
        network_with_lisa['significant'] = lisa.p_sim < 0.05

        network_with_lisa['cluster_type'] = SpatialAutocorrelation._classify_lisa_quadrants(
            lisa, network_proj[attribute].values
        )

        hotspots = network_with_lisa[
            (network_with_lisa['cluster_type'] == 'High-High') &
            (network_with_lisa['significant'] == True)
        ]

        print("local moran's I")
        print(f"  Total segments analysed:        {len(network_with_lisa)}")
        print(f"  Significant hotspots (HH):      {len(hotspots)}")
        print(f"  Mean Local I (hotspots):         {hotspots['local_i'].mean():.4f}")

        return network_with_lisa

    @staticmethod
    def _classify_lisa_quadrants(lisa, y):
        classifications = []
        y_mean = y.mean()

        for i in range(len(lisa.Is)):
            if lisa.p_sim[i] >= 0.05:
                classifications.append('Not Significant')
                continue

            if   y[i] > y_mean and lisa.q[i] == 1:
                classifications.append('High-High')
            elif y[i] < y_mean and lisa.q[i] == 3:
                classifications.append('Low-Low')
            elif y[i] > y_mean and lisa.q[i] == 2:
                classifications.append('High-Low')
            elif y[i] < y_mean and lisa.q[i] == 4:
                classifications.append('Low-High')
            else:
                classifications.append('Not Significant')

        return classifications


class LocationAnalyzer:

    @staticmethod
    def find_candidate_locations(network_proj, min_traffic=5):

        hotspots = network_proj[
            (network_proj['cluster_type'] == 'High-High') &
            (network_proj['significant'] == True) &
            (network_proj['ride_count'] >= min_traffic)
        ].copy()

        if len(hotspots) == 0:
            print("No significant hotspots found")
            return None

        centroids = hotspots.geometry.centroid
        coords = np.column_stack([centroids.x, centroids.y])

        #group segments together (within 2km)
        db = DBSCAN(eps=2000, min_samples=2).fit(coords)
        hotspots['spatial_group'] = db.labels_

        candidates = []
        for group_id in set(db.labels_):
            if group_id == -1: #ignore noise
                continue

            group_segs = hotspots[hotspots['spatial_group'] == group_id]

            weights = group_segs['local_i'].values

            #avg = central point (cluster)
            center = np.average(
                np.column_stack([group_segs.geometry.centroid.x,
                                 group_segs.geometry.centroid.y]),
                axis=0, weights=weights
            )

            candidates.append({
                'geometry':              Point(center),
                'hotspot_segments':      len(group_segs),
                'total_rides':           int(group_segs['ride_count'].sum()),
                'mean_local_morans_i':   float(group_segs['local_i'].mean()),
                'clustering_strength':   float(group_segs['local_i'].sum()),
            })

        print(f"identified {len(candidates)} candidate zones from {len(hotspots)} hotspot segments")
        return gpd.GeoDataFrame(candidates, crs="EPSG:32633", geometry='geometry')

    @staticmethod
    def calculate_trail_access(candidates, network_proj, radius_m=5000):
        #Count trails within radius of each candidate.
            
        candidates['trail_count']           = pd.array([0] * len(candidates), dtype='int64')
        candidates['trail_length_km']       = pd.array([0.0] * len(candidates), dtype='float64')
        candidates['unique_trail_length_km'] = pd.array([0.0] * len(candidates), dtype='float64')
        candidates['total_rides']           = pd.array([0] * len(candidates), dtype='int64')

        for idx, candidate in candidates.iterrows():
            buffer = candidate.geometry.buffer(radius_m)
            nearby = network_proj[network_proj.geometry.intersects(buffer)].copy()

            # Standard metrics (with potential overlap)
            candidates.at[idx, 'trail_count']     = int(len(nearby))
            candidates.at[idx, 'trail_length_km'] = float(nearby['distance_km'].sum())
            candidates.at[idx, 'total_rides']     = int(nearby['ride_count'].sum())
            
            # UNIQUE trail length (merge overlapping segments)
            #trail is made of multiple segments that can overlap within the buffer
            #originally we have rides => segments 
            #in order to actually count accessibility - we need to merge overlapping segments - so we get unique length

            if len(nearby) > 0:
                try:
                    merged_geom = unary_union(nearby.geometry.tolist())
                    
                    if hasattr(merged_geom, 'length'):
                        unique_length_m = merged_geom.length #single linestring
                    elif hasattr(merged_geom, 'geoms'):
                        unique_length_m = sum(geom.length for geom in merged_geom.geoms) # MultiLineString - sum all parts
                    else:
                        unique_length_m = nearby['distance_km'].sum() * 1000 #fallback
                    
                    candidates.at[idx, 'unique_trail_length_km'] = float(unique_length_m / 1000)
                    
                    # Report overlap factor for diagnostics 
                    overlap_factor = nearby['distance_km'].sum() / (unique_length_m / 1000)
                    if overlap_factor > 1.5:
                        print(f"    Candidate {idx}: overlap factor = {overlap_factor:.2f}x "
                              f"({nearby['distance_km'].sum():.1f} km → {unique_length_m/1000:.1f} km unique)")
                
                except Exception as e:
                    print(f"Could not calculate unique length for candidate {idx}: {e}")
                    candidates.at[idx, 'unique_trail_length_km'] = float(nearby['distance_km'].sum())
            else:
                candidates.at[idx, 'unique_trail_length_km'] = 0.0

        # Summary statistics
        print(f"Trail accessibility calculated:")
        print(f"Unique trail length (merged):{candidates['unique_trail_length_km'].sum():.1f} km")
        avg_overlap = candidates['trail_length_km'].sum() / candidates['unique_trail_length_km'].sum() if candidates['unique_trail_length_km'].sum() > 0 else 1.0
        print(f"Average overlap factor:{avg_overlap:.2f}x")
        
        return candidates

    @staticmethod
    def check_environmental_constraints(candidates, zones_proj):
        if zones_proj is None:
            candidates['in_prohibited_zone'] = False
            candidates['zone_type'] = 'Unknown'
            return candidates

        #spatial join - check if candidates fall within protected zones
        joined = gpd.sjoin(candidates, zones_proj[['ZONA', 'geometry']],
                           how='left', predicate='within')

        candidates['zone_type']         = joined['ZONA'].fillna('None')
        candidates['in_prohibited_zone'] = (candidates['zone_type'] == 'A')

        return candidates

    @staticmethod
    def calculate_composite_scores(candidates):
        #score: accesibility + usage + clustering - penalties for protected zones

        #copy - because we want to keep original 
        df = candidates.copy()

        #normalize metrics to 0-100 - this approach is better than min-max scaling
        df['accessibility_score'] = df['unique_trail_length_km'].rank(ascending=True, method='dense') / len(df) * 100
        df['usage_score']         = df['total_rides'].rank(ascending=True, method='dense') / len(df) * 100
        df['clustering_score']    = df['mean_local_morans_i'].rank(ascending=True, method='dense') / len(df) * 100

        df['suitability_score'] = (
            df['accessibility_score'] * 0.30 +
            df['usage_score']         * 0.30 +
            df['clustering_score']    * 0.40
        )

        # Zone A penalty
        df.loc[df['in_prohibited_zone'], 'suitability_score'] = 0.0

        df['rank'] = df['suitability_score'].rank(ascending=False, method='dense').astype(int)

        return df.sort_values('suitability_score', ascending=False)

    @staticmethod
    def analyze(network, rides, study_area, protected_zones=None):
        #moran's I + candidate locations + scoring

        #trails + zones to crs(m)
        network_proj = network.to_crs("EPSG:32633")
        zones_proj   = protected_zones.to_crs("EPSG:32633") if protected_zones is not None else None

        global_moran = SpatialAutocorrelation.calculate_global_morans_i(
            network_proj, attribute='ride_count', distance_threshold=2000
        )

        network_with_lisa = SpatialAutocorrelation.calculate_local_morans_i(
            network_proj, attribute='ride_count', distance_threshold=2000
        )
    
        candidates = LocationAnalyzer.find_candidate_locations(network_with_lisa, min_traffic=5)
        if candidates is None:
            print("No suitable candidates found")
            return None

        candidates = LocationAnalyzer.calculate_trail_access(candidates, network_proj, radius_m=5000)
    
        candidates = LocationAnalyzer.check_environmental_constraints(candidates, zones_proj)
        
        results = LocationAnalyzer.calculate_composite_scores(candidates)

        #attrs - we keep all info together
        results.attrs['global_morans_i'] = global_moran

        return results.to_crs(network.crs)

    @staticmethod
    def save_results(results, output_path):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        export_cols = [
            'rank', 'suitability_score', 'geometry',
            'trail_count', 'trail_length_km', 'unique_trail_length_km',  # Added unique
            'total_rides',
            'mean_local_morans_i', 'clustering_strength',
            'in_prohibited_zone', 'zone_type',
            'hotspot_segments'
        ]

        results[export_cols].to_file(output_path, driver='GPKG')
        print(f"Results saved to {output_path}")

        print("candidates")
        for _, row in results.head(5).iterrows():
            print(f" {int(row['rank'])}. Location "
                  f"({row.geometry.y:.4f}°N, {row.geometry.x:.4f}°E)")
            print(f"Suitability Score:{row['suitability_score']:.1f}/100")
            print(f"Clustering Strength (I):{row['mean_local_morans_i']:.3f}")
            print(f"Trail Access:  {int(row['trail_count'])} segments")
            print(f"Trail Length (raw): {row['trail_length_km']:.1f} km")
            print(f"Trail Length (unique): {row['unique_trail_length_km']:.1f} km")
            overlap = row['trail_length_km'] / row['unique_trail_length_km'] if row['unique_trail_length_km'] > 0 else 1
            print(f"Overlap factor: {overlap:.2f}x")
            print(f"Zone: {row['zone_type']}  "
                  f"{'PROHIBITED' if row['in_prohibited_zone'] else 'PERMITTED'}")