import geopandas as gpd
from shapely.geometry import LineString
from pathlib import Path
import pandas as pd
from tqdm import tqdm
import time
import numpy as np

class NetworkBuilder:    
    @staticmethod
    def create_network_ultra_simple(rides, simplify_tolerance=20, min_length=200):
        """
        ULTRA-SIMPLE APPROACH: Use rides themselves as network segments!
        
        For small datasets (like 548 rides), this is often the best approach:
        1. Simplify each ride
        2. Filter short rides
        3. Done! Each ride becomes a segment.
        
        Pros:
        - Super fast (< 5 seconds)
        - No complex geometry operations
        - Each ride counted exactly once (no double-counting!)
        
        Cons:
        - More segments than a "true" network
        - Some redundancy where rides overlap
        
        For 548 rides, this gives you ~300-500 usable segments.
        """
        print("🚀 ULTRA-SIMPLE Network Creation")
        print("="*70)
        print("Strategy: Use rides as network segments directly")
        start_total = time.time()
        
        # Project to metric CRS
        rides_proj = rides.to_crs('EPSG:32633')
        print(f"Input: {len(rides_proj)} rides")
        
        # STEP 1: Simplify
        print(f"\n1. Simplifying geometries (tolerance: {simplify_tolerance}m)...")
        simplified = rides_proj.copy()
        simplified['geometry'] = simplified.geometry.simplify(simplify_tolerance, preserve_topology=True)
        simplified['length_m'] = simplified.geometry.length
        print(f"   ✓ Simplified")
        
        # STEP 2: Filter short rides
        print(f"\n2. Filtering short segments (min: {min_length}m)...")
        before = len(simplified)
        network_proj = simplified[simplified['length_m'] >= min_length].copy()
        print(f"   ✓ Kept {len(network_proj)} segments (removed {before - len(network_proj)} short rides)")
        
        # STEP 3: Clean up columns
        network_proj['segment_id'] = range(len(network_proj))
        network_proj['distance_km'] = network_proj['length_m'] / 1000
        network_proj['ride_count'] = 1  # Each segment IS a ride
        
        # Keep activity_id for reference
        if 'activity_id' not in network_proj.columns:
            network_proj['activity_id'] = network_proj['segment_id']
        
        # Create rides list (just this ride)
        network_proj['rides'] = [[{
            'activity_id': int(row.get('activity_id', idx)),
            'distance_km': float(row.get('distance_km', 0))
        }] for idx, row in network_proj.iterrows()]
        
        total_time = time.time() - start_total
        print(f"\n{'='*70}")
        print(f"✅ NETWORK CREATED IN {total_time:.1f}s")
        print(f"{'='*70}")
        print(f"   Segments:        {len(network_proj):,}")
        print(f"   Total length:    {network_proj['distance_km'].sum():.1f} km")
        print(f"   Avg segment:     {network_proj['length_m'].mean():.0f} m")
        print(f"   Median segment:  {network_proj['length_m'].median():.0f} m")
        print(f"   Ride counting:   1.0x (perfect - no double-counting!)")
        print(f"{'='*70}\n")
        
        return network_proj.to_crs(rides.crs)
    
    @staticmethod
    def create_network_clustered(rides, simplify_tolerance=20, min_length=200, cluster_distance=100):
        """
        MIDDLE GROUND: Cluster nearby rides into segments
        
        Better than ultra-simple (reduces redundancy) but still fast.
        """
        print("🚀 CLUSTERED Network Creation")
        print("="*70)
        start_total = time.time()
        
        rides_proj = rides.to_crs('EPSG:32633')
        print(f"Input: {len(rides_proj)} rides")
        
        # STEP 1: Simplify
        print(f"\n1. Simplifying...")
        simplified = rides_proj.copy()
        simplified['geometry'] = simplified.geometry.simplify(simplify_tolerance, preserve_topology=True)
        simplified['length_m'] = simplified.geometry.length
        
        # Filter short
        simplified = simplified[simplified['length_m'] >= min_length].copy()
        print(f"   ✓ {len(simplified)} rides after simplification")
        
        # STEP 2: Cluster by spatial proximity
        print(f"\n2. Clustering nearby rides (distance: {cluster_distance}m)...")
        from sklearn.cluster import DBSCAN
        
        # Use centroids for clustering
        centroids = simplified.geometry.centroid
        coords = np.column_stack([centroids.x, centroids.y])
        
        db = DBSCAN(eps=cluster_distance, min_samples=1).fit(coords)
        simplified['cluster'] = db.labels_
        
        n_clusters = len(set(db.labels_))
        print(f"   ✓ Found {n_clusters} clusters")
        
        # STEP 3: For each cluster, pick the longest ride as representative
        print(f"\n3. Selecting representative from each cluster...")
        network_list = []
        
        for cluster_id in tqdm(range(n_clusters), desc="Processing clusters"):
            cluster_rides = simplified[simplified['cluster'] == cluster_id]
            
            # Pick longest ride in cluster
            representative = cluster_rides.nlargest(1, 'length_m').iloc[0]
            
            # Count how many rides in this cluster
            ride_count = len(cluster_rides)
            
            network_list.append({
                'segment_id': cluster_id,
                'geometry': representative.geometry,
                'length_m': representative['length_m'],
                'distance_km': representative['length_m'] / 1000,
                'ride_count': ride_count,
                'rides': [
                    {'activity_id': int(r.get('activity_id', idx)), 
                     'distance_km': float(r.get('distance_km', 0))}
                    for idx, r in cluster_rides.iterrows()
                ]
            })
        
        network_proj = gpd.GeoDataFrame(network_list, crs='EPSG:32633')
        
        total_time = time.time() - start_total
        print(f"\n{'='*70}")
        print(f"✅ NETWORK CREATED IN {total_time:.1f}s")
        print(f"{'='*70}")
        print(f"   Segments:        {len(network_proj):,}")
        print(f"   Total length:    {network_proj['distance_km'].sum():.1f} km")
        print(f"   Avg segment:     {network_proj['length_m'].mean():.0f} m")
        print(f"   Avg rides/seg:   {network_proj['ride_count'].mean():.1f}")
        print(f"   Max rides/seg:   {network_proj['ride_count'].max()}")
        print(f"   Compression:     {len(rides)}/{len(network_proj)} = {len(rides)/len(network_proj):.1f}x")
        print(f"{'='*70}\n")
        
        return network_proj.to_crs(rides.crs)
    
    @staticmethod
    def create_network_sequential(rides, tolerance=15, snap_tolerance=25):
        """
        Automatically choose best method based on dataset size
        """
        n_rides = len(rides)
        
        print(f"\n📊 Auto-selecting network creation method...")
        print(f"   Dataset size: {n_rides} rides")
        
        if n_rides < 100:
            print(f"   → Using ULTRA-SIMPLE (rides as segments)")
            return NetworkBuilder.create_network_ultra_simple(rides, simplify_tolerance=tolerance)
        
        elif n_rides < 1000:
            print(f"   → Using CLUSTERED approach")
            return NetworkBuilder.create_network_clustered(
                rides, 
                simplify_tolerance=tolerance,
                cluster_distance=snap_tolerance * 2
            )
        
        else:
            print(f"   → Using FAST merge approach")
            return NetworkBuilder.create_network_fast(
                rides,
                simplify_tolerance=tolerance,
                merge_tolerance=snap_tolerance
            )
    
    @staticmethod
    def create_network_fast(rides, simplify_tolerance=10, merge_tolerance=50, min_length=200):
        """Fast merge-based approach (for larger datasets)"""
        from shapely.ops import linemerge, unary_union
        
        print("🚀 FAST Network Creation (Merge-based)")
        print("="*70)
        start_total = time.time()
        
        rides_proj = rides.to_crs('EPSG:32633')
        print(f"Processing {len(rides_proj)} rides")
        
        # Simplify
        from shapely.geometry import LineString, MultiLineString

        # Simplify + flatten
        simplified = []
        for g in tqdm(rides_proj.geometry, desc="Simplifying"):
            sg = g.simplify(simplify_tolerance, preserve_topology=True)
            if isinstance(sg, LineString):
                simplified.append(sg)
            elif isinstance(sg, MultiLineString):
                simplified.extend(list(sg.geoms))

        merged = linemerge(simplified)

        if isinstance(merged, LineString):
            segments = [merged]
        elif isinstance(merged, (list, tuple)):
            segments = list(merged)
        else:
            segments = list(merged.geoms) if hasattr(merged, 'geoms') else simplified
        
        # Filter
        segments = [s for s in segments if s.length >= min_length]
        
        network_proj = gpd.GeoDataFrame(
            {
                'segment_id': range(len(segments)),
                'length_m': [s.length for s in segments],
                'distance_km': [s.length/1000 for s in segments]
            },
            geometry=segments,
            crs='EPSG:32633'
        )
        
        print(f"\n✅ Created {len(network_proj)} segments in {time.time() - start_total:.1f}s")
        
        return network_proj.to_crs(rides.crs)
    
    @staticmethod
    def map_rides_to_segments(network, rides, buffer_distance=50):
        """Map rides to network segments"""
        # If network was created with clustered/ultra_simple, rides are already mapped
        if 'rides' in network.columns and 'ride_count' in network.columns:
            print("\n✓ Rides already mapped to segments (no remapping needed)")
            return network
        
        # Otherwise, map them
        print("\n🔄 Mapping rides to segments...")
        network_proj = network.to_crs('EPSG:32633')
        rides_proj = rides.to_crs('EPSG:32633')
        
        network_proj['ride_count'] = 0
        network_proj['rides'] = [[] for _ in range(len(network_proj))]
        
        for idx, ride in tqdm(rides_proj.iterrows(), total=len(rides_proj), desc="Mapping"):
            midpoint = ride.geometry.interpolate(0.5, normalized=True)
            distances = network_proj.geometry.distance(midpoint)
            closest_idx = distances.idxmin()
            
            if distances[closest_idx] <= buffer_distance:
                network_proj.at[closest_idx, 'ride_count'] += 1
                network_proj.at[closest_idx, 'rides'].append({
                    'activity_id': int(ride.get('activity_id', idx)),
                    'distance_km': float(ride.get('distance_km', 0))
                })
        
        print(f"✓ Mapped {network_proj['ride_count'].sum()} ride instances to {len(network_proj)} segments")
        
        return network_proj.to_crs(network.crs)
    
    @staticmethod
    def save_network(network, output_path):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        network_save = network.drop(columns=['rides'], errors='ignore')
        network_save.to_file(output_path, driver='GPKG')
        print(f"💾 Network saved to: {output_path}")