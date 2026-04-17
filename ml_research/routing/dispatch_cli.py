#!/usr/bin/env python
"""Command-line dispatcher demo with live world-state time updates."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List

import requests

import networkx as nx

from world_state_dispatch import DispatchCoordinator
from world_state_dispatch import MultiRoutePlanner
from world_state_dispatch import RouteOption
from world_state_dispatch import WorldStateDB

# New imports for Mapbox & EONET integration
try:
    from mapbox_service import MapboxService
    from eonet_service import EONETService
    from dispatch_helper import DispatchHelper
    MAPBOX_AVAILABLE = True
except ImportError:
    MAPBOX_AVAILABLE = False
    print("[WARN] Mapbox/EONET modules not available. Traffic-aware commands disabled.")


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.api.ml.priority_model import calculate_priority
from backend.api.ml.text_priority_parser import parse_incident_text

try:
    from backend.api.ml.population_model import PopulationDensityModel
except Exception:
    PopulationDensityModel = None


def build_demo_graph() -> nx.Graph:
    graph = nx.Graph()
    edges = [
        ("S1", "A", 1.2),
        ("A", "B", 1.8),
        ("B", "I1", 1.1),
        ("S1", "C", 2.0),
        ("C", "D", 1.5),
        ("D", "I1", 0.9),
        ("S2", "E", 1.0),
        ("E", "B", 1.2),
        ("S2", "F", 1.6),
        ("F", "D", 0.8),
        ("B", "I2", 1.4),
        ("D", "I2", 1.1),
        ("E", "I2", 2.1),
        ("A", "I2", 2.3),
        ("D", "I3", 2.0),
        ("F", "I3", 1.0),
        ("E", "I3", 1.7),
    ]
    for u, v, dist in edges:
        graph.add_edge(u, v, distance_km=dist)
    return graph


def seed_if_empty(world: WorldStateDB) -> None:
    snapshot = world.get_live_snapshot()
    if snapshot["stations"]:
        return
    world.upsert_station("Central", trucks=3, ambulances=2, cars=4)
    world.upsert_station("North", trucks=3, ambulances=2, cars=3)
    world.upsert_station("South", trucks=2, ambulances=1, cars=2)


def station_node_map() -> Dict[str, str]:
    return {"Central": "S1", "North": "S2", "South": "C"}


def incident_node(incident_id: str) -> str:
    known = {"I1", "I2", "I3"}
    incident_id = incident_id.upper()
    if incident_id not in known:
        raise ValueError(f"Unknown incident id: {incident_id}. Use one of {sorted(known)}")
    return incident_id


def print_snapshot(world: WorldStateDB) -> None:
    snap = world.get_live_snapshot()
    print("\n" + "=" * 82)
    print(f"Clock minute: {snap['clock_minute']}")
    print("Inventory:")
    for station, units in snap["stations"].items():
        truck = units.get("truck", {"available": 0, "total": 0})
        amb = units.get("ambulance", {"available": 0, "total": 0})
        car = units.get("car", {"available": 0, "total": 0})
        print(
            f"  {station:<8} trucks {truck['available']}/{truck['total']}  "
            f"ambulances {amb['available']}/{amb['total']}  cars {car['available']}/{car['total']}"
        )

    print("Active dispatches:")
    if not snap["active_dispatches"]:
        print("  (none)")
    else:
        for d in snap["active_dispatches"]:
            print(
                f"  #{d['id']} {d['unit_type']:<9} st={d['station_name']:<8} "
                f"status={d['status']:<9} rem={d['remaining_minutes']:.1f}m "
                f"src={d['source_kind']:<14} incident={d['incident_id']}"
            )
    print("=" * 82)


def parse_requirements(parts: List[str]) -> Dict[str, int]:
    req = {"truck": 0, "ambulance": 0}
    for token in parts:
        if "=" not in token:
            continue
        k, v = token.split("=", 1)
        k = k.strip().lower()
        if k not in req:
            continue
        req[k] = max(0, int(v))
    return req


def init_population_model() -> PopulationDensityModel | None:
    if PopulationDensityModel is None:
        print("[INFO] Population model unavailable. Using parser population hints only.")
        return None

    try:
        model = PopulationDensityModel()
        model.load_census_data("chi_pop.csv")
        return model
    except Exception as exc:
        print(f"[INFO] Population model failed to initialize: {exc}")
        return None


def geocode_location(location_text: str) -> tuple[float | None, float | None, str]:
    loc = (location_text or "").strip()
    if not loc:
        return None, None, ""

    try:
        res = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": f"{loc}, Chicago, IL",
                "format": "json",
                "limit": 1,
            },
            headers={"User-Agent": "trishul_dispatch_cli_v1"},
            timeout=7,
        )
        data = res.json()
        if not data:
            return None, None, ""
        first = data[0]
        return float(first["lat"]), float(first["lon"]), str(first.get("display_name", ""))
    except Exception:
        return None, None, ""


def estimate_population(
    pop_model: PopulationDensityModel | None,
    parsed: Dict[str, object],
    lat: float | None,
    lon: float | None,
) -> tuple[int, str]:
    base_hint = int(parsed.get("population_affected") or 120)

    if pop_model is None or lat is None or lon is None:
        return base_hint, ""

    try:
        zipcode = pop_model.get_zipcode_from_location(lat, lon)
    except Exception:
        return base_hint, ""

    if not zipcode:
        return base_hint, ""

    census_total = int((pop_model.census_data.get(zipcode) or {}).get("total") or 0)
    if census_total <= 0:
        return base_hint, zipcode

    severity = float(parsed.get("severity_score") or 3.0)
    impact_ratio = min(0.08, 0.01 + (severity * 0.01))
    enriched = max(base_hint, int(census_total * impact_ratio))
    return enriched, zipcode


def infer_requirements(parsed: Dict[str, object], population_affected: int) -> Dict[str, int]:
    response_types = {r.strip().lower() for r in (parsed.get("response_types") or [])}
    disaster_type = str(parsed.get("disaster_type") or "").lower()
    severity = float(parsed.get("severity_score") or 3.0)

    trucks = 1 if ("fire" in response_types or disaster_type in {"fire", "earthquake", "chemical_spill", "traffic_collision"}) else 0
    ambulances = 1 if ("ambulance" in response_types or population_affected >= 80) else 0

    if severity >= 4.2:
        if trucks > 0:
            trucks += 1
        if ambulances > 0:
            ambulances += 1

    if population_affected >= 600:
        ambulances = max(ambulances, 2)
    if population_affected >= 1200:
        trucks = max(trucks, 2)

    return {"truck": trucks, "ambulance": ambulances}


def pick_incident_id(parsed: Dict[str, object]) -> str:
    disaster_type = str(parsed.get("disaster_type") or "").lower()
    location = str(parsed.get("location") or "").strip().lower()

    if location:
        ids = ["I1", "I2", "I3"]
        idx = sum(ord(ch) for ch in location) % len(ids)
        return ids[idx]

    mapping = {
        "fire": "I1",
        "flood": "I2",
        "earthquake": "I3",
        "traffic_collision": "I2",
        "chemical_spill": "I3",
        "medical_emergency": "I1",
    }
    return mapping.get(disaster_type, "I1")


def build_catalog(
    planner: MultiRoutePlanner,
    incident_id: str,
    requirements: Dict[str, int],
) -> Dict[str, List[RouteOption]]:
    target = incident_node(incident_id)
    stations = station_node_map()
    catalog: Dict[str, List[RouteOption]] = {}

    if requirements.get("truck", 0) > 0:
        catalog["truck"] = planner.build_route_catalog(
            station_nodes=stations,
            incident_node=target,
            unit_type="truck",
            top_k_per_station=3,
            speed_kmph=35,
        )
    if requirements.get("ambulance", 0) > 0:
        catalog["ambulance"] = planner.build_route_catalog(
            station_nodes=stations,
            incident_node=target,
            unit_type="ambulance",
            top_k_per_station=3,
            speed_kmph=45,
        )
    return catalog


def print_routes(planner: MultiRoutePlanner, incident_id: str, unit_type: str, top_n: int = 6) -> None:
    target = incident_node(incident_id)
    unit_type = unit_type.strip().lower()
    if unit_type not in {"truck", "ambulance"}:
        raise ValueError("unit_type must be truck or ambulance")

    speed = 35 if unit_type == "truck" else 45
    routes = planner.build_route_catalog(
        station_nodes=station_node_map(),
        incident_node=target,
        unit_type=unit_type,
        top_k_per_station=3,
        speed_kmph=speed,
    )
    print(f"\nTop routes for {incident_id.upper()} ({unit_type}):")
    for i, route in enumerate(routes[:top_n], start=1):
        print(
            f"  {i}. {route.route_name:<30} dist={route.distance_km:>4.1f} km "
            f"eta={route.travel_minutes:>4.1f} min path={'->'.join(route.path)}"
        )


def cmd_dispatch(
    world: WorldStateDB,
    planner: MultiRoutePlanner,
    coordinator: DispatchCoordinator,
    incident_id: str,
    req: Dict[str, int],
) -> None:
    if req.get("truck", 0) == 0 and req.get("ambulance", 0) == 0:
        print("Nothing to dispatch. Use truck=<n> and/or ambulance=<n>.")
        return
    catalog = build_catalog(planner, incident_id, req)
    orders = coordinator.dispatch_incident(
        incident_id=incident_id.upper(),
        requirements=req,
        route_catalog=catalog,
        on_scene_minutes=10,
    )
    print(f"\nDispatch created for {incident_id.upper()}:")
    for order in orders:
        print(
            f"  #{order['dispatch_id']} {order['unit_type']} from {order['station_name']} "
            f"source={order['source']} route={order['route_name']}"
        )


def cmd_dispatch_text(
    world: WorldStateDB,
    planner: MultiRoutePlanner,
    coordinator: DispatchCoordinator,
    pop_model: PopulationDensityModel | None,
    text: str,
) -> None:
    parsed = parse_incident_text(text)

    lat, lon, display_name = geocode_location(str(parsed.get("location") or ""))
    population_affected, zipcode = estimate_population(pop_model, parsed, lat, lon)
    parsed["population_affected"] = population_affected

    incident_id = pick_incident_id(parsed)
    req = infer_requirements(parsed, population_affected)
    priority = calculate_priority(
        float(parsed.get("severity_score") or 3.0),
        float(population_affected),
        float(parsed.get("response_time_minutes") or 10.0),
    )

    print("\nParsed incident:")
    print(f"  text: {text}")
    print(f"  disaster_type: {parsed.get('disaster_type')}")
    print(f"  response_types: {parsed.get('response_types')}")
    print(f"  severity_score: {parsed.get('severity_score')}")
    print(f"  location_text: {parsed.get('location') or '(not found)'}")
    if lat is not None and lon is not None:
        print(f"  geocoded: ({lat:.5f}, {lon:.5f})")
        if display_name:
            print(f"  geocode_match: {display_name}")
    else:
        print("  geocoded: (not found)")
    if zipcode:
        print(f"  zipcode: {zipcode}")
    print(f"  population_affected: {population_affected}")
    print(f"  priority_score: {priority:.2f}")
    print(f"  mapped_incident_node: {incident_id}")
    print(f"  dispatch_requirements: trucks={req['truck']} ambulances={req['ambulance']}")

    cmd_dispatch(world, planner, coordinator, incident_id, req)


def cmd_advance(world: WorldStateDB, minutes: int) -> None:
    if minutes <= 0:
        print("Advance minutes must be > 0")
        return
    print(f"\nAdvancing {minutes} minute(s)...")
    for _ in range(minutes):
        world.advance_time(1)
        print_snapshot(world)


def cmd_feedback(world: WorldStateDB, incident_id: str, unit_type: str, predicted: int, actual: int) -> None:
    unit_type = unit_type.strip().lower()
    if unit_type not in {"truck", "ambulance", "car"}:
        raise ValueError("unit_type must be truck, ambulance, or car")
    world.record_feedback(incident_id.upper(), unit_type, predicted_units=predicted, actual_units=actual)
    print(
        f"Feedback recorded: incident={incident_id.upper()} unit={unit_type} "
        f"predicted={predicted} actual={actual}"
    )


def print_help() -> None:
    print(
        """
