#!/usr/bin/env python
"""Single-run comprehensive test for world-state + multi-routing dispatch."""

import os
import sqlite3
import sys
from pathlib import Path

import networkx as nx


sys.path.insert(0, str(Path(__file__).parent.parent))

from routing.world_state_dispatch import DispatchCoordinator
from routing.world_state_dispatch import MultiRoutePlanner
from routing.world_state_dispatch import WorldStateDB


def _build_demo_graph() -> nx.Graph:
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
    ]
    for u, v, dist in edges:
        graph.add_edge(u, v, distance_km=dist)
    return graph


def _print_snapshot(title: str, snapshot: dict) -> None:
    print(f"\n{title}")
    print("-" * 80)
    print(f"Clock minute: {snapshot['clock_minute']}")
    print("Station inventory:")
    for station, units in snapshot["stations"].items():
        truck = units.get("truck", {"available": 0, "total": 0})
        amb = units.get("ambulance", {"available": 0, "total": 0})
        car = units.get("car", {"available": 0, "total": 0})
        print(
            f"  {station} | trucks {truck['available']}/{truck['total']} | "
            f"ambulances {amb['available']}/{amb['total']} | cars {car['available']}/{car['total']}"
        )

    print("Active dispatches:")
    if not snapshot["active_dispatches"]:
        print("  (none)")
    else:
        for d in snapshot["active_dispatches"]:
            print(
                f"  #{d['id']} {d['unit_type']} from {d['station_name']} "
                f"[{d['source_kind']}] status={d['status']} rem={d['remaining_minutes']:.1f}m "
                f"route={d['route_name']} incident={d['incident_id']}"
            )


def run_single_comprehensive_test() -> None:
    print("\n" + "=" * 88)
    print(" WORLD STATE + MULTI ROUTING + LIVE DISPATCH TEST ".center(88))
    print("=" * 88)

    db_file = Path(__file__).parent / "world_state_test.sqlite3"
    if db_file.exists():
        db_file.unlink()

    world = WorldStateDB(str(db_file))
    try:
        print("\n[STEP 1] Build world state database")
        world.upsert_station("Central", trucks=3, ambulances=2, cars=4)
        world.upsert_station("North", trucks=3, ambulances=2, cars=3)
        world.upsert_station("South", trucks=2, ambulances=1, cars=2)

        initial = world.get_live_snapshot()
        _print_snapshot("Initial world-state", initial)

        print("\n[STEP 2] Build multi-route catalog")
        graph = _build_demo_graph()
        planner = MultiRoutePlanner(graph)
        station_nodes = {"Central": "S1", "North": "S2", "South": "C"}

        incident_1_truck_routes = planner.build_route_catalog(
            station_nodes=station_nodes,
            incident_node="I1",
            unit_type="truck",
            top_k_per_station=2,
            speed_kmph=35,
        )
        incident_1_amb_routes = planner.build_route_catalog(
            station_nodes=station_nodes,
            incident_node="I1",
            unit_type="ambulance",
            top_k_per_station=2,
            speed_kmph=45,
        )

        assert len(incident_1_truck_routes) >= 3, "Expected multiple truck routes"
        assert len(incident_1_amb_routes) >= 3, "Expected multiple ambulance routes"

        print(f"  truck routes generated: {len(incident_1_truck_routes)}")
        print(f"  ambulance routes generated: {len(incident_1_amb_routes)}")
        print("  top truck options:")
        for route in incident_1_truck_routes[:4]:
            print(
                f"    {route.route_name} | {route.distance_km:.2f} km | "
                f"ETA {route.travel_minutes:.2f} min"
            )

        print("\n[STEP 3] Dispatch incident I1 with multiple units")
        coordinator = DispatchCoordinator(world)
        i1_orders = coordinator.dispatch_incident(
            incident_id="I1",
            requirements={"truck": 2, "ambulance": 1},
            route_catalog={
                "truck": incident_1_truck_routes,
                "ambulance": incident_1_amb_routes,
            },
            on_scene_minutes=10,
        )
        print(f"  dispatch count: {len(i1_orders)}")
        for order in i1_orders:
            print(
                f"    dispatch #{order['dispatch_id']} | {order['unit_type']} | "
                f"source={order['source']} | station={order['station_name']} | "
                f"route={order['route_name']}"
            )

        snap_after_i1 = world.get_live_snapshot()
        _print_snapshot("After I1 dispatch", snap_after_i1)

        print("\n[STEP 4] Advance time so units are in returning phase")
        world.advance_time(15)
        mid_snap = world.get_live_snapshot()
        _print_snapshot("After +15 minutes", mid_snap)

        print("\n[STEP 5] Dispatch incident I2 and allow returning-unit diversion")
        incident_2_truck_routes = planner.build_route_catalog(
            station_nodes=station_nodes,
            incident_node="I2",
            unit_type="truck",
            top_k_per_station=2,
            speed_kmph=35,
        )
        incident_2_amb_routes = planner.build_route_catalog(
            station_nodes=station_nodes,
            incident_node="I2",
            unit_type="ambulance",
            top_k_per_station=2,
            speed_kmph=45,
        )

        i2_orders = coordinator.dispatch_incident(
            incident_id="I2",
            requirements={"truck": 1, "ambulance": 1},
            route_catalog={
                "truck": incident_2_truck_routes,
                "ambulance": incident_2_amb_routes,
            },
            on_scene_minutes=8,
        )

        diverted_count = sum(1 for o in i2_orders if o["source"] == "returning_unit")
        print(f"  dispatch count: {len(i2_orders)}")
        print(f"  diverted returning units: {diverted_count}")
        for order in i2_orders:
            print(
                f"    dispatch #{order['dispatch_id']} | {order['unit_type']} | "
                f"source={order['source']} | station={order['station_name']} | "
                f"route={order['route_name']}"
            )

        assert len(i2_orders) == 2, "I2 should dispatch one truck and one ambulance"
        assert diverted_count >= 1, "Expected at least one diverted returning unit"

        print("\n[STEP 6] Record outcome feedback and finish timeline")
        world.record_feedback("I1", "truck", predicted_units=2, actual_units=3)
        world.record_feedback("I2", "ambulance", predicted_units=1, actual_units=1)
        world.advance_time(40)

        final_snap = world.get_live_snapshot()
        _print_snapshot("Final state", final_snap)

        assert len(final_snap["active_dispatches"]) == 0, "All units should be back by end"
        assert final_snap["stations"]["Central"]["truck"]["available"] <= final_snap["stations"]["Central"]["truck"]["total"]

        conn = sqlite3.connect(str(db_file))
        try:
            feedback_rows = conn.execute("SELECT COUNT(*) FROM feedback_events").fetchone()[0]
            assert feedback_rows == 2, "Expected 2 feedback events"
            print(f"  feedback records: {feedback_rows}")
        finally:
            conn.close()

        print("\n" + "=" * 88)
        print(" TEST PASSED: world state, multi-routing, live dispatch, return diversion ")
        print("=" * 88 + "\n")

    finally:
        world.close()


if __name__ == "__main__":
    try:
        run_single_comprehensive_test()
    except Exception as exc:
        print(f"\nTEST FAILED: {exc}")
        raise
