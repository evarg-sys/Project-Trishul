import osmnx as ox
import networkx as nx
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import folium
import time

class DisasterRouting:
    def __init__(self, city="Chicago, Illinois, USA"):
        """Initialize the routing system with OSM data for a city."""
        self.city = city
        self.graph = None
        # Increase timeout and add user agent
        self.geolocator = Nominatim(user_agent="disaster_routing_v1", timeout=10)
        # Cache for geocoded addresses to avoid repeated API calls
        self.geocode_cache = {}
        
    def load_network(self, network_type='drive'):
        """Load the road network from OSM."""
        print(f"Loading road network for {self.city}...")
        self.graph = ox.graph_from_place(self.city, network_type=network_type)
        print(f"Network loaded: {len(self.graph.nodes)} nodes, {len(self.graph.edges)} edges")
        
    def geocode_address(self, address):
        """Convert address to coordinates with caching and rate limiting."""
        # Check cache first
        if address in self.geocode_cache:
            print(f"  Using cached coordinates for {address}")
            return self.geocode_cache[address]
        
        # Rate limiting - wait 1 second between requests (Nominatim requirement)
        time.sleep(1)
        
        try:
            location = self.geolocator.geocode(f"{address}, {self.city}")
            if location:
                coords = (location.latitude, location.longitude)
                # Cache the result
                self.geocode_cache[address] = coords
                print(f"  Geocoded: {address} -> {coords}")
                return coords
            else:
                print(f"  Warning: Could not geocode {address}")
                return None
        except Exception as e:
            print(f"  Error geocoding {address}: {e}")
            return None
    
    def get_nearest_node(self, coords):
        """Find nearest graph node to given coordinates."""
        return ox.nearest_nodes(self.graph, coords[1], coords[0])
    
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
    
    def find_shortest_route(self, origin_coords, destination_coords, weight='length'):
        """
        Find the shortest route between two points using current graph state.
        This is a standalone function that can be called independently.
        
        Args:
            origin_coords: (lat, lon) of starting point
            destination_coords: (lat, lon) of destination
            weight: 'length' for distance or 'travel_time' for time
            
        Returns:
            dict with keys:
                - route_nodes: List of node IDs in the route
                - distance: Total distance in meters
                - origin_node: Starting node ID
                - dest_node: Ending node ID
                - success: Boolean indicating if route was found
        """
        origin_node = self.get_nearest_node(origin_coords)
        dest_node = self.get_nearest_node(destination_coords)
        
        try:
            # Find shortest path considering weights
            route_nodes = nx.shortest_path(self.graph, origin_node, dest_node, weight=weight)
            
            # Calculate total distance
            route_length = sum(ox.utils_graph.get_route_edge_attributes(
                self.graph, route_nodes, 'length'))
            
            return {
                'route_nodes': route_nodes,
                'distance': route_length,
                'origin_node': origin_node,
                'dest_node': dest_node,
                'success': True
            }
        
        except nx.NetworkXNoPath:
            return {
                'route_nodes': None,
                'distance': None,
                'origin_node': origin_node,
                'dest_node': dest_node,
                'success': False
            }
    
    def calculate_route(self, origin_coords, destination_coords, weight='length'):
        """
        Calculate optimal route considering all constraints.
        (Wrapper for backward compatibility)
        
        Args:
            origin_coords: (lat, lon) of starting point
            destination_coords: (lat, lon) of destination
            weight: 'length' for distance or 'travel_time' for time
            
        Returns:
            route_nodes: List of node IDs in the route
            route_length: Total distance in meters
        """
        result = self.find_shortest_route(origin_coords, destination_coords, weight)
        
        if not result['success']:
            print("No path found between origin and destination!")
            return None, None
        
        return result['route_nodes'], result['distance']
    
    def visualize_route(self, origin_coords, destination_coords, route_nodes, 
                        disaster_coords=None, save_path='route_map.html', 
                        alternate_routes=None):
        """
        Create an interactive map showing the route and alternates.
        
        Args:
            alternate_routes: List of dicts with 'station_name', 'coords', 'route_nodes', 'color', 'selected'
        """
        # Create base map centered on Chicago
        m = folium.Map(location=[41.8781, -87.6298], zoom_start=12)
        
        # Add disaster area if provided
        if disaster_coords:
            folium.Circle(
                location=disaster_coords,
                radius=250,  # Updated to match new radius
                color='red',
                fill=True,
                fillColor='red',
                fillOpacity=0.4,
                popup='Disaster Area (250m radius - BLOCKED)',
                tooltip='Disaster Zone'
            ).add_to(m)
        
        # Add alternate routes first (so they appear under the main route)
        if alternate_routes:
            for alt in alternate_routes:
                if alt['route_nodes'] and not alt.get('selected', False):
                    route_coords = [(self.graph.nodes[node]['y'], 
                                   self.graph.nodes[node]['x']) for node in alt['route_nodes']]
                    
                    # Add the alternate route line
                    folium.PolyLine(
                        route_coords,
                        color=alt.get('color', 'orange'),
                        weight=3,
                        opacity=0.5,
                        dash_array='10, 5',
                        popup=f"{alt['station_name']}<br>Distance: {alt.get('distance_km', 0):.2f} km<br>Status: Not Selected",
                        tooltip=f"Alternate: {alt['station_name']}"
                    ).add_to(m)
                    
                    # Add marker for alternate station
                    folium.Marker(
                        location=alt['coords'],
                        popup=f"{alt['station_name']}<br>Not Selected",
                        icon=folium.Icon(color='orange', icon='home', prefix='fa'),
                        tooltip=f"Alternate: {alt['station_name']}"
                    ).add_to(m)
        
        # Add origin marker (selected fire station)
        folium.Marker(
            location=origin_coords,
            popup='<b>SELECTED Fire Station</b><br>(Origin)',
            icon=folium.Icon(color='green', icon='home', prefix='fa'),
            tooltip='Selected Station'
        ).add_to(m)
        
        # Add destination marker
        folium.Marker(
            location=destination_coords,
            popup='<b>Disaster Location</b><br>(Destination)',
            icon=folium.Icon(color='red', icon='fire', prefix='fa'),
            tooltip='Disaster Site'
        ).add_to(m)
        
        # Add selected route (on top)
        if route_nodes:
            route_coords = [(self.graph.nodes[node]['y'], 
                           self.graph.nodes[node]['x']) for node in route_nodes]
            folium.PolyLine(
                route_coords,
                color='blue',
                weight=5,
                opacity=0.8,
                popup='Selected Route (Rerouted around disaster)',
                tooltip='Active Route'
            ).add_to(m)
        
        # Add legend
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 50px; right: 50px; width: 220px; height: auto; 
                    background-color: white; z-index:9999; font-size:14px;
                    border:2px solid grey; border-radius: 5px; padding: 10px">
        <p style="margin:0"><b>Legend</b></p>
        <p style="margin:5px 0"><span style="color:blue; font-weight:bold">━━━</span> Selected Route</p>
        <p style="margin:5px 0"><span style="color:orange; font-weight:bold">- - -</span> Alternate Routes</p>
        <p style="margin:5px 0"><span style="color:red">●</span> Disaster Area (Blocked)</p>
        <p style="margin:5px 0"><span style="color:green">📍</span> Selected Station</p>
        <p style="margin:5px 0"><span style="color:orange">📍</span> Alternate Stations</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
        
        m.save(save_path)
        print(f"Map saved to {save_path}")
        return m


# This file will be imported by our main script