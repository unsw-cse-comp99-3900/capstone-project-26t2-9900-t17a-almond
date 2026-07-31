from __future__ import annotations

import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

import networkx as nx

from robustness_experiments.graph.graph_perturbations import (
    ACTION_NAMES,
    XFG_TARGETED_ACTION_NAMES,
    apply_graph_action,
    apply_xfg_targeted_action,
    load_joern_pdg,
)
from robustness_experiments.graph.experiment_design import (
    DEFAULT_GRAPH_BUDGETS,
    operations_form_nested_prefix,
)


def sample_pdg() -> nx.DiGraph:
    graph = nx.DiGraph()
    graph.add_edge(10, 20, **{"c/d": "d"})
    graph.add_edge(20, 30, **{"c/d": "c"})
    graph.add_edge(30, 40, **{"c/d": "d"})
    return graph


class GraphPerturbationTests(unittest.TestCase):
    def test_all_actions_modify_a_copy_and_preserve_the_input(self) -> None:
        expected_deltas = {
            "node_add": (1, 1),
            "node_delete": (-1, None),
            "node_attribute_modify": (0, 0),
            "edge_add": (0, 1),
            "edge_delete": (0, -1),
            "edge_reconnect": (0, 0),
        }
        for action in ACTION_NAMES:
            with self.subTest(action=action):
                original = sample_pdg()
                original_nodes = set(original.nodes)
                original_edges = set(original.edges)

                result = apply_graph_action(original, action=action, seed=7, key_lines={20})

                self.assertTrue(result.valid, result.validation_errors)
                self.assertEqual(result.applied_count, 1)
                self.assertEqual(set(original.nodes), original_nodes)
                self.assertEqual(set(original.edges), original_edges)
                node_delta, edge_delta = expected_deltas[action]
                self.assertEqual(result.graph.number_of_nodes() - original.number_of_nodes(), node_delta)
                if edge_delta is not None:
                    self.assertEqual(result.graph.number_of_edges() - original.number_of_edges(), edge_delta)
                self.assertIn(20, result.graph)

    def test_node_add_carries_a_real_source_line_for_symbolization(self) -> None:
        result = apply_graph_action(sample_pdg(), action="node_add", strategy="guided", key_lines={20})

        synthetic_nodes = [node for node, data in result.graph.nodes(data=True) if data.get("synthetic")]
        self.assertEqual(len(synthetic_nodes), 1)
        self.assertGreater(result.graph.nodes[synthetic_nodes[0]]["source_line"], 0)

    def test_node_attribute_modify_changes_feature_source_without_changing_topology(self) -> None:
        original = sample_pdg()

        result = apply_graph_action(
            original,
            action="node_attribute_modify",
            strategy="guided",
            key_lines={20},
        )

        modified = [node for node, data in result.graph.nodes(data=True) if data.get("feature_modified")]
        self.assertEqual(len(modified), 1)
        self.assertEqual(set(result.graph.edges), set(original.edges))
        self.assertNotEqual(result.graph.nodes[modified[0]]["source_line"], modified[0])

    def test_guided_edge_delete_targets_the_edge_nearest_the_key_line(self) -> None:
        result = apply_graph_action(
            sample_pdg(),
            action="edge_delete",
            strategy="guided",
            key_lines={10},
        )

        self.assertNotIn((10, 20), result.graph.edges)
        self.assertIn((20, 30), result.graph.edges)

    def test_guided_strategy_requires_key_lines(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires at least one key line"):
            apply_graph_action(sample_pdg(), action="edge_delete", strategy="guided")

    def test_xfg_targeted_actions_modify_a_copy_and_preserve_key_lines(self) -> None:
        for action in XFG_TARGETED_ACTION_NAMES:
            with self.subTest(action=action):
                original = sample_pdg()
                original_edges = set(original.edges)

                result = apply_xfg_targeted_action(
                    original,
                    action=action,
                    winner_nodes=set(original.nodes),
                    winner_key_line=20,
                    target_label=0,
                    budget=1,
                    key_lines={20},
                    neutral_source_line=40,
                    seed=7,
                )

                self.assertTrue(result.valid, result.validation_errors)
                self.assertEqual(result.applied_count, 1)
                self.assertEqual(set(original.edges), original_edges)
                self.assertIn(20, result.graph)

    def test_winner_xfg_edge_attack_uses_target_direction(self) -> None:
        decrease = apply_xfg_targeted_action(
            sample_pdg(),
            action="winner_xfg_edge_attack",
            winner_nodes={10, 20, 30, 40},
            winner_key_line=20,
            target_label=0,
            key_lines={20},
            neutral_source_line=40,
        )
        increase = apply_xfg_targeted_action(
            sample_pdg(),
            action="winner_xfg_edge_attack",
            winner_nodes={10, 20, 30, 40},
            winner_key_line=20,
            target_label=1,
            key_lines={20},
            neutral_source_line=40,
        )

        self.assertEqual(decrease.graph.number_of_edges(), 2)
        self.assertEqual(increase.graph.number_of_edges(), 4)

    def test_targeted_subgraph_budget_injects_three_nodes_per_step(self) -> None:
        original = sample_pdg()

        result = apply_xfg_targeted_action(
            original,
            action="targeted_subgraph_injection",
            winner_nodes=set(original.nodes),
            winner_key_line=20,
            target_label=1,
            budget=2,
            key_lines={20},
            neutral_source_line=40,
            seed=42,
        )

        self.assertEqual(result.applied_count, 2)
        self.assertEqual(result.graph.number_of_nodes() - original.number_of_nodes(), 6)
        self.assertEqual(result.graph.number_of_edges() - original.number_of_edges(), 8)

    def test_xfg_targeted_action_uses_a_fallback_anchor_when_seed_is_not_a_node(self) -> None:
        result = apply_xfg_targeted_action(
            sample_pdg(),
            action="winner_xfg_edge_attack",
            winner_nodes={10, 30, 40},
            winner_key_line=25,
            target_label=1,
            key_lines={20},
            neutral_source_line=40,
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.applied_count, 1)

    def test_xfg_targeted_action_requires_a_real_winner_node(self) -> None:
        with self.assertRaisesRegex(ValueError, "winner_nodes"):
            apply_xfg_targeted_action(
                sample_pdg(),
                action="winner_xfg_feature_mask",
                winner_nodes={999},
                winner_key_line=20,
                target_label=0,
                key_lines={20},
                neutral_source_line=40,
            )

    def test_random_graph_budgets_form_nested_operation_prefixes(self) -> None:
        for action in ACTION_NAMES:
            with self.subTest(action=action):
                results = [
                    apply_graph_action(
                        sample_pdg(),
                        action=action,
                        count=budget,
                        seed=42,
                        key_lines={20},
                    )
                    for budget in DEFAULT_GRAPH_BUDGETS
                ]
                operations = [
                    [asdict(operation) for operation in result.operations]
                    for result in results
                ]

                for previous, current in zip(operations, operations[1:]):
                    self.assertTrue(operations_form_nested_prefix(previous, current))

    def test_winner_xfg_budgets_form_nested_operation_prefixes(self) -> None:
        for action in XFG_TARGETED_ACTION_NAMES:
            with self.subTest(action=action):
                results = [
                    apply_xfg_targeted_action(
                        sample_pdg(),
                        action=action,
                        winner_nodes=set(sample_pdg().nodes),
                        winner_key_line=20,
                        target_label=1,
                        budget=budget,
                        key_lines={20},
                        neutral_source_line=40,
                        seed=42,
                    )
                    for budget in DEFAULT_GRAPH_BUDGETS
                ]
                operations = [
                    [asdict(operation) for operation in result.operations]
                    for result in results
                ]

                for previous, current in zip(operations, operations[1:]):
                    self.assertTrue(operations_form_nested_prefix(previous, current))

    def test_load_joern_pdg_keeps_only_control_and_data_edges(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "nodes.csv").write_text(
                "key\ttype\tlocation\n1\tStatement\t10:1\n2\tStatement\t20:1\n3\tStatement\t30:1\n",
                encoding="utf-8",
            )
            (root / "edges.csv").write_text(
                "start\tend\ttype\n1\t2\tCONTROLS\n2\t3\tREACHES\n1\t3\tIS_AST_PARENT\n",
                encoding="utf-8",
            )

            graph = load_joern_pdg(root)

        self.assertEqual(set(graph.nodes), {10, 20, 30})
        self.assertEqual(graph.edges[10, 20]["c/d"], "c")
        self.assertEqual(graph.edges[20, 30]["c/d"], "d")
        self.assertNotIn((10, 30), graph.edges)


if __name__ == "__main__":
    unittest.main()
