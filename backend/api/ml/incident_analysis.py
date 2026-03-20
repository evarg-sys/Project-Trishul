from __future__ import annotations

import json
import importlib
import math
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib import request

from django.db.utils import OperationalError, ProgrammingError

from .text_priority_parser import parse_incident_text
from ..models import FireStation, Hospital


_SPACY_NLP = None
_ENSEMBLE_DETECTOR = None


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


def _default_response_types(category: str) -> list[str]:
    return {
        "fire": ["fire"],
        "flood": ["ambulance", "fire"],
        "earthquake": ["ambulance", "fire", "police"],
        "traffic_collision": ["ambulance", "fire", "police"],
        "chemical": ["fire", "ambulance", "police"],
        "medical": ["ambulance"],
        "unknown": ["ambulance"],
    }.get(str(category or "unknown").lower(), ["ambulance"])


def _load_ensemble_detector():
    global _ENSEMBLE_DETECTOR
    if _ENSEMBLE_DETECTOR is not None:
        return _ENSEMBLE_DETECTOR

    try:
        from .disaster_detection import DisasterEnsembleSystem
    except Exception:
        return None

    try:
        model_dir = str(Path(__file__).parent / "disaster_models")
        _ENSEMBLE_DETECTOR = DisasterEnsembleSystem(model_dir=model_dir)
    except Exception:
        _ENSEMBLE_DETECTOR = None
    return _ENSEMBLE_DETECTOR


def _load_spacy_model():
    global _SPACY_NLP
    if _SPACY_NLP is not None:
        return _SPACY_NLP

    try:
        spacy_module = importlib.import_module("spacy")
    except Exception:
        return None

    try:
        _SPACY_NLP = spacy_module.load("en_core_web_sm")
    except Exception:
        _SPACY_NLP = None
    return _SPACY_NLP


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return r * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


def _extract_vehicle_count(text: str) -> int:
    lowered = text.lower()
    match = re.search(r"\b(\d{1,3})\s*(?:car|cars|vehicle|vehicles|truck|trucks)\b", lowered)
    if match:
        return int(match.group(1))
    if re.search(r"\bmulti[-\s]?vehicle\b", lowered):
        return 4
    return 0


def _classify_rule_based(text: str) -> dict[str, Any]:
    lowered = text.lower()
    vehicle_count = _extract_vehicle_count(lowered)

    traffic_hit = bool(
        re.search(
            r"\b(?:pile[-\s]?up|collision|crash|rollover|accident|car crash|vehicle crash)\b",
            lowered,
        )
    )
    if traffic_hit and (vehicle_count >= 2 or "pile" in lowered):
        confidence = 90.0 if vehicle_count >= 5 else 82.0
        return {
            "incident_category": "traffic_collision",
            "confidence": confidence,
            "reason": "multi_vehicle_collision_pattern",
            "vehicle_count": vehicle_count,
        }

    if any(token in lowered for token in ("chemical", "hazmat", "toxic", "gas leak", "fumes")):
        return {
            "incident_category": "chemical",
            "confidence": 80.0,
            "reason": "chemical_hazard_keywords",
            "vehicle_count": vehicle_count,
        }

    if any(token in lowered for token in ("fire", "blaze", "burning", "flames", "wildfire")):
        return {
            "incident_category": "fire",
            "confidence": 76.0,
            "reason": "fire_keywords",
            "vehicle_count": vehicle_count,
        }

    if any(token in lowered for token in ("flood", "flooding", "inundation", "water rising")):
        return {
            "incident_category": "flood",
            "confidence": 74.0,
            "reason": "flood_keywords",
            "vehicle_count": vehicle_count,
        }

    if any(token in lowered for token in ("earthquake", "quake", "tremor", "seismic")):
        return {
            "incident_category": "earthquake",
            "confidence": 72.0,
            "reason": "earthquake_keywords",
            "vehicle_count": vehicle_count,
        }

    return {
        "incident_category": "unknown",
        "confidence": 35.0,
        "reason": "no_strong_rule_match",
        "vehicle_count": vehicle_count,
    }


