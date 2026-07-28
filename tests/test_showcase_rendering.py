from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from demo_b.showcase.generate_showcase import (
    PDG_DISPLAY_NODE_LIMIT,
    PDG_DISPLAY_EDGE_LIMIT,
    Pdg,
    PdgFocus,
    PdgEdge,
    PdgNode,
    Sample,
    action_focus,
    build_source_catalog,
    load_cve_target_functions,
    pdg_display_slice,
    render_inline_diff,
    render_pdg_svg,
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
            "graph",
            result,
            "a\nb\nc\n",
            "a\nb\nc\n",
        )

        self.assertEqual(original_focus.edges, frozenset({(1, 2)}))
        self.assertEqual(selected_focus.edges, frozenset({(1, 3)}))
        self.assertEqual(original_focus.nodes, frozenset({1, 2, 3}))
        self.assertEqual(selected_focus.nodes, frozenset({1, 2, 3}))

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

    def test_catalog_stages_only_the_selected_function(self) -> None:
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
                source_path=source_path,
                relative_path="cwe119/vulnerable/multi.c",
                target_function=None,
                target_line=8,
            )

            catalog = build_source_catalog([sample], temp_root / "staged", "test-image")
            catalog_item = catalog["samples"][0]
            original = (temp_root / "staged" / catalog_item["source_relpath"]).read_text()

            self.assertEqual(catalog_item["function_hint"], "target")
            self.assertIn("static int target", original)
            self.assertNotIn("helper", original)
            self.assertTrue(catalog_item["variants"])
            for relative_path in catalog_item["variants"].values():
                variant = (temp_root / "staged" / relative_path).read_text()
                self.assertNotIn("helper", variant)

    def test_cve_target_falls_back_to_the_actual_changed_function(self) -> None:
        unchanged = """static int helper(void)
{
    return 1;
}
"""
        vulnerable_target = """static int target(void)
{
    return 1;
}
"""
        fixed_target = vulnerable_target.replace("return 1;", "return 2;")
        with tempfile.TemporaryDirectory() as temp_dir:
            input_root = Path(temp_dir)
            cve_root = input_root / "cvefixes"
            fixed_root = cve_root / "fixed"
            vulnerable_root = cve_root / "vulnerable"
            fixed_root.mkdir(parents=True)
            vulnerable_root.mkdir()
            (cve_root / "metadata.csv").write_text(
                "sample_id,changed_functions\n04,helper\n",
                encoding="utf-8",
            )
            (fixed_root / "04_fixture.c").write_text(
                unchanged + fixed_target,
                encoding="utf-8",
            )
            (vulnerable_root / "04_fixture.c").write_text(
                unchanged + vulnerable_target,
                encoding="utf-8",
            )

            targets = load_cve_target_functions(input_root)

            self.assertEqual(targets["04"], "target")


if __name__ == "__main__":
    unittest.main()
