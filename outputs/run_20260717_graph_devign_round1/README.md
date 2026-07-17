# Graph Perturbation Round 1

This local experiment tests one direct PDG operation at a time against the
archived Devign baseline graphs.

## Configuration

- Samples: 10 Devign sources with archived Joern CSV tables
- Actions: `node_add`, `node_delete`, `node_attribute_modify`, `edge_add`,
  `edge_delete`, and `edge_reconnect`
- Strategy: `random`
- Action count: 1
- Seed: 42
- DeepWuKong threshold: 0.5
- Device: NVIDIA GPU (`cuda:0`)
- Joern: not rerun; the archived baseline CSV tables were reused
- Model lifecycle: one Docker container and one checkpoint load

The experiment uses the same XFG construction, symbolization, model, and
file-level maximum-probability aggregation as the single-source baseline
wrapper. All 10 reproduced baseline probabilities match the archived
`run_20260710_code_devign_round1` values within floating-point precision.

## Outcome

- Baselines completed: 10/10
- Graph perturbations attempted: 60
- Complete perturbation predictions: 57
- Label flips: 1
- End-to-end container runtime after startup: 4.67 seconds

The observed flip was:

| Sample | Action | Added graph element | Baseline | Perturbed | Label |
|---|---|---|---:|---:|---|
| `09_codexglue_devign_25916` | `edge_add` | data edge `5 -> 1` | 0.456266 | 0.841940 | 0 -> 1 |

The largest absolute probability movements were:

| Sample | Action | Baseline | Perturbed | Delta |
|---|---|---:|---:|---:|
| `09_codexglue_devign_25916` | `node_add` | 0.456266 | 0.012808 | -0.443458 |
| `09_codexglue_devign_25916` | `edge_add` | 0.456266 | 0.841940 | +0.385674 |
| `09_codexglue_devign_25916` | `node_attribute_modify` | 0.456266 | 0.118790 | -0.337476 |
| `07_codexglue_devign_4012` | `node_attribute_modify` | 0.899059 | 0.980166 | +0.081107 |
| `01_codexglue_devign_10453` | `node_attribute_modify` | 0.073688 | 0.009756 | -0.063932 |

## Incomplete Cases

All three incomplete cases occurred on `04_codexglue_devign_13727`, whose PDG
has only two nodes and one edge:

- `node_delete` produced a one-node, zero-edge XFG that the model could not tensorize.
- `edge_delete` produced zero-edge XFGs that the model could not tensorize.
- `edge_reconnect` had no legal replacement target.

The graph operations themselves passed structural validation. These cases are
reported as incomplete model predictions rather than successful zero scores.

## Files

- `baseline_summary.csv`: compact baseline table matching the code-level run layout
- `prediction_comparison.csv`: baseline-versus-perturbed table matching the code-level run layout
- `action_summary.csv`: compact per-action comparison matching the code-level run layout
- `runs/baseline/`: one baseline prediction JSON per sample
- `runs/perturbed/`: one perturbed prediction and graph-audit JSON per sample/action
- `baseline_predictions.csv`: extended baseline table with PDG, XFG, and runtime fields
- `perturbation_results.csv`: extended per-attempt graph-operation table
- `action_metrics.csv`: extended success, probability, and runtime metrics by action
- `summary.json`: experiment configuration and aggregate outcome
- `details.json`: full XFG predictions and graph-operation audit details
- `runner.py`: ignored local container-side experiment runner

Unlike the code-level run, the `nodes` and `edges` columns count line-level PDG
nodes and edges. The code-level run counts raw Joern CSV rows because Joern is
regenerated for each source variant. Graph-level variants reuse the archived
Joern CSV and modify the derived PDG in memory, so raw Joern row counts do not
change and would be misleading here.

This is a small exploratory run. One flip on one near-threshold sample is a
useful robustness signal, but it is not enough to rank the six actions or make
dataset-level claims.
