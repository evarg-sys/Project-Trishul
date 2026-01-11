import osmnx as ox
import networkx as nx
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import folium
import time

class DisasterRouting:
    def __init__(self, city="Chicago, Illinois, USA"):
        self.city = city
        self.graph = None
        self.geolocator = Nominatim(user_agent="disaster_routing_v1", timeout=10)
        self.geocode_cache = {}

    def load_network(self, network_type='drive'):
        print(f"Loading road network for {self.city}...")
        self.graph = ox.graph_from_place(self.city, network_type=network_type)
        print(f"Network loaded: {len(self.graph.nodes)} nodes, {len(self.graph.edges)} edges")

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
        except:
            pass
        return None

    def get_nearest_node(self, coords):
        return ox.nearest_nodes(self.graph, coords[1], coords[0])

    def mark_disaster_area(self, center_coords, radius_meters=500):
        blocked_edges = []
        for node in self.graph.nodes():
            node_coords = (self.graph.nodes[node]['y'], self.graph.nodes[node]['x'])
            if geodesic(center_coords, node_coords).meters <= radius_meters:
                for edge in self.graph.edges(node):
                    blocked_edges.append(edge)
        self.graph.remove_edges_from(blocked_edges)
        return blocked_edges

    def add_road_closures(self, closure_coords_list):
        for coords in closure_coords_list:
            node = self.get_nearest_node(coords)
            self.graph.remove_edges_from(list(self.graph.edges(node)))

    def adjust_traffic_weights(self, traffic_data):
        for edge, multiplier in traffic_data.items():
            if self.graph.has_edge(*edge):
                current = self.graph[edge[0]][edge[1]][edge[2]].get('travel_time', 1)
                self.graph[edge[0]][edge[1]][edge[2]]['travel_time'] = current * multiplier

    def find_shortest_route(self, origin_coords, destination_coords, weight='length'):
        o = self.get_nearest_node(origin_coords)
        d = self.get_nearest_node(destination_coords)
        try:
            route = nx.shortest_path(self.graph, o, d, weight=weight)
            dist = sum(ox.utils_graph.get_route_edge_attributes(self.graph, route, 'length'))
            return {"route_nodes": route, "distance": dist, "success": True}
        except:
            return {"route_nodes": None, "distance": None, "success": False}

    def calculate_route(self, origin_coords, destination_coords, weight='length'):
        r = self.find_shortest_route(origin_coords, destination_coords, weight)
        if not r["success"]:
            return None, None
        return r["route_nodes"], r["distance"]

    # ---------- AMBULANCE ADDITIONS ----------

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

    def generate_ambulance_routes(self, disaster_coords, weight='length'):
        hospitals = self.find_nearby_hospitals(disaster_coords)
        routes = []
        for h in hospitals:
            r = self.find_shortest_route(h["coords"], disaster_coords, weight)
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

    # ---------- VISUALIZATION (FIRE + AMBULANCE) ----------

    def visualize_route(self, origin_coords, destination_coords, route_nodes, 
                        disaster_coords=None, save_path='route_map.html', 
                        alternate_routes=None, ambulance_routes=None):

        m = folium.Map(location=[41.8781, -87.6298], zoom_start=12)

        if disaster_coords:
            folium.Circle(
                location=disaster_coords, radius=250,
                color='red', fill=True, fillOpacity=0.4,
                popup='Disaster Area'
            ).add_to(m)

        # Fire alternates
        if alternate_routes:
            for alt in alternate_routes:
                if alt['route_nodes'] and not alt.get('selected', False):
                    coords = [(self.graph.nodes[n]['y'], self.graph.nodes[n]['x']) for n in alt['route_nodes']]
                    folium.PolyLine(coords, weight=3, opacity=0.5, dash_array='10,5').add_to(m)
                    folium.Marker(alt['coords'], icon=folium.Icon(color='orange')).add_to(m)

        # Ambulance alternates
        if ambulance_routes:
            for amb in ambulance_routes:
                if amb['route_nodes'] and not amb.get('selected', False):
                    coords = [(self.graph.nodes[n]['y'], self.graph.nodes[n]['x']) for n in amb['route_nodes']]
                    folium.PolyLine(coords, weight=3, opacity=0.5, dash_array='5,5').add_to(m)
                    folium.Marker(amb['coords'], icon=folium.Icon(color='purple', icon='plus', prefix='fa')).add_to(m)

        # Selected fire route
        if route_nodes:
            coords = [(self.graph.nodes[n]['y'], self.graph.nodes[n]['x']) for n in route_nodes]
            folium.PolyLine(coords, weight=5, opacity=0.8).add_to(m)

        folium.Marker(origin_coords, icon=folium.Icon(color='green')).add_to(m)
        folium.Marker(destination_coords, icon=folium.Icon(color='red')).add_to(m)

        # Selected ambulance route
        if ambulance_routes:
            for amb in ambulance_routes:
                if amb.get("selected"):
                    coords = [(self.graph.nodes[n]['y'], self.graph.nodes[n]['x']) for n in amb['route_nodes']]
                    folium.PolyLine(coords, weight=5, opacity=0.9).add_to(m)
                    folium.Marker(amb['coords'], icon=folium.Icon(color='purple', icon='ambulance', prefix='fa')).add_to(m)

        m.save(save_path)
        print(f"Map saved to {save_path}")
        return m
