import geopandas as gpd
import numpy as np
import pandas as pd
from pathlib import Path

class RenderOptimizer:
    """
    Smart sampling and simplification for HTML rendering
    Ensures fast load times without compromising analysis quality
    """
    
    @staticmethod
    def sample_network_for_render(network, max_segments=300, strategy='traffic_weighted'):
        """
        Sample network intelligently for HTML rendering
        
        Parameters:
        -----------
        network : GeoDataFrame
            Full network with all segments
        max_segments : int
            Maximum segments to include in HTML
        strategy : str
            'traffic_weighted' - Prioritize busy trails (recommended)
            'spatial_coverage' - Ensure geographic spread
            'random' - Simple random sample
        
        Returns:
        --------
        GeoDataFrame with sampled segments
        """
        if len(network) <= max_segments:
            print(f"   ✓ Network size ({len(network)}) ≤ max ({max_segments}), no sampling needed")
            return network.copy()
        
        print(f"\n📊 Sampling network for HTML rendering...")
        print(f"   Input: {len(network)} segments")
        print(f"   Target: {max_segments} segments")
        print(f"   Strategy: {strategy}")
        
        if strategy == 'traffic_weighted':
            # Sample proportionally to ride_count
            # High-traffic trails are more likely to be included
            weights = network['ride_count'].clip(lower=1)  # Avoid zero weights
            probs = weights / weights.sum()
            
            sample_idx = np.random.choice(
                network.index, 
                size=max_segments, 
                replace=False,
                p=probs
            )
            sampled = network.loc[sample_idx].copy()
            
            # Report coverage
            traffic_coverage = sampled['ride_count'].sum() / network['ride_count'].sum() * 100
            length_coverage = sampled['distance_km'].sum() / network['distance_km'].sum() * 100
            
            print(f"   ✓ Sampled {len(sampled)} segments")
            print(f"   📈 Traffic coverage: {traffic_coverage:.1f}%")
            print(f"   📏 Length coverage: {length_coverage:.1f}%")
            
        elif strategy == 'spatial_coverage':
            # Grid-based sampling for even geographic coverage
            try:
                from sklearn.cluster import KMeans
                
                network_proj = network.to_crs("EPSG:32633")
                centroids = network_proj.geometry.centroid
                coords = np.column_stack([centroids.x, centroids.y])
                
                # Cluster into max_segments groups
                kmeans = KMeans(n_clusters=max_segments, random_state=42, n_init=10)
                clusters = kmeans.fit_predict(coords)
                
                # Take highest-traffic segment from each cluster
                network_temp = network.copy()
                network_temp['cluster'] = clusters
                
                sampled_idx = network_temp.groupby('cluster')['ride_count'].idxmax()
                sampled = network.loc[sampled_idx].copy()
                
                print(f"   ✓ Spatial coverage sampling: {len(sampled)} segments")
                
            except ImportError:
                print(f"   ⚠️ sklearn not available, falling back to random sampling")
                sampled = network.sample(n=max_segments, random_state=42)
            
        elif strategy == 'top_traffic':
            # Simply take the N highest-traffic segments
            sampled = network.nlargest(max_segments, 'ride_count').copy()
            print(f"   ✓ Top {max_segments} highest-traffic segments selected")
            
        else:  # random
            sampled = network.sample(n=max_segments, random_state=42)
            print(f"   ✓ Random sample: {len(sampled)} segments")
        
        return sampled
    
    @staticmethod
    def aggressive_simplify(gdf, tolerance_m=20):
        """
        Simplify geometries aggressively for HTML rendering
        
        Parameters:
        -----------
        gdf : GeoDataFrame
            Input features to simplify
        tolerance_m : float
            Simplification tolerance in meters
        
        Returns:
        --------
        GeoDataFrame with simplified geometry (WGS84)
        """
        print(f"   🔧 Simplifying geometries (tolerance: {tolerance_m}m)...")
        
        # Project to metric CRS
        original_crs = gdf.crs
        gdf_proj = gdf.to_crs("EPSG:32633")
        
        # Count original points
        original_points = gdf_proj.geometry.apply(
            lambda g: len(g.coords) if hasattr(g, 'coords') else 0
        ).sum()
        
        # Simplify
        gdf_proj['geometry'] = gdf_proj.geometry.simplify(
            tolerance_m, 
            preserve_topology=True
        )
        
        # Count simplified points
        simplified_points = gdf_proj.geometry.apply(
            lambda g: len(g.coords) if hasattr(g, 'coords') else 0
        ).sum()
        
        reduction = (1 - simplified_points / original_points) * 100
        print(f"   ✓ Coordinate reduction: {reduction:.1f}% ({original_points:,} → {simplified_points:,})")
        
        # Convert back to WGS84
        return gdf_proj.to_crs(original_crs)
    
    @staticmethod
    def sample_rides_for_categories(rides, max_total=1500, max_per_category=150):
        """
        Sample rides for length category layers
        
        Parameters:
        -----------
        rides : GeoDataFrame
            All rides
        max_total : int
            Maximum total rides across all categories
        max_per_category : int
            Maximum rides per length category
        
        Returns:
        --------
        GeoDataFrame with sampled rides
        """
        print(f"\n📊 Sampling rides for category layers...")
        print(f"   Input: {len(rides)} rides")
        print(f"   Max per category: {max_per_category}")
        
        # Create length categories
        rides_temp = rides.copy()
        rides_temp['length_category'] = pd.cut(
            rides_temp['distance_km'],
            bins=[0, 25, 50, float('inf')],
            labels=['Short', 'Medium', 'Long']
        )
        
        # Sample each category
        sampled_list = []
        for category in ['Short', 'Medium', 'Long']:
            subset = rides_temp[rides_temp['length_category'] == category]
            
            if len(subset) > max_per_category:
                subset_sampled = subset.sample(n=max_per_category, random_state=42)
                print(f"   {category:8s}: {len(subset):5,} → {max_per_category} rides")
            else:
                subset_sampled = subset
                print(f"   {category:8s}: {len(subset):5,} rides (no sampling needed)")
            
            sampled_list.append(subset_sampled)
        
        sampled = pd.concat(sampled_list, ignore_index=True)
        sampled = sampled.drop(columns=['length_category'])
        
        print(f"   ✓ Total sampled: {len(sampled)} rides")
        
        return sampled
    
    @staticmethod
    def estimate_html_size(network_gdf=None, rides_gdf=None, candidates_gdf=None, 
                          zones_gdf=None, heatmap_points=0):
        """
        Estimate final HTML file size
        
        Parameters:
        -----------
        network_gdf : GeoDataFrame, optional
            Network segments to render
        rides_gdf : GeoDataFrame, optional
            Rides to render
        candidates_gdf : GeoDataFrame, optional
            Candidate locations
        zones_gdf : GeoDataFrame, optional
            Protected zones
        heatmap_points : int
            Number of heatmap points
        
        Returns:
        --------
        float : Estimated size in MB
        """
        total_bytes = 0
        
        # Base Folium overhead
        total_bytes += 2 * 1024 * 1024  # 2 MB base
        
        # Network segments (~1.5 KB per segment)
        if network_gdf is not None:
            avg_coords = network_gdf.geometry.apply(
                lambda g: len(g.coords) if hasattr(g, 'coords') else 5
            ).mean()
            bytes_per_segment = 50 * avg_coords  # ~50 bytes per coordinate
            total_bytes += len(network_gdf) * bytes_per_segment
        
        # Rides (~800 bytes per ride)
        if rides_gdf is not None:
            avg_coords = rides_gdf.geometry.apply(
                lambda g: len(g.coords) if hasattr(g, 'coords') else 20
            ).mean()
            bytes_per_ride = 40 * avg_coords
            total_bytes += len(rides_gdf) * bytes_per_ride
        
        # Candidates (negligible)
        if candidates_gdf is not None:
            total_bytes += len(candidates_gdf) * 500
        
        # Zones (small)
        if zones_gdf is not None:
            total_bytes += len(zones_gdf) * 5000
        
        # Heatmap points (~25 bytes per point)
        total_bytes += heatmap_points * 25
        
        size_mb = total_bytes / (1024 * 1024)
        return round(size_mb, 1)
    
    @staticmethod
    def optimize_for_render(network, rides, max_network=300, max_rides=1500,
                           simplify_tolerance=20, sampling_strategy='traffic_weighted'):
        """
        One-stop optimization: sample and simplify everything for HTML
        
        Returns:
        --------
        tuple: (network_optimized, rides_optimized)
        """
        print("="*70)
        print("OPTIMIZING DATA FOR HTML RENDERING")
        print("="*70)
        
        # Sample network
        network_sampled = RenderOptimizer.sample_network_for_render(
            network, 
            max_segments=max_network,
            strategy=sampling_strategy
        )
        
        # Simplify network
        network_optimized = RenderOptimizer.aggressive_simplify(
            network_sampled,
            tolerance_m=simplify_tolerance
        )
        
        # Sample rides
        rides_sampled = RenderOptimizer.sample_rides_for_categories(
            rides,
            max_total=max_rides,
            max_per_category=150
        )
        
        # Simplify rides
        rides_optimized = RenderOptimizer.aggressive_simplify(
            rides_sampled,
            tolerance_m=simplify_tolerance
        )
        
        # Estimate size
        estimated_size = RenderOptimizer.estimate_html_size(
            network_gdf=network_optimized,
            rides_gdf=rides_optimized,
            heatmap_points=8000
        )
        
        print(f"\n✅ OPTIMIZATION COMPLETE")
        print(f"   Network: {len(network)} → {len(network_optimized)} segments")
        print(f"   Rides: {len(rides)} → {len(rides_optimized)} rides")
        print(f"   Estimated HTML size: ~{estimated_size} MB")
        print("="*70)
        
        return network_optimized, rides_optimized