"""
NASA EONET v3 natural disaster event ingestion service.

This module provides access to active natural disaster events from the NASA
Earth Observatory Natural Event Tracker (EONET) API.

Reference: https://eonet.gsfc.nasa.gov/api/v3/events

Features:
  - Fetch active natural disaster events
  - Filter by status, time range, category, and geographic bounding box
  - Detect if an incident location is near an EONET hazard
  - Normalize event data into simple, usable structures
"""

import os
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import json

import requests


@dataclass
class EventGeometry:
    """A single geometry from an EONET event."""
    geometry_type: str  # point, polygon, etc.
    coordinates: Any  # raw coordinates from EONET


@dataclass
class NormalizedEvent:
    """Simplified EONET event structure."""
    id: str
    title: str
    category: str
    closed: bool
    updated: Optional[str] = None
    geometries: Optional[List[Dict[str, Any]]] = None
    sources: Optional[List[Dict[str, str]]] = None

    def __post_init__(self):
        if self.geometries is None:
            self.geometries = []
        if self.sources is None:
            self.sources = []

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EONETService:
    """
    Client for NASA EONET natural disaster events.
    
    Usage:
        service = EONETService()
        
        # Fetch active fire events
        events = service.fetch_events(category="fires")
        
        # Check if incident is near a hazard
        is_hazard = service.is_near_hazard(
            lon=-87.6280,
            lat=41.8850,
            events=events,
            radius_km=5
        )
    """

    def __init__(self):
        """Initialize EONET service (no API key required)."""
        self.base_url = "https://eonet.gsfc.nasa.gov/api/v3"
        self.session = None

    def fetch_events(
        self,
        status: str = "open",
        category: Optional[str] = None,
        days: Optional[int] = None,
        bbox: Optional[Tuple[float, float, float, float]] = None,
        limit: int = 500,
    ) -> List[NormalizedEvent]:
        """
        Fetch natural disaster events from EONET API.
        
        Args:
            status: Event status ("open" for active, "all" for historical)
            category: Event category filter (e.g., "fires", "floods", "wildfires")
                     See list_categories() for available options
            days: Only events updated in the last N days
            bbox: Bounding box as (min_lon, min_lat, max_lon, max_lat)
            limit: Maximum events to return (default 500)
        
        Returns:
            List of NormalizedEvent objects
        
        Examples:
            # Get all active events
            events = service.fetch_events()
            
            # Get fire events
            events = service.fetch_events(category="fires")
            
            # Get events in Chicago area (last 7 days)
            events = service.fetch_events(
                bbox=(-88.0, 41.7, -87.3, 42.0),
                days=7
            )
        """
        try:
            url = f"{self.base_url}/events"

            params = {"limit": limit}

            if status:
                params["status"] = status
            if category:
                params["category"] = category
            if bbox:
                # Format: min_lon,min_lat,max_lon,max_lat
                params["bbox"] = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"

            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            events = []
            for event in data.get("events", []):
                # Apply days filter manually (API doesn't support it directly)
                if days:
                    updated_str = event.get("updated")
                    if updated_str and not self._is_recent(updated_str, days):
                        continue

                normalized = self._normalize_event(event)
                events.append(normalized)

            return events

        except requests.exceptions.Timeout:
            print("[ERROR] EONET API request timed out")
            return []
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] EONET API error: {e}")
            return []
        except (KeyError, ValueError) as e:
            print(f"[ERROR] Failed to parse EONET response: {e}")
            return []

    def fetch_event_by_id(self, event_id: str) -> Optional[NormalizedEvent]:
        """
        Fetch a specific event by ID.
        
        Args:
            event_id: EONET event ID (e.g., "EONET_4982")
        
        Returns:
            NormalizedEvent or None if not found
        """
        try:
            url = f"{self.base_url}/events/{event_id}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "events" in data and data["events"]:
                return self._normalize_event(data["events"][0])
            return None

        except Exception as e:
            print(f"[ERROR] Failed to fetch event {event_id}: {e}")
            return None

    def list_categories(self) -> Dict[str, str]:
        """
        Get available event categories.
        
        Returns:
            Dict mapping category IDs to description
            Example: {"6": "Fires", "8": "Floods", ...}
        """
        try:
            url = f"{self.base_url}/categories"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            categories = {}
            for cat in data.get("categories", []):
                cat_id = str(cat.get("id"))
                title = cat.get("title", "Unknown")
                categories[cat_id] = title

            return categories

        except Exception as e:
            print(f"[ERROR] Failed to fetch categories: {e}")
            return {}

    def is_near_hazard(
        self,
        lon: float,
        lat: float,
        events: List[NormalizedEvent],
        radius_km: float = 5.0,
    ) -> bool:
        """
        Check if a location is near any EONET hazard.
        
        Args:
            lon: Location longitude
            lat: Location latitude
            events: List of NormalizedEvent to check
            radius_km: Search radius in kilometers
        
        Returns:
            True if location is within radius_km of any event
        """
        for event in events:
            dist = self._distance_to_event(lon, lat, event, radius_km)
            if dist <= radius_km:
                return True
        return False

    def get_nearby_hazards(
        self,
        lon: float,
        lat: float,
        events: List[NormalizedEvent],
        radius_km: float = 5.0,
    ) -> List[Tuple[NormalizedEvent, float]]:
        """
        Get all hazards within radius and their distances.
        
        Args:
            lon: Location longitude
            lat: Location latitude
            events: List of NormalizedEvent to check
            radius_km: Search radius in kilometers
        
        Returns:
            List of (event, distance_km) tuples sorted by distance
        """
        nearby = []
        for event in events:
            dist = self._distance_to_event(lon, lat, event, 999.0)
            if dist <= radius_km:
                nearby.append((event, dist))

        nearby.sort(key=lambda x: x[1])
        return nearby

    def _normalize_event(self, event: Dict[str, Any]) -> NormalizedEvent:
        """Convert raw EONET event to NormalizedEvent."""
        event_id = event.get("id", "unknown")
        title = event.get("title", "Unknown Event")
        
        # Extract category
        categories = event.get("categories", [])
        category = categories[0].get("title", "Other") if categories else "Other"
        
        # Check if closed
        closed = False
        if event.get("closed"):
            closed = True
        
        # Extract geometries
        geometries = []
        geom_data = event.get("geometry", [])
        for geom in geom_data:
            geometries.append({
                "type": geom.get("type", "unknown"),
                "coordinates": geom.get("coordinates"),
                "date": geom.get("date"),
            })

        # Extract sources
        sources = []
        source_data = event.get("sources", [])
        for src in source_data:
            sources.append({
                "id": src.get("id", ""),
                "url": src.get("url", ""),
            })

        return NormalizedEvent(
            id=event_id,
            title=title,
            category=category,
            closed=closed,
            updated=event.get("updated"),
            geometries=geometries,
            sources=sources,
        )

    def _distance_to_event(
        self,
        lon: float,
        lat: float,
        event: NormalizedEvent,
        max_radius: float,
    ) -> float:
        """
        Calculate distance from point to event.
        Returns distance in km, or max_radius+1 if too far.
        """
        min_dist = max_radius + 1

        for geom in event.geometries:
            geom_type = geom.get("type", "").lower()
            coords = geom.get("coordinates")

            if not coords:
                continue

            if geom_type == "point":
                # Point: [lon, lat]
                try:
                    event_lon, event_lat = coords[0], coords[1]
                    dist = self._haversine_distance(lon, lat, event_lon, event_lat)
                    min_dist = min(min_dist, dist)
                except (TypeError, IndexError):
                    continue

            elif geom_type == "polygon":
                # Polygon: [[[lon, lat], [lon, lat], ...]]
                try:
                    ring = coords[0] if coords else []
                    dist = self._distance_to_polygon(lon, lat, ring)
                    min_dist = min(min_dist, dist)
                except (TypeError, IndexError):
                    continue

            elif geom_type == "multipolygon":
                # MultiPolygon: [[[[lon, lat], ...]], [[[lon, lat], ...]]]
                try:
                    for polygon in coords:
                        if polygon:
                            ring = polygon[0] if polygon else []
                            dist = self._distance_to_polygon(lon, lat, ring)
                            min_dist = min(min_dist, dist)
                except (TypeError, IndexError):
                    continue

        return min_dist

    def _distance_to_polygon(
        self,
        lon: float,
        lat: float,
        ring: List[Tuple[float, float]],
    ) -> float:
        """
        Distance from point to polygon.
        Uses centroid for simplicity (approximation).
        """
        if not ring:
            return float('inf')

        try:
            # Calculate centroid
            avg_lon = sum(p[0] for p in ring) / len(ring)
            avg_lat = sum(p[1] for p in ring) / len(ring)
            return self._haversine_distance(lon, lat, avg_lon, avg_lat)
        except (TypeError, IndexError, ZeroDivisionError):
            return float('inf')

    @staticmethod
    def _haversine_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        """
        Distance in kilometers using Haversine formula.
        """
        import math

        R = 6371  # Earth radius in km
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    @staticmethod
    def _is_recent(date_str: str, days: int) -> bool:
        """Check if date string is within N days."""
        try:
            event_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            cutoff = datetime.now(event_date.tzinfo) - timedelta(days=days)
            return event_date >= cutoff
        except (ValueError, AttributeError):
            return False


