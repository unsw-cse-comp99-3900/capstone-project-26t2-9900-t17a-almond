# CWE-119 Winner-XFG-Targeted Graph Experiment

This local experiment tests aggressive graph-only perturbations against a
fixed DeepWuKong CWE-119 checkpoint. It does not modify source code or retrain
the model.

## Configuration

- Dataset: 10 CWE-119 samples.
- Attacked samples: 8 samples whose baseline prediction matched the label.
- Excluded samples: 2 baseline false positives.
- Actions: `winner_xfg_edge_attack`, `winner_xfg_feature_mask`, and
  `targeted_subgraph_injection`.
- Budgets: 1, 3, and 5.
- Total: 8 samples x 3 actions x 3 budgets = 72 attacks.
- Threshold: 0.5.
- Seed: 42.

The runner targets the baseline XFG with the maximum vulnerability
probability. Three non-vulnerable samples had a winning XFG with no materialized
PDG nodes, so their attacks used the nearest-PDG-node fallback recorded in the
CSV files.

## Results

- Successfully scored: 72/72.
- Prediction flips: 8/72 (11.11%).
- Attack successes: 8/72 (11.11%).
- Samples with at least one successful attack: 2/8 (25.00%).
- Vulnerable baseline-correct subset: 8/45 attacks succeeded (17.78%).
- Non-vulnerable baseline-correct subset: 0/27 attacks succeeded.
- Runtime: 106.85 seconds on CUDA.

| Action | Successes | Rate |
|---|---:|---:|
| `winner_xfg_edge_attack` | 4/24 | 16.67% |
| `winner_xfg_feature_mask` | 2/24 | 8.33% |
| `targeted_subgraph_injection` | 2/24 | 8.33% |

| Budget | Successes | Rate |
|---|---:|---:|
| 1 | 1/24 | 4.17% |
| 3 | 4/24 | 16.67% |
| 5 | 3/24 | 12.50% |

The strongest observed change was on `04_vulnerable_55`: subgraph injection at
budget 5 reduced the vulnerability probability from 0.997988 to 0.005601.
Budget effects were not monotonic, so a larger graph-edit budget should not be
assumed to produce a stronger attack.

## Interpretation

The targeted actions produced adversarial failures where the earlier random
primitive-action round produced no attack success on baseline-correct samples.
However, all current successes suppress true-positive vulnerable predictions;
none turns a correctly predicted non-vulnerable sample into a false positive.

These are graph-only stress tests. The modified PDGs are not guaranteed to map
back to compilable or semantics-preserving source code, so the results measure
model sensitivity to graph representation changes rather than realizable code
attacks.

## Files

- `baseline_summary.csv`: one baseline row per sample.
- `prediction_comparison.csv`: one row per attack.
- `action_summary.csv`: aggregated action and budget metrics.
- `summary.json`: machine-readable experiment summary.
- `runs/`: detailed baseline and perturbed prediction records.
