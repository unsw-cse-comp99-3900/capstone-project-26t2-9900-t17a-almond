# DeepWuKong Perturbation Experiment Results

Date: 2026-07-10

This note records the first end-to-end perturbation run using the local
DeepWuKong Docker runtime.

## Setup

The experiment uses the source-level perturbation workflow:

```text
original source -> Joern -> PDG -> XFG -> DeepWuKong prediction
perturbed source -> Joern -> regenerated PDG/XFG -> DeepWuKong prediction
```

The main metric is prediction flip:

```text
flipped = baseline_predicted_label != perturbed_predicted_label
```

## Actions

Three actions were evaluated:

| Action | Graph-level intent | Source-level edit |
|---|---|---|
| `dead_statement` | `node_add` | Insert harmless dummy integer statements. |
| `control_wrapper` | `control_edge_add` | Wrap one safe statement in `if (1) { ... }`. |
| `temp_variable_split` | `data_edge_rewire` | Split simple assignments through a temporary variable. |

## Artifacts

Generated sources:

```text
artifacts/perturbed_sources/run_20260710/sources
```

Consolidated baseline DeepWuKong predictions:

```text
outputs/run_20260710_code_devign_round1/runs/baseline
```

Consolidated perturbed DeepWuKong predictions:

```text
outputs/run_20260710_code_devign_round1/runs/perturbed
```

Each sample or variant is stored as one JSON file containing both its prediction
and detailed runtime metadata. Host input paths and archived Joern paths are
repository-relative; original Docker paths remain under `container_*` fields.

Compact result tables:

```text
outputs/run_20260710_code_devign_round1/baseline_summary.csv
outputs/run_20260710_code_devign_round1/action_summary.csv
outputs/run_20260710_code_devign_round1/prediction_comparison.csv
```

## Summary

| Metric | Value |
|---|---:|
| Baseline samples | 10 |
| Generated perturbed variants | 23 |
| Successful perturbed DeepWuKong runs | 23 |
| Prediction flips | 0 |
| Perturbed variants predicted vulnerable | 2 |
| Maximum absolute probability change | 0.147869 |

All generated variants were accepted by Joern and DeepWuKong inference. The
experiment therefore validates the pipeline, but the current perturbations are
too conservative to flip predictions.

## Action-Level Results

| Action | Count | Flips | Average probability delta | Minimum delta | Maximum delta | Average node delta | Average edge delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| `control_wrapper` | 10 | 0 | -0.000369 | -0.005678 | 0.001640 | 4.0 | 9.1 |
| `dead_statement` | 10 | 0 | -0.014650 | -0.147869 | 0.001375 | 12.0 | 27.0 |
| `temp_variable_split` | 3 | 0 | -0.023493 | -0.071008 | 0.000530 | 8.0 | 17.3 |

## Notable Cases

| Sample | Action | Baseline probability | Perturbed probability | Delta | Label change |
|---|---|---:|---:|---:|---|
| `07_codexglue_devign_4012` | `dead_statement` | 0.899059 | 0.751189 | -0.147869 | `1 -> 1` |
| `01_codexglue_devign_10453` | `temp_variable_split` | 0.073688 | 0.002680 | -0.071008 | `0 -> 0` |
| `07_codexglue_devign_4012` | `control_wrapper` | 0.899059 | 0.893381 | -0.005678 | `1 -> 1` |
| `06_codexglue_devign_15513` | `control_wrapper` | 0.000057 | 0.001698 | 0.001640 | `0 -> 0` |

Sample `09_codexglue_devign_25916` remains close to the decision threshold:

```text
baseline probability: 0.456266
control_wrapper:      0.456266
dead_statement:       0.456266
threshold:            0.5
```

It is a good target for stronger perturbations because it needs a relatively
small positive probability shift to flip from non-vulnerable to vulnerable.

## Interpretation

The current actions reliably change Joern graph size:

- `control_wrapper` usually adds about 4 nodes and 9 edges.
- `dead_statement` usually adds about 12 nodes and 27 edges.
- `temp_variable_split` usually adds about 8 nodes and 17 edges, but only
  applies to 3 of the 10 current source files.

However, DeepWuKong aggregates file-level prediction using the maximum
vulnerable probability across generated XFG slices. If a perturbation does not
alter the highest-scoring XFG slice, the final probability may remain unchanged.
This likely explains why several variants have exactly the same probability as
their baseline.

## Next Steps

The next implementation step should not be a large set of new actions. A better
short-term path is:

1. Add repeat counts for existing actions, for example `dead_statement x3` or
   `control_wrapper x3`.
2. Prioritize near-threshold samples, especially `09_codexglue_devign_25916`.
3. Add one XFG-targeted source action, such as inserting no-op statements near
   pointer operations, array indexing, arithmetic, or sensitive calls.
4. Keep `prediction_comparison.csv` as the primary table for judging whether a
   perturbation caused a model flip.
