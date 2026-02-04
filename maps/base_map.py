import folium
from folium.plugins import MarkerCluster, HeatMap, Fullscreen, MiniMap
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import Config

#base layer for interactive map: get the map layers, AIO, legende
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
            min_zoom=Config.MIN_ZOOM,
            prefer_canvas=True
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
                'weight': 3
            },
            control=False
        ).add_to(m)
    
    @staticmethod
    def add_description(m, network, candidates):
        
        if candidates is None or len(candidates) == 0:
            print("no candidates provided, skipping description panel")
            return
        
        top_candidate = candidates.iloc[0]
        hottest_segment = network.nlargest(1, 'ride_count').iloc[0]
        
        # Calculate insights from UNIQUE segments (no double-counting)
        total_segments = len(network)
        total_trail_km = network['distance_km'].sum()
        avg_segment_traffic = network['ride_count'].mean()
        high_traffic_segments = len(network[network['ride_count'] >= Config.TRAFFIC_THRESHOLDS['medium']])
        
        # Average segment length (diagnostic for overlaps)
        avg_segment_length_km = total_trail_km / total_segments if total_segments > 0 else 0
        
        # Get spatial statistics if available
        global_moran_html = ""
        if hasattr(candidates, 'attrs') and 'global_morans_i' in candidates.attrs:
            gm = candidates.attrs['global_morans_i']
            sig_status = "Significant" if gm['significant'] else "Not Significant"
            global_moran_html = f"""
                <p style="margin: 8px 0;">
                    <b style="color: #3498db;">Global Spatial Autocorrelation:</b><br>
                    <span style="font-size: 12px;">
                    • Moran's I: <b>{gm['morans_i']:.4f}</b> (expected: {gm['expected_i']:.4f})<br>
                    • Z-score: {gm['z_score']:.3f} (p={gm['p_value']:.4f}) {sig_status}<br>
                    • {gm['interpretation']}
                    </span>
                </p>
                <hr style="margin: 10px 0; border: none; border-top: 1px solid #ecf0f1;">
            """
        
        summary_html = f"""
        <div style="
            position: fixed;
            top: 120px;
            left: 60px;
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            z-index: 1000;
            max-width: 380px;
            font-family: Arial;
        ">
            <h4 style="margin: 0 0 8px 0; color: #2c3e50; font-size: 16px;">
                Mountain Bike Trail Network Analysis
            </h4>
            <p style="margin: 0 0 12px 0; font-size: 11px; color: #7f8c8d; line-height: 1.4;">
                Spatial autocorrelation analysis of mountain biking patterns in Šumava National Park 
                using Local Indicators of Spatial Association (LISA) to identify statistically 
                significant trail hotspots and optimal trail center placement.
            </p>
            <hr style="margin: 10px 0; border: none; border-top: 1px solid #ecf0f1;">
            <div style="font-size: 13px; line-height: 1.5;">
                {global_moran_html}
                <p style="margin: 8px 0;">
                    <b style="color: #27ae60;">🏆 Optimal Trail Center Location:</b><br>
                    <span style="font-size: 12px;">
                    📍 {top_candidate.geometry.y:.4f}°N, {top_candidate.geometry.x:.4f}°E<br>
                    • Suitability Score: <b>{top_candidate['suitability_score']:.0f}/100</b><br>
                    • Local Moran's I: <b>{top_candidate.get('mean_local_morans_i', 0):.3f}</b><br>
                    • Accessible Trails: {int(top_candidate['trail_count'])} unique segments 
                    ({top_candidate['trail_length_km']:.1f} km within 5 km)<br>
                    • Hotspot Segments: {int(top_candidate.get('hotspot_segments', 0))}
                    </span>
                </p>
                <p style="margin: 8px 0;">
                    <b style="color: #e74c3c;"> Most Popular Trail:</b><br>
                    <span style="font-size: 12px;">
                    {hottest_segment['ride_count']} recorded rides • {hottest_segment['distance_km']:.1f} km length
                    </span>
                </p>
                <p style="margin: 8px 0;">
                    <b style="color: #3498db;"> Network Statistics:</b><br>
                    <span style="font-size: 12px;">
                    • Total network length: <b>{total_trail_km:.1f} km</b><br>
                    • High-traffic trails: {high_traffic_segments} segments (≥{Config.TRAFFIC_THRESHOLDS['medium']} rides)<br>
                    • Mean usage: {avg_segment_traffic:.1f} rides/segment
                    </span>
                </p>
                <p style="margin: 8px 0;">
                    <b style="color: {'#27ae60' if not top_candidate.get('in_prohibited_zone', False) else '#e74c3c'};">
                        🌲 Protected Area Compliance:
                    </b><br>
                    <span style="font-size: 12px;">
    {'✅ Outside Zone A (strictly protected core)<br>Development permitted with restrictions' 
    if not top_candidate.get('in_prohibited_zone', False)
    else '⚠️ Within Zone A (strictly protected core)<br>Development prohibited - alternative sites required'}
                    </span>
                </p>
            </div>
            <hr style="margin: 10px 0; border: none; border-top: 1px solid #ecf0f1;">
            <p style="margin: 5px 0; font-size: 10px; color: #95a5a6; text-align: center;">
                Methodology: Global and Local Moran's I spatial autocorrelation with environmental constraints
            </p>
        </div>
        """
        
        m.get_root().html.add_child(folium.Element(summary_html))

    @staticmethod
    def save_map(m, output_path):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        m.save(str(output_path))
        print(f"Map saved to: {output_path}")