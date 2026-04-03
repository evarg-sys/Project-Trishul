import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import networkx as nx


@dataclass
class RouteOption:
    unit_type: str
    station_name: str
    route_name: str
    distance_km: float
    travel_minutes: float
    path: List[str]


class WorldStateDB:
    """SQLite-backed world state for live dispatch and resource inventory."""

    def __init__(self, db_path: str):
        self.db_path = str(Path(db_path))
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self.conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS world_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS stations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS station_inventory (
                station_id INTEGER NOT NULL,
                unit_type TEXT NOT NULL,
                total_units INTEGER NOT NULL,
                available_units INTEGER NOT NULL,
                PRIMARY KEY (station_id, unit_type),
                FOREIGN KEY (station_id) REFERENCES stations(id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS dispatches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT NOT NULL,
                unit_type TEXT NOT NULL,
                station_name TEXT,
                source_kind TEXT NOT NULL,
                route_name TEXT,
                distance_km REAL NOT NULL,
                travel_minutes REAL NOT NULL,
                on_scene_minutes REAL NOT NULL,
                return_minutes REAL NOT NULL,
                status TEXT NOT NULL,
                remaining_minutes REAL NOT NULL,
                dispatched_at_minute INTEGER NOT NULL,
                completed_at_minute INTEGER,
                notes TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT NOT NULL,
                unit_type TEXT NOT NULL,
                predicted_units INTEGER NOT NULL,
                actual_units INTEGER NOT NULL,
                dispatch_gap INTEGER NOT NULL,
                recorded_at_minute INTEGER NOT NULL
            )
            """
        )

        cur.execute(
            "INSERT OR IGNORE INTO world_meta(key, value) VALUES('clock_minute', '0')"
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def now(self) -> int:
        row = self.conn.execute(
            "SELECT value FROM world_meta WHERE key='clock_minute'"
        ).fetchone()
        return int(row["value"]) if row else 0

    def _set_now(self, minute: int) -> None:
        self.conn.execute(
            "UPDATE world_meta SET value=? WHERE key='clock_minute'", (str(minute),)
        )

    def upsert_station(self, name: str, trucks: int = 0, ambulances: int = 0, cars: int = 0) -> None:
        self.conn.execute("INSERT OR IGNORE INTO stations(name) VALUES(?)", (name,))
        self.conn.commit()
        self.set_inventory(name, "truck", trucks)
        self.set_inventory(name, "ambulance", ambulances)
        self.set_inventory(name, "car", cars)

    def _station_id(self, station_name: str) -> int:
        row = self.conn.execute(
            "SELECT id FROM stations WHERE name=?", (station_name,)
        ).fetchone()
        if not row:
            raise ValueError(f"Unknown station: {station_name}")
        return int(row["id"])

    def set_inventory(self, station_name: str, unit_type: str, total_units: int, available_units: Optional[int] = None) -> None:
        sid = self._station_id(station_name)
        available = total_units if available_units is None else available_units
        self.conn.execute(
            """
            INSERT INTO station_inventory(station_id, unit_type, total_units, available_units)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(station_id, unit_type)
            DO UPDATE SET total_units=excluded.total_units, available_units=excluded.available_units
            """,
            (sid, unit_type, int(total_units), int(available)),
        )
        self.conn.commit()

    def can_dispatch(self, station_name: str, unit_type: str, units: int = 1) -> bool:
        sid = self._station_id(station_name)
        row = self.conn.execute(
            "SELECT available_units FROM station_inventory WHERE station_id=? AND unit_type=?",
            (sid, unit_type),
        ).fetchone()
        if not row:
            return False
        return int(row["available_units"]) >= units

    def _consume_inventory(self, station_name: str, unit_type: str, units: int) -> None:
        sid = self._station_id(station_name)
        self.conn.execute(
            """
            UPDATE station_inventory
            SET available_units = available_units - ?
            WHERE station_id=? AND unit_type=? AND available_units >= ?
            """,
            (units, sid, unit_type, units),
        )
        if self.conn.total_changes == 0:
            raise ValueError(f"Insufficient {unit_type} at {station_name}")

    def _release_inventory(self, station_name: str, unit_type: str, units: int) -> None:
        sid = self._station_id(station_name)
        self.conn.execute(
            """
            UPDATE station_inventory
            SET available_units = available_units + ?
            WHERE station_id=? AND unit_type=?
            """,
            (units, sid, unit_type),
        )

    def create_dispatch(
        self,
        incident_id: str,
        unit_type: str,
        station_name: str,
        route_name: str,
        distance_km: float,
        travel_minutes: float,
        on_scene_minutes: float,
        return_minutes: float,
        source_kind: str = "station",
        consume_inventory: bool = True,
        notes: str = "",
    ) -> int:
        if consume_inventory:
            self._consume_inventory(station_name, unit_type, 1)

        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO dispatches(
                incident_id, unit_type, station_name, source_kind, route_name,
                distance_km, travel_minutes, on_scene_minutes, return_minutes,
                status, remaining_minutes, dispatched_at_minute, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'outbound', ?, ?, ?)
            """,
            (
                incident_id,
                unit_type,
                station_name,
                source_kind,
                route_name,
                float(distance_km),
                float(travel_minutes),
                float(on_scene_minutes),
                float(return_minutes),
                float(travel_minutes),
                self.now(),
                notes,
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def active_dispatches(self) -> List[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT * FROM dispatches
            WHERE status IN ('outbound', 'on_scene', 'returning')
            ORDER BY id
            """
        ).fetchall()

    def advance_time(self, minutes: int) -> None:
        if minutes <= 0:
            return

        cur = self.conn.cursor()
        current = self.now()

        for _ in range(minutes):
            current += 1
            rows = self.active_dispatches()
            for row in rows:
                remaining = float(row["remaining_minutes"]) - 1.0
                if remaining > 0:
                    cur.execute(
                        "UPDATE dispatches SET remaining_minutes=? WHERE id=?",
                        (remaining, int(row["id"])),
                    )
                    continue

                status = row["status"]
                if status == "outbound":
                    cur.execute(
                        "UPDATE dispatches SET status='on_scene', remaining_minutes=? WHERE id=?",
                        (float(row["on_scene_minutes"]), int(row["id"])),
                    )
                elif status == "on_scene":
                    cur.execute(
                        "UPDATE dispatches SET status='returning', remaining_minutes=? WHERE id=?",
                        (float(row["return_minutes"]), int(row["id"])),
                    )
                elif status == "returning":
                    cur.execute(
                        """
                        UPDATE dispatches
                        SET status='completed', remaining_minutes=0, completed_at_minute=?
                        WHERE id=?
                        """,
                        (current, int(row["id"])),
                    )
                    self._release_inventory(row["station_name"], row["unit_type"], 1)

            self._set_now(current)

        self.conn.commit()

    def find_best_returning_candidate(self, unit_type: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT * FROM dispatches
            WHERE unit_type=? AND status='returning'
            ORDER BY remaining_minutes ASC
            LIMIT 1
            """,
            (unit_type,),
        ).fetchone()

    def divert_returning_unit(
        self,
        dispatch_id: int,
        incident_id: str,
        route_name: str,
        distance_km: float,
        travel_minutes: float,
        on_scene_minutes: float,
        return_minutes: float,
    ) -> int:
        row = self.conn.execute(
            "SELECT * FROM dispatches WHERE id=?", (dispatch_id,)
        ).fetchone()
        if not row or row["status"] != "returning":
            raise ValueError("Dispatch is not in returning state")

        self.conn.execute(
            """
            UPDATE dispatches
            SET status='diverted', completed_at_minute=?, notes=?
            WHERE id=?
            """,
            (self.now(), f"diverted_to:{incident_id}", dispatch_id),
        )

        new_id = self.create_dispatch(
            incident_id=incident_id,
            unit_type=row["unit_type"],
            station_name=row["station_name"],
            route_name=route_name,
            distance_km=distance_km,
            travel_minutes=travel_minutes,
            on_scene_minutes=on_scene_minutes,
            return_minutes=return_minutes,
            source_kind="returning_unit",
            consume_inventory=False,
            notes=f"diverted_from:{dispatch_id}",
        )
        self.conn.commit()
        return new_id

    def get_live_snapshot(self) -> Dict[str, object]:
        stations = {}
        rows = self.conn.execute(
            """
            SELECT s.name, i.unit_type, i.total_units, i.available_units
            FROM stations s
            JOIN station_inventory i ON i.station_id = s.id
            ORDER BY s.name, i.unit_type
            """
        ).fetchall()

        for r in rows:
            stations.setdefault(r["name"], {})[r["unit_type"]] = {
                "total": int(r["total_units"]),
                "available": int(r["available_units"]),
            }

        active = [dict(r) for r in self.active_dispatches()]
        return {
            "clock_minute": self.now(),
            "stations": stations,
            "active_dispatches": active,
        }

    def record_feedback(self, incident_id: str, unit_type: str, predicted_units: int, actual_units: int) -> None:
        gap = int(actual_units) - int(predicted_units)
        self.conn.execute(
            """
            INSERT INTO feedback_events(
                incident_id, unit_type, predicted_units, actual_units, dispatch_gap, recorded_at_minute
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (incident_id, unit_type, int(predicted_units), int(actual_units), gap, self.now()),
        )
        self.conn.commit()


class MultiRoutePlanner:
    """Produces multiple route options from a weighted graph."""

    def __init__(self, graph: nx.Graph):
        self.graph = graph

    def station_routes(
        self,
        station_name: str,
        station_node: str,
        incident_node: str,
        unit_type: str,
        top_k: int = 3,
        speed_kmph: float = 40.0,
    ) -> List[RouteOption]:
        routes: List[RouteOption] = []
        path_iter = nx.shortest_simple_paths(
            self.graph,
            station_node,
            incident_node,
            weight="distance_km",
        )

        for idx, path in enumerate(path_iter):
            if idx >= top_k:
                break

            distance_km = 0.0
            for a, b in zip(path[:-1], path[1:]):
                distance_km += float(self.graph[a][b]["distance_km"])

            travel_minutes = (distance_km / max(speed_kmph, 1e-6)) * 60.0
            routes.append(
                RouteOption(
                    unit_type=unit_type,
                    station_name=station_name,
                    route_name=f"{station_name}:{unit_type}:route_{idx + 1}",
                    distance_km=round(distance_km, 3),
                    travel_minutes=round(travel_minutes, 2),
                    path=list(path),
                )
            )

        return routes

    def build_route_catalog(
        self,
        station_nodes: Dict[str, str],
        incident_node: str,
        unit_type: str,
        top_k_per_station: int = 3,
        speed_kmph: float = 40.0,
    ) -> List[RouteOption]:
        all_routes: List[RouteOption] = []
        for station_name, station_node in station_nodes.items():
            all_routes.extend(
                self.station_routes(
                    station_name=station_name,
                    station_node=station_node,
                    incident_node=incident_node,
                    unit_type=unit_type,
                    top_k=top_k_per_station,
                    speed_kmph=speed_kmph,
                )
            )
        all_routes.sort(key=lambda r: r.travel_minutes)
        return all_routes


class DispatchCoordinator:
    """Dispatch engine that chooses among multiple routes + returning units."""

    def __init__(self, world_state: WorldStateDB):
        self.world_state = world_state

    def dispatch_incident(
        self,
        incident_id: str,
        requirements: Dict[str, int],
        route_catalog: Dict[str, List[RouteOption]],
        on_scene_minutes: float = 20.0,
    ) -> List[Dict[str, object]]:
        orders: List[Dict[str, object]] = []

        for unit_type, required_count in requirements.items():
            options = sorted(route_catalog.get(unit_type, []), key=lambda r: r.travel_minutes)
            if required_count <= 0:
                continue

            for _ in range(required_count):
                if not options:
                    raise ValueError(f"No route options available for {unit_type}")

                best_station_route = None
                for option in options:
                    if self.world_state.can_dispatch(option.station_name, unit_type, 1):
                        best_station_route = option
                        break

                if best_station_route is None:
                    raise ValueError(f"No available {unit_type} inventory for incident {incident_id}")

                returning = self.world_state.find_best_returning_candidate(unit_type)
                use_returning = False

                if returning is not None:
                    # If a returning unit is expected to reach a turn-around point sooner,
                    # divert it directly to the new incident.
                    remaining_return = float(returning["remaining_minutes"])
                    diverted_eta = round(remaining_return * 0.6, 2)
                    use_returning = diverted_eta < best_station_route.travel_minutes

                if use_returning and returning is not None:
                    dispatch_id = self.world_state.divert_returning_unit(
                        dispatch_id=int(returning["id"]),
                        incident_id=incident_id,
                        route_name=f"diverted:{best_station_route.route_name}",
                        distance_km=max(best_station_route.distance_km * 0.6, 0.1),
                        travel_minutes=max(round(float(returning["remaining_minutes"]) * 0.6, 2), 1.0),
                        on_scene_minutes=on_scene_minutes,
                        return_minutes=max(round(best_station_route.travel_minutes * 0.8, 2), 1.0),
                    )
                    orders.append(
                        {
                            "dispatch_id": dispatch_id,
                            "incident_id": incident_id,
                            "unit_type": unit_type,
                            "source": "returning_unit",
                            "station_name": returning["station_name"],
                            "route_name": f"diverted:{best_station_route.route_name}",
                        }
                    )
                else:
                    dispatch_id = self.world_state.create_dispatch(
                        incident_id=incident_id,
                        unit_type=unit_type,
                        station_name=best_station_route.station_name,
                        route_name=best_station_route.route_name,
                        distance_km=best_station_route.distance_km,
                        travel_minutes=best_station_route.travel_minutes,
                        on_scene_minutes=on_scene_minutes,
                        return_minutes=max(best_station_route.travel_minutes, 1.0),
                    )
                    orders.append(
                        {
                            "dispatch_id": dispatch_id,
                            "incident_id": incident_id,
                            "unit_type": unit_type,
                            "source": "station",
                            "station_name": best_station_route.station_name,
                            "route_name": best_station_route.route_name,
                        }
                    )

        return orders