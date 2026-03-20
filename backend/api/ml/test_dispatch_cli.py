import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from api.ml.dispatch_cli import _yes_no_to_bool, _rank_incidents, _save_feedback, _collect_feedback, _parse_response_types


class DispatchCliTests(unittest.TestCase):
    def test_yes_values(self):
        self.assertTrue(_yes_no_to_bool("y"))
        self.assertTrue(_yes_no_to_bool("YES"))
        self.assertTrue(_yes_no_to_bool("1"))

    def test_no_values(self):
        self.assertFalse(_yes_no_to_bool("n", default=True))
        self.assertFalse(_yes_no_to_bool("no", default=True))
        self.assertFalse(_yes_no_to_bool("0", default=True))

    def test_default_on_unknown_or_blank(self):
        self.assertTrue(_yes_no_to_bool("", default=True))
        self.assertFalse(_yes_no_to_bool("", default=False))
        self.assertTrue(_yes_no_to_bool("maybe", default=True))

    def test_parse_response_types(self):
        self.assertEqual(
            _parse_response_types("ambulance, fire, police, fire"),
            ["ambulance", "fire", "police"],
        )


class RankIncidentsTests(unittest.TestCase):
    def _make_result(self, priority: float, disaster_type: str = "fire") -> dict:
        return {
            "decision": {
                "priority_score": priority,
                "disaster_type": disaster_type,
                "response_type": "fire_truck",
                "severity_score": 3.0,
            },
            "planning": {"alerts": []},
        }

    def test_sorted_descending_by_priority(self):
        results = [
            self._make_result(20.0, "flood"),
            self._make_result(80.0, "fire"),
            self._make_result(50.0, "earthquake"),
        ]
        ranked = _rank_incidents(results)
        priorities = [r["decision"]["priority_score"] for r in ranked]
        self.assertEqual(priorities, [80.0, 50.0, 20.0])

    def test_empty_list_returns_empty(self):
        self.assertEqual(_rank_incidents([]), [])

    def test_missing_priority_score_treated_as_zero(self):
        results = [
            {"decision": {}, "planning": {}},
            self._make_result(10.0, "fire"),
        ]
        ranked = _rank_incidents(results)
        self.assertEqual(ranked[0]["decision"].get("priority_score"), 10.0)

    def test_single_incident_unchanged(self):
        results = [self._make_result(42.0)]
        ranked = _rank_incidents(results)
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0]["decision"]["priority_score"], 42.0)


class SaveFeedbackTests(unittest.TestCase):
    def test_creates_file_with_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "feedback_data.json"
            import api.ml.dispatch_cli as cli_module
            original = cli_module._FEEDBACK_FILE
            cli_module._FEEDBACK_FILE = path
            try:
                _save_feedback("house on fire", "fire", 4, ["fire"], source="test")
                data = json.loads(path.read_text())
                self.assertEqual(len(data), 1)
                self.assertEqual(data[0]["label"], "fire")
                self.assertEqual(data[0]["severity"], 4)
                self.assertEqual(data[0]["response_types"], ["fire"])
                self.assertEqual(data[0]["source"], "test")
            finally:
                cli_module._FEEDBACK_FILE = original

    def test_appends_to_existing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "feedback_data.json"
            path.write_text(json.dumps([{"text": "existing", "label": "flood", "severity": 3, "source": "old"}]))
            import api.ml.dispatch_cli as cli_module
            original = cli_module._FEEDBACK_FILE
            cli_module._FEEDBACK_FILE = path
            try:
                _save_feedback("second entry", "earthquake", 5, ["ambulance", "fire", "police"], source="test")
                data = json.loads(path.read_text())
                self.assertEqual(len(data), 2)
                self.assertEqual(data[1]["label"], "earthquake")
                self.assertEqual(data[1]["response_types"], ["ambulance", "fire", "police"])
            finally:
                cli_module._FEEDBACK_FILE = original


