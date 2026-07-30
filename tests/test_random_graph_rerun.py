from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import rerun_random_graph


class RandomGraphRerunTests(unittest.TestCase):
    def test_resolve_run_dir_accepts_only_direct_output_children(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            run_dir = project_root / "outputs" / "run_test"
            run_dir.mkdir(parents=True)
            with patch.object(rerun_random_graph, "PROJECT_ROOT", project_root):
                resolved = rerun_random_graph.resolve_run_dir(Path("outputs/run_test"))
                with self.assertRaisesRegex(ValueError, "direct child"):
                    rerun_random_graph.resolve_run_dir(Path("outputs/group/run_test"))

        self.assertEqual(resolved, run_dir.resolve())

    def test_summary_update_records_partial_rerun_without_replacing_other_stages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            summary_path = run_dir / "summary.json"
            summary_path.write_text(
                json.dumps(
                    {
                        "status": "completed_with_graph_errors",
                        "graph_perturbations": {
                            "targeted_graph": {"status": "completed"},
                        },
                    }
                ),
                encoding="utf-8",
            )
            rerun_random_graph.update_full_test_summary(
                run_dir,
                backup_dir=run_dir / "graph_random_before_rerun_test",
                random_summary={
                    "metadata": {
                        "perturbations_scored": 100,
                        "perturbations_unscored_no_xfg": 5,
                    }
                },
            )
            result = json.loads(summary_path.read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["graph_perturbations"]["targeted_graph"]["status"], "completed")
        self.assertEqual(result["graph_perturbations"]["random_graph"]["scored"], 100)
        self.assertEqual(result["graph_perturbations"]["random_graph"]["unscored_no_xfg"], 5)
        self.assertEqual(result["partial_reruns"][0]["stage"], "random_graph")


if __name__ == "__main__":
    unittest.main()
