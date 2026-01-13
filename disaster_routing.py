import osmnx as ox
import networkx as nx
from geopy.geocoders import Nominatim
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
        m = folium.Map(location=disaster_coords, zoom_start=13)

        folium.Circle(
            location=disaster_coords, radius=300,
            color="red", fill=True, fillOpacity=0.4,
            popup="DISASTER LOCATION"
        ).add_to(m)

        if fire_routes:
            for r in fire_routes:
                coords = [(self.graph.nodes[n]['y'], self.graph.nodes[n]['x']) for n in r["route_nodes"]]
                folium.PolyLine(
                    coords,
                    color="red" if r.get("selected") else "orange",
                    weight=6 if r.get("selected") else 3,
                    opacity=0.9 if r.get("selected") else 0.5,
                    dash_array=None if r.get("selected") else "10,5"
                ).add_to(m)
                folium.Marker(
                    r["coords"],
                    popup=f"Fire Station: {r['station_name']}",
                    icon=folium.Icon(color="red", icon="fire")
                ).add_to(m)

        if ambulance_routes:
            for r in ambulance_routes:
                coords = [(self.graph.nodes[n]['y'], self.graph.nodes[n]['x']) for n in r["route_nodes"]]
                folium.PolyLine(
                    coords,
                    color="blue" if r.get("selected") else "lightblue",
                    weight=6 if r.get("selected") else 3,
                    opacity=0.9 if r.get("selected") else 0.5,
                    dash_array=None if r.get("selected") else "5,5"
                ).add_to(m)
                folium.Marker(
                    r["coords"],
                    popup=f"Hospital: {r['station_name']}",
                    icon=folium.Icon(color="blue", icon="plus")
                ).add_to(m)

        m.save(save_path)
        print(f"Map saved to {save_path}")
        return m


if __name__ == "__main__":
    router = DisasterRouting("Chicago, Illinois, USA")
    router.load_network()

    disaster = (41.8781, -87.6298)

    fire_routes = router.generate_fire_routes(disaster)
    ambulance_routes = router.generate_ambulance_routes(disaster)

    router.visualize_route(disaster, fire_routes, ambulance_routes, "dispatch_map.html")
