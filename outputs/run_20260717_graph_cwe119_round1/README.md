# CWE-119 Graph Perturbation Round 1

This local experiment applies one direct PDG action at a time to 10 selected
official CWE-119 source files and compares each result with its unmodified
baseline prediction.

## Pipeline

```text
source -> Joern once -> baseline PDG -> baseline XFGs -> baseline prediction
                              |
                              +-> PDG copy -> graph action -> new XFGs -> perturbed prediction
```

Each action starts from a fresh copy of the same baseline PDG. Actions are not
accumulated. The Joern CSV tables are stored under
`artifacts/joern_csv/generated/cwe119_round1/` and are reused for all six
actions.

## Configuration

- Samples: 5 vulnerable and 5 non-vulnerable CWE-119 selections
- Actions: `node_add`, `node_delete`, `node_attribute_modify`, `edge_add`,
  `edge_delete`, and `edge_reconnect`
- Strategy: `random`
- Action count: 1
- Seed: 42
- DeepWuKong threshold: 0.5
- Device: NVIDIA GPU (`cuda:0`)
- Model lifecycle: one Docker container and one checkpoint load

## Outcome

- Joern baseline CSV generation: 10/10 successful
- Baseline predictions: 10/10 successful
- Graph perturbation predictions: 60/60 successful
- Label flips: 1
- Graph/model experiment runtime after container startup: 88.22 seconds

The observed flip was:

| Sample | Action | Graph operation | Baseline | Perturbed | Label |
|---|---|---|---:|---:|---|
| `10_non-vulnerable_43` | `node_delete` | Delete node 40 and five incident data edges | 0.925352 | 0.000511 | 1 -> 0 |

The deleted node was not a protected DeepWuKong key line. The action changed
the line-level PDG from 16 nodes/18 edges to 15 nodes/13 edges while preserving
9 generated XFG slices.

## Baseline Context

All five selected vulnerable files were predicted vulnerable. Three of the five
selected non-vulnerable files were predicted non-vulnerable; samples
`09_non-vulnerable_83` and `10_non-vulnerable_43` were predicted vulnerable.
The observed `node_delete` flip changed the latter from a vulnerable prediction
to a non-vulnerable prediction.

These are whole-source predictions, not direct scores of the single official
XFG pickle selected in the metadata. DeepWuKong generates all sensitive XFGs
from each source and uses their maximum vulnerability probability. The two
largest vulnerable files generated 201 and 1064 XFGs and already had baseline
probabilities near 1.0, so a one-step action is unlikely to change their
file-level maximum.

## Files

- `baseline_summary.csv`: compact baseline table
- `prediction_comparison.csv`: 60 baseline-versus-perturbed comparisons
- `action_summary.csv`: compact per-action comparison
- `runs/baseline/`: 10 baseline prediction JSON files
- `runs/perturbed/`: 60 perturbed prediction and graph-audit JSON files
- `baseline_predictions.csv`: extended baseline table
- `perturbation_results.csv`: extended graph-operation table
- `action_metrics.csv`: extended probability and runtime metrics
- `summary.json`: experiment configuration and aggregate outcome
- `details.json`: full XFG prediction details
- `prepare_joern_csv.py`: local one-time Joern CSV preparation runner
- `runner.py`: local graph perturbation experiment runner

The `nodes` and `edges` columns are line-level PDG counts. They are not raw
Joern CSV row counts.

This is an exploratory robustness run. A single flip demonstrates sensitivity
for one sample/action/seed combination; it is not enough to rank actions or
make dataset-level robustness claims.
