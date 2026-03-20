"""Interactive CLI menu for the ML dispatch engine."""

from __future__ import annotations

import json
from pathlib import Path

from .dispatch_engine import DispatchEngine

# Valid class labels the ML can predict (must match training labels)
VALID_LABELS = [
    "fire",
    "flood",
    "earthquake",
    "traffic_collision",
    "chemical_spill",
    "medical_emergency",
    "none",
]
VALID_RESPONSE_TYPES = ["ambulance", "fire", "police"]

# Feedback is stored here and auto-merged by train_incident_model.py
_FEEDBACK_FILE = Path(__file__).resolve().parents[2] / "training" / "feedback_data.json"


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


def _parse_response_types(raw: str) -> list[str]:
    values = [part.strip().lower() for part in (raw or "").split(",")]
    return [value for value in _normalize_response_types(values) if value in VALID_RESPONSE_TYPES]


def _save_feedback(
    text: str,
    label: str,
    severity: int,
    response_types: list[str] | None = None,
    source: str = "cli",
) -> None:
    """Append one labelled example to the persistent feedback file."""
    existing: list = []
    if _FEEDBACK_FILE.exists():
        try:
            existing = json.loads(_FEEDBACK_FILE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            existing = []
    existing.append({
        "text": text,
        "label": label,
        "severity": severity,
        "response_types": _normalize_response_types(response_types or []),
        "source": source,
    })
    _FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    _FEEDBACK_FILE.write_text(json.dumps(existing, indent=2), encoding="utf-8")


def _collect_feedback(result: dict, incident_text: str) -> None:
    """Ask the operator if the ML prediction was correct; save the label either way."""
    if not incident_text:
        return
    decision = result.get("decision", {})
    predicted = decision.get("disaster_type") or "unknown"
    predicted_responses = _normalize_response_types(
        decision.get("response_types") or [decision.get("response_type") or ""]
    )
    severity_score = decision.get("severity_score") or 3.0
    default_sev = max(1, min(5, round(float(severity_score))))

    print("\n-- Feedback --")
    print(f"  ML predicted: '{predicted}'")
    print(f"  Response units: {', '.join(predicted_responses) if predicted_responses else '-'}")
    type_correct = _yes_no_to_bool(input("  Was the disaster type correct? (Y/n): "), default=True)
    response_correct = _yes_no_to_bool(input("  Were the response units correct? (Y/n): "), default=True)

    final_label = predicted
    final_responses = predicted_responses

    if not type_correct:
        print(f"  Valid types: {', '.join(VALID_LABELS)}")
        correct_label = input("  Correct disaster type: ").strip().lower()
        if correct_label not in VALID_LABELS:
            print(f"  '{correct_label}' not recognised - skipping save.")
            return
        final_label = correct_label

    if not response_correct:
        print(f"  Valid response units: {', '.join(VALID_RESPONSE_TYPES)}")
        raw_responses = input("  Correct response units (comma-separated): ").strip()
        corrected_responses = _parse_response_types(raw_responses)
        if not corrected_responses:
            print("  No valid response units provided - skipping save.")
            return
        final_responses = corrected_responses

    if type_correct and response_correct:
        _save_feedback(incident_text, final_label, default_sev, final_responses, source="cli_confirmed")
        print("  Saved as confirmed training data.")
    else:
        sev_raw = input(f"  Severity 1-5 (Enter to keep {default_sev}): ").strip()
        try:
            sev = max(1, min(5, int(sev_raw))) if sev_raw else default_sev
        except ValueError:
            sev = default_sev
        _save_feedback(incident_text, final_label, sev, final_responses, source="cli_corrected")
        print(f"  Correction saved: '{final_label}' severity {sev} with responses [{', '.join(final_responses)}].")
        print("  Run  python training/train_incident_model.py  to retrain.")


def _yes_no_to_bool(value: str, default: bool = False) -> bool:
    raw = (value or "").strip().lower()
    if not raw:
        return default
    if raw in {"y", "yes", "true", "1"}:
        return True
    if raw in {"n", "no", "false", "0"}:
        return False
    return default


def _print_header() -> None:
    print("\n" + "=" * 72)
    print("TRISHUL ML DISPATCH ENGINE - CLI MENU")
    print("=" * 72)


def _print_menu() -> None:
    print("\nChoose input mode:")
    print("  1) Location + Description")
    print("  2) Parsed Text Only")
    print("  3) Location + Description + Coordinates")
    print("  4) Multiple incidents + ranked priority table")
    print("  5) Exit")


def _print_summary(result: dict) -> None:
    decision = result.get("decision", {})
    planning = result.get("planning", {})
    models = result.get("models", {})
    detection = models.get("detection", {})

    print("\nDecision summary:")
    print(f"  Disaster type: {decision.get('disaster_type')}")
    print(f"  Response type: {decision.get('response_type')}")
    if decision.get("response_types"):
        print(f"  Response units: {', '.join(decision.get('response_types') or [])}")
    print(f"  Severity: {decision.get('severity_score')}")
    print(f"  Population affected: {decision.get('population_affected')}")
    print(f"  Priority score: {decision.get('priority_score')}")

    if detection:
        print("\nML understanding:")
        print(f"  Detected: {detection.get('detected')}")
        print(f"  Confidence: {detection.get('confidence')}")
        print(f"  Agreement: {detection.get('agreement') or detection.get('ensemble_agreement')}")

    final_plan = planning.get("final_plan", {})
    if final_plan:
        print("\nFinal plan roles:")
        for role, count in (final_plan.get("required_roles") or {}).items():
            print(f"  - {role}: {count}")

    alerts = planning.get("alerts", [])
    if alerts:
        print("\nAlerts:")
        for alert in alerts:
            print(f"  - [{alert.get('level')}] {alert.get('code')}: {alert.get('message')}")


def _run_location_description(engine: DispatchEngine) -> None:
    location = input("Location: ").strip()
    description = input("Description: ").strip()
    include_routes = _yes_no_to_bool(input("Include routing model? (y/N): "), default=False)

    result = engine.dispatch(
        location=location,
        description=description,
        include_routes=include_routes,
    )
    _print_summary(result)
    print("\nDispatch result:")
    print(json.dumps(result, indent=2))
    _collect_feedback(result, description or location)


def _run_parsed_text(engine: DispatchEngine) -> None:
    parsed_text = input("Parsed text: ").strip()
    include_routes = _yes_no_to_bool(input("Include routing model? (y/N): "), default=False)

    result = engine.dispatch(
        parsed_text=parsed_text,
        include_routes=include_routes,
    )
    _print_summary(result)
    print("\nDispatch result:")
    print(json.dumps(result, indent=2))
    _collect_feedback(result, parsed_text)


def _rank_incidents(results: list) -> list:
    """Return dispatch results sorted by priority_score descending."""
    return sorted(
        results,
        key=lambda r: float(r.get("decision", {}).get("priority_score") or 0),
        reverse=True,
    )


def _run_multi_incident_table(engine: DispatchEngine) -> None:
    """Collect N incidents, dispatch each, print a ranked priority table."""
    print("\nEnter incidents one by one. Leave location blank to finish.")
    raw_incidents: list = []
    idx = 1
    while True:
        print(f"\n--- Incident {idx} ---")
        location = input("  Location (blank to finish): ").strip()
        if not location:
            break
        description = input("  Description: ").strip()
        raw_incidents.append({"location": location, "description": description})
        idx += 1

    if not raw_incidents:
        print("No incidents entered.")
        return

    print(f"\nDispatching {len(raw_incidents)} incident(s)...")
    results: list = []
    for inc in raw_incidents:
        try:
            result = engine.dispatch(
                location=inc["location"],
                description=inc["description"],
            )
            result["_input_location"] = inc["location"]
            result["_input_description"] = inc["description"]
            results.append(result)
        except Exception as exc:  # noqa: BLE001
            print(f"  [WARN] dispatch failed for '{inc['location']}': {exc}")

    if not results:
        print("All dispatches failed. Nothing to rank.")
        return

    ranked = _rank_incidents(results)

    sep = "=" * 105
    fmt = "{:<5} {:<26} {:<18} {:<14} {:<6} {:<10} {}"
    print("\n" + sep)
    print("  RANKED INCIDENT PRIORITY TABLE")
    print(sep)
    print(fmt.format("Rank", "Location", "Disaster", "Response", "Sev", "Priority", "Alerts"))
    print("-" * 105)
    for rank, r in enumerate(ranked, 1):
        dec = r.get("decision", {})
        planning = r.get("planning", {})
        alerts = planning.get("alerts", [])
        alert_codes = ", ".join(a.get("code", "") for a in alerts) if alerts else "-"
        loc = (r.get("_input_location") or "")[:25]
        print(fmt.format(
            rank,
            loc,
            (dec.get("disaster_type") or "-")[:17],
            (dec.get("response_type") or "-")[:13],
            dec.get("severity_score", "-"),
            dec.get("priority_score", "-"),
            alert_codes,
        ))
    print(sep)

    # Offer per-incident feedback after the table
    want_feedback = _yes_no_to_bool(
        input("\nProvide feedback on predictions? (y/N): "), default=False
    )
    if want_feedback:
        for rank, r in enumerate(ranked, 1):
            inc_text = r.get("_input_description") or r.get("_input_location") or ""
            print(f"\nIncident #{rank} - {r.get('_input_location', '')}")
            _collect_feedback(r, inc_text)


def _run_with_coords(engine: DispatchEngine) -> None:
    location = input("Location label (optional): ").strip()
    description = input("Description: ").strip()
    latitude = float(input("Latitude: ").strip())
    longitude = float(input("Longitude: ").strip())
    include_routes = _yes_no_to_bool(input("Include routing model? (y/N): "), default=False)

    result = engine.dispatch(
        location=location,
        description=description,
        latitude=latitude,
        longitude=longitude,
        include_routes=include_routes,
    )
    _print_summary(result)
    print("\nDispatch result:")
    print(json.dumps(result, indent=2))
    _collect_feedback(result, description or location)


def run_menu() -> None:
    _print_header()
    print("Initializing engine...\n")
    engine = DispatchEngine(preload_road_network=False)

    while True:
        _print_menu()
        choice = input("Enter choice (1-5): ").strip()

        try:
            if choice == "1":
                _run_location_description(engine)
            elif choice == "2":
                _run_parsed_text(engine)
            elif choice == "3":
                _run_with_coords(engine)
            elif choice == "4":
                _run_multi_incident_table(engine)
            elif choice == "5":
                print("Exiting dispatch CLI.")
                return
            else:
                print("Invalid choice. Please pick 1-5.")
        except ValueError as exc:
            print(f"Invalid numeric input: {exc}")
        except Exception as exc:
            print(f"Dispatch failed: {exc}")


if __name__ == "__main__":
    run_menu()