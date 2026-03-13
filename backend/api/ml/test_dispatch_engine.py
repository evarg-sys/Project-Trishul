import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from api.ml import dispatch_engine as de


class _FakeDetector:
    def __init__(self, disaster_type="flood", severity=4.5):
        self.disaster_type = disaster_type
        self.severity = severity

    def detect(self, _text, return_all_models=True):
        return {
            "detected": True,
            "disaster_type": self.disaster_type,
            "severity": self.severity,
            "confidence": 82.0,
            "confidence_level": "high",
        }


class _FakeRouting:
    graph = object()

    def load_network(self, _network_type="drive"):
        return None

    def generate_fire_routes(self, _coords):
        return [
            {
                "station_name": "Station A",
                "distance_km": 2.0,
                "selected": True,
                "type": "fire",
            }
        ]

    def generate_ambulance_routes(self, _coords):
        return [
            {
                "station_name": "Hospital A",
                "distance_km": 1.2,
                "selected": True,
                "type": "ambulance",
            }
        ]


class DispatchEngineTests(unittest.TestCase):
    def setUp(self):
        de.DisasterEnsembleSystem = None
        de.DisasterRouting = None
        self.engine = de.DispatchEngine(preload_road_network=False)
        self.engine._resolve_coordinates = lambda **kwargs: (41.88, -87.63)
        self.engine.population_model.estimate_for_location = lambda *_args, **_kwargs: {
            "total_population": 900,
            "zipcode": "60601",
            "density": 1200,
            "radius_meters": 700,
        }

    def test_dispatch_accepts_location_and_description(self):
        result = self.engine.dispatch(
            location="55 N Wacker Dr",
            description="major fire with heavy smoke and trapped people",
            include_routes=False,
        )

        decision = result["decision"]
        self.assertEqual(decision["disaster_type"], "fire")
        self.assertEqual(decision["population_affected"], 900)
        self.assertGreater(decision["priority_score"], 0)

    def test_dispatch_accepts_parsed_text_only(self):
        result = self.engine.dispatch(
            parsed_text="earthquake lots of people hurt at 945 W harrison",
            include_routes=False,
        )

        decision = result["decision"]
        self.assertEqual(decision["disaster_type"], "earthquake")
        self.assertEqual(result["input"]["location"], "945 W harrison")
        self.assertGreater(decision["severity_score"], 3.0)

    def test_detector_output_overrides_parsed_disaster_type(self):
        self.engine.detector = _FakeDetector(disaster_type="flood", severity=4.8)

        result = self.engine.dispatch(
            parsed_text="small fire near downtown",
            include_routes=False,
        )

        self.assertEqual(result["decision"]["disaster_type"], "flood")
        self.assertGreaterEqual(result["decision"]["severity_score"], 4.8)

    def test_routing_model_estimates_response_time(self):
        self.engine.routing = _FakeRouting()

        result = self.engine.dispatch(
            parsed_text="major fire near river north",
            include_routes=True,
        )

        response_minutes = result["decision"]["response_time_minutes"]
        self.assertAlmostEqual(response_minutes, 6.0, places=3)
        self.assertEqual(result["models"]["routes"]["method"], "routing_model")


if __name__ == "__main__":
    unittest.main()