def _classify_hf_api(text: str) -> dict[str, Any] | None:
    token = os.getenv("HF_API_TOKEN")
    if not token:
        return None

    url = "https://api-inference.huggingface.co/models/facebook/bart-large-mnli"
    labels = [
        "traffic collision",
        "fire",
        "flood",
        "earthquake",
        "chemical spill",
        "medical emergency",
    ]
    payload = {
        "inputs": text,
        "parameters": {
            "candidate_labels": labels,
            "multi_label": False,
        },
    }

    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=4) as response:
            body = response.read().decode("utf-8")
        parsed = json.loads(body)
        top_label = (parsed.get("labels") or [""])[0]
        top_score = float((parsed.get("scores") or [0.0])[0])
    except Exception:
        return None

    mapping = {
        "traffic collision": "traffic_collision",
        "fire": "fire",
        "flood": "flood",
        "earthquake": "earthquake",
        "chemical spill": "chemical",
        "medical emergency": "medical",
    }
    return {
        "incident_category": mapping.get(top_label, "unknown"),
        "confidence": round(top_score * 100.0, 2),
        "reason": "huggingface_api",
    }


def _classify_ml_ensemble(text: str) -> dict[str, Any] | None:
    detector = _load_ensemble_detector()
    if detector is None:
        return None

    try:
        result = detector.detect(text, return_all_models=True)
    except Exception:
        return None

    if not result.get("detected"):
        return None

    predicted = str(result.get("disaster_type") or "unknown").lower()
    category_map = {
        "chemical_spill": "chemical",
        "medical_emergency": "medical",
    }
    category = category_map.get(predicted, predicted)
    if category not in {"fire", "flood", "earthquake", "traffic_collision", "chemical", "medical"}:
        category = "unknown"
    response_types = _normalize_response_types(result.get("response_types") or _default_response_types(category))

    return {
        "incident_category": category,
        "confidence": float(result.get("confidence") or 0.0),
        "severity": float(result.get("severity") or 3.0),
        "reason": "ensemble_ml",
        "confidence_level": result.get("confidence_level"),
        "agreement": result.get("agreement"),
        "response_types": response_types,
        "primary_response": response_types[0] if response_types else "ambulance",
    }


def _extract_entities_spacy(text: str) -> dict[str, Any]:
    nlp = _load_spacy_model()
    if not nlp:
        return {"entities": [], "method": "none"}

    doc = nlp(text)
    entities = [{"text": ent.text, "label": ent.label_} for ent in doc.ents]
    return {"entities": entities, "method": "spacy"}


def analyze_incident_text(text: str) -> dict[str, Any]:
    source_text = (text or "").strip()
    parsed = parse_incident_text(source_text)
    rule = _classify_rule_based(source_text)
    hf = _classify_hf_api(source_text)
    ml = _classify_ml_ensemble(source_text)
    entity_data = _extract_entities_spacy(source_text)

    selected = rule
    method = "rule"
    if ml:
        selected = ml
        method = "ensemble_ml"
        if hf and hf.get("confidence", 0.0) > ml.get("confidence", 0.0) + 8:
            selected = hf
            method = "huggingface_api"
    elif hf and hf.get("confidence", 0.0) > rule.get("confidence", 0.0):
        selected = hf
        method = "huggingface_api"

    category = selected.get("incident_category", "unknown")
    if rule.get("incident_category") == "traffic_collision":
        category = "traffic_collision"
    disaster_type = parsed.get("disaster_type", "fire")
    if category in {"fire", "flood", "earthquake"}:
        disaster_type = category

    response_types = _normalize_response_types(parsed.get("response_types") or [])
    if selected.get("response_types"):
        response_types = _normalize_response_types(selected.get("response_types"))
    if category in {"traffic_collision", "chemical", "earthquake"}:
        response_types = _normalize_response_types(response_types + _default_response_types(category))
    if not response_types:
        response_types = _default_response_types(category)
    response_type = response_types[0]

    severity = float(parsed.get("severity_score", 3.0))
    if ml and ml.get("severity") is not None:
        severity = max(severity, float(ml.get("severity") or severity))
    if category == "traffic_collision":
        severity = min(5.0, max(severity, 3.6 + (rule.get("vehicle_count", 0) / 10.0)))
    elif category == "chemical":
        severity = min(5.0, max(severity, 4.2))

    confidence = float(selected.get("confidence", 40.0))
    confidence_level = "high" if confidence >= 70 else "medium" if confidence >= 50 else "low"

    return {
        "raw_text": source_text,
        "incident_category": category,
        "disaster_type": disaster_type,
        "response_type": response_type,
        "response_types": response_types,
        "severity_score": round(severity, 2),
        "population_affected": int(parsed.get("population_affected", 0)),
        "response_time_minutes": float(parsed.get("response_time_minutes", 10.0)),
        "location": parsed.get("location", ""),
        "vehicle_count": int(rule.get("vehicle_count", 0)),
        "confidence": round(confidence, 2),
        "confidence_level": confidence_level,
        "parser_method": method,
        "parser_reason": selected.get("reason", "unknown"),
        "ml_detection": ml or {},
        "entities": entity_data.get("entities", []),
    }


