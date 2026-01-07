import folium
import geopandas as gpd
from folium import plugins
from folium.plugins import MarkerCluster

study_area = gpd.read_file('data/raw/00_study_area.gpkg')
stops = gpd.read_file('data/processed/gtfs_layers.gpkg', layer='stops')
pois = gpd.read_file('data/raw/03_tourism_pois.gpkg')
bounds = study_area.total_bounds
center = [(bounds[1] + bounds[3])/2, (bounds[0] + bounds[2])/2]

#simple map creation
m = folium.Map(
    location=center, #lat, lon
    zoom_start=9,
    tiles='OpenStreetMap'
)

folium.GeoJson(
    study_area,
    name='Study Area',
    style_function=lambda x: {
        'fillColor': 'transparent',
        'color': 'red',
        'weight': 2
    }
).add_to(m)

# Adding POIs to the map ===========================================
def get_coordinates(geometry):
    if geometry.geom_type == 'Point':
        return[geometry.y, geometry.x]
    else:
        centroid = geometry.centroid
        return [centroid.y, centroid.x]

# Create POI layer
poi_layer = folium.FeatureGroup(name='POIs', show=True)

# Add markers to feature group
for idx, poi in pois.iterrows():
    coords = get_coordinates(poi.geometry)
    name = poi.get('name', 'Unknown')
    category = poi.get('category', 'Unknown')
    popup_content = f"<b>{name}</b><br>Category: {category}"
    
    folium.Marker(
        location=coords,
        popup=folium.Popup(popup_content, max_width=200),
        tooltip=name,
        icon=folium.Icon(color='green', icon='tree', prefix='fa')
    ).add_to(poi_layer)

poi_layer.add_to(m)

# Add JavaScript to control visibility based on zoom
zoom_control_js = """
<script>
    var poiLayer = null;
    
    // Find the POI layer
    map.eachLayer(function(layer) {
        if (layer.options && layer.options.name === 'POIs') {
            poiLayer = layer;
        }
    });
    
    // Hide markers at low zoom levels
    function updatePOIVisibility() {
        var currentZoom = map.getZoom();
        var minZoom = 13;  // Show POIs only at zoom 13 or higher
        
        if (poiLayer) {
            if (currentZoom >= minZoom) {
                map.addLayer(poiLayer);
            } else {
                map.removeLayer(poiLayer);
            }
        }
    }
    
    // Update visibility on zoom
    map.on('zoomend', updatePOIVisibility);
    
    // Initial check
    updatePOIVisibility();
</script>
"""

m.get_root().html.add_child(folium.Element(zoom_control_js))

# Adding Transport Stops to the map ===========================================
transport_stops = folium.FeatureGroup(
    name='Public Transport Stops',
    show=True,
    overlay=True, 
    control=True
).add_to(m)

#==============================================================================
folium.LayerControl(position= 'topright', collapsed=False).add_to(m)
m.save('maps/map_v1.html')
print("Map saved to maps/map_v1.html")
