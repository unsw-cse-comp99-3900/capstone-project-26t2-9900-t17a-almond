# Demo B

This repository contains the DeepWuKong baseline, source-level graph
perturbation actions, and the artifacts from the first perturbation experiment.

## Pipeline

```text
input_sources/
  -> demo_b perturbation workflow
  -> artifacts/perturbed_sources
  -> artifacts/joern_csv
  -> DeepWuKong PDG/XFG generation and inference
  -> outputs prediction comparisons and reports
```

## Current Implementation

- `baselines/deepwukong/`: DeepWuKong CWE-119 inference scripts, configuration,
  and checkpoint.
- `demo_b/perturbations.py`: the three implemented source-level actions.
- `input_sources/`: the ten C source samples used by the first experiment.
- `artifacts/perturbed_sources/`: generated source variants and manifests.
- `artifacts/joern_csv/`: baseline and perturbed Joern graph artifacts.
- `outputs/run_20260710/`: predictions, comparison tables, and experiment notes.

Generate all currently implemented perturbations:

```powershell
python demo_b\perturbations.py
```

See [`demo_b/PERTURBATIONS.md`](demo_b/PERTURBATIONS.md) for the action design
and detailed usage.
