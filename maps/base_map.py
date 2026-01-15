import folium
from folium.plugins import MarkerCluster, HeatMap, Fullscreen
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
            tiles=None,  # We'll add custom tiles
            control_scale=True,
            zoom_control=True,
            max_zoom=Config.MAX_ZOOM,
            min_zoom=Config.MIN_ZOOM
        )
        
        # OpenStreetMap (default)
        folium.TileLayer(
            'OpenStreetMap',
            name='Street Map',
            overlay=False,
            control=True
        ).add_to(m)
        
        # Satellite imagery
        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri',
            name='Satellite',
            overlay=False,
            control=True
        ).add_to(m)
        
        # Topographic
        folium.TileLayer(
            'OpenTopoMap',
            name='Topographic',
            overlay=False,
            control=True
        ).add_to(m)
        
        # Add minimap and fullscreen
        MiniMap(toggle_display=True).add_to(m)
        Fullscreen().add_to(m)
        
        return m
    
    @staticmethod
    def add_study_area(m, study_area):
        """Add study area boundary"""
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
    def add_interactive_network(m, network):
        
        layer = folium.FeatureGroup(
            name='🕸️ Trail Network (Click for routes!)',
            show=True
        )
        
        thresholds = Config.TRAFFIC_THRESHOLDS
        
        for idx, segment in network.iterrows():
            ride_count = segment['ride_count']
            rides_info = segment['rides']
            
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
            
            # Create popup
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
            
            for i, ride_info in enumerate(rides_info, 1):
                popup_html += f"""
                <div style="margin: 8px 0; padding: 8px; background: #f8f9fa; 
                            border-radius: 4px; border-left: 3px solid {color};">
                    <b>{i}. {ride_info['name']}</b><br>
                    <span style="color: #7f8c8d;">
                        📏 {ride_info['length_km']:.1f} km | 🔄 {ride_info['route_type']}
                    </span>
                </div>
                """
            
            popup_html += "</div></div>"
            
            # Add to map
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
            ).add_to(layer)
        
        layer.add_to(m)
        print(f"   ✓ Added {len(network)} interactive segments")
    
    @staticmethod
    def add_instructions(m):
        """Add usage instructions overlay"""
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
                <li><b>Click trail segments</b> to see all routes using it</li>
                <li><b>Colors:</b> Blue→Orange→Red = increasing traffic</li>
                <li><b>Toggle layers</b> to explore rides by type</li>
                <li><b>Switch base maps</b> for satellite/topo views</li>
            </ul>
        </div>
        """
        m.get_root().html.add_child(folium.Element(instructions))

    def save_map(m, output_path):
            """Save map to HTML file"""
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            m.save(str(output_path))
            print(f" Map saved to: {output_path}")
   
