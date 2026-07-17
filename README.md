# Demo B: DeepWuKong Perturbation

This repository contains a reproducible workflow for measuring how controlled
code-level and graph-level perturbations affect DeepWuKong vulnerability
predictions.

## Current Status

The repository currently provides:

- a DeepWuKong CWE-119 inference baseline and checkpoint;
- six source-code perturbation actions in `demo_b/code/code_perturbations.py`;
- six direct NetworkX PDG actions in `demo_b/graph/graph_perturbations.py`;
- random and key-line-guided target selection for graph actions;
- source-action budget and minimal-flip search;
- unit tests, an interactive PDG showcase, and an offline result dashboard;
- dataset-separated Devign, official CWE-119, and CVEfixes samples, plus one
  archived end-to-end experiment from 2026-07-10.

The graph-action module currently produces validated perturbed PDG objects and
JSON audit records. Automatic batch inference directly from those perturbed
graphs is the next integration step; the existing source branch already runs
end-to-end through Joern and DeepWuKong.

## Two Perturbation Branches

```text
code level
  source -> code action -> perturbed source -> Joern -> PDG -> XFG -> model

graph level
  source -> Joern -> NetworkX PDG -> graph action -> perturbed PDG -> XFG -> model
```

The graph branch reads Joern CSV files once and changes an in-memory PDG copy.
It does not overwrite `nodes.csv` or `edges.csv`.

## Repository Layout

| Path | Purpose |
|---|---|
| `demo_b/code/` | Source-code perturbations, budget search, and code-level documentation. |
| `demo_b/graph/` | Direct PDG perturbations and graph-level documentation. |
| `demo_b/` | Shared comparison, visualization, and showcase tools. |
| `baselines/deepwukong/` | DeepWuKong wrapper, configuration, checkpoint, and model documentation. |
| `input_sources/` | Dataset-separated Devign, official CWE-119, and CVEfixes C samples. |
| `artifacts/perturbed_sources/` | Generated source variants and manifests. |
| `artifacts/joern_csv/` | Baseline and perturbed Joern graph tables. |
| `artifacts/joern_cpg/` | Archived Joern CPG validation artifacts. |
| `artifacts/xfg/` | Official XFG references and future serialized XFG artifacts. |
| `outputs/` | Consolidated predictions, graph snapshots, and experiment summaries. |
| `legacy/perturbation/references/` | Papers used when designing the actions. |
| `tests/` | Host-side unit tests for perturbation, comparison, and visualization modules. |

## Code-Level Quick Start

Generate all source-code actions:

```powershell
python demo_b\code\code_perturbations.py
```

Generate selected actions and budgets:

```powershell
python demo_b\code\code_perturbations.py --actions dead_statement control_wrapper --counts 1 2 3 5
```

Run DeepWuKong for generated source variants:

```powershell
python demo_b\code\code_perturbations.py --run-deepwukong
```

## Graph-Level Quick Start

Apply one direct edge action to an archived Joern PDG:

```powershell
python demo_b\graph\graph_perturbations.py `
  --csv-root artifacts\joern_csv\run_20260710\baseline\00_codexglue_devign_9763 `
  --action edge_delete `
  --strategy random `
  --seed 42 `
  --output outputs\generated\graph_perturbations\edge_delete.json
```

Use `--strategy guided --key-lines <line...>` when DeepWuKong key lines are
available. See `demo_b/graph/README.md` for action semantics and current
integration limits.

## Verification

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

## Archived Experiment

The archived 2026-07-10 run contains 10 baseline samples and 23 source-level
variants. All variants completed Joern and DeepWuKong inference; none flipped
the predicted label. The maximum absolute vulnerability-probability change was
`0.147869`.

Start with `outputs/run_20260710/README.md` for the archived results,
`demo_b/code/README.md` for source actions, and `demo_b/graph/README.md` for
direct graph actions.
