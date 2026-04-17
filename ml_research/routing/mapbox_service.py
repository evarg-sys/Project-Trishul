"""
Mapbox traffic-aware routing service.

This module provides traffic-aware route calculations using the Mapbox Directions API.
It's designed to integrate with the dispatch CLI for real-time ETA calculations.

Required environment variables:
  - MAPBOX_ACCESS_TOKEN: Your Mapbox API token
"""

import os
import asyncio
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import json

try:
    import aiohttp
except ImportError:
    aiohttp = None

import requests


@dataclass
class RouteResult:
    """Result from Mapbox traffic routing."""
    found: bool
    distance_meters: float = 0.0
    duration_seconds: float = 0.0
    duration_minutes: float = 0.0
    route_geometry: Optional[Dict[str, Any]] = None
    route_legs: List[Dict[str, Any]] = None
    error: Optional[str] = None

    def __post_init__(self):
        if self.route_legs is None:
            self.route_legs = []


@dataclass
class ResponderRanking:
    """Ranked responder with dispatch score."""
    responder_id: str
    responder_name: str
    distance_meters: float
    eta_seconds: float
    eta_minutes: float
    hazard_penalty: float = 0.0
    score: float = 0.0  # eta_seconds + hazard_penalty
    near_hazard: bool = False


class MapboxService:
    """
    Client for Mapbox Directions API with traffic profile.
    
    Usage:
        service = MapboxService()
        route = service.get_traffic_route(
            origin_lon=-87.6298,
            origin_lat=41.8781,
            dest_lon=-87.6200,
            dest_lat=41.9000
        )
        if route.found:
            print(f"ETA: {route.duration_minutes:.1f} minutes")
    """

    def __init__(self, token: Optional[str] = None):
        """
        Initialize Mapbox service.
        
        Args:
            token: Mapbox API token (defaults to MAPBOX_ACCESS_TOKEN env var)
        """
        self.token = token or os.environ.get("MAPBOX_ACCESS_TOKEN")
        if not self.token:
            raise ValueError(
                "MAPBOX_ACCESS_TOKEN not found. "
                "Set via environment variable or pass as argument."
            )
        self.base_url = "https://api.mapbox.com/directions/v5/mapbox"
        self.session = None

    def get_traffic_route(
        self,
        origin_lon: float,
        origin_lat: float,
        dest_lon: float,
        dest_lat: float,
        alternatives: bool = False,
        steps: bool = True,
        geometries: str = "geojson",
    ) -> RouteResult:
        """
        Get traffic-aware route using driving-traffic profile.
        
        Args:
            origin_lon: Origin longitude
            origin_lat: Origin latitude
            dest_lon: Destination longitude
            dest_lat: Destination latitude
            alternatives: Return alternative routes (default False)
            steps: Include turn-by-turn steps (default True)
            geometries: GeoJSON format (default "geojson")
        
        Returns:
            RouteResult with route details and metadata
        """
        # Validate coordinates
        if not self._validate_coords(origin_lon, origin_lat, dest_lon, dest_lat):
            return RouteResult(
                found=False,
                error="Invalid coordinates provided"
            )

        try:
            # Build URL: /driving-traffic/lon1,lat1;lon2,lat2
            coords = f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
            url = f"{self.base_url}/driving-traffic/{coords}"

            params = {
                "access_token": self.token,
                "alternatives": str(alternatives).lower(),
                "steps": str(steps).lower(),
                "geometries": geometries,
                "overview": "full",
                "annotations": "congestion,distance,duration",
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Check for route results
            if data.get("code") != "Ok" or not data.get("routes"):
                return RouteResult(
                    found=False,
                    error=f"Mapbox error: {data.get('message', 'No routes found')}"
                )

            # Extract primary route
            route = data["routes"][0]
            distance_m = route["distance"]
            duration_s = route["duration"]

            return RouteResult(
                found=True,
                distance_meters=distance_m,
                duration_seconds=duration_s,
                duration_minutes=duration_s / 60.0,
                route_geometry=route.get("geometry"),
                route_legs=route.get("legs", []),
            )

        except requests.exceptions.Timeout:
            return RouteResult(
                found=False,
                error="Mapbox API request timed out"
            )
        except requests.exceptions.RequestException as e:
            return RouteResult(
                found=False,
                error=f"Mapbox API error: {str(e)}"
            )
        except (KeyError, ValueError) as e:
            return RouteResult(
                found=False,
                error=f"Failed to parse Mapbox response: {str(e)}"
            )

    def rank_responders(
        self,
        incident_lon: float,
        incident_lat: float,
        responders: List[Dict[str, Any]],
        hazard_zones: Optional[List[Dict[str, Any]]] = None,
    ) -> List[ResponderRanking]:
        """
        Rank responders by distance and hazard proximity.
        
        This is a synchronous wrapper. For better performance with many responders,
        consider using rank_responders_async.
        
        Args:
            incident_lon: Incident location longitude
            incident_lat: Incident location latitude
            responders: List of responder dicts with keys:
                - id: Responder unique ID
                - name: Responder name/callsign
                - lon: Current longitude
                - lat: Current latitude
            hazard_zones: Optional list of EONET hazard geometries
        
        Returns:
            List of ResponderRanking sorted by score (best first)
        """
        rankings = []

        for responder in responders:
            try:
                responder_id = responder["id"]
                responder_name = responder["name"]
                resp_lon = responder["lon"]
                resp_lat = responder["lat"]

                # Get route from responder to incident
                route = self.get_traffic_route(
                    origin_lon=resp_lon,
                    origin_lat=resp_lat,
                    dest_lon=incident_lon,
                    dest_lat=incident_lat,
                )

                if not route.found:
                    # If route fails, use straight-line estimate
                    route = self._fallback_route(resp_lon, resp_lat, incident_lon, incident_lat)

                # Calculate hazard penalty
                hazard_penalty = 0.0
                near_hazard = False
                if hazard_zones:
                    hazard_penalty, near_hazard = self._calculate_hazard_penalty(
                        route, incident_lon, incident_lat, hazard_zones
                    )

                # Score = ETA + hazard penalty (lower is better)
                score = route.duration_seconds + hazard_penalty

                rankings.append(ResponderRanking(
                    responder_id=responder_id,
                    responder_name=responder_name,
                    distance_meters=route.distance_meters,
                    eta_seconds=route.duration_seconds,
                    eta_minutes=route.duration_minutes,
                    hazard_penalty=hazard_penalty,
                    score=score,
                    near_hazard=near_hazard,
                ))

            except (KeyError, TypeError) as e:
                print(f"Warning: Failed to process responder {responder}: {e}")
                continue

        # Sort by score (ascending = best first)
        rankings.sort(key=lambda r: r.score)
        return rankings

    async def rank_responders_async(
        self,
        incident_lon: float,
        incident_lat: float,
        responders: List[Dict[str, Any]],
        hazard_zones: Optional[List[Dict[str, Any]]] = None,
    ) -> List[ResponderRanking]:
        """
        Async version of rank_responders for faster processing of many responders.
        
        Requires aiohttp. Falls back to sync version if unavailable.
        
        Args:
            incident_lon: Incident location longitude
            incident_lat: Incident location latitude
            responders: List of responder dicts (see rank_responders)
            hazard_zones: Optional list of EONET hazard geometries
        
        Returns:
            List of ResponderRanking sorted by score (best first)
        """
        if aiohttp is None:
            print("[WARN] aiohttp not installed, falling back to sync ranking")
            return self.rank_responders(incident_lon, incident_lat, responders, hazard_zones)

        rankings = []
        tasks = []

        async with aiohttp.ClientSession() as session:
            for responder in responders:
                task = self._rank_responder_async(
                    session, incident_lon, incident_lat, responder, hazard_zones
                )
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    print(f"[WARN] Async responder ranking failed: {result}")
                    continue
                if result:
                    rankings.append(result)

        rankings.sort(key=lambda r: r.score)
        return rankings

    async def _rank_responder_async(
        self,
        session: Any,
        incident_lon: float,
        incident_lat: float,
        responder: Dict[str, Any],
        hazard_zones: Optional[List[Dict[str, Any]]],
    ) -> Optional[ResponderRanking]:
        """Helper for async responder ranking."""
        try:
            responder_id = responder["id"]
            responder_name = responder["name"]
            resp_lon = responder["lon"]
            resp_lat = responder["lat"]

            coords = f"{resp_lon},{resp_lat};{incident_lon},{incident_lat}"
            url = f"{self.base_url}/driving-traffic/{coords}"

            params = {
                "access_token": self.token,
                "alternatives": "false",
                "steps": "false",
                "geometries": "geojson",
                "overview": "full",
                "annotations": "congestion,distance,duration",
            }

            async with session.get(url, params=params, timeout=10) as response:
                data = await response.json()

                if data.get("code") != "Ok" or not data.get("routes"):
                    route = self._fallback_route(resp_lon, resp_lat, incident_lon, incident_lat)
                else:
                    r = data["routes"][0]
                    route = RouteResult(
                        found=True,
                        distance_meters=r["distance"],
                        duration_seconds=r["duration"],
                        duration_minutes=r["duration"] / 60.0,
                        route_geometry=r.get("geometry"),
                        route_legs=r.get("legs", []),
                    )

                hazard_penalty = 0.0
                near_hazard = False
                if hazard_zones:
                    hazard_penalty, near_hazard = self._calculate_hazard_penalty(
                        route, incident_lon, incident_lat, hazard_zones
                    )

                score = route.duration_seconds + hazard_penalty

                return ResponderRanking(
                    responder_id=responder_id,
                    responder_name=responder_name,
                    distance_meters=route.distance_meters,
                    eta_seconds=route.duration_seconds,
                    eta_minutes=route.duration_minutes,
                    hazard_penalty=hazard_penalty,
                    score=score,
                    near_hazard=near_hazard,
                )

        except Exception as e:
            print(f"[WARN] Async responder ranking failed: {e}")
            return None

    def _calculate_hazard_penalty(
        self,
        route: RouteResult,
        incident_lon: float,
        incident_lat: float,
        hazard_zones: List[Dict[str, Any]],
    ) -> Tuple[float, bool]:
        """
        Calculate hazard penalty based on proximity to EONET events.
        
        Returns:
            (hazard_penalty_seconds, is_near_hazard)
        """
        penalty = 0.0
        near_hazard = False

        for hazard in hazard_zones:
            geom = hazard.get("geometries", [])
            if not geom:
                continue

            # Check if incident is near hazard
            dist_to_hazard = self._distance_to_hazard(
                incident_lon, incident_lat, geom[0] if geom else {}
            )

            # Penalty if within 5km
            if dist_to_hazard < 5000:
                near_hazard = True
                # Scale penalty: closer = higher penalty
                # At 0m: +300s, at 5000m: +30s
                penalty += max(30, 300 - (dist_to_hazard / 5000) * 270)

        return penalty, near_hazard

    def _distance_to_hazard(self, lon: float, lat: float, geom: Dict[str, Any]) -> float:
        """
        Approximate distance from point to hazard geometry.
        
        For Point: Euclidean distance
        For other: distance to centroid/bounding box
        """
        geom_type = geom.get("type", "").lower()

        if geom_type == "point":
            coords = geom.get("coordinates", [0, 0])
            return self._haversine_distance(lon, lat, coords[0], coords[1])

        # For polygons/multipolygons, use centroid approximation
        coords = geom.get("coordinates", [])
        if coords:
            try:
                # Flatten all coordinates
                all_points = self._flatten_coords(coords)
                if all_points:
                    # Use centroid
                    avg_lon = sum(p[0] for p in all_points) / len(all_points)
                    avg_lat = sum(p[1] for p in all_points) / len(all_points)
                    return self._haversine_distance(lon, lat, avg_lon, avg_lat)
            except (TypeError, IndexError):
                pass

        return float('inf')

    def _flatten_coords(self, coords: List[Any]) -> List[Tuple[float, float]]:
        """Recursively flatten nested coordinate arrays."""
        result = []
        for item in coords:
            if isinstance(item, (list, tuple)):
                if len(item) == 2 and isinstance(item[0], float):
                    result.append((item[0], item[1]))
                else:
                    result.extend(self._flatten_coords(item))
        return result

    @staticmethod
    def _haversine_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        """
        Calculate approximate distance in meters using Haversine formula.
        """
        import math

        R = 6371000  # Earth radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    @staticmethod
    def _validate_coords(lon1: float, lat1: float, lon2: float, lat2: float) -> bool:
        """Validate coordinate ranges."""
        for lon, lat in [(lon1, lat1), (lon2, lat2)]:
            if not (-180 <= lon <= 180 and -85.051129 <= lat <= 85.051129):
                return False
        return True

    def _fallback_route(self, origin_lon: float, origin_lat: float,
                       dest_lon: float, dest_lat: float) -> RouteResult:
        """
        Fallback estimation when API fails.
        Uses straight-line distance and assumes avg speed of 40 km/h.
        """
        dist_m = self._haversine_distance(origin_lon, origin_lat, dest_lon, dest_lat)
        # Assume 40 km/h = 11.11 m/s
        duration_s = dist_m / 11.11
        return RouteResult(
            found=False,
            distance_meters=dist_m,
            duration_seconds=duration_s,
            duration_minutes=duration_s / 60.0,
            error="Using fallback straight-line estimate"
        )


# Convenience function for quick routing
def quick_route(origin_lon: float, origin_lat: float, dest_lon: float, dest_lat: float) -> RouteResult:
    """Quick one-shot route lookup."""
    service = MapboxService()
    return service.get_traffic_route(origin_lon, origin_lat, dest_lon, dest_lat)


if __name__ == "__main__":
    # Example usage
    import sys

    if "rank" in sys.argv:
        # Example: rank responders
        service = MapboxService()
        responders = [
            {"id": "u1", "name": "Engine-1", "lon": -87.6300, "lat": 41.8800},
            {"id": "u2", "name": "Ambulance-5", "lon": -87.6200, "lat": 41.8700},
        ]
        rankings = service.rank_responders(
            incident_lon=-87.6280,
            incident_lat=41.8850,
            responders=responders,
        )
        for rank in rankings:
            print(f"{rank.responder_name}: {rank.eta_minutes:.1f}m ETA (score: {rank.score:.0f})")
    else:
        # Example: single route
        route = quick_route(
            origin_lon=-87.6300,
            origin_lat=41.8800,
            dest_lon=-87.6280,
            dest_lat=41.8850,
        )
        if route.found:
            print(f"Distance: {route.distance_meters:.0f}m")
            print(f"ETA: {route.duration_minutes:.1f} minutes")
        else:
            print(f"Error: {route.error}")
