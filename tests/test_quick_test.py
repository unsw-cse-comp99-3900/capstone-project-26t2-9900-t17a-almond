import sys
import unittest
from pathlib import Path


TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from run_quick_test import validate_prediction


class QuickTestValidationTests(unittest.TestCase):
    def test_accepts_a_complete_prediction(self):
        errors = validate_prediction({
            "predicted_label": "1",
            "vulnerability_probability": "0.875",
            "num_nodes": "12",
            "num_edges": "24",
        })
        self.assertEqual(errors, [])

    def test_reports_missing_and_invalid_prediction_fields(self):
        errors = validate_prediction({
            "predicted_label": "",
            "vulnerability_probability": "1.5",
            "num_nodes": "0",
            "num_edges": "not-a-number",
        })
        self.assertEqual(
            errors,
            [
                "predicted_label is missing",
                "vulnerability_probability is outside the range 0..1",
                "num_nodes is not positive",
                "num_edges is missing or invalid",
            ],
        )
