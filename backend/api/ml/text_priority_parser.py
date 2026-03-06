"""Parse free-text incident reports into structured priority inputs."""

from __future__ import annotations

import re


def _extract_location(text: str) -> str:
    # Capture simple phrases like "at 55 W Illinois St".
    m = re.search(r"\b(?:at|near|in)\s+([A-Za-z0-9 ,.-]{5,})", text)
    if not m:
        return ""
    loc = m.group(1)
    # Trim common connectors that usually start description text.
    loc = re.split(
        r"\b(?:and|with|where|need|needs|because|after|while|many|lots|people|injured|hurt|stranded|trapped)\b",
        loc,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    loc = loc.strip(" .,")
    return loc


def _infer_disaster_type(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ("fire", "blaze", "burning", "flames", "wildfire")):
        return "fire"
    if any(k in t for k in ("flood", "flooding", "inundation", "water rising")):
        return "flood"
    if any(k in t for k in ("earthquake", "quake", "tremor", "seismic")):
        return "earthquake"
    return "fire"


def _infer_response_type(text: str, disaster_type: str) -> str:
    t = text.lower()
    if any(k in t for k in ("ambulance", "medical", "paramedic", "injured")):
        return "ambulance"
    if any(k in t for k in ("fire truck", "firefighter", "fire brigade")):
        return "fire"
    if "police" in t:
        return "police"

    # Reasonable default by disaster type.
    if disaster_type == "fire":
        return "fire"
    return "ambulance"


def _extract_population_hint(text: str) -> int:
    t = text.lower()

    # Explicit number references.
    m = re.search(
        r"\b(\d{1,5})\s*(?:people|persons|injured|hurt|trapped|evacuated|casualties)\b",
        t,
    )
    if m:
        value = int(m.group(1))
        return max(20, value)

    if any(k in t for k in ("hundreds", "crowd", "stadium", "festival")):
        return 800
    if any(k in t for k in ("many", "lots of people", "a lot of people", "packed")):
        return 300
    if any(k in t for k in ("few", "small", "single family")):
        return 50
    return 120


def _extract_response_time_hint(text: str, response_type: str) -> float:
    t = text.lower()
    m = re.search(r"\b(\d{1,3})\s*(?:min|mins|minute|minutes)\b", t)
    if m:
        return float(m.group(1))

    by_type = {
        "fire": 10.0,
        "ambulance": 8.0,
        "police": 7.0,
    }
    return by_type.get(response_type, 12.0)


def _infer_severity(text: str, disaster_type: str) -> float:
    t = text.lower()
    base = {
        "fire": 3.0,
        "flood": 2.6,
        "earthquake": 4.0,
    }.get(disaster_type, 2.5)

    if any(k in t for k in ("big", "major", "massive", "severe", "catastrophic", "out of control")):
        base += 1.0
    if any(k in t for k in ("urgent", "emergency", "help", "asap", "now", "critical")):
        base += 0.4
    if any(k in t for k in ("explosion", "collapsed", "trapped")):
        base += 0.6

    # Mild bump if there are explicit casualties.
    casualty = re.search(r"\b(\d{1,4})\s*(?:injured|hurt|casualties|dead|deaths)\b", t)
    if casualty:
        base += min(1.0, int(casualty.group(1)) / 50.0)

    return round(max(1.0, min(5.0, base)), 2)


def parse_incident_text(text: str) -> dict:
    """Parse free text report into fields used by priority scoring."""
    source_text = (text or "").strip()
    disaster_type = _infer_disaster_type(source_text)
    response_type = _infer_response_type(source_text, disaster_type)

    return {
        "raw_text": source_text,
        "location": _extract_location(source_text),
        "disaster_type": disaster_type,
        "response_type": response_type,
        "severity_score": _infer_severity(source_text, disaster_type),
        "population_affected": _extract_population_hint(source_text),
        "response_time_minutes": _extract_response_time_hint(source_text, response_type),
    }
