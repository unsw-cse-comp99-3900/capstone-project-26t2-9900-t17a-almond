from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import networkx as nx

from demo_b.graph.run_xfg_targeted_experiment import effective_winner_nodes, read_metadata


class XFGTargetedExperimentTests(unittest.TestCase):
    def test_read_metadata_accepts_utf8_bom(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metadata.csv"
            path.write_text("sample_id,label\nsecond,0\nfirst,1\n", encoding="utf-8-sig")

            rows = read_metadata(path)

        self.assertEqual([row["sample_id"] for row in rows], ["first", "second"])

    def test_effective_winner_nodes_keeps_real_xfg_nodes(self) -> None:
        graph = nx.DiGraph()
        graph.add_edges_from([(10, 20), (20, 30)])

        nodes, fallback = effective_winner_nodes(
            graph,
            {"key_line": 20, "nodes": [20, 30, 999]},
        )

        self.assertEqual(nodes, [20, 30])
        self.assertEqual(fallback, "winner_xfg")

    def test_effective_winner_nodes_falls_back_to_nearest_pdg_nodes(self) -> None:
        graph = nx.DiGraph()
        graph.add_edges_from([(10, 20), (20, 30), (30, 40)])

        nodes, fallback = effective_winner_nodes(
            graph,
            {"key_line": 26, "nodes": []},
            limit=2,
        )

        self.assertEqual(nodes, [30, 20])
        self.assertEqual(fallback, "nearest_pdg_nodes")


if __name__ == "__main__":
    unittest.main()
