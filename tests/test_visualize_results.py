import tempfile
import unittest
from pathlib import Path

from robustness_experiments.visualize_results import (
    ANALYSIS_FILENAME,
    build_graph_comparison_rows,
    comparison_groups,
    paired_common_summaries,
    perturbation_configuration,
    read_rows,
    render_index,
    render_report,
    sample_level_summaries,
    seed_level_summaries,
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
    seed: str = "",
    baseline_eligible: str = "",
    method_family: str = "",
    status: str = "success",
) -> dict[str, str]:
    result = {
        "sample": sample,
        "action": action,
        "budget": budget,
        "seed": seed,
        "baseline_eligible": baseline_eligible,
        "function": "f",
        "status": status,
        "method_family": method_family,
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
        self.assertEqual(content.count('class="comparison-chart'), 7)
        self.assertEqual(content.count('class="chart-explanation"'), 7)
        self.assertIn("Terminology / 名词解释", content)
        self.assertIn('class="chart-key-detail"', content)
        self.assertIn("它不是置信区间，也不是标准差", content)
        self.assertIn("Effect direction", content)
        self.assertIn("Sample-level effect distribution", content)
        self.assertIn('class="estimate-bar', content)
        self.assertIn('class="comparison-chart vertical-bar-chart"', content)
        self.assertIn("Bar height = observed estimate", content)
        self.assertIn("Charts show observed estimates without confidence-interval error bars", content)
        self.assertNotIn('<line class="ci-whisker"', content)
        self.assertNotIn('<p class="confidence-note"', content)
        self.assertIn("Box = middle 50% of sample changes", content)
        self.assertIn("Whiskers = observed minimum to maximum", content)
        self.assertIn("Applicability at the fixed setting", content)
        self.assertIn("Realised structural perturbation", content)
        self.assertNotIn("Sample robustness matrix", content)
        self.assertIn("Bilingual analysis notes / 中英文分析说明", content)
        self.assertIn("## 中文说明", analysis)
        self.assertIn("## English Notes", analysis)
        self.assertIn("## Chart-by-chart Conclusions / 各图表推论", analysis)
        self.assertIn("| 有效性 / Effectiveness |", analysis)
        self.assertIn("| 样本级分布 / Sample-level distribution |", analysis)
        self.assertIn("### 数据规律", analysis)
        self.assertIn("### Observed patterns", analysis)
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
        self.assertIn("Fixed-budget vertical bar panels hold budget fixed", content)
        self.assertIn("Budget-response line panels hold the method fixed", content)
        self.assertIn("non-decreasing budget-response pattern", content)
        self.assertEqual(content.count('class="comparison-chart'), 10)
        self.assertEqual(content.count('class="chart-explanation"'), 10)
        self.assertIn("Terminology / 名词解释", content)
        self.assertIn("线段只帮助观察趋势", content)
        self.assertIn("Scored coverage rate", content)
        self.assertIn("Mean absolute node change", content)
        self.assertIn("Sample probability change distributions by budget", content)
        self.assertIn('class="comparison-chart distribution-facets"', content)
        self.assertIn('class="axis-label budget-label"', content)
        self.assertIn('transform="rotate(-45', content)
        self.assertIn("Control: each panel keeps one perturbation method fixed", content)
        self.assertIn("not a 95% confidence interval", content)
        self.assertIn("Circle = observed estimate", content)
        self.assertIn("Charts show observed estimates without confidence-interval error bars", content)
        self.assertNotIn('<line class="ci-whisker"', content)
        self.assertNotIn("Vertical capped line = 95% confidence interval", content)
        self.assertIn("Dark reference line = no average change", content)
        self.assertIn('class="estimate-bar', content)
        for budget in (">1<", ">3<", ">5<"):
            self.assertIn(budget, content)
        for method in ("XFG edge attack", "XFG feature mask", "targeted subgraph injection"):
            self.assertIn(method, content)
        self.assertIn("预算响应", analysis)
        self.assertIn("budget response", analysis)
        self.assertIn("B1=", analysis)
        self.assertIn("## Chart Reading Guide / 图表理解对照表", analysis)
        self.assertIn("## Chart-by-chart Conclusions / 各图表推论", analysis)
        self.assertIn("| Budget响应 / Budget response |", analysis)
        self.assertIn("| 结构变化 / Realised structural change |", analysis)
        self.assertIn("| 95%置信区间 | 95% confidence interval |", analysis)
        self.assertIn("does not draw 95% confidence intervals as error bars", analysis)
        self.assertIn("| 须线 | Whiskers |", analysis)

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

    def test_multi_seed_asr_uses_only_baseline_eligible_rows(self):
        rows = []
        for seed in ("7", "17", "29"):
            rows.append(
                row(
                    "winner_xfg_edge_attack",
                    sample="eligible",
                    budget="1",
                    seed=seed,
                    baseline_eligible="True",
                    attack_success="True",
                )
            )
            rows.append(
                row(
                    "winner_xfg_edge_attack",
                    sample="baseline_error",
                    budget="1",
                    seed=seed,
                    baseline_eligible="False",
                    attack_success="",
                )
            )

        group = comparison_groups(rows)[0]

        self.assertEqual(group["seed_count"], 3)
        self.assertEqual(group["scored"], 6)
        self.assertEqual(group["outcome_scored"], 3)
        self.assertEqual(group["successes"], 3)
        self.assertEqual(group["success_rate"], 1.0)

    def test_sample_and_seed_summaries_do_not_treat_seeds_as_new_samples(self):
        rows = [
            row(
                "node_add",
                sample=sample,
                budget="1",
                seed=seed,
                baseline_eligible="True",
                attack_success=str(sample == "a" and seed == "7"),
            )
            for sample in ("a", "b")
            for seed in ("7", "17")
        ]

        sample_summary = sample_level_summaries(rows)[0]
        seed_summaries = seed_level_summaries(rows)

        self.assertEqual(sample_summary["scored_samples"], 2)
        self.assertEqual(sample_summary["any_seed_success_samples"], 1)
        self.assertEqual(sample_summary["any_seed_success_rate"], 0.5)
        self.assertEqual(sample_summary["mean_per_sample_seed_success_rate"], 0.25)
        self.assertEqual(
            {summary["seed"]: summary["success_rate"] for summary in seed_summaries},
            {7: 0.5, 17: 0.0},
        )

    def test_paired_common_summary_excludes_keys_unscored_in_either_family(self):
        rows = [
            row(
                "random_graph::node_add",
                sample="a",
                budget="1",
                seed="7",
                method_family="random_graph",
                baseline_eligible="True",
                attack_success="False",
            ),
            row(
                "winner_xfg::winner_xfg_edge_attack",
                sample="a",
                budget="1",
                seed="7",
                method_family="winner_xfg",
                baseline_eligible="True",
                attack_success="True",
            ),
            row(
                "random_graph::node_delete",
                sample="b",
                budget="1",
                seed="7",
                method_family="random_graph",
                baseline_eligible="True",
                attack_success="",
                status="no_xfg",
            ),
            row(
                "winner_xfg::winner_xfg_edge_attack",
                sample="b",
                budget="1",
                seed="7",
                method_family="winner_xfg",
                baseline_eligible="True",
                attack_success="True",
            ),
        ]

        summaries = paired_common_summaries(rows)

        self.assertEqual({summary["common_samples"] for summary in summaries}, {1})
        self.assertEqual(
            {summary["family"]: summary["common_sample_seed_keys"] for summary in summaries},
            {"random_graph": 1, "winner_xfg": 1},
        )

    def test_multi_budget_seed_report_has_horizontal_vertical_and_seed_filters(self):
        rows = [
            row(
                action,
                sample=f"s{index}",
                budget=budget,
                seed=seed,
                baseline_eligible="True",
                attack_success=str(index == 0),
            )
            for action in ("node_add", "winner_xfg_edge_attack")
            for budget in ("1", "3", "5")
            for seed in ("7", "17")
            for index in range(2)
        ]
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.html"
            render_report(rows, report, "Graph comparison")
            content = report.read_text(encoding="utf-8")
            sample_summary_exists = (report.parent / "sample_level_summary.csv").is_file()
            seed_summary_exists = (report.parent / "seed_level_summary.csv").is_file()

        self.assertIn("Method comparison at each fixed budget", content)
        self.assertIn("Budget response for each fixed method", content)
        self.assertIn('id="seed-selector"', content)
        self.assertIn("<th>Seed</th>", content)
        self.assertIn("Independent-sample outcomes", content)
        self.assertIn("Seed rate mean ± SD [range]", content)
        self.assertTrue(sample_summary_exists)
        self.assertTrue(seed_summary_exists)

    def test_combined_report_writes_paired_common_cohort_evidence(self):
        rows = [
            row(
                action,
                sample=sample,
                budget=budget,
                seed=seed,
                method_family=family,
                baseline_eligible="True",
                attack_success=str(family == "winner_xfg" and sample == "a"),
            )
            for family, action in (
                ("random_graph", "random_graph::node_add"),
                ("winner_xfg", "winner_xfg::winner_xfg_edge_attack"),
            )
            for sample in ("a", "b")
            for budget in ("1", "3")
            for seed in ("7", "17")
        ]
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.html"
            render_report(rows, report, "Combined graph report")
            content = report.read_text(encoding="utf-8")

            self.assertIn("Paired common-cohort comparison", content)
            self.assertIn("Random overall vs Winner-XFG overall by budget", content)
            self.assertIn(
                'aria-label="Random overall versus Winner-XFG overall attack success rate by budget"',
                content,
            )
            self.assertEqual(content.count('class="paired-family-bar"'), 4)
            self.assertIn("Paired bars = Random and Winner-XFG on the same cohort", content)
            self.assertIn("Bar height = variant attack success rate", content)
            self.assertIn('data-family="random_graph" data-budget="1"', content)
            self.assertIn('data-family="winner_xfg" data-budget="3"', content)
            self.assertTrue((report.parent / "paired_common_summary.csv").is_file())

    def test_combined_graph_rows_require_matching_budgets_and_seeds(self):
        header = (
            "sample,action,budget,seed,status,base_prob,variant_prob,delta_probability,"
            "delta_nodes,delta_edges,flipped,attack_success,baseline_eligible\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            for folder, action in (
                ("graph_random", "node_add"),
                ("graph_targeted", "winner_xfg_edge_attack"),
            ):
                target = run / folder
                target.mkdir()
                body = "".join(
                    f"s,{action},{budget},{seed},success,0.8,0.2,-0.6,1,2,True,True,True\n"
                    for budget in ("1", "3", "5")
                    for seed in ("7", "17")
                )
                (target / "prediction_comparison.csv").write_text(header + body, encoding="utf-8")

            combined = build_graph_comparison_rows(run)

        self.assertEqual(len(combined), 12)
        self.assertIn("random_graph::node_add", {item["action"] for item in combined})
        self.assertIn(
            "winner_xfg::winner_xfg_edge_attack",
            {item["action"] for item in combined},
        )

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
            comparison_dir = run / "graph_comparison"
            random_dir.mkdir(parents=True)
            targeted_dir.mkdir(parents=True)
            comparison_dir.mkdir(parents=True)
            for comparison in (
                run / "prediction_comparison.csv",
                random_dir / "prediction_comparison.csv",
                targeted_dir / "prediction_comparison.csv",
                comparison_dir / "prediction_comparison.csv",
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
        self.assertEqual(main_content.count("Random vs Winner-XFG"), 1)
        self.assertIn('<option value="dashboard.html" selected>Code perturbations</option>', main_content)
        self.assertIn('<option value="dashboard.html" selected>Random graph baseline</option>', random_content)
        self.assertIn(
            '<option value="../graph_comparison/dashboard.html">Random vs Winner-XFG</option>',
            random_content,
        )
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
