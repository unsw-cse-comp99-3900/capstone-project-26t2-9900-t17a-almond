import unittest

from robustness_experiments.compare_deepwukong import aggregate_xfgs, compare


class CompareDeepWuKongTests(unittest.TestCase):
    def test_max_reduction_and_id_based_join(self):
        original = aggregate_xfgs([
            {"sample_id": "b", "xfg_id": "b-1", "vulnerability_probability": "0.2"},
            {"sample_id": "a", "xfg_id": "a-1", "vulnerability_probability": "0.8", "true_label": "1"},
            {"sample_id": "a", "xfg_id": "a-2", "vulnerability_probability": "0.1"},
        ], "max")
        perturbed = aggregate_xfgs([
            {"sample_id": "a", "xfg_id": "a-3", "vulnerability_probability": "0.3"},
            {"sample_id": "b", "xfg_id": "b-2", "vulnerability_probability": "0.7"},
        ], "max")
        rows = compare(original, perturbed, 0.5)
        self.assertEqual([row["sample_id"] for row in rows], ["a", "b"])
        self.assertEqual(rows[0]["prediction_flipped"], 1)
        self.assertEqual(rows[1]["prediction_flipped"], 1)
        self.assertEqual(rows[0]["original_xfg_count"], 2)


if __name__ == "__main__":
    unittest.main()
