"""
Network Builder Module
Create unified trail network from overlapping rides
"""

import geopandas as gpd
from shapely.geometry import LineString, MultiLineString
from shapely.ops import unary_union, linemerge
from pathlib import Path


class NetworkBuilder:
    
    @staticmethod
    def create_network(rides, tolerance=50):        
        # Project to meters for accurate processing
        rides_proj = rides.to_crs('EPSG:32633')
        # Merge all geometries
        all_geoms = rides_proj.geometry.tolist()
        merged = unary_union(all_geoms)
        
        # Try to merge connected line segments
        try:
            merged = linemerge(merged)
            print("   ✓ Merged connected segments")
        except:
            print("   ⚠️  Could not merge all segments")
        
        # Convert to list of segments
        if isinstance(merged, LineString):
            segments = [merged]
        elif isinstance(merged, MultiLineString):
            segments = list(merged.geoms)
        else:
            segments = []
        
        # Create GeoDataFrame
        network = gpd.GeoDataFrame(
            {
                'segment_id': range(len(segments)),
                'length_m': [seg.length for seg in segments]
            },
            geometry=segments,
            crs='EPSG:32633'
        )
        
        # Back to original CRS
        network['length_km'] = network.geometry.length / 1000
        network = network.to_crs(rides.crs)

        
        total_length = network['length_km'].sum()
        print(f"   ✓ Created {len(network)} segments")
        print(f"   ✓ Total network length: {total_length:.1f} km")
        
        return network
    
    @staticmethod
    def map_rides_to_segments(network, rides, buffer_distance=100):
        
        # Project for accurate buffering
        network_proj = network.to_crs('EPSG:32633')
        rides_proj = rides.to_crs('EPSG:32633')
        
        segment_rides = []
        
        for seg_idx, segment in network_proj.iterrows():
            # Buffer the segment
            seg_buffer = segment.geometry.buffer(buffer_distance)
            
            # Find intersecting rides
            intersecting = []
            for ride_idx, ride in rides_proj.iterrows():
                if seg_buffer.intersects(ride.geometry):
                    ride_info = {
                        'length_km': rides.loc[ride_idx, 'length_km'],
                        'route_type': rides.loc[ride_idx, 'route_type'],
                        'ride_id': ride_idx
                    }
                    intersecting.append(ride_info)
            
            segment_rides.append(intersecting)
        
        network['rides'] = segment_rides
        network['ride_count'] = [len(r) for r in segment_rides]
        
        avg_rides = network['ride_count'].mean()
        max_rides = network['ride_count'].max()
        
        print(f"   ✓ Mapped rides to {len(network)} segments")
        print(f"   📊 Avg rides per segment: {avg_rides:.1f}")
        print(f"   📊 Most popular segment: {max_rides} rides")
        
        return network
    
    @staticmethod
    def save_network(network, output_path):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save without the 'rides' list column (not serializable)
        network_save = network.drop(columns=['rides'], errors='ignore')
        network_save.to_file(output_path, driver='GPKG')
        
        print(f"💾 Saved network to: {output_path}")