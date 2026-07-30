import tempfile
import unittest
from pathlib import Path

from robustness_experiments.visualize_results import (
    ANALYSIS_FILENAME,
    comparison_groups,
    perturbation_configuration,
    read_rows,
    render_index,
    render_report,
    success_term,
    wilson_interval,
)


def row(
    action: str,
    *,
    sample: str,
    budget: str = "",
    base: float = 0.8,
    variant: float = 0.2,
    flipped: bool = True,
    attack_success: str | None = None,
) -> dict[str, str]:
    result = {
        "sample": sample,
        "action": action,
        "budget": budget,
        "function": "f",
        "status": "success",
        "base_label": "1",
        "variant_label": "0" if flipped else "1",
        "flipped": str(flipped),
        "base_prob": str(base),
        "variant_prob": str(variant),
        "delta_prob": str(variant - base),
        "delta_nodes": "1",
        "delta_edges": "2",
    }
    if attack_success is not None:
        result["attack_success"] = attack_success
    return result


class VisualizationTests(unittest.TestCase):
    def test_fixed_budget_report_uses_single_variable_comparisons(self):
        rows = [
            row("dead_statement", sample="a", flipped=True),
            row("dead_statement", sample="b", flipped=False, variant=0.7),
            row("control_wrapper", sample="a", flipped=False, variant=0.75),
            row("control_wrapper", sample="b", flipped=False, variant=0.77),
        ]
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.html"
            render_report(rows, report, "Code report")
            content = report.read_text(encoding="utf-8")
            analysis = (report.parent / ANALYSIS_FILENAME).read_text(encoding="utf-8")
        self.assertIn("Effectiveness at a controlled fixed setting", content)
        self.assertIn("only perturbation method changes", content)
        self.assertIn("95% Wilson intervals", content)
        self.assertIn("Evidence-backed observations", content)
        self.assertEqual(content.count('class="comparison-chart"'), 7)
        self.assertIn("Effect direction", content)
        self.assertIn("Sample-level effect distribution", content)
        self.assertIn("Applicability at the fixed setting", content)
        self.assertIn("Realised structural perturbation", content)
        self.assertNotIn("Sample robustness matrix", content)
        self.assertIn("Bilingual analysis notes / 中英文分析说明", content)
        self.assertIn("## 中文说明", analysis)
        self.assertIn("## English Notes", analysis)
        self.assertIn("95% Wilson CI", analysis)
        self.assertNotEqual(ANALYSIS_FILENAME.lower(), "readme.md")

    def test_budget_report_has_one_line_per_method_and_shared_budgets(self):
        rows = []
        for method in ("winner_xfg_edge_attack", "winner_xfg_feature_mask", "targeted_subgraph_injection"):
            for budget in ("1", "3", "5"):
                for sample_index in range(4):
                    success = sample_index < int(budget) // 2
                    rows.append(
                        row(
                            method,
                            sample=f"s{sample_index}",
                            budget=budget,
                            flipped=success,
                            attack_success=str(success),
                        )
                    )
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "targeted.html"
            render_report(rows, report, "Targeted report")
            content = report.read_text(encoding="utf-8")
            analysis = (report.parent / ANALYSIS_FILENAME).read_text(encoding="utf-8")
        self.assertEqual(success_term(rows), "Attack Success Rate (ASR)")
        self.assertIn("Effectiveness under controlled budget changes", content)
        self.assertIn("Each panel changes only perturbation budget", content)
        self.assertIn("non-decreasing budget-response pattern", content)
        self.assertEqual(content.count('class="comparison-chart"'), 7)
        self.assertIn("Scored coverage rate", content)
        self.assertIn("Mean absolute node change", content)
        self.assertIn("Sample probability change distributions by budget", content)
        for budget in (">1<", ">3<", ">5<"):
            self.assertIn(budget, content)
        for method in ("XFG edge attack", "XFG feature mask", "targeted subgraph injection"):
            self.assertIn(method, content)
        self.assertIn("预算响应", analysis)
        self.assertIn("budget response", analysis)
        self.assertIn("B1=", analysis)

    def test_group_statistics_keep_attempted_and_scored_counts_separate(self):
        rows = [row("range_clamp", sample="a", flipped=False)]
        skipped = row("range_clamp", sample="b", flipped=False)
        skipped["status"] = "skipped"
        skipped["delta_prob"] = ""
        rows.append(skipped)
        group = comparison_groups(rows)[0]
        self.assertEqual(group["attempted"], 2)
        self.assertEqual(group["scored"], 1)
        self.assertEqual(group["budget"], 1)
        self.assertEqual(group["coverage_rate"], 0.5)
        self.assertEqual(group["mean_abs_nodes"], 1.0)
        self.assertEqual(group["mean_abs_edges"], 2.0)

    def test_wilson_interval_is_bounded_and_contains_rate(self):
        low, high = wilson_interval(3, 10)
        self.assertGreaterEqual(low, 0)
        self.assertLessEqual(high, 1)
        self.assertLess(low, 0.3)
        self.assertGreater(high, 0.3)

    def test_graph_budget_schema_is_normalised(self):
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "comparison.csv"
            csv_path.write_text(
                "sample,action,budget,status,base_prob,variant_prob,delta_probability,delta_nodes,delta_edges,flipped,attack_success\n"
                "s,winner_xfg_edge_attack,3,success,0.8,0.2,-0.6,0,3,True,True\n",
                encoding="utf-8",
            )
            rows = read_rows(csv_path)
        self.assertEqual(rows[0]["delta_prob"], "-0.6")
        self.assertEqual(perturbation_configuration(rows[0]), ("winner_xfg_edge_attack", "budget 3"))

    def test_result_views_use_one_dropdown_with_current_page_selected(self):
        rows = [row("dead_statement", sample="a", flipped=False)]
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "run_test"
            random_dir = run / "graph_random"
            targeted_dir = run / "graph_targeted"
            random_dir.mkdir(parents=True)
            targeted_dir.mkdir(parents=True)
            for comparison in (
                run / "prediction_comparison.csv",
                random_dir / "prediction_comparison.csv",
                targeted_dir / "prediction_comparison.csv",
            ):
                comparison.write_text("available", encoding="utf-8")

            main_report = run / "dashboard.html"
            render_report(rows, main_report, "Main report")
            main_content = main_report.read_text(encoding="utf-8")
            render_report(rows, random_dir / "dashboard.html", "Random report")
            random_content = (random_dir / "dashboard.html").read_text(encoding="utf-8")

        self.assertIn('id="report-selector"', main_content)
        self.assertEqual(main_content.count("Random graph baseline"), 1)
        self.assertEqual(main_content.count("Winner-XFG targeted"), 1)
        self.assertIn('<option value="dashboard.html" selected>Code perturbations</option>', main_content)
        self.assertIn('<option value="dashboard.html" selected>Random graph baseline</option>', random_content)
        self.assertNotIn('class="related"', main_content)

    def test_current_full_run_and_subreports_render_when_present(self):
        runs = sorted(Path("outputs").glob("run_*/prediction_comparison.csv"))
        if not runs:
            self.skipTest("no local experiment run")
        latest = runs[-1].parent
        comparisons = [latest / "prediction_comparison.csv"]
        comparisons.extend(path for path in (
            latest / "graph_random" / "prediction_comparison.csv",
            latest / "graph_targeted" / "prediction_comparison.csv",
        ) if path.is_file())
        with tempfile.TemporaryDirectory() as directory:
            for comparison in comparisons:
                report = Path(directory) / f"{comparison.parent.name}.html"
                render_report(read_rows(comparison), report, comparison.parent.name)
                content = report.read_text(encoding="utf-8")
                self.assertIn("Statistical evidence", content)
                self.assertIn("Variant evidence", content)

    def test_index_links_to_each_dashboard(self):
        run = sorted(Path("outputs").glob("run_*/prediction_comparison.csv"))[-1].parent
        with tempfile.TemporaryDirectory() as directory:
            index = Path(directory) / "index.html"
            render_index([run], index)
            content = index.read_text(encoding="utf-8")
        self.assertIn("DeepWuKong experiment index", content)
        self.assertIn(f"{run.name}/dashboard.html", content)


if __name__ == "__main__":
    unittest.main()
