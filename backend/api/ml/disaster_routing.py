import osmnx as ox
import networkx as nx
from geopy.geocoders import Nominatim
import time
import json

class DisasterRouting:
    def __init__(self, city="Chicago, Illinois, USA", mapbox_token=None):
        self.city = city
        self.graph = None
        self.geolocator = Nominatim(user_agent="disaster_routing_v1", timeout=10)
        self.geocode_cache = {}
        self.mapbox_token = mapbox_token

    def load_network(self, network_type='drive'):
        print(f"Loading road network for {self.city}...")
        self.graph = ox.graph_from_place(self.city, network_type=network_type)
        print(f"Loaded {len(self.graph.nodes)} nodes, {len(self.graph.edges)} edges")

    def geocode_address(self, address):
        if address in self.geocode_cache:
            return self.geocode_cache[address]

        time.sleep(1)
        try:
            location = self.geolocator.geocode(f"{address}, {self.city}")
            if location:
                coords = (location.latitude, location.longitude)
                self.geocode_cache[address] = coords
                return coords
        except Exception as e:
            print("Geocoding error:", e)
        return None

    def get_nearest_node(self, coords):
        return ox.nearest_nodes(self.graph, coords[1], coords[0])

    def find_shortest_route(self, origin_coords, destination_coords, weight='length'):
        o = self.get_nearest_node(origin_coords)
        d = self.get_nearest_node(destination_coords)
        try:
            route = nx.shortest_path(self.graph, o, d, weight=weight)
            dist = sum(ox.utils_graph.get_route_edge_attributes(self.graph, route, 'length'))
            return {"route_nodes": route, "distance": dist, "success": True}
        except:
            return {"route_nodes": None, "distance": None, "success": False}

    # ---------- FIRE STATIONS ----------

    def find_nearby_fire_stations(self, center_coords, radius_meters=5000, max_results=5):
        tags = {"amenity": "fire_station"}
        gdf = ox.geometries_from_point(center_coords, tags=tags, dist=radius_meters)
        stations = []
        for _, row in gdf.iterrows():
            if row.geometry:
                c = row.geometry.centroid
                stations.append({
                    "name": row.get("name", "Unnamed Fire Station"),
                    "coords": (c.y, c.x)
                })
        return stations[:max_results]

    def generate_fire_routes(self, disaster_coords):
        stations = self.find_nearby_fire_stations(disaster_coords)
        routes = []
        for s in stations:
            r = self.find_shortest_route(s["coords"], disaster_coords)
            if r["success"]:
                routes.append({
                    "station_name": s["name"],
                    "coords": s["coords"],
                    "route_nodes": r["route_nodes"],
                    "distance_km": r["distance"]/1000,
                    "type": "fire"
                })
        routes.sort(key=lambda x: x["distance_km"])
        if routes:
            routes[0]["selected"] = True
        return routes

    # ---------- HOSPITALS ----------

    def find_nearby_hospitals(self, center_coords, radius_meters=5000, max_results=5):
        tags = {"amenity": "hospital"}
        gdf = ox.geometries_from_point(center_coords, tags=tags, dist=radius_meters)
        hospitals = []
        for _, row in gdf.iterrows():
            if row.geometry:
                c = row.geometry.centroid
                hospitals.append({
                    "name": row.get("name", "Unnamed Hospital"),
                    "coords": (c.y, c.x)
                })
        return hospitals[:max_results]

    def generate_ambulance_routes(self, disaster_coords):
        hospitals = self.find_nearby_hospitals(disaster_coords)
        routes = []
        for h in hospitals:
            r = self.find_shortest_route(h["coords"], disaster_coords)
            if r["success"]:
                routes.append({
                    "station_name": h["name"],
                    "coords": h["coords"],
                    "route_nodes": r["route_nodes"],
                    "distance_km": r["distance"]/1000,
                    "type": "ambulance"
                })
        routes.sort(key=lambda x: x["distance_km"])
        if routes:
            routes[0]["selected"] = True
        return routes

    # ---------- VISUALIZATION ----------

    def visualize_route(self, disaster_coords, fire_routes=None, ambulance_routes=None, save_path="dispatch_map.html"):
        if not self.mapbox_token:
            print("Error: Mapbox token is required. Set it in __init__ or as environment variable.")
            return None

        # Prepare GeoJSON features
        features = []

        # Add disaster location circle
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [disaster_coords[1], disaster_coords[0]]
            },
            "properties": {
                "type": "disaster",
                "title": "DISASTER LOCATION"
            }
        })

        # Add fire routes
        if fire_routes:
            for r in fire_routes:
                coords = [[self.graph.nodes[n]['x'], self.graph.nodes[n]['y']] for n in r["route_nodes"]]
                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": coords
                    },
                    "properties": {
                        "type": "fire_route",
                        "selected": r.get("selected", False),
                        "station_name": r["station_name"],
                        "distance_km": r["distance_km"]
                    }
                })
                # Add fire station marker
                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [r["coords"][1], r["coords"][0]]
                    },
                    "properties": {
                        "type": "fire_station",
                        "title": r["station_name"],
                        "distance": f"{r['distance_km']:.2f} km",
                        "selected": r.get("selected", False)
                    }
                })

        # Add ambulance routes
        if ambulance_routes:
            for r in ambulance_routes:
                coords = [[self.graph.nodes[n]['x'], self.graph.nodes[n]['y']] for n in r["route_nodes"]]
                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": coords
                    },
                    "properties": {
                        "type": "ambulance_route",
                        "selected": r.get("selected", False),
                        "station_name": r["station_name"],
                        "distance_km": r["distance_km"]
                    }
                })
                # Add hospital marker
                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [r["coords"][1], r["coords"][0]]
                    },
                    "properties": {
                        "type": "hospital",
                        "title": r["station_name"],
                        "distance": f"{r['distance_km']:.2f} km",
                        "selected": r.get("selected", False)
                    }
                })

        geojson_data = json.dumps({
            "type": "FeatureCollection",
            "features": features
        })

        # Create HTML with Mapbox GL JS
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Disaster Routing Map</title>
    <meta name="viewport" content="initial-scale=1,maximum-scale=1,user-scalable=no">
    <link href="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.css" rel="stylesheet">
    <script src="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js"></script>
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ position: absolute; top: 0; bottom: 0; width: 100%; }}
        
        .mapboxgl-popup-content {{
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }}
        
        .popup-title {{
            font-weight: bold;
            font-size: 14px;
            margin-bottom: 5px;
        }}
        
        .popup-distance {{
            color: #666;
            font-size: 12px;
        }}
        
        .marker-fire {{
            width: 40px;
            height: 40px;
            border-radius: 50%;
            border: 3px solid white;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            cursor: pointer;
            transition: transform 0.2s;
        }}
        
        .marker-fire:hover {{
            transform: scale(1.1);
        }}
        
        .marker-fire.selected {{
            border-color: #FFD700;
            border-width: 4px;
            box-shadow: 0 4px 16px rgba(255,215,0,0.6);
        }}
        
        .marker-hospital {{
            width: 40px;
            height: 40px;
            border-radius: 50%;
            border: 3px solid white;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            cursor: pointer;
            transition: transform 0.2s;
        }}
        
        .marker-hospital:hover {{
            transform: scale(1.1);
        }}
        
        .marker-hospital.selected {{
            border-color: #FFD700;
            border-width: 4px;
            box-shadow: 0 4px 16px rgba(255,215,0,0.6);
        }}
        
        .marker-disaster {{
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: rgba(255, 0, 0, 0.3);
            border: 3px solid #FF0000;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            animation: pulse 2s infinite;
        }}
        
        @keyframes pulse {{
            0%, 100% {{ transform: scale(1); opacity: 1; }}
            50% {{ transform: scale(1.1); opacity: 0.8; }}
        }}
    </style>
