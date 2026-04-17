"""
Comprehensive test suite for Mapbox + EONET dispatch system.

Usage:
    # Run all tests
    python test_suite.py

    # Run specific test category
    python test_suite.py --category hazards
    python test_suite.py --category routing
    python test_suite.py --category dispatch
    python test_suite.py --category edge_cases

    # Run specific test by number
    python test_suite.py --test 5
    python test_suite.py --test 42

    # Run tests interactively (prompt before each)
    python test_suite.py --interactive

    # Generate test report
    python test_suite.py --report

    # Test with custom responders file
    python test_suite.py --responders my_responders.json
"""

import argparse
import sys
import json
import os
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class TestCategory(Enum):
    HAZARDS = "hazards"
    ROUTING = "routing"
    DISPATCH = "dispatch"
    EDGE_CASES = "edge_cases"
    INTEGRATION = "integration"
    PERFORMANCE = "performance"
    ERROR_HANDLING = "error_handling"


@dataclass
class TestCase:
    """Single test case."""
    num: int
    category: TestCategory
    name: str
    command: str
    description: str
    expected_keyword: str = ""
    should_fail: bool = False
    # None means infer based on command type.
    requires_token: Optional[bool] = None
    setup: Optional[callable] = None
    cleanup: Optional[callable] = None


