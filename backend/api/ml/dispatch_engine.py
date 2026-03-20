"""Unified ML dispatch engine orchestration.

This module integrates the three ML components into one callable workflow:
- text understanding / disaster detection
- population affected estimation
- routing-aware response estimation

Accepted inputs:
- location + description
- parsed_text only
- or explicit latitude/longitude
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Optional

from .priority_model import calculate_priority
from .text_priority_parser import parse_incident_text
from .population_model import PopulationDensityModel


def _normalize_response_types(values: list[str] | tuple[str, ...] | None) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values or []:
        item = str(value or "").strip().lower()
        if not item or item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered

try:
    from geopy.geocoders import Nominatim
except Exception:
    Nominatim = None

try:
    from .disaster_detection import DisasterEnsembleSystem
except Exception:
    DisasterEnsembleSystem = None

try:
    from .disaster_routing import DisasterRouting
except Exception:
    DisasterRouting = None


@dataclass
class EngineConfig:
    city: str = "Chicago, Illinois, USA"
    geocode_bias: str = "Chicago, IL"
    population_radius_meters: int = 700
    response_speed_km_per_min_fire: float = 0.5
    response_speed_km_per_min_ambulance: float = 0.6
    response_buffer_minutes: float = 2.0


class DispatchEngine:
    """Orchestrates ML models into a single dispatch decision payload."""

    def __init__(
        self,
        config: Optional[EngineConfig] = None,
        census_file: str = "chi_pop.csv",
        detector_model_dir: Optional[str] = None,
        preload_road_network: bool = False,
    ) -> None:
        self.config = config or EngineConfig()
        self.geolocator = Nominatim(user_agent="trishul_dispatch_engine_v1", timeout=10) if Nominatim else None

        self.population_model = PopulationDensityModel()
        self.population_model.load_census_data(census_file)

        self.detector = None
        if DisasterEnsembleSystem is not None:
            try:
                model_dir = detector_model_dir or str(Path(__file__).parent / "disaster_models")
                self.detector = DisasterEnsembleSystem(model_dir=model_dir)
            except Exception:
                self.detector = None

        self.routing = None
        if DisasterRouting is not None:
            try:
                self.routing = DisasterRouting(city=self.config.city)
                if preload_road_network:
                    self.routing.load_network("drive")
            except Exception:
                self.routing = None

    def dispatch(
        self,
        *,
        location: Optional[str] = None,
        description: Optional[str] = None,
        parsed_text: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        include_routes: bool = True,
    ) -> dict[str, Any]:
        source_text = (parsed_text or self._compose_text(location=location, description=description)).strip()
        if not source_text and not location and (latitude is None or longitude is None):
            raise ValueError("Provide either parsed_text or (location/description) or explicit latitude+longitude")

        parsed = parse_incident_text(source_text)
        resolved_location = (location or parsed.get("location") or "").strip()

        coords = self._resolve_coordinates(
            location=resolved_location,
            latitude=latitude,
            longitude=longitude,
        )

        detection = self._detect_disaster(source_text)
        disaster_type = self._choose_disaster_type(parsed, detection)
        severity_score = self._choose_severity(parsed, detection)

        population_affected, population_meta = self._estimate_population(coords, parsed)

        planning = self._run_incident_planning(
            text=source_text,
            coords=coords,
            population_hint=population_affected,
        )
        planning_analysis = planning.get("analysis", {}) if planning else {}
        planning_category = planning_analysis.get("incident_category")
        response_types = self._choose_response_types(
            source_text=source_text,
            parsed=parsed,
            detection=detection,
            disaster_type=planning_category or disaster_type,
            planning=planning_analysis,
        )
        response_type = response_types[0] if response_types else self._choose_response_type(parsed, disaster_type)
        planning_severity = planning_analysis.get("severity_score")
        if planning_severity is not None:
            try:
                severity_score = max(float(severity_score), float(planning_severity))
            except Exception:
                pass

        response_time_minutes, routes = self._estimate_response_time_and_routes(
            coords=coords,
            response_type=response_type,
            include_routes=include_routes,
        )

        priority_score = calculate_priority(
            severity=severity_score,
            population=population_affected,
            response_time=response_time_minutes,
        )

        return {
            "input": {
                "location": resolved_location,
                "description": description or "",
                "parsed_text": parsed_text or "",
                "coordinates": {"lat": coords[0], "lon": coords[1]} if coords else None,
            },
            "decision": {
                "disaster_type": disaster_type,
                "response_type": response_type,
                "response_types": response_types,
                "severity_score": round(float(severity_score), 3),
                "population_affected": int(population_affected),
                "response_time_minutes": round(float(response_time_minutes), 3),
                "priority_score": round(float(priority_score), 4),
            },
            "planning": {
                "capability_match": planning.get("capability_match", {}) if planning else {},
                "final_plan": planning.get("final_plan", {}) if planning else {},
                "alerts": planning.get("alerts", []) if planning else [],
                "actions": planning.get("actions", {}) if planning else {},
                "cases": planning.get("cases", {}) if planning else {},
            },
            "models": {
                "parsed": parsed,
                "detection": detection,
                "population": population_meta,
                "routes": routes,
            },
        }

    def _compose_text(self, *, location: Optional[str], description: Optional[str]) -> str:
        parts = []
        if description:
            parts.append(description.strip())
        if location:
            parts.append(f"at {location.strip()}")
        return " ".join(p for p in parts if p)

    def _resolve_coordinates(
        self,
        *,
        location: str,
        latitude: Optional[float],
        longitude: Optional[float],
    ) -> Optional[tuple[float, float]]:
        if latitude is not None and longitude is not None:
            return float(latitude), float(longitude)

        if not location or self.geolocator is None:
            return None

        query = location
        if "chicago" not in location.lower():
            query = f"{location}, {self.config.geocode_bias}"

        try:
            geo = self.geolocator.geocode(query)
            if not geo:
                return None
            return float(geo.latitude), float(geo.longitude)
        except Exception:
            return None

    def _detect_disaster(self, text: str) -> dict[str, Any]:
        if not text:
            return {"detected": False}
        if self.detector is None:
            return {"detected": False, "reason": "detector_unavailable"}
        try:
            return self.detector.detect(text, return_all_models=True)
        except Exception:
            return {"detected": False, "reason": "detector_failed"}

    def _choose_disaster_type(self, parsed: dict[str, Any], detection: dict[str, Any]) -> str:
        detected = (detection or {}).get("disaster_type")
        if detection.get("detected") and detected and str(detected).lower() != "none":
            return str(detected).lower()
        return str(parsed.get("disaster_type") or "fire").lower()

    def _choose_response_type(self, parsed: dict[str, Any], disaster_type: str) -> str:
        response_type = str(parsed.get("response_type") or "").lower().strip()
        if response_type:
            return response_type
        return "fire" if disaster_type == "fire" else "ambulance"

    def _choose_response_types(
        self,
        *,
        source_text: str,
        parsed: dict[str, Any],
        detection: dict[str, Any],
        disaster_type: str,
        planning: dict[str, Any],
    ) -> list[str]:
        planned = _normalize_response_types(planning.get("response_types") or [])
        if planned:
            return planned

        detected = _normalize_response_types(detection.get("response_types") or [])
        if detected:
            return detected

        parsed_responses = _normalize_response_types(parsed.get("response_types") or [])
        if parsed_responses:
            return parsed_responses

        lowered = source_text.lower()
        if any(token in lowered for token in ("pile up", "pile-up", "collision", "crash", "rollover", "accident", "multi-vehicle")):
            return ["ambulance", "fire", "police"]

        mapping = {
            "fire": ["fire"],
            "flood": ["ambulance", "fire"],
            "earthquake": ["ambulance", "fire", "police"],
            "traffic_collision": ["ambulance", "fire", "police"],
            "chemical_spill": ["fire", "ambulance", "police"],
            "medical_emergency": ["ambulance"],
        }
        return mapping.get(str(disaster_type or "").lower(), [self._choose_response_type(parsed, disaster_type)])

    def _choose_severity(self, parsed: dict[str, Any], detection: dict[str, Any]) -> float:
        parsed_severity = float(parsed.get("severity_score", 3.0))
        detected_severity = detection.get("severity")
        if detected_severity is None:
            return parsed_severity
        try:
            return max(parsed_severity, float(detected_severity))
        except Exception:
            return parsed_severity

    def _run_incident_planning(
        self,
        *,
        text: str,
        coords: Optional[tuple[float, float]],
        population_hint: int,
    ) -> dict[str, Any]:
        self._ensure_django_ready()

        try:
            from .incident_analysis import analyze_and_plan_incident
        except Exception:
            return {}

        try:
            lat = coords[0] if coords else None
            lon = coords[1] if coords else None
            return analyze_and_plan_incident(
                text=text,
                latitude=lat,
                longitude=lon,
                population_hint=population_hint,
            )
        except Exception:
            return {}

    def _ensure_django_ready(self) -> None:
        try:
            from django.apps import apps
        except Exception:
            return

        if apps.ready:
            return

        settings_module = os.environ.get("DJANGO_SETTINGS_MODULE")
        if not settings_module:
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", "disaster_backend.settings")

        try:
            import django
            django.setup()
        except Exception:
            return

    def _estimate_population(
        self,
        coords: Optional[tuple[float, float]],
        parsed: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        if coords is None:
            fallback = int(parsed.get("population_affected") or 0)
            return fallback, {"method": "text_hint", "estimated": fallback}

        try:
            result = self.population_model.estimate_for_location(
                coords[0],
                coords[1],
                radius_meters=self.config.population_radius_meters,
            )
        except Exception:
            result = None

        if result and result.get("total_population") is not None:
            est = int(result["total_population"])
            return est, {
                "method": "population_model",
                "estimated": est,
                "zipcode": result.get("zipcode"),
                "density": result.get("density"),
                "radius_meters": result.get("radius_meters"),
            }

        fallback = int(parsed.get("population_affected") or 0)
        return fallback, {"method": "text_hint_fallback", "estimated": fallback}

    def _estimate_response_time_and_routes(
        self,
        *,
        coords: Optional[tuple[float, float]],
        response_type: str,
        include_routes: bool,
    ) -> tuple[float, dict[str, Any]]:
        default_time = {
            "fire": 10.0,
            "ambulance": 8.0,
            "police": 7.0,
        }.get(response_type, 12.0)

        if not include_routes or coords is None or self.routing is None:
            return default_time, {"method": "default", "routes": []}

        try:
            if self.routing.graph is None:
                self.routing.load_network("drive")

            if response_type == "fire":
                routes = self.routing.generate_fire_routes(coords)
            elif response_type == "ambulance":
                routes = self.routing.generate_ambulance_routes(coords)
            else:
                routes = []

            if not routes:
                return default_time, {"method": "default_no_routes", "routes": []}

            selected = next((r for r in routes if r.get("selected")), routes[0])
            distance_km = float(selected.get("distance_km") or 0)

            speed = (
                self.config.response_speed_km_per_min_fire
                if response_type == "fire"
                else self.config.response_speed_km_per_min_ambulance
            )
            travel = distance_km / max(speed, 0.1)
            eta = self.config.response_buffer_minutes + travel

            return float(eta), {
                "method": "routing_model",
                "selected_route": selected,
                "routes": routes,
            }
        except Exception as exc:
            return default_time, {
                "method": "default_routing_failed",
                "routes": [],
                "error": str(exc),
                "error_type": type(exc).__name__,
            }


def run_dispatch_engine(
    *,
    location: Optional[str] = None,
    description: Optional[str] = None,
    parsed_text: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    include_routes: bool = True,
) -> dict[str, Any]:
    """Convenience single-call function for dispatch engine execution."""
    engine = DispatchEngine()
    return engine.dispatch(
        location=location,
        description=description,
        parsed_text=parsed_text,
        latitude=latitude,
        longitude=longitude,
        include_routes=include_routes,
    )