def build_capability_requirements(analysis: dict[str, Any]) -> dict[str, Any]:
    category = analysis.get("incident_category") or analysis.get("disaster_type") or "unknown"
    severity = float(analysis.get("severity_score") or 3.0)
    population = int(analysis.get("population_affected") or 0)
    vehicle_count = int(analysis.get("vehicle_count") or 0)

    by_category = {
        "fire": {"engine": 1, "ladder": 1, "chief": 1, "ems": 1},
        "flood": {"rescue_boat": 1, "high_water_vehicle": 1, "ems": 1},
        "chemical": {"hazmat_team": 1, "police_perimeter": 1, "ems": 1},
        "traffic_collision": {"ems": 1, "rescue_team": 1, "police_perimeter": 1},
        "earthquake": {"rescue_team": 1, "chief": 1, "ems": 1},
    }

    required_roles = deepcopy(by_category.get(category, {"ems": 1}))

    if category == "traffic_collision" and vehicle_count >= 5:
        required_roles["ems"] = max(required_roles.get("ems", 1), 2)
    if severity >= 4.4:
        required_roles["ems"] = max(required_roles.get("ems", 1), 2)
    if population >= 500:
        required_roles["engine"] = max(required_roles.get("engine", 0), 2)

    return {
        "incident_category": category,
        "response_types": _default_response_types(category),
        "required_roles": required_roles,
        "policy_basis": {
            "severity": severity,
            "population": population,
            "vehicle_count": vehicle_count,
        },
    }


def _nearest_fire_stations(latitude: float | None, longitude: float | None) -> list[dict[str, Any]]:
    stations = []
    try:
        queryset = FireStation.objects.filter(operational=True, available_trucks__gt=0)
    except (OperationalError, ProgrammingError):
        return []

    try:
        iterator = list(queryset)
    except (OperationalError, ProgrammingError):
        return []

    for station in iterator:
        if latitude is not None and longitude is not None:
            distance = round(_haversine_km(latitude, longitude, station.latitude, station.longitude), 3)
        else:
            distance = None
        stations.append(
            {
                "id": station.id,
                "name": station.name,
                "distance_km": distance,
                "available_trucks": station.available_trucks,
            }
        )

    return sorted(stations, key=lambda item: item["distance_km"] if item["distance_km"] is not None else 1e9)


def _nearest_hospitals(latitude: float | None, longitude: float | None) -> list[dict[str, Any]]:
    hospitals = []
    try:
        queryset = Hospital.objects.filter(operational=True, available_ambulances__gt=0)
    except (OperationalError, ProgrammingError):
        return []

    try:
        iterator = list(queryset)
    except (OperationalError, ProgrammingError):
        return []

    for hospital in iterator:
        if latitude is not None and longitude is not None:
            distance = round(_haversine_km(latitude, longitude, hospital.latitude, hospital.longitude), 3)
        else:
            distance = None
        hospitals.append(
            {
                "id": hospital.id,
                "name": hospital.name,
                "distance_km": distance,
                "available_ambulances": hospital.available_ambulances,
            }
        )

    return sorted(hospitals, key=lambda item: item["distance_km"] if item["distance_km"] is not None else 1e9)


