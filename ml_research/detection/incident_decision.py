from __future__ import annotations

import re
from copy import deepcopy
from typing import Any


def derive_incident_category(text: str, detected_type: str | None) -> dict[str, Any]:
    lowered = (text or "").lower()
    vehicle_match = re.search(r"\b(\d{1,3})\s*(?:car|cars|vehicle|vehicles|truck|trucks)\b", lowered)
    vehicle_count = int(vehicle_match.group(1)) if vehicle_match else 0

    if re.search(r"\b(?:pile[-\s]?up|collision|crash|rollover|accident|multi[-\s]?vehicle)\b", lowered):
        if vehicle_count >= 2 or "pile" in lowered:
            return {"incident_category": "traffic_collision", "vehicle_count": vehicle_count}

    if any(token in lowered for token in ("chemical", "hazmat", "toxic", "gas leak", "fumes")):
        return {"incident_category": "chemical", "vehicle_count": vehicle_count}

    if detected_type in {"fire", "flood", "earthquake"}:
        return {"incident_category": detected_type, "vehicle_count": vehicle_count}

    return {"incident_category": "unknown", "vehicle_count": vehicle_count}


def build_capability_requirements(
    incident_category: str,
    severity: float,
    confidence: float,
    vehicle_count: int,
) -> dict[str, Any]:
    by_category = {
        "fire": {"engine": 1, "ladder": 1, "chief": 1, "ems": 1},
        "flood": {"rescue_boat": 1, "high_water_vehicle": 1, "ems": 1},
        "chemical": {"hazmat_team": 1, "police_perimeter": 1, "ems": 1},
        "traffic_collision": {"ems": 1, "rescue_team": 1, "police_perimeter": 1},
        "earthquake": {"rescue_team": 1, "chief": 1, "ems": 1},
    }

    required_roles = deepcopy(by_category.get(incident_category, {"ems": 1}))
    if incident_category == "traffic_collision" and vehicle_count >= 5:
        required_roles["ems"] = max(required_roles.get("ems", 1), 2)
    if severity >= 4.4:
        required_roles["ems"] = max(required_roles.get("ems", 1), 2)

    low_confidence = confidence < 50
    minimum_safe = {"ems": 1}

    final_roles = minimum_safe if low_confidence else required_roles
    actions = {
        "downgrade_plan": low_confidence,
        "request_mutual_aid": False,
        "escalate_to_operator_review": low_confidence,
    }

    alerts = []
    if low_confidence:
        alerts.append(
            {
                "level": "warning",
                "code": "low_confidence_input",
                "message": "Parser confidence is low.",
            }
        )

    return {
        "required_roles": required_roles,
        "final_plan": {
            "incident_category": incident_category,
            "required_roles": final_roles,
            "notes": "minimum_safe_response" if low_confidence else "standard_response",
        },
        "actions": actions,
        "cases": {
            "low_confidence_input": low_confidence,
            "not_enough_units_available": False,
            "policy_conflict": False,
        },
        "alerts": alerts,
    }