# Convenience functions
def fetch_active_events(category: Optional[str] = None) -> List[NormalizedEvent]:
    """Quick fetch of active events."""
    service = EONETService()
    return service.fetch_events(status="open", category=category)


def is_incident_near_hazard(
    lon: float,
    lat: float,
    radius_km: float = 5.0,
) -> bool:
    """Quick check if location has nearby active hazards."""
    service = EONETService()
    events = service.fetch_events(status="open")
    return service.is_near_hazard(lon, lat, events, radius_km)


if __name__ == "__main__":
    # Example usage
    import sys

    service = EONETService()

    if "list" in sys.argv:
        # List available categories
        cats = service.list_categories()
        print("Available categories:")
        for cat_id, title in sorted(cats.items()):
            print(f"  {cat_id}: {title}")

    elif "bbox" in sys.argv:
        # Fetch events in Chicago area
        events = service.fetch_events(
            status="open",
            bbox=(-88.0, 41.7, -87.3, 42.0),
        )
        print(f"\nFound {len(events)} active events in Chicago area:")
        for event in events:
            print(f"  - {event.title} ({event.category})")

    else:
        # Fetch all active events
        events = service.fetch_events(status="open")
        print(f"Found {len(events)} active events:")
        for event in events:
            print(f"  - {event.title} ({event.category}) - Closed: {event.closed}")

        if events:
            # Check hazard proximity
            is_hazard = service.is_near_hazard(-87.6280, 41.8850, events, radius_km=500)
            print(f"\nLocation (-87.6280, 41.8850) near hazard: {is_hazard}")
