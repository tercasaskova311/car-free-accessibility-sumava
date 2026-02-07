#create base layer with folium, add study area boundary and description/info panel with overall stats and top candidates summary
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
            min_zoom=Config.MIN_ZOOM,
            prefer_canvas=True
        )
        
        folium.TileLayer(
            'OpenStreetMap',
            name='Open Street Map',
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
        
        return m
    
    @staticmethod
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
            control=False
        ).add_to(m)
    
    @staticmethod
    def add_description(m, network, candidates):
        #Shows overall analysis results + top 3 candidates

        top_n = min(3, len(candidates))
        top_candidates = candidates.head(top_n)
        hottest_segment = network.nlargest(1, 'ride_count').iloc[0]
        
        # Network statistics
        total_segments = len(network)
        total_trail_km = network['distance_km'].sum()
        avg_segment_traffic = network['ride_count'].mean()
        high_traffic_segments = len(network[network['ride_count'] >= Config.TRAFFIC_THRESHOLDS['medium']])
        
        # Get spatial statistics
        global_moran_html = ""
        if hasattr(candidates, 'attrs') and 'global_morans_i' in candidates.attrs:
            gm = candidates.attrs['global_morans_i']
            sig_status = "Significant" if gm['significant'] else "Not Significant"
            
            if gm['significant']:
                if gm['morans_i'] > gm['expected_i']:
                    pattern_desc = "High-traffic trails cluster together — distinct activity hotspots detected"
                else:
                    pattern_desc = "High and low traffic trails are dispersed"
            else:
                pattern_desc = "Trail usage appears randomly distributed"
            
            # Build HTML for global Moran's I summary
            global_moran_html = f"""
                <div style="margin: 10px 0; padding: 10px; background: #f8f9fa; border-left: 3px solid #3498db; border-radius: 4px;">
                    <p style="margin: 0 0 6px 0;">
                        <b style="color: #2c3e50; font-size: 13px;">Global Spatial Pattern</b>
                    </p>
                    <div style="font-size: 11px; line-height: 1.6; color: #34495e;">
                        <strong>Moran's I = {gm['morans_i']:.4f}</strong> 
                        (expected: {gm['expected_i']:.4f})
                    </div>
                    <div style="font-size: 10px; margin-top: 4px; color: #7f8c8d;">
                        Z-score: {gm['z_score']:.3f}, p = {gm['p_value']:.4f} 
                        <span style="color: {'#27ae60' if gm['significant'] else '#95a5a6'};">
                            [{sig_status}]
                        </span>
                    </div>
                    <div style="font-size: 10px; margin-top: 6px; color: #7f8c8d; font-style: italic;">
                        → {pattern_desc}
                    </div>
                </div>
            """
        
        # Build candidate cards HTML - showing rank, score, coordinates, local Moran's I, trail access, and zone status
        candidates_html = ""
        colors = ['#27ae60', '#f39c12', '#e67e22']  # Green, yellow, orange for ranks 1-3
        
        for idx, (_, cand) in enumerate(top_candidates.iterrows()):
            rank = int(cand['rank'])
            score = float(cand['suitability_score'])
            prohibited = bool(cand.get('in_prohibited_zone', False))
            color = colors[idx] if idx < len(colors) else '#95a5a6'
            
            # Use unique trail length (with fallback)
            unique_trail_km = float(cand.get('unique_trail_length_km', cand.get('trail_length_km', 0)))
            
            # Status icon
            status_icon = "❌" if prohibited else "✅"
            status_color = "#e74c3c" if prohibited else color
            
            candidates_html += f"""
                <div style="margin: 8px 0; padding: 8px; background: white; border-left: 3px solid {status_color}; border-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                        <b style="color: {status_color}; font-size: 12px;">{status_icon} Rank #{rank}</b>
                        <span style="font-size: 11px; font-weight: bold; color: {status_color};">{score:.0f}/100</span>
                    </div>
                    <div style="font-size: 10px; line-height: 1.5; color: #34495e;">
                        <div style="margin: 2px 0;">
                            📍 {cand.geometry.y:.4f}°N, {cand.geometry.x:.4f}°E
                        </div>
                        <div style="margin: 2px 0;">
                            Local Moran's I: <b>{cand.get('mean_local_morans_i', 0):.3f}</b>, 
                            Hotspots of segments: <b>{int(cand.get('hotspot_segments', 0))}</b>
                        </div>
                        <div style="margin: 2px 0;">
                            Access: <b>{unique_trail_km:.1f} km</b> km of trails and mtb roads 
                            ({int(cand['trail_count'])} segments)
                        </div>
                        <div style="margin: 2px 0; font-size: 9px; color: #7f8c8d;">
                            Zone: <b>{cand.get('zone_type', 'Unknown')}</b> 
                            {'(prohibited)' if prohibited else '(permitted)'}
                        </div>
                    </div>
                </div>
            """
        
        summary_html = f"""
        <div style="
            position: fixed;
            top: 120px;
            left: 60px;
            background: white;
            padding: 16px 18px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.25);
            z-index: 1000;
            max-width: 420px;
            font-family: 'Arial', sans-serif;
            max-height: 85vh;
            overflow-y: auto;
        ">
            <h4 style="
                margin: 0 0 6px 0; 
                color: #2c3e50; 
                font-size: 16px;
                font-weight: 600;
                border-bottom: 2px solid #3498db;
                padding-bottom: 6px;
            ">
                MTB Trail Center Analysis
            </h4>

            <p style="
                margin: 6px 0 12px 0; 
                font-size: 11px; 
                color: #7f8c8d; 
                line-height: 1.5;
            ">
                Spatial autocorrelation analysis (LISA) to identify optimal trail center 
                locations based on activity clustering in Šumava National Park.
            </p>

            {global_moran_html}

            <!-- NETWORK OVERVIEW -->
            <div style="margin: 12px 0; padding: 10px; background: #f8f9fa; border-radius: 4px;">
                <p style="margin: 0 0 6px 0;">
                    <b style="color: #2c3e50; font-size: 13px;">📊 Network Overview</b>
                </p>
                <div style="font-size: 11px; line-height: 1.5; color: #34495e;">
                    <div style="margin: 3px 0;">
                        • Total network: <strong>{total_trail_km:.1f} km</strong> km of trails across
                    </div>
                    <div style="margin: 3px 0;">
                        • High-traffic segment: <strong>{high_traffic_segments}</strong>
                        (≥{Config.TRAFFIC_THRESHOLDS['medium']} rides)
                    </div>
                    <div style="margin: 3px 0;">
                        • Peak segment: <strong>{hottest_segment['ride_count']}</strong> rides
                    </div>
                    <div style="margin: 3px 0;">
                        • Mean usage: <strong>{avg_segment_traffic:.1f}</strong> rides/segment
                    </div>
                </div>
            </div>

            <!-- TOP CANDIDATES -->
            <div style="margin: 12px 0;">
                <p style="margin: 0 0 8px 0;">
                    <b style="color: #2c3e50; font-size: 13px;">🏆 Top {top_n} Candidate Locations</b>
                </p>
                {candidates_html}
            </div>

            <!-- METHODOLOGY -->
            <div style="
                margin-top: 12px; 
                padding-top: 10px; 
                border-top: 1px solid #ecf0f1; 
            ">
                <p style="
                    margin: 0; 
                    font-size: 9px; 
                    color: #95a5a6; 
                    line-height: 1.4;
                    text-align: center;
                ">
                    <strong style="color: #7f8c8d;">Methods:</strong> 
                    Global & Local Moran's I, distance-based spatial weights (2 km), 
                    Monte Carlo permutation tests (p < 0.05), multi-criteria scoring.
                    *Segments = created as part of network building, not original ride segments.
                    Segments are equal to parts of LineStings that have been split 
                    at intersections and simplified.
                </p>
            </div>
        </div>
        """
        
        m.get_root().html.add_child(folium.Element(summary_html))

    @staticmethod
    def save_map(m, output_path):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        m.save(str(output_path))
        print(f"Map saved to: {output_path}")