Commands:
  help
    Show this help.

  status
    Show world state snapshot (clock, inventory, active dispatches).

  routes <incident> <unit_type> [top_n]
    Show route options. Example: routes I2 truck 5

  dispatch <incident> truck=<n> ambulance=<n>
    Create dispatches for an incident. Example: dispatch I1 truck=2 ambulance=1

  dispatch_text <free text>
    Parse text, estimate severity/population/priority, map to route node, and dispatch.
    Example: dispatch_text major fire at 410 s morgan st many people hurt

  advance <minutes>
    Move simulation clock forward and print update every minute.

  feedback <incident> <unit_type> <predicted> <actual>
    Record outcome feedback. Example: feedback I1 truck 2 3

  reset
    Clear station inventory and reseed defaults.

*** Traffic-aware routing & hazard detection (requires MAPBOX_ACCESS_TOKEN) ***

  fetch-hazards [days=7] [category=fires] [save=file.json]
    Fetch active EONET disaster events.
    Example: fetch-hazards days=14 category=fires save=hazards.json

  route-unit --from lon,lat --to lon,lat
    Get traffic-aware route with ETA using Mapbox driving-traffic profile.
    Example: route-unit --from -87.65,41.88 --to -87.62,41.90

  recommend-dispatch --incident lon,lat [--responders file.json] [--no-hazards]
    Get dispatch recommendation for incident with traffic ETA and hazard scoring.
    Example: recommend-dispatch --incident -87.628,41.885

  exit
    Quit CLI.
