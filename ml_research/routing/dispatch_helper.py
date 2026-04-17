"""
Dispatch helper with traffic-aware and hazard-aware scoring.

This module combines Mapbox traffic routing and EONET hazard detection
to provide intelligent responder dispatch recommendations.

Scoring logic:
  score = eta_seconds + hazard_penalty
  
Where:
  - eta_seconds: Traffic-aware travel time from responder to incident
  - hazard_penalty: Time-in-seconds equivalent penalty for proximity to active disasters
  
A lower score is better (recommend the responder with lowest score).
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import json

from mapbox_service import MapboxService, ResponderRanking
from eonet_service import EONETService, NormalizedEvent


@dataclass
class DispatchRecommendation:
    """Complete dispatch recommendation for an incident."""
    incident_id: str
    incident_lon: float
    incident_lat: float
    best_responder: Optional[ResponderRanking] = None
    all_ranked: List[ResponderRanking] = None
    hazards_nearby: List[NormalizedEvent] = None
    hazard_distance_km: Optional[float] = None
    score_breakdown: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.all_ranked is None:
            self.all_ranked = []
        if self.hazards_nearby is None:
            self.hazards_nearby = []


class DispatchHelper:
    """
    Dispatcher that recommends responders based on traffic ETA and hazard proximity.
    
    Usage:
        helper = DispatchHelper()
        
        # Get recommendation
        rec = helper.recommend_dispatch(
            incident_lon=-87.6280,
            incident_lat=41.8850,
            responders=[
                {"id": "e1", "name": "Engine-1", "lon": -87.65, "lat": 41.88},
                {"id": "a2", "name": "Ambulance-2", "lon": -87.62, "lat": 41.90},
            ]
        )
        
        print(f"Dispatch {rec.best_responder.responder_name}")
    """

    def __init__(
        self,
        mapbox_token: Optional[str] = None,
        hazard_radius_km: float = 5.0,
        hazard_penalty_factor: float = 1.0,
    ):
        """
        Initialize dispatch helper.
        
        Args:
            mapbox_token: Mapbox API token (optional, reads from env if not provided)
            hazard_radius_km: Radius to search for EONET hazards
            hazard_penalty_factor: Multiplier for hazard penalties (default 1.0)
        """
        self.mapbox = MapboxService(token=mapbox_token)
        self.eonet = EONETService()
        self.hazard_radius_km = hazard_radius_km
        self.hazard_penalty_factor = hazard_penalty_factor

    def recommend_dispatch(
        self,
        incident_id: str,
        incident_lon: float,
        incident_lat: float,
        responders: List[Dict[str, Any]],
        include_hazards: bool = True,
        hazard_status: str = "open",
    ) -> DispatchRecommendation:
        """
        Get dispatch recommendation for an incident.
        
        Args:
            incident_id: Incident identifier (for logging/reference)
            incident_lon: Incident longitude
            incident_lat: Incident latitude
            responders: List of responder dicts with:
                - id: unique responder ID
                - name: responder name/callsign
                - lon: current longitude
                - lat: current latitude
            include_hazards: Whether to fetch and consider EONET hazards
            hazard_status: EONET event status filter ("open" for active)
        
        Returns:
            DispatchRecommendation with ranking and best choice
        """
        # Fetch hazards if requested
        hazards = []
        if include_hazards:
            hazards = self.eonet.fetch_events(status=hazard_status)

        # Rank responders
        rankings = self.mapbox.rank_responders(
            incident_lon=incident_lon,
            incident_lat=incident_lat,
            responders=responders,
            hazard_zones=[
                {"geometries": h.geometries}
                for h in hazards
            ] if hazards else None,
        )

        # Find nearby hazards for context
        nearby_hazards = self.eonet.get_nearby_hazards(
            incident_lon, incident_lat, hazards, self.hazard_radius_km
        )
        hazard_objs = [h[0] for h in nearby_hazards]
        hazard_min_dist = nearby_hazards[0][1] if nearby_hazards else None

        best = rankings[0] if rankings else None

        rec = DispatchRecommendation(
            incident_id=incident_id,
            incident_lon=incident_lon,
            incident_lat=incident_lat,
            best_responder=best,
            all_ranked=rankings,
            hazards_nearby=hazard_objs,
            hazard_distance_km=hazard_min_dist,
            score_breakdown=self._explain_score(best) if best else None,
        )

        return rec

    def validate_responders(self, responders: List[Dict[str, Any]]) -> Tuple[bool, str]:
        """
        Validate responder list format.
        
        Returns:
            (is_valid, error_message)
        """
        if not responders:
            return False, "Responder list is empty"

        for idx, r in enumerate(responders):
            required = {"id", "name", "lon", "lat"}
            missing = required - set(r.keys())
            if missing:
                return False, f"Responder {idx}: missing fields {missing}"

            try:
                float(r["lon"])
                float(r["lat"])
            except (ValueError, TypeError):
                return False, f"Responder {idx}: invalid coordinates"

        return True, ""

    def _explain_score(self, ranking: ResponderRanking) -> Dict[str, Any]:
        """Return breakdown of score components."""
        return {
            "responder_id": ranking.responder_id,
            "responder_name": ranking.responder_name,
            "eta_seconds": ranking.eta_seconds,
            "eta_minutes": ranking.eta_minutes,
            "distance_meters": ranking.distance_meters,
            "hazard_penalty_seconds": ranking.hazard_penalty,
            "total_score": ranking.score,
            "near_hazard": ranking.near_hazard,
        }


class DispatchBatcher:
    """
    Batch processor for multiple incidents.
    Useful for scenario planning and comparing dispatch strategies.
    """

    def __init__(self, helper: DispatchHelper):
        """Initialize with a DispatchHelper instance."""
        self.helper = helper

    def dispatch_multiple(
        self,
        incidents: List[Dict[str, Any]],
        responders: List[Dict[str, Any]],
    ) -> List[DispatchRecommendation]:
        """
        Get recommendations for multiple incidents.
        
        Args:
            incidents: List of dicts with:
                - id: incident ID
                - lon: longitude
                - lat: latitude
            responders: Shared responder pool
        
        Returns:
            List of DispatchRecommendation
        """
        recommendations = []
        for incident in incidents:
            rec = self.helper.recommend_dispatch(
                incident_id=incident["id"],
                incident_lon=incident["lon"],
                incident_lat=incident["lat"],
                responders=responders,
            )
            recommendations.append(rec)

        return recommendations

    def simulate_dispatch_allocation(
        self,
        incidents: List[Dict[str, Any]],
        responders: List[Dict[str, Any]],
        max_allocation_per_responder: int = 2,
    ) -> Dict[str, Any]:
        """
        Simulate dispatch allocation for multiple incidents with limited resources.
        
        This is a simple greedy algorithm: repeatedly assign the best available
        responder from the pool, then mark as allocated.
        
        Args:
            incidents: List of incident dicts
            responders: Pool of available responders
            max_allocation_per_responder: How many incidents per responder
        
        Returns:
            Dict with allocation mapping and stats
        """
        allocations = {}  # incident_id -> [responder_ids]
        responder_load = {r["id"]: 0 for r in responders}

        for incident in sorted(incidents, key=lambda x: x.get("priority", 0), reverse=True):
            incident_id = incident["id"]
            allocated_for_incident = []

            # Rank all responders for this incident
            rankings = self.helper.mapbox.rank_responders(
                incident_lon=incident["lon"],
                incident_lat=incident["lat"],
                responders=responders,
            )

            # Assign best available responder
            for ranking in rankings:
                if responder_load[ranking.responder_id] < max_allocation_per_responder:
                    allocated_for_incident.append(ranking.responder_id)
                    responder_load[ranking.responder_id] += 1
                    break

            allocations[incident_id] = allocated_for_incident

        return {
            "allocations": allocations,
            "responder_load": responder_load,
        }


def quick_recommend(
    incident_lon: float,
    incident_lat: float,
    responders: List[Dict[str, Any]],
) -> DispatchRecommendation:
    """Quick one-shot dispatch recommendation."""
    helper = DispatchHelper()
    return helper.recommend_dispatch(
        incident_id="incident_001",
        incident_lon=incident_lon,
        incident_lat=incident_lat,
        responders=responders,
    )


if __name__ == "__main__":
    # Example usage
    import sys

    helper = DispatchHelper()

    # Validate responders
    responders = [
        {"id": "e1", "name": "Engine-1", "lon": -87.650, "lat": 41.880},
        {"id": "a2", "name": "Ambulance-2", "lon": -87.620, "lat": 41.900},
        {"id": "e3", "name": "Engine-3", "lon": -87.600, "lat": 41.850},
    ]

    valid, msg = helper.validate_responders(responders)
    if not valid:
        print(f"Invalid responders: {msg}")
        sys.exit(1)

    # Get recommendation
    rec = helper.recommend_dispatch(
        incident_id="fire_001",
        incident_lon=-87.6280,
        incident_lat=41.8850,
        responders=responders,
        include_hazards=True,
    )

    print(f"\n=== Dispatch Recommendation ===")
    print(f"Incident: {rec.incident_id} at ({rec.incident_lon}, {rec.incident_lat})")
    
    if rec.best_responder:
        print(f"\nBest choice: {rec.best_responder.responder_name}")
        print(f"  ETA: {rec.best_responder.eta_minutes:.1f} minutes")
        print(f"  Distance: {rec.best_responder.distance_meters:.0f} meters")
        print(f"  Score: {rec.best_responder.score:.0f}")
    else:
        print("No responders available")

    if rec.hazards_nearby:
        print(f"\nNearby hazards ({len(rec.hazards_nearby)}):")
        for hazard in rec.hazards_nearby:
            print(f"  - {hazard.title} ({hazard.category})")

    print(f"\nAll candidates (sorted by score):")
    for rank in rec.all_ranked:
        hazard_flag = " [NEAR HAZARD]" if rank.near_hazard else ""
        print(f"  {rank.responder_name:<15} ETA: {rank.eta_minutes:>5.1f}m Score: {rank.score:>7.0f}{hazard_flag}")
