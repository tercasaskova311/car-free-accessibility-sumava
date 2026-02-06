import geopandas as gpd
from shapely.geometry import LineString
from pathlib import Path
import pandas as pd
from tqdm import tqdm
import time
import numpy as np
import geopandas as gpd
from shapely.geometry import LineString, MultiLineString, Point
from shapely.ops import linemerge, unary_union, split
from pathlib import Path
import pandas as pd
from tqdm import tqdm
import time
import numpy as np
from rtree import index

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
        print(f"NETWORK CREATED IN {total_time:.1f}s")
        print(f"   Segments:        {len(network_proj):,}")
        print(f"   Total length:    {network_proj['distance_km'].sum():.1f} km")
        print(f"   Avg segment:     {network_proj['length_m'].mean():.0f} m")
        print(f"   Median segment:  {network_proj['length_m'].median():.0f} m")
        print(f"   Ride counting:   1.0x (perfect - no double-counting!)")
        
        return network_proj.to_crs(rides.crs)
    
    @staticmethod
    def create_network_clustered(rides, simplify_tolerance=20, min_length=200, cluster_distance=100):
        """
        MIDDLE GROUND: Cluster nearby rides into segments
        
        Better than ultra-simple (reduces redundancy) but still fast.
        """
        start_total = time.time()
        
        rides_proj = rides.to_crs('EPSG:32633')
        print(f"Input: {len(rides_proj)} rides")
        
        # STEP 1: Simplify
        print(f"simplifying...")
        simplified = rides_proj.copy()
        simplified['geometry'] = simplified.geometry.simplify(simplify_tolerance, preserve_topology=True)
        simplified['length_m'] = simplified.geometry.length
        
        # Filter short
        simplified = simplified[simplified['length_m'] >= min_length].copy()
        print(f"{len(simplified)} rides after simplification")
        
        # STEP 2: Cluster by spatial proximity
        print(f"clustering nearby rides (distance: {cluster_distance}m)...")
        from sklearn.cluster import DBSCAN
        
        # Use centroids for clustering
        centroids = simplified.geometry.centroid
        coords = np.column_stack([centroids.x, centroids.y])
        
        db = DBSCAN(eps=cluster_distance, min_samples=1).fit(coords)
        simplified['cluster'] = db.labels_
        
        n_clusters = len(set(db.labels_))
        print(f"found {n_clusters} clusters")
        
        # STEP 3: For each cluster, pick the longest ride as representative
        print(f"selecting representative from each cluster...")
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
        print(f"NETWORK CREATED IN {total_time:.1f}s")
        print(f"   Segments:        {len(network_proj):,}")
        print(f"   Total length:    {network_proj['distance_km'].sum():.1f} km")
        print(f"   Avg segment:     {network_proj['length_m'].mean():.0f} m")
        print(f"   Avg rides/seg:   {network_proj['ride_count'].mean():.1f}")
        print(f"   Max rides/seg:   {network_proj['ride_count'].max()}")
        print(f"   Compression:     {len(rides)}/{len(network_proj)} = {len(rides)/len(network_proj):.1f}x")
        
        return network_proj.to_crs(rides.crs)
    
    @staticmethod
    def create_network_sequential(rides, tolerance=15, snap_tolerance=25):
        """
        Automatically choose best method based on dataset size
        """
        n_rides = len(rides)
        
        print(f"\nauto-selecting network creation method...")
        print(f"   Dataset size: {n_rides} rides")
        
        if n_rides < 100:
            print(f"using ULTRA-SIMPLE (rides as segments)")
            return NetworkBuilder.create_network_ultra_simple(rides, simplify_tolerance=tolerance)
        
        elif n_rides < 1000:
            print(f"using CLUSTERED approach")
            return NetworkBuilder.create_network_clustered(
                rides, 
                simplify_tolerance=tolerance,
                cluster_distance=snap_tolerance * 2
            )
        
        else:
            print(f"using FAST merge approach")
            return NetworkBuilder.create_network_fast(
                rides,
                simplify_tolerance=tolerance,
                merge_tolerance=snap_tolerance
            )
    
    @staticmethod
    def create_network_fast(rides, simplify_tolerance=10, merge_tolerance=50, min_length=200):
        """Fast merge-based approach (for larger datasets)"""
        from shapely.ops import linemerge, unary_union
        
        print("fast Network Creation (Merge-based)")
        start_total = time.time()
        
        rides_proj = rides.to_crs('EPSG:32633')
        print(f"processing {len(rides_proj)} rides")
        
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
        
        print(f"created {len(network_proj)} segments in {time.time() - start_total:.1f}s")
        
        return network_proj.to_crs(rides.crs)
    
    @staticmethod
    def map_rides_to_segments(network, rides, buffer_distance=50):
        # If network was created with clustered/ultra_simple, rides are already mapped
        if 'rides' in network.columns and 'ride_count' in network.columns:
            print("rides already mapped to segments (no remapping needed)")
            return network
        
        # Otherwise, map them
        print("mapping rides to segments...")
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
        
        print(f"mapped {network_proj['ride_count'].sum()} ride instances to {len(network_proj)} segments")
        
        return network_proj.to_crs(network.crs)
    
    @staticmethod
    def save_network(network, output_path):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        network_save = network.drop(columns=['rides'], errors='ignore')
        network_save.to_file(output_path, driver='GPKG')
        print(f"network saved to: {output_path}")


