import geopandas as gpd
from shapely.geometry import LineString, MultiLineString, Polygon
from shapely.ops import unary_union, linemerge
from pathlib import Path
import pandas as pd
from tqdm import tqdm
import time

class NetworkBuilder:
    
    @staticmethod
    def create_network_sequential(rides, tolerance=15, snap_tolerance=25):
        """
        Simplified sequential version to diagnose issues
        Much simpler, no multiprocessing
        """
        print("Starting sequential network creation...")
        rides_proj = rides.to_crs('EPSG:32633')
        
        print(f"Processing {len(rides_proj)} rides")
        
        # STEP 1: Simplify
        print("\n1. Simplifying geometries...")
        start = time.time()
        rides_proj['geometry'] = [
            g.simplify(tolerance, True) 
            for g in tqdm(rides_proj.geometry, desc="Simplifying")
        ]
        print(f"   Done in {time.time() - start:.1f}s")
        
        # STEP 2: Buffer (this is the slow part)
        print("\n2. Buffering geometries...")
        print("   This will take ~15-30 minutes for 9k rides...")
        start = time.time()
        
        # Process in smaller chunks with progress
        chunk_size = 500
        all_buffered = []
        
        for i in tqdm(range(0, len(rides_proj), chunk_size), desc="Buffering chunks"):
            chunk = rides_proj.iloc[i:i+chunk_size]
            chunk_buffered = [g.buffer(snap_tolerance) for g in chunk.geometry]
            # Union this chunk
            chunk_union = unary_union(chunk_buffered)
            all_buffered.append(chunk_union)
        
        print(f"   Buffering done in {time.time() - start:.1f}s")
        
        # STEP 3: Union all chunks
        print("\n3. Merging all buffered chunks...")
        start = time.time()
        buffered = unary_union(all_buffered)
        print(f"   Done in {time.time() - start:.1f}s")
        
        # STEP 4: Extract centerlines
        print("\n4. Extracting centerlines...")
        start = time.time()
        snapped = buffered.buffer(-snap_tolerance)
        
        if isinstance(snapped, Polygon):
            centerlines = snapped.boundary
        elif hasattr(snapped, 'geoms'):
            centerlines = unary_union([p.boundary for p in snapped.geoms])
        else:
            centerlines = snapped.boundary
        print(f"   Done in {time.time() - start:.1f}s")
        
        # STEP 5: Merge segments
        print("\n5. Merging connected segments...")
        start = time.time()
        merged = linemerge(centerlines)
        
        if isinstance(merged, LineString):
            segments = [merged]
        elif isinstance(merged, MultiLineString):
            segments = list(merged.geoms)
        else:
            segments = []
        print(f"   Done in {time.time() - start:.1f}s")
        
        print(f"\nCreated {len(segments)} segments")
        
        # Filter short segments
        min_length = 50
        segments = [s for s in segments if s.length >= min_length]
        print(f"After filtering: {len(segments)} segments")
        
        network_proj = gpd.GeoDataFrame(
            {
                'segment_id': range(len(segments)),
                'length_m': [seg.length for seg in segments]
            },
            geometry=segments,
            crs='EPSG:32633'
        )
        
        network_proj['distance_km'] = network_proj["length_m"] / 1000
        return network_proj.to_crs(rides.crs)
    
    @staticmethod
    def map_rides_to_segments_simple(network, rides, buffer_distance=200):
        """
        Simplified version with detailed progress
        """
        print("\nMapping rides to segments (simple version)...")
        network_proj = network.to_crs('EPSG:32633')
        rides_proj = rides.to_crs('EPSG:32633').copy()
        
        if 'ride_id' not in rides_proj.columns:
            rides_proj['ride_id'] = range(len(rides_proj))
        
        print(f"  {len(rides_proj)} rides → {len(network_proj)} segments")
        
        # Buffer segments
        print("\n1. Buffering segments...")
        start = time.time()
        buffered_network = network_proj.copy()
        buffered_network['geometry'] = [
            geom.buffer(buffer_distance)
            for geom in tqdm(network_proj.geometry, desc="Buffering")
        ]
        print(f"   Done in {time.time() - start:.1f}s")
        
        # Process rides in chunks
        print("\n2. Finding intersections (chunked)...")
        chunk_size = 1000
        segment_rides_dict = {sid: [] for sid in network['segment_id']}
        
        start = time.time()
        n_chunks = (len(rides_proj) + chunk_size - 1) // chunk_size
        
        for i in tqdm(range(n_chunks), desc="Processing chunks"):
            chunk_start = i * chunk_size
            chunk_end = min((i + 1) * chunk_size, len(rides_proj))
            chunk = rides_proj.iloc[chunk_start:chunk_end]
            
            # Spatial join for this chunk
            joined = gpd.sjoin(
                buffered_network[['segment_id', 'geometry']],
                chunk[['ride_id', 'distance_km', 'geometry']],
                how='inner',
                predicate='intersects'
            )
            
            # Aggregate
            for segment_id, group in joined.groupby('segment_id'):
                for _, row in group.iterrows():
                    segment_rides_dict[segment_id].append({
                        "activity_id": int(row['ride_id']),
                        "distance_km": row['distance_km']
                    })
        
        print(f"   Done in {time.time() - start:.1f}s")
        
        # Map back
        network['rides'] = network['segment_id'].map(segment_rides_dict)
        network['ride_count'] = network['rides'].apply(len)
        
        print(f"\n✓ Complete. Average {network['ride_count'].mean():.1f} rides per segment")
        
        return network
    
    @staticmethod
    def save_network(network, output_path):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        network_save = network.drop(columns=['rides'], errors='ignore')
        network_save.to_file(output_path, driver='GPKG')