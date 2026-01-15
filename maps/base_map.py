import folium
from folium.plugins import MarkerCluster, HeatMap, Fullscreen, MiniMap
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import Config

class BaseLayers:
    @staticmethod
    def create_base_map(center, zoom=11):
        m = folium.Map(
            location=center,
            zoom_start=zoom,
            tiles=None,  
            control_scale=True,
            zoom_control=True,
            max_zoom=Config.MAX_ZOOM,
            min_zoom=Config.MIN_ZOOM
        )
        
        folium.TileLayer(
            'OpenStreetMap',
            name='Street Map',
            overlay=False,
            control=True
        ).add_to(m)
        
        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri',
            name='Satellite',
            overlay=False,
            control=True
        ).add_to(m)
        
        folium.TileLayer(
            'OpenTopoMap',
            name='Topographic',
            overlay=False,
            control=True
        ).add_to(m)
        
        MiniMap(toggle_display=True).add_to(m)
        Fullscreen().add_to(m)
        
        return m
    
    @staticmethod
    #adding AIO - NP + CHKO Šumava - lines as a boundary 
    def add_study_area(m, study_area):
        folium.GeoJson(
            study_area,
            name='Study Area',
            style_function=lambda x: {
                'fillColor': 'transparent',
                'color': Config.COLORS['study_area'],
                'weight': 3,
                'dashArray': '10, 5'
            },
            tooltip='Study Area Boundary'
        ).add_to(m)
    
    @staticmethod
    def add_trail_network_analysis(m, network):
        """
        Add the trail network as a SINGLE always-visible layer
        This replaces the non-working toggle version
        """
        thresholds = Config.TRAFFIC_THRESHOLDS
        
        print("Adding trail network segments...")
        
        for idx, segment in network.iterrows():
            ride_count = segment['ride_count']
            rides_info = segment.get('rides', [])
            
            # Color by popularity
            if ride_count == 0:
                color = Config.COLORS['no_traffic']
                weight = 2
            elif ride_count <= thresholds['low']:
                color = Config.COLORS['low_traffic']
                weight = 3
            elif ride_count <= thresholds['medium']:
                color = Config.COLORS['medium_traffic']
                weight = 4
            else:
                color = Config.COLORS['high_traffic']
                weight = 5
            
            # Build popup
            popup_html = f"""
            <div style="font-family: Arial; min-width: 300px; max-height: 400px; overflow-y: auto;">
                <h4 style="margin: 0 0 10px 0; color: #2c3e50;">
                    Trail Segment
                </h4>
                <p style="margin: 5px 0; font-size: 13px;">
                    <b>Routes using this trail:</b> {ride_count}
                </p>
                <hr style="margin: 10px 0;">
                <div style="font-size: 12px;">
            """
            
            for i, ride_info in enumerate(rides_info[:10], 1):  # Limit to first 10
                popup_html += f"""
                <div style="margin: 8px 0; padding: 8px; background: #f8f9fa; 
                            border-radius: 4px; border-left: 3px solid {color};">
                    <b>{i}. {ride_info.get('name', f'Ride {ride_info.get("activity_id", "?")}'[:30])}</b><br>
                    <span style="color: #7f8c8d;">
                         {ride_info.get('distance_km', 0):.1f} km
                    </span>
                </div>
                """
            
            if len(rides_info) > 10:
                popup_html += f"<p style='color: #7f8c8d; font-size: 11px;'>...and {len(rides_info) - 10} more routes</p>"
            
            popup_html += "</div></div>"
            
            # Add to map (no layer group - always visible)
            folium.GeoJson(
                segment.geometry,
                style_function=lambda x, c=color, w=weight: {
                    'color': c,
                    'weight': w,
                    'opacity': 0.8
                },
                highlight_function=lambda x: {
                    'color': Config.COLORS['highlight'],
                    'weight': 6,
                    'opacity': 1.0
                },
                popup=folium.Popup(popup_html, max_width=350),
                tooltip=f"🚴 {ride_count} routes (click for details)"
            ).add_to(m)
            
            if (idx + 1) % 50 == 0:
                print(f"   Added {idx + 1}/{len(network)} segments...")

        print(f"✓ Added {len(network)} interactive trail segments (always visible)")
    
    @staticmethod
    def add_instructions(m):
        instructions = """
        <div style="position: fixed; 
                    top: 10px; 
                    left: 60px; 
                    background: white; 
                    padding: 15px; 
                    border-radius: 8px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
                    z-index: 1000;
                    max-width: 320px;
                    font-family: Arial;">
            <h4 style="margin: 0 0 10px 0; color: #2c3e50;">🚴 MTB Planner</h4>
            <ul style="margin: 0; padding-left: 20px; font-size: 13px; line-height: 1.6;">
                <li><b>Click on  a given trail</b> to see all routes passing through it</li>
                <li><b>Colors:</b> Blue→Orange→Red = increasing popularity</li>
            </ul>
        </div>
        """
        m.get_root().html.add_child(folium.Element(instructions))

    def save_map(m, output_path):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        m.save(str(output_path))
        print(f" Map saved to: {output_path}")
   
