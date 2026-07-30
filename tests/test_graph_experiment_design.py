from __future__ import annotations

import unittest

from robustness_experiments.graph.experiment_design import (
    DEFAULT_GRAPH_BUDGETS,
    DEFAULT_GRAPH_SEEDS,
    resolve_experiment_values,
    xfg_tensor_is_scoreable,
)


class GraphExperimentDesignTests(unittest.TestCase):
    def test_default_design_uses_three_budgets_and_ten_seeds(self) -> None:
        self.assertEqual(DEFAULT_GRAPH_BUDGETS, (1, 3, 5))
        self.assertEqual(len(DEFAULT_GRAPH_SEEDS), 10)
        self.assertEqual(len(set(DEFAULT_GRAPH_SEEDS)), 10)

    def test_plural_values_override_legacy_scalar_alias(self) -> None:
        values = resolve_experiment_values(
            [5, 1, 3, 3],
            99,
            default=DEFAULT_GRAPH_BUDGETS,
            name="budgets",
            minimum=1,
        )

        self.assertEqual(values, [1, 3, 5])

    def test_legacy_scalar_alias_remains_supported(self) -> None:
        values = resolve_experiment_values(
            None,
            42,
            default=DEFAULT_GRAPH_SEEDS,
            name="seeds",
            sort_values=False,
        )

        self.assertEqual(values, [42])

    def test_empty_xfg_tensors_are_not_scoreable(self) -> None:
        class Tensor:
            def __init__(self, size: int) -> None:
                self.size = size

            def numel(self) -> int:
                return self.size

        class Data:
            def __init__(self, nodes: int, edges: int) -> None:
                self.x = Tensor(nodes)
                self.edge_index = Tensor(edges)

        self.assertFalse(xfg_tensor_is_scoreable(Data(0, 2)))
        self.assertFalse(xfg_tensor_is_scoreable(Data(3, 0)))
        self.assertTrue(xfg_tensor_is_scoreable(Data(3, 2)))


if __name__ == "__main__":
    unittest.main()
