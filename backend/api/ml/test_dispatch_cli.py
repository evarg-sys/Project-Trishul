import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from api.ml.dispatch_cli import _yes_no_to_bool


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


if __name__ == "__main__":
    unittest.main()