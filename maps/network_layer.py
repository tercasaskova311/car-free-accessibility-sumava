import geopandas as gpd
from shapely.geometry import LineString, MultiLineString, Polygon
from shapely.ops import unary_union, linemerge
from pathlib import Path
import pandas as pd
from tqdm import tqdm
import time

class NetworkBuilder:    
    @staticmethod
    def create_network_sequential(rides, tolerance=15):
        """
        Ultra-simple: just union + merge
        """
        print("Creating network from rides...")
        rides_proj = rides.to_crs('EPSG:32633')
        
        # Simplify
        print("1. Simplifying...")
        rides_proj['geometry'] = rides_proj.geometry.simplify(tolerance, preserve_topology=True)
        
        # Union all lines (this is the key step!)
        print("2. Merging all rides into network...")
        all_lines = unary_union(rides_proj.geometry)
        
        # Split into segments
        print("3. Creating segments...")
        merged = linemerge(all_lines)
        
        if isinstance(merged, LineString):
            segments = [merged]
        elif isinstance(merged, MultiLineString):
            segments = list(merged.geoms)
        else:
            segments = []
        
        # Filter short
        segments = [s for s in segments if s.length >= 200]
        
        print(f"✓ Created {len(segments)} unique trail segments")
        
        network = gpd.GeoDataFrame(
            {
                'segment_id': range(len(segments)),
                'length_m': [s.length for s in segments]
            },
            geometry=segments,
            crs='EPSG:32633'
        )
        
        network['distance_km'] = network['length_m'] / 1000
        return network.to_crs(rides.crs)
    
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