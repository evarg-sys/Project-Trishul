"""Interactive CLI menu for the ML dispatch engine."""

from __future__ import annotations

import json

from .dispatch_engine import DispatchEngine


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
    print("  4) Exit")


def _run_location_description(engine: DispatchEngine) -> None:
    location = input("Location: ").strip()
    description = input("Description: ").strip()
    include_routes = _yes_no_to_bool(input("Include routing model? (y/N): "), default=False)

    result = engine.dispatch(
        location=location,
        description=description,
        include_routes=include_routes,
    )
    print("\nDispatch result:")
    print(json.dumps(result, indent=2))


def _run_parsed_text(engine: DispatchEngine) -> None:
    parsed_text = input("Parsed text: ").strip()
    include_routes = _yes_no_to_bool(input("Include routing model? (y/N): "), default=False)

    result = engine.dispatch(
        parsed_text=parsed_text,
        include_routes=include_routes,
    )
    print("\nDispatch result:")
    print(json.dumps(result, indent=2))


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
    print("\nDispatch result:")
    print(json.dumps(result, indent=2))


def run_menu() -> None:
    _print_header()
    print("Initializing engine...\n")
    engine = DispatchEngine(preload_road_network=False)

    while True:
        _print_menu()
        choice = input("Enter choice (1-4): ").strip()

        try:
            if choice == "1":
                _run_location_description(engine)
            elif choice == "2":
                _run_parsed_text(engine)
            elif choice == "3":
                _run_with_coords(engine)
            elif choice == "4":
                print("Exiting dispatch CLI.")
                return
            else:
                print("Invalid choice. Please pick 1, 2, 3, or 4.")
        except ValueError as exc:
            print(f"Invalid numeric input: {exc}")
        except Exception as exc:
            print(f"Dispatch failed: {exc}")


if __name__ == "__main__":
    run_menu()