# Outputs

This directory contains experiment results intended for direct review.

## Run Naming

Every run is stored directly under `outputs/` with this format:

```text
run_<YYYYMMDD>_<level>_<dataset>_round<N>/
```

- `level`: `code` or `graph`.
- `dataset`: for example, `devign` or `cwe119`.
- `round`: the experiment sequence for that date, level, and dataset.

Examples:

```text
run_20260710_code_devign_round1/
run_20260717_graph_devign_round1/
run_20260717_graph_cwe119_round1/
run_20260717_graph_cwe119_round2/
```

## Run Layout

```text
run_<YYYYMMDD>_<level>_<dataset>_round<N>/
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

New run directories follow the same naming convention and are ignored by Git
until a run is deliberately archived. There is no additional `generated/`
directory under `outputs/`.

Joern tables, generated source files, model checkpoints, and pipeline code do
not belong here.
