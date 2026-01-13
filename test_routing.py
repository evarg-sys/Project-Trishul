import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from disaster_routing import DisasterRouting

router = DisasterRouting("Chicago, Illinois, USA")

while True:
    print("\n==============================")
    print(" DISASTER ROUTING SYSTEM ")
    print("==============================")
    print("1) Run new disaster routing")
    print("2) Exit")
    print("==============================")

    main_choice = input("Choose an option: ").strip()

    if main_choice == "2":
        print("Exiting program. Stay safe!")
        break

    if main_choice != "1":
        print("Invalid choice. Try again.")
        continue

    router.load_network()

    addr = input("\nEnter disaster address (or 'back' to return): ")
    if addr.lower() == "back":
        continue

    disaster = router.geocode_address(addr)
    if not disaster:
        print("Could not find that address.")
        continue

    print("Disaster coordinates:", disaster)

    print("\nChoose response type:")
    print("1 = Fire only")
    print("2 = Ambulance only")
    print("3 = Fire + Ambulance")
    rtype = input("Enter 1, 2, or 3: ").strip()

    fire_routes = None
    ambulance_routes = None

    if rtype in ["1", "3"]:
        fire_routes = router.generate_fire_routes(disaster)

    if rtype in ["2", "3"]:
        ambulance_routes = router.generate_ambulance_routes(disaster)

    router.visualize_route(
        disaster_coords=disaster,
        fire_routes=fire_routes,
        ambulance_routes=ambulance_routes,
        save_path="user_disaster.html"
    )

    print("\nMap generated: user_disaster.html")
    print("Open it in your browser to view routes.")
