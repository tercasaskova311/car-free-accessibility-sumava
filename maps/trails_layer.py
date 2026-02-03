import folium
from folium.plugins import MarkerCluster
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import Config

#adding trail info to the map: 1. base trail map, 2. frequency of usage, 3. trails by lenght

class TrailsLayers:
    @staticmethod
    def add_protected_zones(m, zones_gdf):        
        # Zone colors (A = strictest, darker green)
        zone_colors = {
            'A': '#1a5c1a',  # Dark green - core protection
            'B': '#2d8a2d',  # Medium green
            'C': '#4caf50',  # Light green
            'D': '#81c784',  # Very light green
            'I': '#66bb6a',  # Alternative zones
            'II': '#81c784',
            'III': '#a5d6a7',
            'IV': '#c8e6c9'
        }
        
        layer = folium.FeatureGroup(name='Protected Zones', show=True)
        
        for idx, zone in zones_gdf.iterrows():
            zone_type = zone.get('ZONA', 'Unknown')
            color = zone_colors.get(zone_type, '#cccccc')
            
            popup_html = f"""
            <div style="font-family: Arial; min-width: 200px;">
                <h4 style="margin: 0 0 8px 0; color: {color};">
                    Zone {zone_type}
                </h4>
                <p style="margin: 5px 0; font-size: 12px;">
                    <b>Protection Level:</b> {'Strictly Protected (Core)' if zone_type == 'A' 
                        else 'Protected with Restrictions'}<br>
                    <b>Development:</b> {'❌ Prohibited' if zone_type == 'A' 
                        else '⚠️ Restricted'}
                </p>
            </div>
            """
            
            folium.GeoJson(
                zone.geometry,
                style_function=lambda x, c=color: {
                    'fillColor': c,
                    'color': c,
                    'weight': 1,
                    'fillOpacity': 0.3,
                    'opacity': 0.6
                },
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"Zone {zone_type}"
            ).add_to(layer)
        
        layer.add_to(m)
        print(f"Added {len(zones_gdf)} protected zones to map")
    
    @staticmethod
    def add_candidate_locations(m, candidates_gdf, zones_gdf=None):
        #Add candidate trail center locations with enhanced LISA-based information
        layer = folium.FeatureGroup(name='Candidate Locations', show=True)
        
        # Color scheme based on suitability
        def get_marker_color(score, prohibited):
            if prohibited:
                return 'red'
            elif score >= 80:
                return 'darkgreen'
            elif score >= 60:
                return 'green'
            elif score >= 40:
                return 'orange'
            else:
                return 'lightgray'
        
        for idx, candidate in candidates_gdf.iterrows():
            rank = candidate['rank']
            score = candidate['suitability_score']
            prohibited = candidate.get('in_prohibited_zone', False)
            
            # Marker size based on rank (larger = better)
            icon_size = max(15, 35 - (rank * 3))
            
            popup_html = f"""
            <div style="font-family: Arial; min-width: 300px;">
                <h3 style="margin: 0 0 10px 0; color: {get_marker_color(score, prohibited)};">
                    Candidate #{rank}
                </h3>
                
                <div style="background: #f0f0f0; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
                    <h4 style="margin: 0 0 5px 0;">Suitability Score</h4>
                    <div style="font-size: 24px; font-weight: bold; color: {get_marker_color(score, prohibited)};">
                        {score:.1f}/100
                    </div>
                </div>
                
                <p style="margin: 8px 0; font-size: 13px;">
                    <b>📍 Location:</b><br>
                    {candidate.geometry.y:.5f}°N, {candidate.geometry.x:.5f}°E
                </p>
                
                <hr style="margin: 10px 0;">
                
                <p style="margin: 8px 0; font-size: 13px;">
                    <b> Spatial Clustering Analysis:</b><br>
                    • Local Moran's I: <b>{candidate['mean_local_morans_i']:.3f}</b><br>
                    • Hotspot Segments: {int(candidate['hotspot_segments'])}<br>
                    • Clustering Strength: {candidate['clustering_strength']:.2f}
                </p>
                
                <hr style="margin: 10px 0;">
                
                <p style="margin: 8px 0; font-size: 13px;">
                    <b>🚵 Trail Accessibility (5km buffer):</b><br>
                    • Trail Count: {int(candidate['trail_count'])} segments<br>
                    • Total Length: {candidate['trail_length_km']:.1f} km<br>
                    • Total Rides: {int(candidate['total_rides'])}
                </p>
                
                <hr style="margin: 10px 0;">
                
                <p style="margin: 8px 0; font-size: 13px;">
                    <b>🌲 Environmental Status:</b><br>
                    • Zone: <b>{candidate.get('zone_type', 'Unknown')}</b><br>
                    • {'❌ PROHIBITED - Located in core protection zone' if prohibited 
                       else '✅ PERMITTED - Development allowed with restrictions'}
                </p>
            </div>
            """
            
            folium.CircleMarker(
                location=[candidate.geometry.y, candidate.geometry.x],
                radius=icon_size,
                popup=folium.Popup(popup_html, max_width=400),
                tooltip=f"Rank #{rank} | Score: {score:.1f}",
                color='white',
                weight=2,
                fill=True,
                fillColor=get_marker_color(score, prohibited),
                fillOpacity=0.8
            ).add_to(layer)
            
            # Add rank label
            folium.Marker(
                location=[candidate.geometry.y, candidate.geometry.x],
                icon=folium.DivIcon(html=f"""
                    <div style="
                        font-size: 12px;
                        font-weight: bold;
                        color: white;
                        text-align: center;
                        text-shadow: 1px 1px 2px black;
                    ">{rank}</div>
                """)
            ).add_to(layer)
        
        layer.add_to(m)
        print(f"✓ Added {len(candidates_gdf)} candidate locations to map")
    
    @staticmethod
    def add_trail_net(m, rides): #base trail map - made out of uploaded GPS data

        for idx, ride in rides.iterrows():
            color = '#D2B48C'  #light brown
            
            folium.GeoJson(
                ride.geometry,
                style_function=lambda x, c=color: {
                    'color': c,
                    'weight': 1,
                    'opacity': 1
                },
                highlight_function=lambda x: {
                    'weight': 3,
                    'opacity': 1
                },
                control=False  #always visible as base layer
            ).add_to(m)
        
        print(f"✓ Added {len(rides)} base trail lines to map")
        
    @staticmethod
    def add_trail_network(m, network):
        #differ trails by the frequency of usage  (low, medium, high)       
        def get_traffic_color(ride_count):
            if ride_count >= Config.TRAFFIC_THRESHOLDS['medium']:
                return Config.COLORS['high_traffic']
            elif ride_count >= Config.TRAFFIC_THRESHOLDS['low']:
                return Config.COLORS['medium_traffic']
            else:
                return Config.COLORS['low_traffic']
        
        layer = folium.FeatureGroup(name='Popularity of trails', show=True)
        
        for idx, segment in network.iterrows():  #iterate over network - not ride!
            ride_count = segment.get('ride_count', 0)
            color = get_traffic_color(ride_count)  
            
            # Build list of rides for this segment (handle missing 'rides' column)
            rides_info = segment.get('rides', [])
            if rides_info and len(rides_info) > 0:
                rides_list_html = "<br>".join([
                    f"• {r.get('distance_km', 0):.1f}km (ID: {r.get('activity_id', 'N/A')})" 
                    for r in rides_info[:Config.MAX_RIDES_IN_POPUP]
                ])
                
                if len(rides_info) > Config.MAX_RIDES_IN_POPUP:
                    rides_list_html += f"<br>...and {len(rides_info) - Config.MAX_RIDES_IN_POPUP} more"
            else:
                rides_list_html = "No ride details available"
            
            #pop up for segments - show a list of rides which pass thought that given point in the map
            popup_html = f"""
            <div style='font-family: Arial; min-width: 250px;'>
                <h4 style='margin: 0 0 10px 0; color: {color};'>
                    Trail Segment #{segment.get('segment_id', idx)}
                </h4>
                <p style='margin: 5px 0; font-size: 13px;'>
                    <b>Popularity:</b> {ride_count} rides<br>
                    <b>Length:</b> {segment.get('distance_km', 0):.1f} km
                </p>
                <hr style='margin: 10px 0;'>
                <p style='font-size: 12px; margin: 5px 0;'>
                    <b>Rides using this trail:</b><br>
                    {rides_list_html}
                </p>
            </div>
            """
            
            folium.GeoJson(
                segment.geometry,  
                style_function=lambda x, c=color: {
                    'color': c,
                    'weight': 4,
                    'opacity': 0.8
                },
                highlight_function=lambda x: {
                    'weight': 6,
                    'opacity': 1.0
                },
                popup=folium.Popup(popup_html, max_width=350),
                tooltip=f"{ride_count} rides • {segment.get('distance_km', 0):.1f}km"
            ).add_to(layer)  
        
        layer.add_to(m)
        print(f"✓ Added {len(network)} trail segments to map")  
    
    @staticmethod
    def add_rides_by_length(m, rides):

        # split rides by km(short, medium, long)
        rides['length_category'] = pd.cut(
            rides['distance_km'],
            bins=[0, 25, 50, float('inf')],
            labels=['Short (0-25 km)', 'Medium (25-50km)', 
                    'Long (50+)']
        )
        
        colors_by_length = {
            'Short (0-25 km)': '#9b59b6',    # light purple
            'Medium (25-50km)': '#8e44ad',  # strong purple
            'Long (50+)': '#5e3370'     # dark violet
        }
        
        for category in rides['length_category'].dropna().unique():
            subset = rides[rides['length_category'] == category]

            layer = folium.FeatureGroup(
                name=f'{category} ({len(subset)})',
                show=False
            )

            # all rides in category as single GeoJson - in order to speedup
            folium.GeoJson(
                subset[['geometry', 'activity_id', 'distance_km']],
                style_function=lambda x, c=colors_by_length.get(category, '#9b59b6'): {
                    'color': c,
                    'weight': 3,
                    'opacity': 0.7
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=['activity_id', 'distance_km'],
                    aliases=['Ride:', 'Distance (km):']
                )
            ).add_to(layer)
            
            layer.add_to(m)