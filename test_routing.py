import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from disaster_routing import DisasterRouting

# ---------------- Setup ----------------
print("Initializing routing system...")
router = DisasterRouting("Chicago, Illinois, USA")

fire_station = (41.8894, -87.6376)   # Fire station example
disaster = (41.8781, -87.6298)       # Downtown Chicago

# ---------------- Test 1: Basic Fire Route ----------------
print("\nRunning Test 1: Basic Fire Route")
router.load_network()

route1, dist1 = router.calculate_route(fire_station, disaster)
print("Test 1 distance (m):", dist1)

if route1:
    router.visualize_route(
        origin_coords=fire_station,
        destination_coords=disaster,
        route_nodes=route1,
        disaster_coords=disaster,
        save_path="test1_fire.html"
    )
else:
    print("Test 1: No route found.")

# ---------------- Test 2: Fire Route with Disaster Block ----------------
print("\nRunning Test 2: Fire Route with Disaster Block")
router.load_network()  # reset graph
router.mark_disaster_area(disaster, radius_meters=120)  # smaller radius

route2, dist2 = router.calculate_route(fire_station, disaster)
print("Test 2 rerouted distance (m):", dist2)

if route2:
    router.visualize_route(
        origin_coords=fire_station,
        destination_coords=disaster,
        route_nodes=route2,
        disaster_coords=disaster,
        save_path="test2_fire_blocked.html"
    )
else:
    print("Test 2: No route found — radius may be too large.")

# ---------------- Test 3: Fire + Ambulance ----------------
print("\nRunning Test 3: Fire + Ambulance")
router.load_network()  # reset again
router.mark_disaster_area(disaster, radius_meters=120)

route3, dist3 = router.calculate_route(fire_station, disaster)
ambulance_routes = router.generate_ambulance_routes(disaster)

print("Test 3 fire distance (m):", dist3)
print("Ambulance routes found:", len(ambulance_routes))

if route3:
    router.visualize_route(
        origin_coords=fire_station,
        destination_coords=disaster,
        route_nodes=route3,
        disaster_coords=disaster,
        ambulance_routes=ambulance_routes,
        save_path="test3_fire_ambulance.html"
    )
else:
    print("Test 3: No fire route found — try smaller radius.")

print("\nAll tests finished.")
print("Generated files (if routes existed):")
print(" - test1_fire.html")
print(" - test2_fire_blocked.html")
print(" - test3_fire_ambulance.html")
