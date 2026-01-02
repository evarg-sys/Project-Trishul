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


# Example usage
if __name__ == "__main__":
    # Initialize routing system
    print("Initializing routing system...")
    router = DisasterRouting("Chicago, Illinois, USA")
    router.load_network()
    
    # Define fire stations with their constraints/capabilities
    # Mix of stations that will pass and fail different constraints
    fire_stations = [
        {
            'name': 'Engine 13 (Downtown)',
            'address': '201 S Dearborn St, Chicago, IL',
            'coords': router.geocode_address('201 S Dearborn St, Chicago, IL'),
            'available_trucks': 3,
            'operational': True
        },
        {
            'name': 'Engine 78 (Lincoln Park)',
            'address': '2646 N Halsted St, Chicago, IL',
            'coords': router.geocode_address('2646 N Halsted St, Chicago, IL'),
            'available_trucks': 1,  # FAIL: Not enough trucks
            'operational': True
        },
        {
            'name': 'Engine 17 (West Loop)',
            'address': '1360 S Blue Island Ave, Chicago, IL',
            'coords': router.geocode_address('1360 S Blue Island Ave, Chicago, IL'),
            'available_trucks': 2,
            'operational': False  # FAIL: Under maintenance
        },
        {
            'name': 'Engine 42 (Near North)',
            'address': '55 W Illinois St, Chicago, IL',
            'coords': router.geocode_address('55 W Illinois St, Chicago, IL'),
            'available_trucks': 4,
            'operational': True  # PASS: Should work!
        },
        {
            'name': 'Engine 5 (South Side)',
            'address': '5555 S University Ave, Chicago, IL',
            'coords': router.geocode_address('5555 S University Ave, Chicago, IL'),
            'available_trucks': 3,
            'operational': True  # Might FAIL: Could be too far
        },
        {
            'name': 'Engine 98 (Far North)',
            'address': '7025 N Clark St, Chicago, IL',
            'coords': router.geocode_address('7025 N Clark St, Chicago, IL'),
            'available_trucks': 2,
            'operational': True  # FAIL: Too far (>10km)
        }
    ]
    
    # Define disaster location
    print("\n" + "="*60)
    print("DISASTER ALERT")
    print("="*60)
    disaster_address = "1060 W Addison St, Chicago, IL"
    disaster_coords = router.geocode_address(disaster_address)
    print(f"Location: {disaster_address}")
    print(f"Coordinates: {disaster_coords}")
    
    # FIRST: Calculate routes WITHOUT blocking to see baseline distances
    print("\n" + "="*60)
    print("PHASE 1: Finding Primary Routes (No Blockages)")
    print("="*60)
    
    primary_routes = {}
    for station in fire_stations:
        if station['coords']:
            result = router.find_shortest_route(station['coords'], disaster_coords)
            if result['success']:
                primary_routes[station['name']] = {
                    'distance': result['distance'],
                    'route': result['route_nodes']
                }
                print(f"  {station['name']}: {result['distance']/1000:.2f} km (direct)")
    
    # NOW: Mark disaster area as blocked (smaller radius: 250m)
    print("\n" + "="*60)
    print("PHASE 2: Blocking Disaster Area")
    print("="*60)
    print("Blocking roads in disaster area (250m radius)...")
    router.mark_disaster_area(disaster_coords, radius_meters=250)
    print("✓ Disaster area blocked")
    
    # Define constraints for fire station selection
    constraints = {
        'min_available_trucks': 2,      # Need at least 2 trucks
        'must_be_operational': True,     # Station must be operational
        'max_distance_km': 15            # Within 15km (increased from 10km)
    }
    
    print("\n" + "="*60)
    print("PHASE 3: Finding Best Available Station (With Rerouting)")
    print("="*60)
    print(f"Constraints:")
    print(f"  • Minimum trucks: {constraints['min_available_trucks']}")
    print(f"  • Must be operational: {constraints['must_be_operational']}")
    print(f"  • Max distance: {constraints['max_distance_km']} km")
    print(f"\nTotal fire stations to check: {len(fire_stations)}")
    print("\nChecking fire stations with disaster area blocked...")
    print("-" * 60)
    
    # Find best fire station
    selected = find_closest_available_fire_station(
        router, 
        fire_stations, 
        disaster_coords, 
        constraints
    )
    
    # Get all available stations for comparison (recalculate to get full list)
    available_stations = []
    for station in fire_stations:
        if station['coords']:
            # Check constraints quickly
            meets_constraints = True
            if constraints:
                if station.get('available_trucks', 0) < constraints.get('min_available_trucks', 0):
                    meets_constraints = False
                if not station.get('operational', True) and constraints.get('must_be_operational'):
                    meets_constraints = False
            
            if meets_constraints:
                result = router.find_shortest_route(station['coords'], disaster_coords)
                if result['success']:
                    available_stations.append({
                        'station': station,
                        'route': result,
                        'distance_km': result['distance'] / 1000
                    })
    
    if selected:
        print("\n" + "="*60)
        print("✓ DISPATCH DECISION")
        print("="*60)
        print(f"Selected Station: {selected['station']['name']}")
        print(f"Distance to disaster: {selected['distance_km']:.2f} km")
        
        # Calculate time estimates (assuming average speed of 50 km/h for emergency vehicles)
        avg_speed_kmh = 50
        selected_time_minutes = (selected['distance_km'] / avg_speed_kmh) * 60
        
        # Show comparison with primary route if available
        if selected['station']['name'] in primary_routes:
            primary_dist = primary_routes[selected['station']['name']]['distance'] / 1000
            primary_time_minutes = (primary_dist / avg_speed_kmh) * 60
            
            extra_distance = selected['distance_km'] - primary_dist
            time_lost_minutes = selected_time_minutes - primary_time_minutes
            
            print(f"\nRoute Comparison:")
            print(f"  Primary route: {primary_dist:.2f} km (~{primary_time_minutes:.1f} min)")
            print(f"  Rerouted: {selected['distance_km']:.2f} km (~{selected_time_minutes:.1f} min)")
            print(f"  Extra distance: +{extra_distance:.2f} km")
            print(f"  Time lost: +{time_lost_minutes:.1f} minutes due to rerouting")
        else:
            print(f"\nEstimated arrival time: {selected_time_minutes:.1f} minutes")
        
        print(f"\nStation Details:")
        print(f"  Available trucks: {selected['station']['available_trucks']}")
        print(f"  Route waypoints: {len(selected['route']['route_nodes'])}")
        print(f"  Operational: {'Yes' if selected['station']['operational'] else 'No'}")
        
        # Show why this station was selected
        print("\nSelection Criteria Met:")
        print(f"  ✓ Has {selected['station']['available_trucks']} trucks (>= {constraints['min_available_trucks']} required)")
        print(f"  ✓ Operational status: {selected['station']['operational']}")
        print(f"  ✓ Distance {selected['distance_km']:.2f} km (<= {constraints['max_distance_km']} km limit)")
        print(f"  ✓ Alternate route found (rerouted around disaster area)")
        
        # Prepare alternate routes for visualization
        alternate_route_data = []
        for station_result in available_stations:
            if station_result['station']['name'] != selected['station']['name']:
                alternate_route_data.append({
                    'station_name': station_result['station']['name'],
                    'coords': station_result['station']['coords'],
                    'route_nodes': station_result['route']['route_nodes'],
                    'distance_km': station_result['distance_km'],
                    'color': 'orange',
                    'selected': False
                })
        
        # Visualize the route with alternates
        print("\nCreating map visualization...")
        router.visualize_route(
            selected['station']['coords'],
            disaster_coords,
            selected['route']['route_nodes'],
            disaster_coords,
            save_path='fire_station_dispatch.html',
            alternate_routes=alternate_route_data
        )
        print("✓ Map visualization complete!")
        print("  • Blue solid line = Selected route (rerouted around disaster)")
        print("  • Orange dashed lines = Alternate station routes (not selected)")
        print("  • Red circle = Blocked disaster area (250m radius)")
        print(f"  • Shows {len(alternate_route_data)} alternate options for comparison")
        
        # If rerouting is needed (station blocked), find next closest
        print("\n" + "="*60)
        print("BACKUP OPTION (If primary station gets blocked)")
        print("="*60)
        
        # Remove the selected station and find the next one
        remaining_stations = [s for s in fire_stations if s['name'] != selected['station']['name']]
        backup = find_closest_available_fire_station(
            router,
            remaining_stations,
            disaster_coords,
            constraints
        )
        
        if backup:
            print(f"\n✓ Backup station identified: {backup['station']['name']}")
            print(f"   Distance: {backup['distance_km']:.2f} km")
            print(f"   Available trucks: {backup['station']['available_trucks']}")
        else:
            print("\n✗ No backup station available!")
            print("   Recommendation: Request mutual aid from neighboring districts")
    else:
        print("\n" + "="*60)
        print("✗ NO AVAILABLE STATIONS")
        print("="*60)
        print("No fire stations meet all the required constraints!")
        print("\nSummary of failures:")
        for station in fire_stations:
            print(f"\n{station['name']}:")
            if station['available_trucks'] < constraints['min_available_trucks']:
                print(f"  ✗ Only {station['available_trucks']} trucks (need {constraints['min_available_trucks']})")
            if not station['operational']:
                print(f"  ✗ Not operational")
            
        print("\nRecommendations:")
        print("  1. Relax minimum truck requirement")
        print("  2. Increase maximum distance limit")
        print("  3. Request mutual aid from neighboring districts")
        print("  4. Consider using non-operational stations in emergency")