class CollectFeedbackTests(unittest.TestCase):
    def _fake_result(self, disaster_type: str = "fire", severity: float = 4.0) -> dict:
        return {
            "decision": {
                "disaster_type": disaster_type,
                "severity_score": severity,
                "response_type": "fire",
                "response_types": ["fire"],
            }
        }

    def test_confirmed_prediction_saves_as_confirmed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "feedback_data.json"
            import api.ml.dispatch_cli as cli_module
            original = cli_module._FEEDBACK_FILE
            cli_module._FEEDBACK_FILE = path
            try:
                with patch("builtins.input", side_effect=["y", "y"]):
                    _collect_feedback(self._fake_result("fire"), "house on fire downtown")
                data = json.loads(path.read_text())
                self.assertEqual(data[0]["source"], "cli_confirmed")
                self.assertEqual(data[0]["label"], "fire")
                self.assertEqual(data[0]["response_types"], ["fire"])
            finally:
                cli_module._FEEDBACK_FILE = original

    def test_corrected_prediction_saves_as_corrected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "feedback_data.json"
            import api.ml.dispatch_cli as cli_module
            original = cli_module._FEEDBACK_FILE
            cli_module._FEEDBACK_FILE = path
            try:
                with patch("builtins.input", side_effect=["n", "n", "flood", "ambulance, fire", "3"]):
                    _collect_feedback(self._fake_result("fire"), "river flooding streets")
                data = json.loads(path.read_text())
                self.assertEqual(data[0]["source"], "cli_corrected")
                self.assertEqual(data[0]["label"], "flood")
                self.assertEqual(data[0]["severity"], 3)
                self.assertEqual(data[0]["response_types"], ["ambulance", "fire"])
            finally:
                cli_module._FEEDBACK_FILE = original

    def test_response_only_correction_saves(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "feedback_data.json"
            import api.ml.dispatch_cli as cli_module
            original = cli_module._FEEDBACK_FILE
            cli_module._FEEDBACK_FILE = path
            try:
                with patch("builtins.input", side_effect=["y", "n", "ambulance, fire, police", "4"]):
                    _collect_feedback(self._fake_result("traffic_collision", 4.0), "multi vehicle crash downtown")
                data = json.loads(path.read_text())
                self.assertEqual(data[0]["label"], "traffic_collision")
                self.assertEqual(data[0]["response_types"], ["ambulance", "fire", "police"])
            finally:
                cli_module._FEEDBACK_FILE = original

    def test_invalid_label_skips_save(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "feedback_data.json"
            import api.ml.dispatch_cli as cli_module
            original = cli_module._FEEDBACK_FILE
            cli_module._FEEDBACK_FILE = path
            try:
                with patch("builtins.input", side_effect=["n", "y", "unicorn"]):
                    _collect_feedback(self._fake_result("fire"), "some text")
                self.assertFalse(path.exists())  # nothing saved
            finally:
                cli_module._FEEDBACK_FILE = original

    def test_invalid_response_bundle_skips_save(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "feedback_data.json"
            import api.ml.dispatch_cli as cli_module
            original = cli_module._FEEDBACK_FILE
            cli_module._FEEDBACK_FILE = path
            try:
                with patch("builtins.input", side_effect=["y", "n", "dragons"]):
                    _collect_feedback(self._fake_result("fire"), "some text")
                self.assertFalse(path.exists())
            finally:
                cli_module._FEEDBACK_FILE = original

    def test_empty_text_skips_silently(self):
        # Should not raise, should not write anything
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "feedback_data.json"
            import api.ml.dispatch_cli as cli_module
            original = cli_module._FEEDBACK_FILE
            cli_module._FEEDBACK_FILE = path
            try:
                _collect_feedback(self._fake_result(), "")  # no user input expected
                self.assertFalse(path.exists())
            finally:
                cli_module._FEEDBACK_FILE = original


if __name__ == "__main__":
    unittest.main()