import osmnx as ox
import networkx as nx
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import folium

class DisasterRouting:
    def __init__(self, city="Chicago, Illinois, USA"):
        """Initialize the routing system with OSM data for a city."""
        self.city = city
        self.graph = None
        self.geolocator = Nominatim(user_agent="disaster_routing")
        
    def load_network(self, network_type='drive'):
        """Load the road network from OSM."""
        print(f"Loading road network for {self.city}...")
        self.graph = ox.graph_from_place(self.city, network_type=network_type)
        print(f"Network loaded: {len(self.graph.nodes)} nodes, {len(self.graph.edges)} edges")
        
    def geocode_address(self, address):
        """Convert address to coordinates."""
        location = self.geolocator.geocode(f"{address}, {self.city}")
        if location:
            return (location.latitude, location.longitude)
        return None
    
    def get_nearest_node(self, coords):
    #"""Find nearest graph node to given coordinates."""
        return ox.distance.nearest_nodes(self.graph, coords[1], coords[0])
    
    def mark_disaster_area(self, center_coords, radius_meters=500):
        """
        Mark roads within disaster area as blocked.
        
        Args:
            center_coords: (lat, lon) tuple of disaster center
            radius_meters: radius of affected area in meters
        """
        blocked_edges = []
        center_node = self.get_nearest_node(center_coords)
        
        # Get all nodes within radius
        for node in self.graph.nodes():
            node_coords = (self.graph.nodes[node]['y'], self.graph.nodes[node]['x'])
            distance = geodesic(center_coords, node_coords).meters
            
            if distance <= radius_meters:
                # Mark all edges connected to this node as blocked
                for edge in self.graph.edges(node):
                    blocked_edges.append(edge)
        
        # Remove blocked edges from graph
        self.graph.remove_edges_from(blocked_edges)
        print(f"Blocked {len(blocked_edges)} road segments in disaster area")
        
        return blocked_edges
    
    def add_road_closures(self, closure_coords_list):
        """
        Add specific road closures.
        
        Args:
            closure_coords_list: List of (lat, lon) tuples for road closures
        """
        for coords in closure_coords_list:
            node = self.get_nearest_node(coords)
            # Remove edges around this node
            edges_to_remove = list(self.graph.edges(node))
            self.graph.remove_edges_from(edges_to_remove)
    
    def adjust_traffic_weights(self, traffic_data):
        """
        Adjust edge weights based on traffic conditions.
        
        Args:
            traffic_data: Dict mapping edge tuples to traffic multipliers
                         {(u, v, key): multiplier} where multiplier > 1 = slower
        """
        for edge, multiplier in traffic_data.items():
            if self.graph.has_edge(*edge):
                # Multiply travel time by traffic factor
                current_time = self.graph[edge[0]][edge[1]][edge[2]].get('travel_time', 1)
                self.graph[edge[0]][edge[1]][edge[2]]['travel_time'] = current_time * multiplier
    
    def calculate_route(self, origin_coords, destination_coords, weight='length'):
        """
        Calculate optimal route considering all constraints.
        
        Args:
            origin_coords: (lat, lon) of starting point
            destination_coords: (lat, lon) of destination
            weight: 'length' for distance or 'travel_time' for time
            
        Returns:
            route_nodes: List of node IDs in the route
            route_length: Total distance in meters
        """
        origin_node = self.get_nearest_node(origin_coords)
        dest_node = self.get_nearest_node(destination_coords)
        
        try:
            # Find shortest path considering weights
            route_nodes = nx.shortest_path(self.graph, origin_node, dest_node, weight=weight)
            
            # Calculate total distance
            route_length = sum(ox.utils_graph.get_route_edge_attributes(
                self.graph, route_nodes, 'length'))
            
            return route_nodes, route_length
        
        except nx.NetworkXNoPath:
            print("No path found between origin and destination!")
            return None, None
    
    def visualize_route(self, origin_coords, destination_coords, route_nodes, 
                        disaster_coords=None, save_path='route_map.html'):
        """Create an interactive map showing the route."""
        # Create base map centered on Chicago
        m = folium.Map(location=[41.8781, -87.6298], zoom_start=12)
        
        # Add disaster area if provided
        if disaster_coords:
            folium.Circle(
                location=disaster_coords,
                radius=500,
                color='red',
                fill=True,
                fillColor='red',
                fillOpacity=0.3,
                popup='Disaster Area'
            ).add_to(m)
        
        # Add origin marker (fire station)
        folium.Marker(
            location=origin_coords,
            popup='Fire Station (Origin)',
            icon=folium.Icon(color='green', icon='home')
        ).add_to(m)
        
        # Add destination marker
        folium.Marker(
            location=destination_coords,
            popup='Destination',
            icon=folium.Icon(color='blue', icon='info-sign')
        ).add_to(m)
        
        # Add route
        if route_nodes:
            route_coords = [(self.graph.nodes[node]['y'], 
                           self.graph.nodes[node]['x']) for node in route_nodes]
            folium.PolyLine(
                route_coords,
                color='blue',
                weight=5,
                opacity=0.7
            ).add_to(m)
        
        m.save(save_path)
        print(f"Map saved to {save_path}")
        return m


# This file will be imported by our main script