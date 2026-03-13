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
from pathlib import Path
from typing import Any, Optional

from .priority_model import calculate_priority
from .text_priority_parser import parse_incident_text
from .population_model import PopulationDensityModel

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
        response_type = self._choose_response_type(parsed, disaster_type)
        severity_score = self._choose_severity(parsed, detection)

        population_affected, population_meta = self._estimate_population(coords, parsed)
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
                "severity_score": round(float(severity_score), 3),
                "population_affected": int(population_affected),
                "response_time_minutes": round(float(response_time_minutes), 3),
                "priority_score": round(float(priority_score), 4),
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

    def _choose_severity(self, parsed: dict[str, Any], detection: dict[str, Any]) -> float:
        parsed_severity = float(parsed.get("severity_score", 3.0))
        detected_severity = detection.get("severity")
        if detected_severity is None:
            return parsed_severity
        try:
            return max(parsed_severity, float(detected_severity))
        except Exception:
            return parsed_severity

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