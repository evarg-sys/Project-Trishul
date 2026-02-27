from disaster_routing import DisasterRouting

def find_closest_available_fire_station(router, fire_stations, disaster_coords, constraints=None):
    """
    Find the closest fire station that meets all constraints.
    Now checks if disaster blocks the route and finds alternate paths.
    
    Args:
        router: DisasterRouting instance
        fire_stations: List of dicts with 'name', 'address', 'coords', and optional constraint info
        disaster_coords: (lat, lon) of disaster location
        constraints: Dict of constraint checks (e.g., {'min_available_trucks': 2})
        
    Returns:
        dict with selected fire station info and route details
    """
    available_stations = []
    
    for station in fire_stations:
        # Check if station meets constraints
        if constraints:
            meets_constraints = True
            
            # Check minimum available trucks
            if 'min_available_trucks' in constraints:
                if station.get('available_trucks', 0) < constraints['min_available_trucks']:
                    print(f"  ✗ {station['name']}: Not enough trucks ({station.get('available_trucks', 0)} < {constraints['min_available_trucks']})")
                    meets_constraints = False
            
            # Check if station is operational
            if 'must_be_operational' in constraints and constraints['must_be_operational']:
                if not station.get('operational', True):
                    print(f"  ✗ {station['name']}: Not operational")
                    meets_constraints = False
            
            # Check maximum distance constraint
            if 'max_distance_km' in constraints:
                # Quick distance check before routing
                from geopy.distance import geodesic
                straight_line_dist = geodesic(station['coords'], disaster_coords).kilometers
                if straight_line_dist > constraints['max_distance_km']:
                    print(f"  ✗ {station['name']}: Too far ({straight_line_dist:.2f} km)")
                    meets_constraints = False
            
            if not meets_constraints:
                continue
        
        # Calculate route to disaster (disaster area should already be blocked in graph)
        print(f"  Calculating alternate route from {station['name']}...")
        result = router.find_shortest_route(station['coords'], disaster_coords)
        
        if result['success']:
            available_stations.append({
                'station': station,
                'route': result,
                'distance_km': result['distance'] / 1000,
                'rerouted': True  # Mark as rerouted since disaster area is blocked
            })
            print(f"  ✓ {station['name']}: {result['distance']/1000:.2f} km (rerouted around disaster)")
        else:
            print(f"  ✗ {station['name']}: No alternate route available (completely blocked)")
    
    # Find the closest available station
    if not available_stations:
        return None
    
    closest = min(available_stations, key=lambda x: x['distance_km'])
    return closest