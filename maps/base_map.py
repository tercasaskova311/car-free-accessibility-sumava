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
   
