# Outputs

This directory contains experiment results intended for direct review.

## Archived Run Layout

```text
run_<id>/
  README.md
  baseline_summary.csv
  action_summary.csv
  prediction_comparison.csv
  runs/
    baseline/<sample>.json
    perturbed/<variant>.json
```

Each archived sample has one JSON containing both the prediction and detailed
runtime metadata. Per-sample CSV, metadata, and Markdown files are not duplicated
because they can be derived from that JSON.

## Generated Runs

New DeepWuKong executions write raw output under `generated/`. That directory is
ignored by Git until a run is deliberately consolidated and documented.

Joern tables, generated source files, model checkpoints, and pipeline code do
not belong here.