""".strip()
    )


def reset_world(world: WorldStateDB) -> None:
    world.conn.execute("DELETE FROM feedback_events")
    world.conn.execute("DELETE FROM dispatches")
    world.conn.execute("DELETE FROM station_inventory")
    world.conn.execute("DELETE FROM stations")
    world.conn.execute("UPDATE world_meta SET value='0' WHERE key='clock_minute'")
    world.conn.commit()
    seed_if_empty(world)


def run_demo(world: WorldStateDB, planner: MultiRoutePlanner, coordinator: DispatchCoordinator) -> None:
    print("\nRunning proof demo sequence...")
    print_snapshot(world)
    print_routes(planner, "I1", "truck", top_n=4)
    cmd_dispatch(world, planner, coordinator, "I1", {"truck": 2, "ambulance": 1})
    print_snapshot(world)
    cmd_advance(world, 8)
    cmd_dispatch(world, planner, coordinator, "I2", {"truck": 1, "ambulance": 1})
    print_snapshot(world)
    cmd_feedback(world, "I1", "truck", 2, 3)
    print("Demo complete.")


def run_model_demo(
    world: WorldStateDB,
    planner: MultiRoutePlanner,
    coordinator: DispatchCoordinator,
    pop_model: PopulationDensityModel | None,
) -> None:
    print("\nRunning parser+population integrated demo...")
    cmd_dispatch_text(
        world,
        planner,
        coordinator,
        pop_model,
        "major fire at 410 s morgan st lots of people hurt need ambulance quickly",
    )
    print_snapshot(world)
    cmd_advance(world, 6)


# ============================================================================
# New commands for Mapbox traffic-aware routing & EONET hazard detection
# ============================================================================

def cmd_fetch_hazards(days: int = 7, category: str = "", save_file: str = "") -> None:
    """
    Fetch and display active EONET disaster events.
    
    Usage:
      fetch-hazards [days=7] [category=fires] [save=hazards.json]
    """
    if not MAPBOX_AVAILABLE:
        print("[ERROR] Mapbox/EONET modules not available")
        return

    eonet = EONETService()
    filters = {"status": "open"}
    if days > 0:
        filters["days"] = days
    if category:
        filters["category"] = category

    print(f"\n[INFO] Fetching active EONET events{' in category=' + category if category else ''}...")
    events = eonet.fetch_events(**filters)

    if not events:
        print("No active events found.")
        return

    print(f"\nFound {len(events)} active event(s):")
    for i, event in enumerate(events, 1):
        num_geoms = len(event.geometries)
        print(f"  {i}. {event.title}")
        print(f"     Category: {event.category}")
        print(f"     Closed: {event.closed}")
        print(f"     Geometries: {num_geoms}")
        if event.sources:
            print(f"     Sources: {len(event.sources)}")

    if save_file:
        try:
            data = [e.to_dict() for e in events]
            with open(save_file, "w") as f:
                __import__("json").dump(data, f, indent=2, default=str)
            print(f"\n[OK] Saved {len(events)} event(s) to {save_file}")
        except Exception as e:
            print(f"[ERROR] Failed to save: {e}")


def cmd_route_unit(from_coords: str, to_coords: str) -> None:
    """
    Calculate traffic-aware route between two locations using Mapbox.
    
    Usage:
      route-unit --from lon,lat --to lon,lat
    
    Example:
      route-unit --from -87.65,41.88 --to -87.62,41.90
    """
    if not MAPBOX_AVAILABLE:
        print("[ERROR] Mapbox module not available")
        return

    try:
        from_parts = from_coords.split(",")
        to_parts = to_coords.split(",")
        
        from_lon, from_lat = float(from_parts[0]), float(from_parts[1])
        to_lon, to_lat = float(to_parts[0]), float(to_parts[1])
    except (ValueError, IndexError):
        print("Usage: route-unit --from lon,lat --to lon,lat")
        print("Example: route-unit --from -87.65,41.88 --to -87.62,41.90")
        return

    mapbox = MapboxService()
    print(f"\n[INFO] Computing traffic route from ({from_lon},{from_lat}) to ({to_lon},{to_lat})...")
    
    route = mapbox.get_traffic_route(from_lon, from_lat, to_lon, to_lat)

    if route.found:
        print(f"[OK] Route found:")
        print(f"  Distance: {route.distance_meters / 1000:.2f} km ({route.distance_meters:.0f}m)")
        print(f"  Duration: {route.duration_minutes:.1f} minutes ({route.duration_seconds:.0f}s)")
        print(f"  ETA: {route.duration_minutes:.1f} min")
    else:
        print(f"[ERROR] Route not found: {route.error}")


def cmd_recommend_dispatch(
    incident_coords: str,
    responders_file: str = "",
    use_hazards: bool = True,
) -> None:
    """
    Get dispatch recommendation for an incident using traffic ETA and hazards.
    
    Usage:
      recommend-dispatch --incident lon,lat [--responders file.json] [--no-hazards]
    
    Responders JSON format:
      [
        {"id": "e1", "name": "Engine-1", "lon": -87.65, "lat": 41.88},
        {"id": "a2", "name": "Ambulance-2", "lon": -87.62, "lat": 41.90}
      ]
    """
    if not MAPBOX_AVAILABLE:
        print("[ERROR] Mapbox/EONET modules not available")
        return

    # Parse incident coords
    try:
        incident_parts = incident_coords.split(",")
        incident_lon = float(incident_parts[0])
        incident_lat = float(incident_parts[1])
    except (ValueError, IndexError):
        print("Usage: recommend-dispatch --incident lon,lat [--responders file.json]")
        return

    # Load responders
    responders = []
    if responders_file:
        try:
            with open(responders_file, "r") as f:
                responders = __import__("json").load(f)
            print(f"[OK] Loaded {len(responders)} responder(s) from {responders_file}")
        except Exception as e:
            print(f"[ERROR] Failed to load responders: {e}")
            return
    else:
        # Use demo responders from existing world state
        responders = [
            {"id": "e1", "name": "Engine-1", "lon": -87.650, "lat": 41.880},
            {"id": "a2", "name": "Ambulance-2", "lon": -87.620, "lat": 41.900},
            {"id": "e3", "name": "Engine-3", "lon": -87.600, "lat": 41.850},
        ]
        print(f"[INFO] Using {len(responders)} demo responders")

    # Get recommendation
    helper = DispatchHelper()
    valid, msg = helper.validate_responders(responders)
    if not valid:
        print(f"[ERROR] Invalid responders: {msg}")
        return

    print(f"\n[INFO] Computing dispatch recommendation for ({incident_lon},{incident_lat})...")
    rec = helper.recommend_dispatch(
        incident_id="incident_001",
        incident_lon=incident_lon,
        incident_lat=incident_lat,
        responders=responders,
        include_hazards=use_hazards,
    )

    # Print results
    print(f"\n[RECOMMENDATION]")
    if rec.best_responder:
        print(f"  Best: {rec.best_responder.responder_name}")
        print(f"  ETA: {rec.best_responder.eta_minutes:.1f} minutes")
        print(f"  Distance: {rec.best_responder.distance_meters / 1000:.2f} km")
        print(f"  Score: {rec.best_responder.score:.0f}")
        if rec.best_responder.near_hazard:
            print(f"  [WARNING] Near active hazard!")
    else:
        print("  (No responders available)")

    if rec.hazards_nearby:
        print(f"\nNearby hazards ({len(rec.hazards_nearby)}):")
        for hazard in rec.hazards_nearby:
            print(f"  - {hazard.title} ({hazard.category})")

    print(f"\nAll candidates (sorted by score):")
    print(f"  {'Responder':<15} {'ETA (min)':>10} {'Distance (km)':>15} {'Score':>10} {'Hazard':>10}")
    print(f"  {'-'*15} {'-'*10} {'-'*15} {'-'*10} {'-'*10}")
    for rank in rec.all_ranked:
        hazard_flag = "YES" if rank.near_hazard else "no"
        print(
            f"  {rank.responder_name:<15} {rank.eta_minutes:>10.1f} "
            f"{rank.distance_meters/1000:>15.2f} {rank.score:>10.0f} {hazard_flag:>10}"
        )


def parse_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="World-state dispatch CLI")
    parser.add_argument(
        "--db",
        default=str(Path(__file__).resolve().parent.parent / "tests" / "world_state_cli.sqlite3"),
        help="Path to sqlite db file",
    )
    parser.add_argument("--fresh", action="store_true", help="Reset world-state before starting")
    parser.add_argument("--demo", action="store_true", help="Run automatic proof demo then continue interactive")
    parser.add_argument("--model-demo", action="store_true", help="Run parser/population integrated demo then continue interactive")
    parser.add_argument("--text", default="", help="One-shot text dispatch input")
    parser.add_argument("--advance-after", type=int, default=0, help="Advance time N minutes after --text dispatch")
    parser.add_argument("--no-interactive", action="store_true", help="Exit after one-shot/demo commands")
    return parser.parse_args()


def main() -> None:
    args = parse_cli_args()
    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    world = WorldStateDB(str(db_path))
    planner = MultiRoutePlanner(build_demo_graph())
    coordinator = DispatchCoordinator(world)
    pop_model = init_population_model()

    try:
        if args.fresh:
            reset_world(world)
        else:
            seed_if_empty(world)

        print("\nDispatch CLI ready")
        print(f"DB: {db_path}")
        print("Type 'help' for commands.")

        if args.demo:
            run_demo(world, planner, coordinator)

        if args.model_demo:
            run_model_demo(world, planner, coordinator, pop_model)

        if args.text.strip():
            cmd_dispatch_text(world, planner, coordinator, pop_model, args.text.strip())
            if args.advance_after > 0:
                cmd_advance(world, args.advance_after)
            print_snapshot(world)

        if args.no_interactive:
            return

        while True:
            raw = input("\nws> ").strip()
            if not raw:
                continue

            if raw.lower().startswith("dispatch_text "):
                text = raw[len("dispatch_text "):].strip()
                if not text:
                    print("Usage: dispatch_text <free text>")
                    continue
                try:
                    cmd_dispatch_text(world, planner, coordinator, pop_model, text)
                except Exception as exc:
                    print(f"Command error: {exc}")
                continue

            # Handle traffic-aware commands with special parsing
            if raw.lower().startswith("fetch-hazards"):
                try:
                    parts = raw.split()
                    days = 7
                    category = ""
                    save_file = ""
                    
                    for part in parts[1:]:
                        if "=" in part:
                            k, v = part.split("=", 1)
                            if k == "days":
                                days = int(v)
                            elif k == "category":
                                category = v
                            elif k == "save":
                                save_file = v
                    
                    cmd_fetch_hazards(days, category, save_file)
                except Exception as exc:
                    print(f"Command error: {exc}")
                continue

            if raw.lower().startswith("route-unit"):
                try:
                    parts = raw.split()
                    from_coords = ""
                    to_coords = ""
                    
                    i = 1
                    while i < len(parts):
                        if parts[i] == "--from" and i + 1 < len(parts):
                            from_coords = parts[i + 1]
                            i += 2
                        elif parts[i] == "--to" and i + 1 < len(parts):
                            to_coords = parts[i + 1]
                            i += 2
                        else:
                            i += 1
                    
                    if not from_coords or not to_coords:
                        print("Usage: route-unit --from lon,lat --to lon,lat")
                        continue
                    
                    cmd_route_unit(from_coords, to_coords)
                except Exception as exc:
                    print(f"Command error: {exc}")
                continue

            if raw.lower().startswith("recommend-dispatch"):
                try:
                    parts = raw.split()
                    incident_coords = ""
                    responders_file = ""
                    use_hazards = True
                    
                    i = 1
                    while i < len(parts):
                        if parts[i] == "--incident" and i + 1 < len(parts):
                            incident_coords = parts[i + 1]
                            i += 2
                        elif parts[i] == "--responders" and i + 1 < len(parts):
                            responders_file = parts[i + 1]
                            i += 2
                        elif parts[i] == "--no-hazards":
                            use_hazards = False
                            i += 1
                        else:
                            i += 1
                    
                    if not incident_coords:
                        print("Usage: recommend-dispatch --incident lon,lat [--responders file.json] [--no-hazards]")
                        continue
                    
                    cmd_recommend_dispatch(incident_coords, responders_file, use_hazards)
                except Exception as exc:
                    print(f"Command error: {exc}")
                continue

            parts = raw.split()
            cmd = parts[0].lower()

            try:
                if cmd == "help":
                    print_help()
                elif cmd == "status":
                    print_snapshot(world)
                elif cmd == "routes":
                    if len(parts) < 3:
                        print("Usage: routes <incident> <unit_type> [top_n]")
                        continue
                    top_n = int(parts[3]) if len(parts) >= 4 else 6
                    print_routes(planner, parts[1], parts[2], top_n)
                elif cmd == "dispatch":
                    if len(parts) < 2:
                        print("Usage: dispatch <incident> truck=<n> ambulance=<n>")
                        continue
                    req = parse_requirements(parts[2:])
                    cmd_dispatch(world, planner, coordinator, parts[1], req)
                elif cmd == "advance":
                    if len(parts) != 2:
                        print("Usage: advance <minutes>")
                        continue
                    cmd_advance(world, int(parts[1]))
                elif cmd == "feedback":
                    if len(parts) != 5:
                        print("Usage: feedback <incident> <unit_type> <predicted> <actual>")
                        continue
                    cmd_feedback(world, parts[1], parts[2], int(parts[3]), int(parts[4]))
                elif cmd == "reset":
                    reset_world(world)
                    print("World state reset and reseeded.")
                elif cmd in {"exit", "quit"}:
                    print("Exiting CLI.")
                    break
                else:
                    print(f"Unknown command: {cmd}. Type 'help'.")
            except Exception as exc:
                print(f"Command error: {exc}")
    finally:
        world.close()


if __name__ == "__main__":
    main()
