#add zones with legend and candidate locations

import folium
from folium.plugins import MarkerCluster
import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import Config


class TrailsLayers:
    @staticmethod
    def add_protected_zones(m, zones_gdf):
        #Add protected zones with legend for both national park and protected landscape area
        zone_colors = {
            'A': '#1a5c1a', 'B': '#2d8a2d', 'C': '#4caf50', 'D': '#81c784',
            'I': '#66bb6a', 'II': '#81c784', 'III': '#a5d6a7', 'IV': '#c8e6c9'
        }
        
        zone_labels = {
            'A': 'Zone A (NP) - Strictly Protected Core',
            'B': 'Zone B (NP) - Managed Protection',
            'C': 'Zone C (NP) - Outer Protection',
            'D': 'Zone D (NP) - Buffer Zone',
            'I': 'Zone I - CHKO protected area',
            'II': 'Zone II - CHKO protected area',
            'III': 'Zone III - CHKO protected area',
            'IV': 'Zone IV - CHKO protected area'
        }
        
        layer = folium.FeatureGroup(name='Protected Zones', show=True)
        
        for _, zone in zones_gdf.iterrows():
            zone_type = str(zone.get('ZONA', 'Unknown'))
            color = zone_colors.get(zone_type, '#cccccc')
            
            folium.GeoJson(
                zone.geometry,
                style_function=lambda x, c=color: {
                    'fillColor': c,
                    'color': c,
                    'weight': 1,
                    'fillOpacity': 0.25,
                    'opacity': 0.5
                },
                tooltip=f"Zone {zone_type}"  # Simple hover tooltip to show zone type on map
            ).add_to(layer)
        
        layer.add_to(m)
        
        # Add legend in lower right corner
        legend_html = '''
        <div style="
            position: fixed;
            bottom: 50px;
            right: 20px;
            background: white;
            padding: 12px;
            border-radius: 8px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.3);
            z-index: 1000;
            font-family: Arial;
            font-size: 12px;
        ">
            <h4 style="margin: 0 0 8px 0; font-size: 13px; color: #2c3e50;">
                🌲 Protection Zones
            </h4>
        '''
        
        # Add each zone to legend (only zones present in data)
        present_zones = sorted(zones_gdf['ZONA'].unique())
        for zone_type in present_zones:
            if zone_type in zone_colors:
                color = zone_colors[zone_type]
                label = zone_labels.get(zone_type, f'Zone {zone_type}')
                legend_html += f'''
            <div style="margin: 4px 0; display: flex; align-items: center;">
                <span style="
                    display: inline-block;
                    width: 20px;
                    height: 12px;
                    background: {color};
                    margin-right: 6px;
                    border: 1px solid #999;
                    opacity: 0.7;
                "></span>
                <span style="font-size: 11px;">{label}</span>
            </div>
                '''
        
        legend_html += '''
            <div style="margin-top: 8px; padding-top: 6px; border-top: 1px solid #ddd; font-size: 10px; color: #666;">
                Zone A: Development prohibited
            </div>
        </div>
        '''
        
        m.get_root().html.add_child(folium.Element(legend_html))
        
        print(f"  ✓ Added {len(zones_gdf)} protected zones with legend")
    

    @staticmethod
    def add_candidate_locations(m, candidates, protected_zones=None):
        #choose top 3 candidates (based on suitability score/spatial_analysis) and add to map

        layer = folium.FeatureGroup(name='Candidate Locations', show=True)
        if candidates is None or len(candidates) == 0:
            return

        top_k = min(3, len(candidates))

        for i in range(top_k):
            row = candidates.iloc[i]

            rank = int(row['rank'])
            score = row['suitability_score']

            # Visual encoding
            if rank == 1:
                color = 'yellow'
                radius = 14
            elif rank == 2:
                color = 'orange'
                radius = 11
            else:
                color = 'pink'
                radius = 9
            
            #simple pop up for the map
            popup_html = f"""
            <b>Candidate #{rank}</b><br>
            Score: {score:.1f}/100<br>
            Trails (unique): {row['unique_trail_length_km']:.1f} km<br>
            Total rides: {int(row['total_rides'])}<br>
            Zone: {row['zone_type']}
            """

            #marker for each candidate place
            folium.CircleMarker(
                location=[row.geometry.y, row.geometry.x],
                radius=radius,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.85,
                popup=popup_html
            ).add_to(layer)
        layer.add_to(m)

    @staticmethod
    def add_trail_net(m, network):
        # Add base trail network layer (subsampled and simplified for performance)
        #subsampled: 500 segments - means only 500 segments shown in the map
        #simplify 10m - means only every 10th meter is kept in geometry

        sample_size = Config.BASE_TRAIL_SAMPLE_SIZE   # 500
        simplify    = Config.RENDER_SIMPLIFY_M        # 10 m
        display = network.copy()

        # Simplify geometry
        display_proj = display.to_crs("EPSG:32633")
        display_proj['geometry'] = display_proj.geometry.simplify(simplify)
        display = display_proj.to_crs("EPSG:4326")

        # Subsample if needed
        if len(display) > sample_size:
            display = display.sample(n=sample_size, random_state=42)
            print(f"Base trail layer subsampled: {len(network)} → {sample_size}")

        layer = folium.FeatureGroup(name='Trail Network', show=True)
        # Single GeoJson call for all segments! Improves performance.
        folium.GeoJson(
            display,
            color='#805110',
            name= 'trails',
            weight=2,
            opacity=0.7
        ).add_to(layer)
        
        layer.add_to(m)
        print(f"Trail network added ({len(display)} segments)")
 
    @staticmethod
    def trails_in_hh(m, network_proj):
        #Highlight trails that are part of High-High LISA clusters

        layer = folium.FeatureGroup(name='High-High Clusters', show=True)        
        
        hh_trails = network_proj[network_proj['cluster_type'] == 'High-High']
        hh_trails = hh_trails.sort_values('ride_count', ascending=False).head(10)  # Show top 10 for clarity
        hh_trails['distance_km'] = hh_trails['distance_km'].round(0)
        
        if len(hh_trails) == 0:
            print("No High-High clusters found to highlight.")
            return
        
        for _, trail in hh_trails.iterrows():
            folium.GeoJson(
                trail.geometry,
                name='High-High Clusters',
                style_function=lambda x: {
                    'color': "#E64E36",
                    'weight': 4,
                    'opacity': 0.9
                },
                tooltip=f"High-High Cluster: {trail['ride_count']} rides"
            ).add_to(layer)
        layer.add_to(m)

        print(f"Highlighted {len(hh_trails)} High-High cluster trails")
    

        