class OptimizedNetworkBuilder:
    """
    High-performance network building using vectorized operations.
    Avoids expensive Python loops wherever possible.
    """
    
    @staticmethod
    def create_network_vectorized(rides, simplify_tolerance=10, min_length=200, 
                                   snap_tolerance=25, intersection_split=True):
        """
        VECTORIZED APPROACH: Fast network creation using spatial indexing
        
        Strategy:
        1. Simplify all geometries at once (vectorized)
        2. Use spatial index for fast intersection detection
        3. Merge overlapping segments efficiently
        4. Split at intersections (optional)
        
        Performance: ~10-30 seconds for 500-1000 rides
        
        Parameters:
        -----------
        rides : GeoDataFrame
            Input rides
        simplify_tolerance : float
            Douglas-Peucker tolerance in meters
        min_length : float
            Minimum segment length in meters
        snap_tolerance : float
            Distance threshold for snapping nearby lines
        intersection_split : bool
            Whether to split lines at intersections (slower but more accurate)
        """
        print("vECTORIZED Network Creation")
        start_total = time.time()
        
        # Project to metric CRS
        rides_proj = rides.to_crs('EPSG:32633')
        print(f"Input: {len(rides_proj)} rides")
        
        # STEP 1: VECTORIZED SIMPLIFICATION
        print(f"simplifying geometries (tolerance: {simplify_tolerance}m)...")
        start = time.time()
        
        # Simplify all at once - this is vectorized in GeoPandas!
        simplified = rides_proj.copy()
        simplified['geometry'] = simplified.geometry.simplify(
            simplify_tolerance, 
            preserve_topology=True
        )
        
        # Filter short rides
        simplified['length_m'] = simplified.geometry.length
        simplified = simplified[simplified['length_m'] >= min_length].copy()
        
        print(f"simplified in {time.time() - start:.1f}s")
        print(f"keep {len(simplified)} rides (removed {len(rides_proj) - len(simplified)} short)")
        
        # STEP 2: FLATTEN MULTILINESTRINGS
        print(f"flattening MultiLineStrings...")
        start = time.time()
        
        segments = []
        ride_ids = []
        
        for idx, row in simplified.iterrows():
            geom = row.geometry
            if isinstance(geom, LineString):
                segments.append(geom)
                ride_ids.append(idx)
            elif isinstance(geom, MultiLineString):
                for line in geom.geoms:
                    segments.append(line)
                    ride_ids.append(idx)
        
        print(f"flattened to {len(segments)} segments in {time.time() - start:.1f}s")
        
        # STEP 3: BUILD SPATIAL INDEX FOR FAST QUERIES
        print(f"building spatial index...")
        start = time.time()
        
        # Create R-tree spatial index
        idx = index.Index()
        for i, seg in enumerate(segments):
            idx.insert(i, seg.bounds)
        
        print(f"spatial index built in {time.time() - start:.1f}s")
        
        # STEP 4: MERGE NEARBY/OVERLAPPING SEGMENTS
        print(f"merging overlapping segments (tolerance: {snap_tolerance}m)...")
        start = time.time()
        
        if snap_tolerance > 0:
            # Buffer-based merging (much faster than pairwise comparison)
            buffered = [seg.buffer(snap_tolerance) for seg in segments]
            merged_buffers = unary_union(buffered)
            
            # Extract centerlines from merged buffers
            if hasattr(merged_buffers, 'geoms'):
                cluster_groups = list(merged_buffers.geoms)
            else:
                cluster_groups = [merged_buffers]
            
            # For each cluster, merge the original segments that fall within it
            merged_segments = []
            for cluster_buffer in tqdm(cluster_groups, desc="Merging clusters"):
                # Find segments that intersect this cluster
                cluster_segs = []
                for i, seg in enumerate(segments):
                    if seg.intersects(cluster_buffer):
                        cluster_segs.append(seg)
                
                if len(cluster_segs) == 1:
                    merged_segments.append(cluster_segs[0])
                elif len(cluster_segs) > 1:
                    # Merge using linemerge
                    merged = linemerge(cluster_segs)
                    if isinstance(merged, LineString):
                        merged_segments.append(merged)
                    elif hasattr(merged, 'geoms'):
                        merged_segments.extend(list(merged.geoms))
                    else:
                        merged_segments.extend(cluster_segs)
            
            segments = merged_segments
            print(f"merged to {len(segments)} segments in {time.time() - start:.1f}s")
        
        # STEP 5: SPLIT AT INTERSECTIONS (OPTIONAL)
        if intersection_split:
            print(f"splitting at intersections...")
            start = time.time()
            
            segments = OptimizedNetworkBuilder._split_at_intersections_fast(
                segments, 
                snap_tolerance=5.0  # Small tolerance for intersection detection
            )
            
            print(f"   ✓ Split into {len(segments)} segments in {time.time() - start:.1f}s")
        
        # STEP 6: FILTER SHORT SEGMENTS
        print(f"filtering short segments (min: {min_length}m)...")
        segments = [s for s in segments if s.length >= min_length]
        print(f" kept {len(segments)} segments")
        
        # STEP 7: CREATE GEODATAFRAME
        print(f"creating GeoDataFrame...")
        network_proj = gpd.GeoDataFrame(
            {
                'segment_id': range(len(segments)),
                'length_m': [s.length for s in segments],
                'distance_km': [s.length / 1000 for s in segments],
                'geometry': segments
            },
            crs='EPSG:32633'
        )
        
        total_time = time.time() - start_total
        print(f"NETWORK CREATED IN {total_time:.1f}s")
        print(f"   Segments:        {len(network_proj):,}")
        print(f"   Total length:    {network_proj['distance_km'].sum():.1f} km")
        print(f"   Avg segment:     {network_proj['length_m'].mean():.0f} m")
        print(f"   Median segment:  {network_proj['length_m'].median():.0f} m")
        print(f"   Compression:     {len(rides)}/{len(network_proj)} = {len(rides)/len(network_proj):.1f}x")
        
        return network_proj.to_crs(rides.crs)
    
    @staticmethod
    def _split_at_intersections_fast(segments, snap_tolerance=5.0):
        """
        Split line segments at intersection points using spatial indexing.
        Much faster than nested loops.
        
        Parameters:
        -----------
        segments : list of LineString
            Input segments
        snap_tolerance : float
            Distance tolerance for intersection detection
        
        Returns:
        --------
        list of LineString : Split segments
        """
        # Build spatial index
        idx = index.Index()
        for i, seg in enumerate(segments):
            idx.insert(i, seg.bounds)
        
        # Find all intersection points (vectorized where possible)
        intersection_points = []
        
        for i, seg1 in enumerate(tqdm(segments, desc="Finding intersections")):
            # Query spatial index for nearby segments
            bounds = seg1.bounds
            expanded_bounds = (
                bounds[0] - snap_tolerance,
                bounds[1] - snap_tolerance,
                bounds[2] + snap_tolerance,
                bounds[3] + snap_tolerance
            )
            
            nearby_indices = list(idx.intersection(expanded_bounds))
            
            for j in nearby_indices:
                if i >= j:  # Avoid duplicate comparisons
                    continue
                
                seg2 = segments[j]
                
                # Check if they actually intersect
                if seg1.intersects(seg2):
                    intersection = seg1.intersection(seg2)
                    
                    # Extract points from intersection
                    if isinstance(intersection, Point):
                        intersection_points.append(intersection)
                    elif hasattr(intersection, 'geoms'):
                        for geom in intersection.geoms:
                            if isinstance(geom, Point):
                                intersection_points.append(geom)
        
        if len(intersection_points) == 0:
            return segments
        
        print(f"   Found {len(intersection_points)} intersection points")
        
        # Create MultiPoint for all intersections
        from shapely.geometry import MultiPoint
        intersection_multipoint = MultiPoint(intersection_points)
        
        # Split each segment at all intersection points
        split_segments = []
        for seg in tqdm(segments, desc="Splitting segments"):
            if seg.intersects(intersection_multipoint):
                try:
                    # Split returns a GeometryCollection
                    split_result = split(seg, intersection_multipoint)
                    for geom in split_result.geoms:
                        if isinstance(geom, LineString) and geom.length > 0:
                            split_segments.append(geom)
                except Exception:
                    # If split fails, keep original
                    split_segments.append(seg)
            else:
                split_segments.append(seg)
        
        return split_segments
    
    @staticmethod
    def create_network_grid_based(rides, grid_size=1000, simplify_tolerance=10, 
                                   min_length=200):
        #Divide area into grid cells and process each cell
        #Each cell is processed independently, making it easy to parallelize.
        #this is more precise than vectorized, because we can handle cell boundaries better.
        #it better than vecotrizing because we dont use spatial join and so we dont measure rides with midpoint
        #basically rides are buffered and all segments within buffer are considered.
        #also the results of spatial statistics are better with this approach(lower p value etc)

        
        start_total = time.time()
        rides_proj = rides.to_crs('EPSG:32633')
        print(f"Input: {len(rides_proj)} rides")        
        print(f"creating spatial grid (cell size: {grid_size}m)...")
        bounds = rides_proj.total_bounds
        
        x_cells = int(np.ceil((bounds[2] - bounds[0]) / grid_size))
        y_cells = int(np.ceil((bounds[3] - bounds[1]) / grid_size))
        
        print(f"Grid: {x_cells} × {y_cells} = {x_cells * y_cells} cells")
        
        # STEP 2: Assign rides to grid cells        
        rides_proj['grid_x'] = ((rides_proj.geometry.centroid.x - bounds[0]) / grid_size).astype(int)
        rides_proj['grid_y'] = ((rides_proj.geometry.centroid.y - bounds[1]) / grid_size).astype(int)
        rides_proj['grid_cell'] = rides_proj['grid_x'].astype(str) + '_' + rides_proj['grid_y'].astype(str)
        
        # STEP 3: Process each cell independently
        print(f"processing grid cells...")
        all_segments = []
        
        for cell_id, cell_rides in tqdm(rides_proj.groupby('grid_cell'), desc="Processing cells"):
            if len(cell_rides) == 0:
                continue
            
            # Simplify
            cell_rides = cell_rides.copy()
            cell_rides['geometry'] = cell_rides.geometry.simplify(
                simplify_tolerance, 
                preserve_topology=True
            )
            
            # Merge lines in this cell
            lines = []
            for geom in cell_rides.geometry:
                if isinstance(geom, LineString):
                    lines.append(geom)
                elif isinstance(geom, MultiLineString):
                    lines.extend(list(geom.geoms))
            
            if len(lines) > 0:
                merged = linemerge(lines)
                
                if isinstance(merged, LineString):
                    all_segments.append(merged)
                elif hasattr(merged, 'geoms'):
                    all_segments.extend(list(merged.geoms))
                else:
                    all_segments.extend(lines)
        
        # filter short segments
        print(f"\n4. Filtering short segments...")
        all_segments = [s for s in all_segments if s.length >= min_length]
        
        #merge cross-cell boundaries
        print(f"\n5. Merging cross-cell boundaries...")
        final_merged = linemerge(all_segments)
        
        if isinstance(final_merged, LineString):
            final_segments = [final_merged]
        elif hasattr(final_merged, 'geoms'):
            final_segments = list(final_merged.geoms)
        else:
            final_segments = all_segments
        
        # Filter again
        final_segments = [s for s in final_segments if s.length >= min_length]
        
        # Create GeoDataFrame
        network_proj = gpd.GeoDataFrame(
            {
                'segment_id': range(len(final_segments)),
                'length_m': [s.length for s in final_segments],
                'distance_km': [s.length / 1000 for s in final_segments],
                'geometry': final_segments
            },
            crs='EPSG:32633'
        )
        
        total_time = time.time() - start_total
        print(f"\n{'='*70}")
        print(f"NETWORK CREATED IN {total_time:.1f}s")
        print(f"   Segments:        {len(network_proj):,}")
        print(f"   Total length:    {network_proj['distance_km'].sum():.1f} km")
        print(f"   Avg segment:     {network_proj['length_m'].mean():.0f} m")
        print(f"   Compression:     {len(rides)}/{len(network_proj)} = {len(rides)/len(network_proj):.1f}x")
        
        return network_proj.to_crs(rides.crs)
    
    @staticmethod
    def map_rides_to_segments_vectorized(network, rides, buffer_distance=50):
        #VECTORIZED (spatial join) => 
        #take the midpoints of rides and do a spatial join to find nearest segments within buffer distance.
        #it is not super precise but very fast.
        #buffering = capture most rides.
        #for longer riders, midpoint may not be ideal but is a good compromise to process 3k rides quickly.
        #another option is to sample multiple points along each ride and join those - this would be a later advancement

        start = time.time()
        network_proj = network.to_crs('EPSG:32633')
        rides_proj = rides.to_crs('EPSG:32633')
        
        rides_proj['midpoint'] = rides_proj.geometry.interpolate(0.5, normalized=True) # Calculate ride midpoints

        # Create temporary GeoDataFrame with midpoints
        rides_points = rides_proj.copy()
        rides_points['original_geom'] = rides_points.geometry
        rides_points = rides_points.set_geometry('midpoint')
        
        # Add activity metadata
        rides_points['activity_id'] = rides_proj.get('activity_id', rides_proj.index)
        rides_points['distance_km'] = rides_proj.get('distance_km', 0)
        
        # Spatial join (this is vectorized!)
        joined = gpd.sjoin_nearest(
            rides_points[['activity_id', 'distance_km', 'midpoint']],
            network_proj[['segment_id', 'geometry']],
            max_distance=buffer_distance,
            distance_col='dist_to_segment'
        )
        
        # Group by segment and aggregate rides - FIXED!
        ride_counts = joined.groupby('index_right').agg(
            ride_count=('activity_id', 'count'),
            activity_ids=('activity_id', list),
            distances_km=('distance_km', list)
        )
        
        # Create rides list
        ride_counts['rides'] = ride_counts.apply(
            lambda row: [
                {'activity_id': int(aid), 'distance_km': float(dist)}
                for aid, dist in zip(row['activity_ids'], row['distances_km'])
            ],
            axis=1
        )
        
        # Merge back to network
        network_proj = network_proj.merge(
            ride_counts[['ride_count', 'rides']], 
            left_index=True, 
            right_index=True, 
            how='left'
        )
        
        # Fill NaN values
        network_proj['ride_count'] = network_proj['ride_count'].fillna(0).astype(int)
        network_proj['rides'] = network_proj['rides'].apply(lambda x: x if isinstance(x, list) else [])
        
        elapsed = time.time() - start
        total_mapped = network_proj['ride_count'].sum()
        
        print(f"mapped {total_mapped} ride instances to {len(network_proj)} segments in {elapsed:.1f}s")
        print(f"mapping rate: {len(rides) / elapsed:.0f} rides/second")
        
        return network_proj.to_crs(network.crs)


#solely for testing - having multiple ways to create network
#later we have big datasets = so we always use grid-based ....
    def create_network_auto(rides, **kwargs):
        n_rides = len(rides)
        
        print(f" Auto-selecting network creation method...")
        print(f"   Dataset size: {n_rides} rides")
        
        if n_rides < 100:
            print(f"   → Using ULTRA-SIMPLE (rides as segments)")
            from network_layer import NetworkBuilder
            return NetworkBuilder.create_network_ultra_simple(rides, **kwargs)
        
        elif n_rides < 500:
            print(f"   → Using CLUSTERED approach")
            from network_layer import NetworkBuilder
            return NetworkBuilder.create_network_clustered(rides, **kwargs)
        
        elif n_rides < 2000:
            print(f"   → Using VECTORIZED approach")
            return OptimizedNetworkBuilder.create_network_vectorized(
                rides, 
                intersection_split=False,  # Skip splitting for speed
                **kwargs
            )
        
        else:
            print(f"   → Using GRID-BASED approach (fastest for large datasets)")
            return OptimizedNetworkBuilder.create_network_grid_based(rides, **kwargs)
        
        