def match_eligible_units(
    requirements: dict[str, Any],
    latitude: float | None,
    longitude: float | None,
) -> dict[str, Any]:
    required_roles = requirements.get("required_roles", {})
    fire_units = _nearest_fire_stations(latitude, longitude)
    ems_units = _nearest_hospitals(latitude, longitude)

    role_to_source = {
        "engine": "fire",
        "ladder": "fire",
        "chief": "fire",
        "rescue_team": "fire",
        "high_water_vehicle": "fire",
        "hazmat_team": "fire",
        "ems": "hospital",
    }

    eligible_units: dict[str, list[dict[str, Any]]] = {}
    gaps: list[dict[str, Any]] = []

    for role, required_count in required_roles.items():
        source = role_to_source.get(role)
        if source == "fire":
            selected = fire_units[:required_count]
        elif source == "hospital":
            selected = ems_units[:required_count]
        else:
            selected = []

        eligible_units[role] = selected

        if len(selected) < required_count:
            gaps.append(
                {
                    "role": role,
                    "required": required_count,
                    "available": len(selected),
                    "reason": "no_local_resource" if source is None else "insufficient_units",
                }
            )

    return {
        "eligible_units": eligible_units,
        "gaps": gaps,
        "available_summary": {
            "fire_units": len(fire_units),
            "hospitals": len(ems_units),
        },
    }


def evaluate_exception_policy(
    analysis: dict[str, Any],
    requirements: dict[str, Any],
    matches: dict[str, Any],
) -> dict[str, Any]:
    required_roles = requirements.get("required_roles", {})
    eligible_units = matches.get("eligible_units", {})
    gaps = matches.get("gaps", [])
    confidence = float(analysis.get("confidence") or 0.0)
    incident_category = analysis.get("incident_category", "unknown")

    low_confidence = confidence < 50.0
    insufficient_units = any(g.get("reason") == "insufficient_units" for g in gaps)
    policy_conflict = any(g.get("reason") == "no_local_resource" for g in gaps)

    alerts: list[dict[str, Any]] = []
    if low_confidence:
        alerts.append({"level": "warning", "code": "low_confidence_input", "message": "Parser confidence is low."})
    if insufficient_units:
        alerts.append({"level": "critical", "code": "not_enough_units", "message": "Not enough local units for required roles."})
    if policy_conflict:
        alerts.append({"level": "critical", "code": "policy_conflict", "message": "Some required roles are unavailable in local policy/resources."})

    minimum_safe_by_category = {
        "fire": {"engine": 1, "ems": 1},
        "flood": {"ems": 1},
        "chemical": {"ems": 1, "police_perimeter": 1},
        "traffic_collision": {"ems": 1},
        "earthquake": {"ems": 1},
        "unknown": {"ems": 1},
    }

    downgraded = low_confidence or insufficient_units or policy_conflict
    minimum_safe = minimum_safe_by_category.get(incident_category, {"ems": 1})

    planned_roles = required_roles if not downgraded else minimum_safe
    final_units = {}
    for role, count in planned_roles.items():
        final_units[role] = (eligible_units.get(role) or [])[:count]

    request_mutual_aid = insufficient_units or policy_conflict
    needs_operator_review = low_confidence or policy_conflict

    return {
        "cases": {
            "low_confidence_input": low_confidence,
            "not_enough_units_available": insufficient_units,
            "policy_conflict": policy_conflict,
        },
        "actions": {
            "downgrade_plan": downgraded,
            "request_mutual_aid": request_mutual_aid,
            "escalate_to_operator_review": needs_operator_review,
        },
        "final_plan": {
            "incident_category": incident_category,
            "required_roles": planned_roles,
            "eligible_units": final_units,
            "notes": "minimum_safe_response" if downgraded else "standard_response",
        },
        "alerts": alerts,
    }


def analyze_and_plan_incident(
    text: str,
    latitude: float | None,
    longitude: float | None,
    population_hint: int | None = None,
) -> dict[str, Any]:
    analysis = analyze_incident_text(text)
    if population_hint is not None:
        analysis["population_affected"] = max(int(population_hint), int(analysis.get("population_affected", 0)))

    requirements = build_capability_requirements(analysis)
    matches = match_eligible_units(requirements, latitude, longitude)
    escalation = evaluate_exception_policy(analysis, requirements, matches)

    return {
        "analysis": analysis,
        "capability_match": {
            "required_roles": requirements.get("required_roles", {}),
            "eligible_units": matches.get("eligible_units", {}),
            "gaps": matches.get("gaps", []),
            "available_summary": matches.get("available_summary", {}),
        },
        "final_plan": escalation.get("final_plan", {}),
        "alerts": escalation.get("alerts", []),
        "actions": escalation.get("actions", {}),
        "cases": escalation.get("cases", {}),
    }
