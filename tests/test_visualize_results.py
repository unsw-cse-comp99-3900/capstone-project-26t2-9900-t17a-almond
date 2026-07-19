import tempfile
import unittest
from pathlib import Path

from demo_b.visualize_results import read_rows, render_index, render_report


class VisualizationTests(unittest.TestCase):
    def test_report_contains_filters_and_summary(self):
        rows = read_rows(Path("outputs/run_20260710_code_devign_round1/prediction_comparison.csv"))
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.html"
            render_report(rows, report, "Test report")
            content = report.read_text(encoding="utf-8")
        self.assertIn('id="action-checks"', content)
        self.assertIn('id="select-all"', content)
        self.assertIn('class="method-picker"', content)
        self.assertIn('class="table-scroll"', content)
        self.assertIn('class="variant-table"', content)
        self.assertNotIn('id="primary-action"', content)
        self.assertIn("dead_statement", content)
        self.assertIn("What changed most?", content)

    def test_graph_budget_schema_and_incomplete_rows_are_supported(self):
        rows = read_rows(Path("outputs/run_20260717_graph_cwe119_round2/prediction_comparison.csv"))
        self.assertEqual(rows[0]["delta_prob"], rows[0]["delta_probability"])
        self.assertEqual(rows[0]["budget"], "1")
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "graph-report.html"
            render_report(
                rows, report, "Graph run",
                [("run_one", "../run_one/dashboard.html"), ("run_two", "../run_two/dashboard.html")],
                "run_two",
            )
            graph_content = report.read_text(encoding="utf-8")
        self.assertIn("winner_xfg_edge_attack | budget 1", graph_content)
        self.assertIn("targeted_subgraph_injection | budget 5", graph_content)
        self.assertEqual(graph_content.count('type="checkbox"'), 10)  # 9 configurations plus All
        self.assertIn('id="run-selector"', graph_content)
        self.assertIn('option value="../run_two/dashboard.html" selected', graph_content)

        code_rows = read_rows(Path("outputs/run_20260717_code_devign_round1/prediction_comparison.csv"))
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.html"
            render_report(code_rows, report, "Code run")
            content = report.read_text(encoding="utf-8")
        self.assertIn("unscored / incomplete", content)

    def test_every_archived_comparison_table_renders(self):
        comparisons = sorted(Path("outputs").glob("run_*/prediction_comparison.csv"))
        self.assertGreaterEqual(len(comparisons), 1)
        with tempfile.TemporaryDirectory() as directory:
            for comparison in comparisons:
                report = Path(directory) / f"{comparison.parent.name}.html"
                render_report(read_rows(comparison), report, comparison.parent.name)
                self.assertIn('class="table-scroll"', report.read_text(encoding="utf-8"))

    def test_index_links_to_each_dashboard(self):
        runs = [
            Path("outputs/run_20260717_code_cwe119_round1"),
            Path("outputs/run_20260717_graph_cwe119_round2"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            index = Path(directory) / "index.html"
            render_index(runs, index)
            content = index.read_text(encoding="utf-8")
        self.assertIn("DeepWuKong experiment index", content)
        self.assertIn("run_20260717_code_cwe119_round1/dashboard.html", content)
        self.assertIn("run_20260717_graph_cwe119_round2/dashboard.html", content)


if __name__ == "__main__":
    unittest.main()