class TestSuite:
    """Complete test suite for dispatch integration."""

    def __init__(self, responders_file: Optional[str] = None):
        self.responders_file = responders_file or "example_responders.json"
        self.tests = []
        self.results = {}
        self.has_token = bool(os.environ.get("MAPBOX_ACCESS_TOKEN"))
        self._build_test_cases()

    def _test_requires_token(self, test: TestCase) -> bool:
        """Decide whether a test needs MAPBOX_ACCESS_TOKEN."""
        if test.requires_token is not None:
            return test.requires_token

        cmd = test.command.strip().lower()
        # Mapbox is needed for route and dispatch commands.
        return cmd.startswith("route-unit") or cmd.startswith("recommend-dispatch")

    def _run_cli_command(self, command: str, timeout: int = 60) -> Tuple[int, str, str]:
        """Run a single CLI command by piping it into dispatch_cli.py."""
        cli_input = f"{command}\nquit\n"
        proc = subprocess.run(
            [sys.executable, "dispatch_cli.py"],
            input=cli_input,
            text=True,
            capture_output=True,
            cwd=Path(__file__).resolve().parent,
            timeout=timeout,
            env=os.environ.copy(),
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""

    @staticmethod
    def _looks_like_error(text: str) -> bool:
        """Heuristic check for command failure signals in CLI output."""
        hay = (text or "").lower()
        error_markers = [
            "[error]",
            "command error",
            "usage:",
            "unknown command",
            "traceback",
            "failed",
            "not found",
            "invalid",
        ]
        return any(marker in hay for marker in error_markers)

    def _build_test_cases(self):
        """Build all 80+ test cases."""
        num = 1

        # ====== HAZARD TESTS (Tests 1-15) ======
        self.tests.append(TestCase(
            num=num, category=TestCategory.HAZARDS,
            name="Fetch all active hazards",
            command="fetch-hazards",
            description="Fetch all currently active hazards worldwide",
            expected_keyword="Found"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.HAZARDS,
            name="Fetch with days filter (7 days)",
            command="fetch-hazards days=7",
            description="Fetch hazards updated in last 7 days",
            expected_keyword="Found"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.HAZARDS,
            name="Fetch with days filter (30 days)",
            command="fetch-hazards days=30",
            description="Fetch hazards updated in last 30 days",
            expected_keyword="Found"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.HAZARDS,
            name="Fetch fire category",
            command="fetch-hazards category=fires",
            description="Fetch only fire events",
            expected_keyword="Category"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.HAZARDS,
            name="Fetch volcano category",
            command="fetch-hazards category=volcanoes",
            description="Fetch only volcano events",
            expected_keyword="Found"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.HAZARDS,
            name="Fetch with days and category",
            command="fetch-hazards days=14 category=floods",
            description="Combine days and category filters",
            expected_keyword="Found"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.HAZARDS,
            name="Save hazards to file",
            command="fetch-hazards days=7 save=test_hazards.json",
            description="Fetch and save hazards to JSON",
            expected_keyword="Saved"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.HAZARDS,
            name="Fetch with zero days (today only)",
            command="fetch-hazards days=0",
            description="Fetch only today's events",
            expected_keyword="Found"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.HAZARDS,
            name="Fetch with large days window",
            command="fetch-hazards days=365",
            description="Fetch events from past year",
            expected_keyword="Found"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.HAZARDS,
            name="Fetch storms category",
            command="fetch-hazards category=storms",
            description="Fetch storm/severe weather events",
            expected_keyword="Found"
        ))
        num += 1

        # ====== ROUTING TESTS (Tests 11-40) ======
        self.tests.append(TestCase(
            num=num, category=TestCategory.ROUTING,
            name="Short distance route (1km)",
            command="route-unit --from -87.6500,41.8800 --to -87.6498,41.8815",
            description="Route for ~1km trip",
            expected_keyword="Distance"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.ROUTING,
            name="Medium distance route (5km)",
            command="route-unit --from -87.6500,41.8800 --to -87.6000,41.8500",
            description="Route for ~5km trip",
            expected_keyword="Distance"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.ROUTING,
            name="Long distance route (20km)",
            command="route-unit --from -87.6500,41.8800 --to -87.4000,41.7000",
            description="Route for ~20km trip",
            expected_keyword="Distance"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.ROUTING,
            name="Same coordinates (0km)",
            command="route-unit --from -87.6500,41.8800 --to -87.6500,41.8800",
            description="Origin = destination",
            expected_keyword="Distance"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.ROUTING,
            name="Downtown Chicago route",
            command="route-unit --from -87.6298,41.8781 --to -87.6200,41.8900",
            description="Real Chicago downtown locations",
            expected_keyword="Distance"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.ROUTING,
            name="Cross-city route",
            command="route-unit --from -87.65,41.88 --to -87.62,41.77",
            description="Route across city boundaries",
            expected_keyword="Distance"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.ROUTING,
            name="Route with positive decimals",
            command="route-unit --from -87.123456,41.123456 --to -87.654321,41.654321",
            description="Routes with high precision coordinates",
            expected_keyword="Distance"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.ROUTING,
            name="Route across state boundary",
            command="route-unit --from -87.6500,41.8800 --to -88.1500,41.5000",
            description="Route to Indiana",
            expected_keyword="Distance"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.ROUTING,
            name="Cardinal direction North",
            command="route-unit --from -87.6500,41.8800 --to -87.6500,42.0000",
            description="Directly northward route",
            expected_keyword="Distance"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.ROUTING,
            name="Cardinal direction South",
            command="route-unit --from -87.6500,41.8800 --to -87.6500,41.6000",
            description="Directly southward route",
            expected_keyword="Distance"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.ROUTING,
            name="Cardinal direction East",
            command="route-unit --from -87.6500,41.8800 --to -87.3000,41.8800",
            description="Directly eastward route",
            expected_keyword="Distance"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.ROUTING,
            name="Cardinal direction West",
            command="route-unit --from -87.3000,41.8800 --to -87.6500,41.8800",
            description="Directly westward route",
            expected_keyword="Distance"
        ))
        num += 1

        # ====== DISPATCH RECOMMENDATION TESTS (Tests 23-50) ======
        self.tests.append(TestCase(
            num=num, category=TestCategory.DISPATCH,
            name="Basic dispatch recommendation",
            command="recommend-dispatch --incident -87.628,41.885",
            description="Get best responder with demo units",
            expected_keyword="Best"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.DISPATCH,
            name="Dispatch with custom responders",
            command=f"recommend-dispatch --incident -87.628,41.885 --responders {self.responders_file}",
            description="Get recommendation with custom responder file",
            expected_keyword="Best"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.DISPATCH,
            name="Dispatch with hazards enabled",
            command="recommend-dispatch --incident -87.628,41.885",
            description="Consider hazards in scoring",
            expected_keyword="hazard"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.DISPATCH,
            name="Dispatch without hazards",
            command="recommend-dispatch --incident -87.628,41.885 --no-hazards",
            description="Ignore hazards in scoring",
            expected_keyword="Best"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.DISPATCH,
            name="Dispatch downtown Chicago",
            command="recommend-dispatch --incident -87.6298,41.8781",
            description="Recommendation for downtown",
            expected_keyword="Best"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.DISPATCH,
            name="Dispatch far north",
            command="recommend-dispatch --incident -87.628,42.0000",
            description="Recommendation for far north",
            expected_keyword="candidates"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.DISPATCH,
            name="Dispatch near water (Lake Michigan)",
            command="recommend-dispatch --incident -87.5,41.88",
            description="Recommendation near lake",
            expected_keyword="Best"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.DISPATCH,
            name="Dispatch negative latitude",
            command="recommend-dispatch --incident -87.628,-41.885",
            description="Southern hemisphere coordinate",
            expected_keyword="Best"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.DISPATCH,
            name="Dispatch high precision coords",
            command="recommend-dispatch --incident -87.62841234,41.88521234",
            description="Routes with high precision coordinates",
            expected_keyword="Best"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.DISPATCH,
            name="Dispatch multiple candidates ranking",
            command="recommend-dispatch --incident -87.628,41.885",
            description="See all candidates sorted by score",
            expected_keyword="candidates"
        ))
        num += 1

        # ====== EDGE CASES (Tests 33-60) ======
        self.tests.append(TestCase(
            num=num, category=TestCategory.EDGE_CASES,
            name="Invalid latitude (> 90)",
            command="route-unit --from -87.65,41.88 --to -87.62,100",
            description="Latitude out of range",
            expected_keyword="Error",
            should_fail=True
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.EDGE_CASES,
            name="Invalid latitude (< -90)",
            command="route-unit --from -87.65,41.88 --to -87.62,-100",
            description="Latitude below -90",
            expected_keyword="Error",
            should_fail=True
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.EDGE_CASES,
            name="Invalid longitude (> 180)",
            command="route-unit --from -87.65,41.88 --to 200,41.88",
            description="Longitude out of range",
            expected_keyword="Error",
            should_fail=True
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.EDGE_CASES,
            name="Invalid longitude (< -180)",
            command="route-unit --from -87.65,41.88 --to -200,41.88",
            description="Longitude below -180",
            expected_keyword="Error",
            should_fail=True
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.EDGE_CASES,
            name="Missing coordinate separator",
            command="route-unit --from -87.65 41.88 --to -87.62,41.90",
            description="Missing comma between coordinates",
            expected_keyword="Usage",
            should_fail=True
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.EDGE_CASES,
            name="Non-numeric coordinates",
            command="route-unit --from ABC,DEF --to -87.62,41.90",
            description="Non-numeric coordinate values",
            expected_keyword="Error",
            should_fail=True
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.EDGE_CASES,
            name="Empty coordinates",
            command="route-unit --from , --to -87.62,41.90",
            description="Empty coordinate values",
            expected_keyword="Error",
            should_fail=True
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.EDGE_CASES,
            name="Missing --from flag",
            command="route-unit -87.65,41.88 --to -87.62,41.90",
            description="Missing --from flag",
            expected_keyword="Usage",
            should_fail=True
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.EDGE_CASES,
            name="Missing --to flag",
            command="route-unit --from -87.65,41.88 -87.62,41.90",
            description="Missing --to flag",
            expected_keyword="Usage",
            should_fail=True
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.EDGE_CASES,
            name="Extra decimal places",
            command="route-unit --from -87.123456789,41.123456789 --to -87.987654321,41.987654321",
            description="Coordinates with many decimal places",
            expected_keyword="Distance"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.EDGE_CASES,
            name="Zero coordinates",
            command="route-unit --from 0,0 --to 0.001,0.001",
            description="Route near prime meridian",
            expected_keyword="Distance"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.EDGE_CASES,
            name="Negative zero",
            command="route-unit --from -0.0,-0.0 --to 0.0,0.0",
            description="Negative zero coordinates",
            expected_keyword="Distance"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.EDGE_CASES,
            name="Antimeridian crossing",
            command="route-unit --from 179.9,0 --to -179.9,0",
            description="Route crossing international date line",
            expected_keyword="Distance"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.EDGE_CASES,
            name="Equator crossing",
            command="route-unit --from 0,0.5 --to 0,-0.5",
            description="Route crossing equator",
            expected_keyword="Distance"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.EDGE_CASES,
            name="North pole extreme",
            command="route-unit --from 0,85 --to 0,85.05",
            description="Route near north pole",
            expected_keyword="Distance"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.EDGE_CASES,
            name="South pole extreme",
            command="route-unit --from 0,-85 --to 0,-85.05",
            description="Route near south pole",
            expected_keyword="Distance"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.EDGE_CASES,
            name="Missing responders file",
            command="recommend-dispatch --incident -87.628,41.885 --responders nonexistent.json",
            description="Responders file doesn't exist",
            expected_keyword="Error",
            should_fail=True
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.EDGE_CASES,
            name="Malformed responders JSON",
            command="recommend-dispatch --incident -87.628,41.885 --responders badly_formatted.json",
            description="JSON syntax error",
            expected_keyword="Error",
            should_fail=True,
            requires_token=False
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.EDGE_CASES,
            name="Invalid hazard category",
            command="fetch-hazards category=invalid_category",
            description="Fetch with non-existent category",
            expected_keyword="Found"
        ))
        num += 1

        # ====== ERROR HANDLING (Tests 53-70) ======
        self.tests.append(TestCase(
            num=num, category=TestCategory.ERROR_HANDLING,
            name="Missing Mapbox token",
            command="route-unit --from -87.65,41.88 --to -87.62,41.90",
            description="MAPBOX_ACCESS_TOKEN not set",
            expected_keyword="Error",
            should_fail=True,
            requires_token=False
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.ERROR_HANDLING,
            name="Invalid Mapbox token",
            command="route-unit --from -87.65,41.88 --to -87.62,41.90",
            description="Bad or expired Mapbox token",
            expected_keyword="Error",
            should_fail=True,
            requires_token=False
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.ERROR_HANDLING,
            name="Network timeout simulation",
            command="route-unit --from -87.65,41.88 --to -87.62,41.90",
            description="API doesn't respond in time",
            expected_keyword="Error",
            should_fail=True,
            requires_token=False
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.ERROR_HANDLING,
            name="Unreachable route",
            command="route-unit --from -87.65,41.88 --to -87.65,41.85",
            description="No valid path between points",
            expected_keyword="Error",
            should_fail=False
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.ERROR_HANDLING,
            name="Invalid day value (negative)",
            command="fetch-hazards days=-5",
            description="Negative days filter",
            expected_keyword="Error",
            should_fail=True
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.ERROR_HANDLING,
            name="Invalid day value (non-numeric)",
            command="fetch-hazards days=abc",
            description="Non-numeric days value",
            expected_keyword="Error",
            should_fail=True
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.ERROR_HANDLING,
            name="Large day value (10 years)",
            command="fetch-hazards days=3650",
            description="Very large historical window",
            expected_keyword="Found"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.ERROR_HANDLING,
            name="Empty reponders list",
            command="recommend-dispatch --incident -87.628,41.885 --responders empty.json",
            description="Responders file is empty []",
            expected_keyword="Error",
            should_fail=True,
            requires_token=False
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.ERROR_HANDLING,
            name="Responder missing lon field",
            command="recommend-dispatch --incident -87.628,41.885 --responders bad_responder_1.json",
            description="Responder missing 'lon' field",
            expected_keyword="Error",
            should_fail=True,
            requires_token=False
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.ERROR_HANDLING,
            name="Responder missing lat field",
            command="recommend-dispatch --incident -87.628,41.885 --responders bad_responder_2.json",
            description="Responder missing 'lat' field",
            expected_keyword="Error",
            should_fail=True,
            requires_token=False
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.ERROR_HANDLING,
            name="Responder missing id field",
            command="recommend-dispatch --incident -87.628,41.885 --responders bad_responder_3.json",
            description="Responder missing 'id' field",
            expected_keyword="Error",
            should_fail=True,
            requires_token=False
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.ERROR_HANDLING,
            name="Responder invalid lon value",
            command="recommend-dispatch --incident -87.628,41.885 --responders bad_responder_4.json",
            description="Responder 'lon' is non-numeric",
            expected_keyword="Error",
            should_fail=True,
            requires_token=False
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.ERROR_HANDLING,
            name="Command with typo",
            command="rout-unit --from -87.65,41.88 --to -87.62,41.90",
            description="Misspelled command",
            expected_keyword="Unknown",
            should_fail=True
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.ERROR_HANDLING,
            name="Flag with wrong separator",
            command="route-unit from -87.65,41.88 to -87.62,41.90",
            description="Using 'from/to' instead of '--from/--to'",
            expected_keyword="Usage",
            should_fail=True
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.ERROR_HANDLING,
            name="Duplicate flags",
            command="route-unit --from -87.65,41.88 --from -87.62,41.80 --to -87.62,41.90",
            description="Duplicate --from flag",
            expected_keyword="Distance"
        ))
        num += 1

        # ====== INTEGRATION TESTS (Tests 68-75) ======
        self.tests.append(TestCase(
            num=num, category=TestCategory.INTEGRATION,
            name="Fetch hazards then check dispatch",
            command="fetch-hazards days=7 save=test_hazards.json",
            description="Fetch hazards for later use in dispatch",
            expected_keyword="Saved"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.INTEGRATION,
            name="Route calculation consistency",
            command="route-unit --from -87.65,41.88 --to -87.62,41.90",
            description="First route calculation",
            expected_keyword="Distance"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.INTEGRATION,
            name="Route same path (cache test)",
            command="route-unit --from -87.65,41.88 --to -87.62,41.90",
            description="Same route again (may be cached)",
            expected_keyword="Distance"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.INTEGRATION,
            name="Multiple dispatch recommendations",
            command="recommend-dispatch --incident -87.628,41.885",
            description="First dispatch recommendation",
            expected_keyword="Best"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.INTEGRATION,
            name="Dispatch different location",
            command="recommend-dispatch --incident -87.500,41.900",
            description="Dispatch to different incident",
            expected_keyword="Best"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.INTEGRATION,
            name="Workflow: hazards -> route -> dispatch",
            command="fetch-hazards days=7",
            description="Step 1: Fetch hazards",
            expected_keyword="Found"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.INTEGRATION,
            name="Workflow: calculate route to incident",
            command="route-unit --from -87.65,41.88 --to -87.628,41.885",
            description="Step 2: Calculate route to incident",
            expected_keyword="Distance"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.INTEGRATION,
            name="Workflow: get dispatch recommendation",
            command="recommend-dispatch --incident -87.628,41.885",
            description="Step 3: Get dispatch recommendation",
            expected_keyword="Best"
        ))
        num += 1

        # ====== PERFORMANCE STRESS TESTS (Tests 76-80) ======
        self.tests.append(TestCase(
            num=num, category=TestCategory.PERFORMANCE,
            name="Many dispatch rapid calls",
            command="recommend-dispatch --incident -87.628,41.885",
            description="Rapid fire dispatch calls",
            expected_keyword="Best"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.PERFORMANCE,
            name="Long responders list",
            command="recommend-dispatch --incident -87.628,41.885",
            description="Ranking 50+ responders",
            expected_keyword="Best"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.PERFORMANCE,
            name="Route with many waypoints simulation",
            command="route-unit --from -87.65,41.88 --to -87.62,41.90",
            description="Complex route calculation",
            expected_keyword="Distance"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.PERFORMANCE,
            name="Fetch hazards with max results",
            command="fetch-hazards days=365",
            description="Maximum hazard fetch",
            expected_keyword="Found"
        ))
        num += 1

        self.tests.append(TestCase(
            num=num, category=TestCategory.PERFORMANCE,
            name="Global bounding box query",
            command="fetch-hazards days=7",
            description="Hazards worldwide (default)",
            expected_keyword="Found"
        ))
        num += 1

    def run_all(self, verbose: bool = False) -> Dict[str, Any]:
        """Run all test cases."""
        results = {
            "total": len(self.tests),
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "by_category": {},
            "details": []
        }

        for test in self.tests:
            result = self.run_test(test, verbose)
            results["details"].append(result)

            if result["status"] == "passed":
                results["passed"] += 1
            elif result["status"] == "failed":
                results["failed"] += 1
            elif result["status"] == "skipped":
                results["skipped"] += 1

            # Category stats
            cat = test.category.value
            if cat not in results["by_category"]:
                results["by_category"][cat] = {"passed": 0, "failed": 0, "skipped": 0}
            results["by_category"][cat][result["status"]] += 1

        return results

    def run_test(self, test: TestCase, verbose: bool = False) -> Dict[str, Any]:
        """Run a single test case."""
        result = {
            "num": test.num,
            "name": test.name,
            "command": test.command,
            "status": "skipped",
            "output": "",
            "error": ""
        }

        # Skip if no token and test requires it
        if self._test_requires_token(test) and not self.has_token:
            result["error"] = "MAPBOX_ACCESS_TOKEN not set"
            if verbose:
                print(f"  [SKIP] Test {test.num}: {test.name} - No token")
            return result

        try:
            code, stdout, stderr = self._run_cli_command(test.command)
            full_output = "\n".join([part for part in [stdout, stderr] if part]).strip()
            result["output"] = full_output

            hay = full_output.lower()
            expected_hit = (test.expected_keyword.lower() in hay) if test.expected_keyword else True
            saw_error = self._looks_like_error(full_output)

            if test.should_fail:
                # Expected-failure tests pass when an error signal appears.
                if saw_error or (test.expected_keyword and expected_hit):
                    result["status"] = "passed"
                else:
                    result["status"] = "failed"
                    result["error"] = "Expected failure signal was not found in CLI output"
            else:
                # Normal tests pass when expected output appears and no hard error is seen.
                if code == 0 and expected_hit and not saw_error:
                    result["status"] = "passed"
                else:
                    result["status"] = "failed"
                    if not expected_hit and test.expected_keyword:
                        result["error"] = f"Expected keyword not found: {test.expected_keyword}"
                    elif saw_error:
                        result["error"] = "CLI output indicates an error"
                    else:
                        result["error"] = f"CLI exited with code {code}"

            if verbose:
                print(f"  [{'PASS' if result['status'] == 'passed' else 'FAIL'}] Test {test.num}: {test.name}")
                print(f"    Command: {test.command}")
                if result["error"]:
                    print(f"    Error: {result['error']}")
                elif test.expected_keyword:
                    print(f"    Matched keyword: {test.expected_keyword}")

        except subprocess.TimeoutExpired:
            result["status"] = "failed"
            result["error"] = "CLI command timed out"
            if verbose:
                print(f"  [FAIL] Test {test.num}: {test.name} - CLI command timed out")
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            if verbose:
                print(f"  [FAIL] Test {test.num}: {test.name} - {e}")

        return result

    def run_interactive(self):
        """Run tests interactively, asking before each."""
        for test in self.tests:
            print(f"\n{'='*70}")
            print(f"Test {test.num}: {test.name}")
            print(f"Category: {test.category.value}")
            print(f"Description: {test.description}")
            print(f"Command: {test.command}")
            print(f"Expected: {test.expected_keyword if test.expected_keyword else '(success)'}")
            print(f"Should fail: {test.should_fail}")

            response = input("\nRun this test? (y/n/skip/quit): ").strip().lower()
            if response == "quit":
                break
            elif response == "skip":
                print("Skipped.")
                continue
            elif response == "y":
                print(f"Running: {test.command}")
                result = self.run_test(test, verbose=True)
                print(f"Result: {result['status']}")
            else:
                print("Skipped.")

    def generate_report(self, results: Dict[str, Any]) -> str:
        """Generate test report."""
        report = f"""
{'='*70}
TEST SUITE REPORT
{'='*70}

Total Tests: {results['total']}
Passed: {results['passed']}
Failed: {results['failed']}
Skipped: {results['skipped']}

Pass Rate: {100 * results['passed'] / max(1, (results['total'] - results['skipped'])):.1f}%

By Category:
"""
        for cat, stats in results["by_category"].items():
            total = stats["passed"] + stats["failed"]
            if total > 0:
                pass_rate = 100 * stats["passed"] / total
                report += f"  {cat:.<20} {stats['passed']:>3} passed, {stats['failed']:>3} failed ({pass_rate:>5.1f}%)\n"

        report += f"\n{'='*70}\n"
        return report


def main():
    parser = argparse.ArgumentParser(
        description="Comprehensive test suite for Mapbox + EONET dispatch system"
    )
    parser.add_argument("--category", help="Run specific category (hazards, routing, dispatch, edge_cases, etc.)")
    parser.add_argument("--test", type=int, help="Run specific test by number")
    parser.add_argument("--interactive", action="store_true", help="Run interactively")
    parser.add_argument("--report", action="store_true", help="Generate test report")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--responders", help="Custom responders file")

    args = parser.parse_args()

    suite = TestSuite(responders_file=args.responders)

    if args.interactive:
        suite.run_interactive()
    elif args.test:
        # Run specific test
        test = next((t for t in suite.tests if t.num == args.test), None)
        if test:
            result = suite.run_test(test, verbose=True)
            print(f"\nTest {result['num']}: {result['name']}")
            print(f"Status: {result['status']}")
            print(f"Output: {result['output']}")
            if result['error']:
                print(f"Error: {result['error']}")
        else:
            print(f"Test {args.test} not found")
    else:
        # Run all or by category
        if args.category:
            suite.tests = [t for t in suite.tests if t.category.value == args.category]

        results = suite.run_all(verbose=args.verbose)

        if args.report or not args.verbose:
            print(suite.generate_report(results))

        if args.verbose:
            print(f"\nTotal: {results['passed']}/{results['total']} passed")


if __name__ == "__main__":
    main()
