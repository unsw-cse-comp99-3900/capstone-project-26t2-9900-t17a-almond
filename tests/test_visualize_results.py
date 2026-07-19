import tempfile
import unittest
from pathlib import Path

from demo_b.visualize_results import (
    method_intensity_heatmap,
    perturbation_configuration,
    read_rows,
    render_index,
    render_report,
    robustness_summary,
    success_matrix,
    success_term,
)


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
        self.assertIn('class="chart-scroll success-chart"', content)
        self.assertIn('class="data-scroll summary-table-scroll"', content)
        self.assertIn('class="data-scroll"', content)
        self.assertIn('class="variant-table"', content)
        self.assertIn("Prediction Flip Rate by configuration", content)
        self.assertIn("Sample robustness matrix", content)
        self.assertNotIn('id="primary-action"', content)
        self.assertIn("dead_statement", content)
        self.assertIn("Sensitivity diagnostic", content)

    def test_graph_targeted_run_has_asr_summary_heatmap_and_nine_column_matrix(self):
        rows = read_rows(Path("outputs/run_20260717_graph_cwe119_round2/prediction_comparison.csv"))
        self.assertEqual(success_term(rows), "Attack Success Rate (ASR)")
        self.assertEqual(robustness_summary(rows)["overall"], (8, 72))
        heatmap = method_intensity_heatmap(rows)
        for method in ("winner_xfg_edge_attack", "winner_xfg_feature_mask", "targeted_subgraph_injection"):
            self.assertIn(method, heatmap)
        for budget in ("budget 1", "budget 3", "budget 5"):
            self.assertIn(budget, heatmap)
        matrix = success_matrix(rows)
        self.assertEqual(matrix.count("<th>winner_xfg_"), 6)
        self.assertEqual(matrix.count("<th>targeted_subgraph_injection"), 3)

    def test_code_configuration_count_and_flip_terminology(self):
        rows = read_rows(Path("outputs/run_20260717_code_devign_round1/prediction_comparison.csv"))
        self.assertEqual(perturbation_configuration(rows[0]), ("data_flow_alias", "count 1"))
        self.assertEqual(success_term(rows), "Prediction Flip Rate")
        report = method_intensity_heatmap(rows)
        self.assertIn("count 1", report)
        self.assertIn("count 3", report)
        self.assertIn("count 5", report)

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
