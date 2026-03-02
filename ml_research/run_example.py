from disaster_routing import DisasterRouting

# Initialize routing system
print("Step 1: Initializing routing system...")
router = DisasterRouting("Chicago, Illinois, USA")

# Load the network
print("Step 2: Loading Chicago road network...")
router.load_network()

# Define fire station (origin)
print("\nStep 3: Setting up fire station location...")
fire_station_address = "201 S Dearborn St, Chicago, IL"
origin_coords = router.geocode_address(fire_station_address)
print(f"Fire Station at: {origin_coords}")

# Define disaster area
print("\nStep 4: Setting up disaster area...")
disaster_address = "1060 W Addison St, Chicago, IL"  # Wrigley Field
disaster_coords = router.geocode_address(disaster_address)
print(f"Disaster Area at: {disaster_coords}")

# Block the disaster area
print("\nStep 5: Blocking roads in disaster area (500m radius)...")
router.mark_disaster_area(disaster_coords, radius_meters=500)

# Define destination
print("\nStep 6: Setting destination...")
destination_address = "875 N Michigan Ave, Chicago, IL"  # Water Tower
destination_coords = router.geocode_address(destination_address)
print(f"Destination at: {destination_coords}")

# Calculate route
print("\nStep 7: Calculating route...")
route_nodes, distance = router.calculate_route(origin_coords, destination_coords)

if route_nodes:
    print(f"\n✓ Route found!")
    print(f"  Distance: {distance:.2f} meters ({distance/1000:.2f} km)")
    print(f"  Route has {len(route_nodes)} waypoints")
    
    # Create visualization
    print("\nStep 8: Creating map visualization...")
    router.visualize_route(origin_coords, destination_coords, route_nodes, 
                          disaster_coords, save_path='chicago_disaster_route.html')
    print("✓ Map saved to chicago_disaster_route.html")
else:
    print("\n✗ No route could be found!")