</head>
<body>
<div id="map"></div>
<script>
    mapboxgl.accessToken = '{self.mapbox_token}';
    
    const map = new mapboxgl.Map({{
        container: 'map',
        style: 'mapbox://styles/mapbox/streets-v12',
        center: [{disaster_coords[1]}, {disaster_coords[0]}],
        zoom: 13
    }});

    const geojsonData = {geojson_data};

    map.on('load', () => {{
        // Add data source
        map.addSource('routes', {{
            'type': 'geojson',
            'data': geojsonData
        }});

        // Add layers for ambulance routes (non-selected) - DOTTED
        map.addLayer({{
            'id': 'ambulance-routes',
            'type': 'line',
            'source': 'routes',
            'filter': ['all', ['==', ['get', 'type'], 'ambulance_route'], ['==', ['get', 'selected'], false]],
            'paint': {{
                'line-color': '#4A90E2',
                'line-width': 4,
                'line-opacity': 0.6,
                'line-dasharray': [2, 3]
            }}
        }});

        // Add layers for fire routes (non-selected) - DOTTED
        map.addLayer({{
            'id': 'fire-routes',
            'type': 'line',
            'source': 'routes',
            'filter': ['all', ['==', ['get', 'type'], 'fire_route'], ['==', ['get', 'selected'], false]],
            'paint': {{
                'line-color': '#FF6B6B',
                'line-width': 4,
                'line-opacity': 0.6,
                'line-dasharray': [2, 3]
            }}
        }});

        // Add layers for ambulance routes (selected) - SOLID
        map.addLayer({{
            'id': 'ambulance-routes-selected',
            'type': 'line',
            'source': 'routes',
            'filter': ['all', ['==', ['get', 'type'], 'ambulance_route'], ['==', ['get', 'selected'], true]],
            'paint': {{
                'line-color': '#0066CC',
                'line-width': 6,
                'line-opacity': 1
            }}
        }});

        // Add layers for fire routes (selected) - SOLID
        map.addLayer({{
            'id': 'fire-routes-selected',
            'type': 'line',
            'source': 'routes',
            'filter': ['all', ['==', ['get', 'type'], 'fire_route'], ['==', ['get', 'selected'], true]],
            'paint': {{
                'line-color': '#E63946',
                'line-width': 6,
                'line-opacity': 1
            }}
        }});

        // Add markers for stations, hospitals, and disaster
        geojsonData.features.forEach((feature) => {{
            if (feature.properties.type === 'fire_station') {{
                const el = document.createElement('div');
                el.className = 'marker-fire' + (feature.properties.selected ? ' selected' : '');
                el.style.backgroundColor = feature.properties.selected ? '#E63946' : '#FF6B6B';
                el.innerHTML = '🚒';
                
                const popup = new mapboxgl.Popup({{ offset: 25 }})
                    .setHTML(`
                        <div class="popup-title">🚒 ${{feature.properties.title}}</div>
                        <div class="popup-distance">${{feature.properties.distance}}</div>
                        ${{feature.properties.selected ? '<div style="color: #FFD700; font-weight: bold; margin-top: 5px;">✓ DISPATCHED</div>' : ''}}
                    `);
                
                new mapboxgl.Marker(el)
                    .setLngLat(feature.geometry.coordinates)
                    .setPopup(popup)
                    .addTo(map);
                    
            }} else if (feature.properties.type === 'hospital') {{
                const el = document.createElement('div');
                el.className = 'marker-hospital' + (feature.properties.selected ? ' selected' : '');
                el.style.backgroundColor = feature.properties.selected ? '#0066CC' : '#4A90E2';
                el.innerHTML = '🏥';
                
                const popup = new mapboxgl.Popup({{ offset: 25 }})
                    .setHTML(`
                        <div class="popup-title">🏥 ${{feature.properties.title}}</div>
                        <div class="popup-distance">${{feature.properties.distance}}</div>
                        ${{feature.properties.selected ? '<div style="color: #FFD700; font-weight: bold; margin-top: 5px;">✓ DISPATCHED</div>' : ''}}
                    `);
                
                new mapboxgl.Marker(el)
                    .setLngLat(feature.geometry.coordinates)
                    .setPopup(popup)
                    .addTo(map);
                    
            }} else if (feature.properties.type === 'disaster') {{
                const el = document.createElement('div');
                el.className = 'marker-disaster';
                el.innerHTML = '⚠️';
                
                const popup = new mapboxgl.Popup({{ closeOnClick: false, offset: 25 }})
                    .setHTML('<div class="popup-title">⚠️ DISASTER LOCATION</div>')
                    .addTo(map);
                
                new mapboxgl.Marker(el)
                    .setLngLat(feature.geometry.coordinates)
                    .setPopup(popup)
                    .addTo(map);
            }}
        }});
    }});
</script>
</body>
</html>
"""

        with open(save_path, 'w') as f:
            f.write(html_content)
        
        print(f"Map saved to {save_path}")
        return save_path