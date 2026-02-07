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
import sys
                       
class OptimizedNetworkBuilder:

    @staticmethod
    def _split_at_intersections_fast(segments, snap_tolerance=5.0):
        """
        Split line segments at intersection points using spatial indexing.
        Much faster than nested loops.
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

        
        