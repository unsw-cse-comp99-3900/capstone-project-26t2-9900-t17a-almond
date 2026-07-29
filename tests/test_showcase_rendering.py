from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from baselines.deepwukong.scripts.generate_showcase_results import (
    build_and_predict_variant,
    effective_winner_nodes,
)
from robustness_experiments.showcase.generate_showcase import (
    CODE_ACTIONS,
    PDG_DISPLAY_NODE_LIMIT,
    PDG_DISPLAY_EDGE_LIMIT,
    PDG_CONTROL_EDGE_BUDGET,
    Pdg,
    PdgFocus,
    PdgEdge,
    PdgNode,
    Sample,
    action_focus,
    build_source_catalog,
    discover_samples,
    pdg_display_slice,
    render_inline_diff,
    render_pdg_svg,
    result_to_payload,
    serialize_pdg,
    statement_kind,
)


class ShowcaseRenderingTests(unittest.TestCase):
    def test_inline_diff_keeps_full_source_and_omits_blank_rows(self) -> None:
        rendered = render_inline_diff(
            "first();\n\nold();\nlast();\n",
            "first();\n\nnew();\nlast();\n",
        )

        self.assertEqual(rendered.count('class="inline-line'), 5)
        self.assertNotIn('class="inline-code"></span>', rendered)
        self.assertIn('diff-remove', rendered)
        self.assertIn('>old();</span>', rendered)
        self.assertIn('diff-add', rendered)
        self.assertIn('>new();</span>', rendered)
        self.assertIn('>last();</span>', rendered)

    def test_inline_diff_preserves_original_and_selected_line_numbers(self) -> None:
        rendered = render_inline_diff("first();\nsecond();\n", "first();\ninserted();\nsecond();\n")

        self.assertIn('<span class="inline-number" aria-hidden="true">2</span>', rendered)
        self.assertIn('<span class="inline-marker" aria-hidden="true">+</span>', rendered)
        self.assertIn('>inserted();</span>', rendered)

    def test_inline_diff_marks_source_rows_for_graph_navigation(self) -> None:
        rendered = render_inline_diff("old();\n", "new();\n")

        self.assertIn('data-old-line="1" data-new-line=""', rendered)
        self.assertIn('data-old-line="" data-new-line="1"', rendered)

    def test_large_pdg_slice_keeps_focus_and_caps_browser_payload(self) -> None:
        node_count = PDG_DISPLAY_NODE_LIMIT + 40
        pdg = Pdg(
            nodes=tuple(PdgNode(node_id=index, source_line=index) for index in range(node_count)),
            edges=tuple(
                PdgEdge(source=index, target=index + 1, kind="data")
                for index in range(node_count - 1)
            ),
        )

        nodes, edges, truncated = pdg_display_slice(pdg, {node_count - 1})
        visible_ids = {node.node_id for node in nodes}

        self.assertTrue(truncated)
        self.assertEqual(len(nodes), PDG_DISPLAY_NODE_LIMIT)
        self.assertIn(node_count - 1, visible_ids)
        self.assertTrue(
            all(edge.source in visible_ids and edge.target in visible_ids for edge in edges)
        )

    def test_dense_pdg_slice_prioritizes_focus_edges_and_caps_edge_payload(self) -> None:
        pdg = Pdg(
            nodes=tuple(PdgNode(node_id=index, source_line=index) for index in range(12)),
            edges=tuple(
                PdgEdge(source=source, target=target, kind="data")
                for source in range(12)
                for target in range(12)
                if source != target
            ),
        )

        _nodes, edges, truncated = pdg_display_slice(pdg, {11}, {(11, 0)})

        self.assertTrue(truncated)
        self.assertEqual(len(edges), PDG_DISPLAY_EDGE_LIMIT)
        self.assertEqual((edges[0].source, edges[0].target), (11, 0))

    def test_dense_pdg_slice_reserves_edge_budget_for_both_types(self) -> None:
        pdg = Pdg(
            nodes=tuple(PdgNode(node_id=index, source_line=index + 1) for index in range(20)),
            edges=tuple(
                PdgEdge(
                    source=source,
                    target=target,
                    kind="control" if (source + target) % 2 == 0 else "data",
                )
                for source in range(20)
                for target in range(20)
                if source != target
            ),
        )

        focused_controls = {
            (edge.source, edge.target)
            for edge in pdg.edges
            if edge.kind == "control"
        }
        _nodes, edges, truncated = pdg_display_slice(pdg, {10}, focused_controls)

        self.assertTrue(truncated)
        self.assertEqual(len(edges), PDG_DISPLAY_EDGE_LIMIT)
        self.assertGreaterEqual(
            sum(edge.kind == "control" for edge in edges),
            PDG_CONTROL_EDGE_BUDGET,
        )
        self.assertGreaterEqual(
            sum(edge.kind == "data" for edge in edges),
            PDG_DISPLAY_EDGE_LIMIT - PDG_CONTROL_EDGE_BUDGET,
        )

    def test_graph_action_focus_keeps_exact_removed_and_added_edges(self) -> None:
        original = Pdg(
            nodes=(PdgNode(1, 1), PdgNode(2, 2), PdgNode(3, 3)),
            edges=(PdgEdge(1, 2, "data"),),
        )
        selected = Pdg(
            nodes=(PdgNode(1, 1), PdgNode(2, 2), PdgNode(3, 3)),
            edges=(PdgEdge(1, 3, "data"),),
        )
        result = {
            "operations": [
                {
                    "target_nodes": [1, 2, 3],
                    "removed_edges": [[1, 2, "d"]],
                    "added_edges": [[1, 3, "d"]],
                }
            ]
        }

        original_focus, selected_focus = action_focus(
            original,
            selected,
            "edge_reconnect",
            result,
            "a\nb\nc\n",
            "a\nb\nc\n",
        )

        self.assertEqual(original_focus.edges, frozenset({(1, 2)}))
        self.assertEqual(selected_focus.edges, frozenset({(1, 3)}))
        self.assertEqual(original_focus.nodes, frozenset({1, 2, 3}))
        self.assertEqual(selected_focus.nodes, frozenset({1, 2, 3}))

    def test_node_deletion_focus_keeps_surviving_context_in_large_selected_graph(self) -> None:
        original = Pdg(
            nodes=tuple(PdgNode(index, index + 1) for index in range(60)),
            edges=tuple(PdgEdge(index, index + 1, "data") for index in range(59)),
        )
        selected = Pdg(
            nodes=original.nodes[:-1],
            edges=original.edges[:-1],
        )
        result = {
            "operations": [
                {
                    "target_nodes": [59],
                    "removed_edges": [[58, 59, "d"]],
                    "added_edges": [],
                }
            ]
        }

        _original_focus, selected_focus = action_focus(
            original,
            selected,
            "node_delete",
            result,
            "\n".join(f"line_{index}" for index in range(60)),
            "\n".join(f"line_{index}" for index in range(59)),
        )
        nodes, _edges, truncated = pdg_display_slice(
            selected,
            set(selected_focus.nodes),
            set(selected_focus.edges),
        )

        self.assertEqual(selected_focus.nodes, frozenset({58}))
        self.assertTrue(truncated)
        self.assertIn(58, {node.node_id for node in nodes})

    def test_rendered_focus_edges_keep_their_type_for_cleared_highlights(self) -> None:
        pdg = Pdg(
            nodes=(PdgNode(1, 1), PdgNode(2, 2)),
            edges=(PdgEdge(1, 2, "data"),),
        )
        focus = PdgFocus(frozenset({2}), frozenset({(1, 2)}))

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rendered = render_pdg_svg(
                pdg,
                "first();\nsecond();\n",
                "focus-edge-test",
                "Focus edge test",
                root,
                root / "cache",
                focus,
            )

        self.assertIn("change-node", rendered)
        self.assertIn("change-edge data-edge", rendered)

    def test_statement_kind_does_not_treat_comparison_calls_as_assignment(self) -> None:
        node = PdgNode(1, 1)

        self.assertEqual(statement_kind("check(actual == expected);\n", node), "CALL")
        self.assertEqual(statement_kind("value += delta;\n", node), "ASSIGN")


    def test_wide_pdg_uses_compact_source_order_lanes(self) -> None:
        pdg = Pdg(
            nodes=tuple(PdgNode(index, index + 1) for index in range(40)),
            edges=tuple(
                PdgEdge(0, index, "control" if index % 2 == 0 else "data")
                for index in range(1, 40)
            ),
        )
        source = "\n".join(f"call_{index}();" for index in range(40))

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rendered = render_pdg_svg(
                pdg,
                source,
                "wide-layout-test",
                "Wide layout test",
                root,
                root / "cache",
                PdgFocus(frozenset({0}), frozenset({(0, 1)})),
            )

        self.assertIn('data-layout="source-order-lanes"', rendered)
        self.assertIn("L1 · CALL", rendered)
        self.assertIn("control-edge", rendered)
        self.assertIn("data-edge", rendered)

    def test_render_cache_refreshes_source_metadata_when_topology_is_unchanged(self) -> None:
        pdg = Pdg(nodes=(PdgNode(1, 1),), edges=())
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            first = render_pdg_svg(
                pdg,
                "check(actual == expected);\n",
                "metadata-cache-test",
                "Metadata cache test",
                root,
                cache,
            )
            second = render_pdg_svg(
                pdg,
                "check(actual != expected);\n",
                "metadata-cache-test",
                "Metadata cache test",
                root,
                cache,
            )

        self.assertIn("actual == expected", first)
        self.assertIn("actual != expected", second)
        self.assertNotIn("actual == expected", second)

    def test_serialized_pdg_keeps_complete_dependency_evidence(self) -> None:
        pdg = Pdg(
            nodes=(PdgNode(1, 1), PdgNode(2, 2)),
            edges=(PdgEdge(1, 2, "data"),),
        )

        payload = serialize_pdg(pdg, "value = source();\nsink(value);\n")

        self.assertEqual([node["id"] for node in payload["nodes"]], [1, 2])
        self.assertEqual(
            payload["edges"],
            [{"source": 1, "target": 2, "kind": "data"}],
        )

    def test_showcase_configures_all_thirteen_code_actions(self) -> None:
        self.assertEqual(
            CODE_ACTIONS,
            (
                "data_flow_alias",
                "dead_statement",
                "xfg_targeted_dead_code",
                "range_clamp",
                "safe_source_substitution",
                "sink_bound_guard",
                "postcondition_validation",
                "integer_overflow_guard",
                "array_index_bound_guard",
                "wide_char_sink_guard",
                "pattern_dead_code",
                "control_wrapper",
                "temp_variable_split",
            ),
        )

    def test_catalog_stages_complete_manifest_source_for_inference(self) -> None:
        source_text = """static int helper(void)
{
    return 1;
}

static int target(int value)
{
    int result = value + 1;
    return result;
}
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            source_path = temp_root / "multi.c"
            source_path.write_text(source_text, encoding="utf-8")
            sample = Sample(
                key="fixture",
                sample_id="fixture",
                dataset="cwe119",
                subgroup="vulnerable",
                label=1,
                label_name="vulnerable",
                source_kind="project_curated",
                source_path=source_path,
                relative_path="cwe119/vulnerable/multi.c",
                function_name="target",
            )

            catalog = build_source_catalog([sample], temp_root / "staged", "test-image")
            catalog_item = catalog["samples"][0]
            original = (temp_root / "staged" / catalog_item["source_relpath"]).read_text()

            self.assertEqual(catalog_item["function_hint"], "target")
            self.assertEqual(catalog_item["label"], 1)
            self.assertEqual(catalog_item["source_kind"], "project_curated")
            self.assertIn("static int helper", original)
            self.assertIn("static int target", original)
            self.assertTrue(catalog_item["variants"])
            for relative_path in catalog_item["variants"].values():
                variant = (temp_root / "staged" / relative_path).read_text()
                self.assertIn("static int helper", variant)
                self.assertIn("static int target", variant)

    def test_discover_samples_uses_staged_manifest_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_root = Path(temp_dir)
            source = input_root / "cwe119" / "vulnerable" / "fixture.c"
            source.parent.mkdir(parents=True)
            source.write_text("int target(void) { return 1; }\n", encoding="utf-8")
            with (input_root / "sample_manifest.csv").open(
                "w", encoding="utf-8", newline=""
            ) as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "dataset",
                        "sample_id",
                        "label",
                        "label_name",
                        "source_kind",
                        "function_name",
                        "staged_file",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "dataset": "cwe119",
                        "sample_id": "fixture",
                        "label": "1",
                        "label_name": "vulnerable",
                        "source_kind": "project_curated",
                        "function_name": "target",
                        "staged_file": "input_sources/cwe119/vulnerable/fixture.c",
                    }
                )

            samples = discover_samples(input_root)

            self.assertEqual(len(samples), 1)
            self.assertEqual(samples[0].key, "cwe119--fixture")
            self.assertEqual(samples[0].label, 1)
            self.assertEqual(samples[0].source_kind, "project_curated")
            self.assertEqual(samples[0].source_path, source)

    def test_effective_winner_nodes_prefers_recorded_xfg_members(self) -> None:
        class Graph:
            nodes = (10, 20, 30)

            @staticmethod
            def degree(node: int) -> int:
                return {10: 1, 20: 3, 30: 2}[node]

        nodes, source = effective_winner_nodes(
            Graph(),
            {"key_line": 19, "nodes": [20, 999]},
        )

        self.assertEqual(nodes, [20])
        self.assertEqual(source, "winner_xfg")

    def test_effective_winner_nodes_falls_back_near_key_line(self) -> None:
        class Graph:
            nodes = (10, 20, 30)

            @staticmethod
            def degree(node: int) -> int:
                return {10: 1, 20: 3, 30: 2}[node]

        nodes, source = effective_winner_nodes(
            Graph(),
            {"key_line": 24, "nodes": [999]},
            limit=2,
        )

        self.assertEqual(nodes, [20, 30])
        self.assertEqual(source, "nearest_pdg_nodes")

    def test_variant_without_xfg_is_not_presented_as_a_prediction(self) -> None:
        class Predictor:
            @staticmethod
            def build_graph(_csv_root: Path, _source_path: Path) -> tuple[object, dict[str, set[int]]]:
                return object(), {}

            @staticmethod
            def predict_graph(
                _pdg: object,
                _key_line_map: dict[str, set[int]],
                _add_symbols: object,
            ) -> dict[str, object]:
                return {"status": "no_xfg", "probability": 0.0, "label": 0}

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sample.c"
            source.write_text("int sample(void) { return 0; }\n", encoding="utf-8")

            def run_joern(**_kwargs: object) -> dict[str, str]:
                csv_dir = root / "joern-output"
                csv_dir.mkdir()
                (csv_dir / "nodes.csv").write_text("key\n", encoding="utf-8")
                (csv_dir / "edges.csv").write_text("start,end\n", encoding="utf-8")
                return {"parse_status": "success", "selected_csv_dir": str(csv_dir)}

            with self.assertRaisesRegex(RuntimeError, "no_xfg"):
                build_and_predict_variant(
                    predictor=Predictor(),
                    add_symbols=object(),
                    run_joern=run_joern,
                    source_path=source,
                    cache_dir=root / "cache",
                    joern_bin=root / "joern",
                    joern_timeout=1,
                )

    def test_partial_targeted_budget_displays_actual_applied_count(self) -> None:
        pdg = Pdg(nodes=(PdgNode(1, 1),), edges=())
        result = {
            "action": "winner_xfg_feature_mask",
            "strategy": "winner_xfg",
            "budget": 5,
            "applied_count": 2,
            "operations": [{"target_nodes": [1], "details": "masked two nodes"}],
            "prediction": {"probability": 0.2, "label": 0, "xfg_count": 1},
            "graph": {"nodes": [{"id": 1}], "edges": []},
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload = result_to_payload(
                "winner_xfg_feature_mask__b5",
                "graph",
                result,
                "return value;\n",
                "return value;\n",
                pdg,
                {"probability": 0.1, "label": 0, "xfg_count": 1},
                root,
                "sample",
                root / "cache",
            )

        self.assertIn("budget 5 · applied 2", payload["short"])
        self.assertEqual(payload["applied_count"], 2)


if __name__ == "__main__":
    unittest.main()
