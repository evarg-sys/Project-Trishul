# test_routing.py
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from disaster_routing import DisasterRouting

# ---------------- TEST DISASTER CASES ----------------
TEST_CASES = [
    ("Downtown Chicago", (41.8781, -87.6298), 120),
    ("UIC Area", (41.8708, -87.6505), 200),
    ("Chinatown", (41.8526, -87.6325), 150),
    ("Hyde Park", (41.7943, -87.5907), 180),
    ("O'Hare Area", (41.9742, -87.9073), 250),
]

router = DisasterRouting("Chicago, Illinois, USA")

for i, (name, disaster, block_radius) in enumerate(TEST_CASES, start=1):
    print("\n==============================")
    print(f"Disaster {i}: {name}")
    print("Location:", disaster)
    print(f"Default blocked radius: {block_radius} meters")
    print("==============================")

    print("Choose test type for this disaster:")
    print("1 = Fire only")
    print("2 = Ambulance only")
    print("3 = Fire + Ambulance")
    choice = input("Enter 1, 2, or 3: ").strip()

    if choice == "1":
        MODE = "fire"
    elif choice == "2":
        MODE = "ambulance"
    else:
        MODE = "both"

    print("Selected mode:", MODE)

    router.load_network()

    if hasattr(router, "mark_disaster_area"):
        print(f"Blocking roads within {block_radius} meters...")
        router.mark_disaster_area(disaster, radius_meters=block_radius)

    fire_routes = None
    ambulance_routes = None

    if MODE in ["fire", "both"]:
        print("Finding fire routes...")
        fire_routes = router.generate_fire_routes(disaster)
        print("Fire routes found:", len(fire_routes))

    if MODE in ["ambulance", "both"]:
        print("Finding ambulance routes...")
        ambulance_routes = router.generate_ambulance_routes(disaster)
        print("Ambulance routes found:", len(ambulance_routes))

    file_name = f"test_{i}_{name.replace(' ', '_').lower()}.html"

    router.visualize_route(
        disaster_coords=disaster,
        fire_routes=fire_routes,
        ambulance_routes=ambulance_routes,
        save_path=file_name
    )

    print(f"Saved map: {file_name}")

print("\nAll disaster tests finished.")
print("Open the generated HTML files to view routes.")
