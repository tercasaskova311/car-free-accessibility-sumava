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
    # ------------------------------------------------------------------
    # Protected zones  (small count — no changes needed)
    # ------------------------------------------------------------------
    @staticmethod
    def add_protected_zones(m, zones_gdf):
        """Add protected zones with legend, no popups"""
        zone_colors = {
            'A': '#1a5c1a', 'B': '#2d8a2d', 'C': '#4caf50', 'D': '#81c784',
            'I': '#66bb6a', 'II': '#81c784', 'III': '#a5d6a7', 'IV': '#c8e6c9'
        }
        
        zone_labels = {
            'A': 'Zone A - Strictly Protected Core',
            'B': 'Zone B - Managed Protection',
            'C': 'Zone C - Outer Protection',
            'D': 'Zone D - Buffer Zone',
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
                tooltip=f"Zone {zone_type}"  # Simple hover tooltip
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
    
    # ------------------------------------------------------------------
    # Candidate locations  (tiny count — no changes needed)
    # ------------------------------------------------------------------
    @staticmethod
    def add_candidate_locations(m, candidates_gdf, zones_gdf=None):
        layer = folium.FeatureGroup(name='Candidate Locations', show=True)

        def _color(score, prohibited):
            if prohibited:       return 'red'
            if score >= 80:      return 'darkgreen'
            if score >= 60:      return 'green'
            if score >= 40:      return 'orange'
            return 'lightgray'

        for _, cand in candidates_gdf.iterrows():
            rank       = int(cand['rank'])
            score      = float(cand['suitability_score'])
            prohibited = bool(cand.get('in_prohibited_zone', False))
            col        = _color(score, prohibited)
            radius     = max(15, 35 - rank * 3)

            popup_html = (
                f'<div style="font-family:Arial;min-width:300px;">'
                f'<h3 style="margin:0 0 10px 0;color:{col};">Candidate #{rank}</h3>'
                f'<div style="background:#f0f0f0;padding:10px;border-radius:5px;margin-bottom:10px;">'
                f'<h4 style="margin:0 0 5px 0;">Suitability Score</h4>'
                f'<div style="font-size:24px;font-weight:bold;color:{col};">{score:.1f}/100</div></div>'
                f'<p style="margin:8px 0;font-size:13px;"><b>📍 Location:</b><br>'
                f'{cand.geometry.y:.5f}°N, {cand.geometry.x:.5f}°E</p><hr style="margin:10px 0;">'
                f'<p style="margin:8px 0;font-size:13px;"><b>Spatial Clustering:</b><br>'
                f'• Local Moran\'s I: <b>{float(cand.get("mean_local_morans_i", 0)):.3f}</b><br>'
                f'• Hotspot Segments: {int(cand.get("hotspot_segments", 0))}<br>'
                f'• Clustering Strength: {float(cand.get("clustering_strength", 0)):.2f}</p>'
                f'<hr style="margin:10px 0;">'
                f'<p style="margin:8px 0;font-size:13px;"><b>🚵 Trail Accessibility (5 km):</b><br>'
                f'• Segments: {int(cand["trail_count"])}<br>'
                f'• Length: {float(cand["trail_length_km"]):.1f} km<br>'
                f'• Rides: {int(cand["total_rides"])}</p>'
                f'<hr style="margin:10px 0;">'
                f'<p style="margin:8px 0;font-size:13px;"><b>🌲 Environment:</b><br>'
                f'• Zone: <b>{cand.get("zone_type", "Unknown")}</b><br>'
                f'• {"❌ PROHIBITED – core protection zone" if prohibited else "✅ PERMITTED – development allowed with restrictions"}'
                f'</p></div>'
            )

            folium.CircleMarker(
                location=[cand.geometry.y, cand.geometry.x],
                radius=radius,
                popup=folium.Popup(popup_html, max_width=200),
                tooltip=f"Rank #{rank} | Score: {score:.1f}",
                color='white', weight=1, fill=True,
                fillColor=col, fillOpacity=0.8
            ).add_to(layer)

            folium.Marker(
                location=[cand.geometry.y, cand.geometry.x],
                icon=folium.DivIcon(html=(
                    f'<div style="font-size:12px;font-weight:bold;color:white;'
                    f'text-align:center;text-shadow:1px 1px 2px black;">{rank}</div>'
                ))
            ).add_to(layer)

        layer.add_to(m)
        print(f"  ✓ Added {len(candidates_gdf)} candidate locations")

    # ------------------------------------------------------------------
    # FIXED: Base trail layer (network segments with traffic coloring)
    # ------------------------------------------------------------------
    @staticmethod
    def add_trail_net(m, network):
        """Add trail network as a simple, clean layer for a dark base map."""
        simplify     = Config.RENDER_SIMPLIFY_M
        # Keep only geometry for display
        display = network[['geometry']].copy()

        # Simplify geometry for performance
        display_proj = display.to_crs("EPSG:32633")
        display_proj['geometry'] = display_proj.geometry.simplify(simplify)
        display = display_proj.to_crs("EPSG:4326")

        layer = folium.FeatureGroup(name='Trail Network', show=True)

        # Simple style: bright color for dark background
        def style_function(feature):
            return {
                'color': '#f2b632',  # golden-orange trails
                'weight': 2,
                'opacity': 0.9
            }

        # Add all trails in a single GeoJson layer
        folium.GeoJson(
            display,
            style_function=style_function,
            tooltip=folium.GeoJsonTooltip(
                fields=[],
                labels=False
            )
        ).add_to(layer)

        layer.add_to(m)
        print(f"  ✓ Base trail network added ({len(display)} segments)")

    # ------------------------------------------------------------------
    # FIXED: Rides by length - optimized
    # ------------------------------------------------------------------
    @staticmethod
    def add_rides_by_length(m, rides):
        """Add rides categorized by length - OPTIMIZED VERSION"""
        simplify          = Config.RENDER_SIMPLIFY_M
        MAX_PER_CATEGORY  = 300  # Reduced from 500

        rides = rides.copy()
        rides['length_category'] = pd.cut(
            rides['distance_km'],
            bins=[0, 25, 50, float('inf')],
            labels=['Short (0-25 km)', 'Medium (25-50 km)', 'Long (50+ km)']
        )
        # Cast Categorical → str  (folium can't serialise Categorical)
        rides['length_category'] = rides['length_category'].astype(str)

        colors_by_length = {
            'Short (0-25 km)':   '#9b59b6',
            'Medium (25-50 km)': '#8e44ad',
            'Long (50+ km)':     '#5e3370'
        }

        # Simplify once
        rides_proj = rides.to_crs("EPSG:32633")
        rides_proj['geometry'] = rides_proj.geometry.simplify(simplify)
        rides = rides_proj.to_crs("EPSG:4326")

        for category in rides['length_category'].unique():
            if category == 'nan':
                continue

            subset = rides[rides['length_category'] == category].copy()
            color  = colors_by_length.get(category, '#9b59b6')

            # Subsample
            if len(subset) > MAX_PER_CATEGORY:
                subset = subset.sample(n=MAX_PER_CATEGORY, random_state=42)
                print(f"   ⚡ {category}: subsampled to {MAX_PER_CATEGORY}")

            # Only the columns folium needs - simplified for performance
            export_cols = ['geometry', 'distance_km']
            export = subset[export_cols].copy()

            layer = folium.FeatureGroup(
                name=f'{category} ({len(subset)})',
                show=False  # Off by default to reduce initial load
            )

            # Single GeoJson for entire category
            folium.GeoJson(
                export,
                style_function=lambda x, c=color: {
                    'color': c, 'weight': 1.5, 'opacity': 0.6
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=['distance_km'],
                    aliases=['Distance (km):'],
                    labels=True
                )
            ).add_to(layer)

            layer.add_to(m)

        print("  ✓ Rides-by-length layers added")