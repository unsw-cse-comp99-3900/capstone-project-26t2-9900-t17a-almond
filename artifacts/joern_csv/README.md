# Joern Graph Tables

This directory stores Joern graph exports for original and perturbed source
files. Despite the `.csv` extension, the archived `nodes.csv` and `edges.csv`
files are tab-separated tables.

## Archived Layout

```text
run_YYYYMMDD/
  baseline/<sample>/
    nodes.csv
    edges.csv
    joern_graph_stats.json
  perturbed/<variant>/
    nodes.csv
    edges.csv
    joern_graph_stats.json
```

Each sample directory is intentionally flat. Joern's generated
`scan/output/_work/source` directory hierarchy is not retained.

`joern_graph_stats.json` uses repository-relative values for `csv_dir` and
`selected_csv_dir`. Original Docker paths remain in `container_csv_dir` and
`container_selected_csv_dir` for provenance.

## Data Meaning

- `nodes.csv` contains code-property-graph nodes and source attributes.
- `edges.csv` contains AST, control-flow, control-dependence, and data-flow
  relationships between node identifiers.
- `joern_graph_stats.json` records parse status, graph size, runtime, and paths.

DeepWuKong also needs the matching source file and its sensitive-API
configuration to rebuild PDGs and XFGs from these tables.
