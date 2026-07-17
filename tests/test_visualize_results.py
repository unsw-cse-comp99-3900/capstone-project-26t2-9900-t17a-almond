import tempfile
import unittest
from pathlib import Path

from demo_b.visualize_results import read_rows, render_report


class VisualizationTests(unittest.TestCase):
    def test_report_contains_filters_and_summary(self):
        rows = read_rows(Path("outputs/run_20260710_code_devign_round1/prediction_comparison.csv"))
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.html"
            render_report(rows, report, "Test report")
            content = report.read_text(encoding="utf-8")
        self.assertIn('id="primary-action"', content)
        self.assertIn('id="action-checks"', content)
        self.assertIn("dead_statement", content)
        self.assertIn("largest probability shift", content)


if __name__ == "__main__":
    unittest.main()
