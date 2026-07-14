# Demo B: DeepWuKong Perturbation

This repository contains a small, reproducible workflow for testing how
source-level perturbations affect DeepWuKong graph-based vulnerability
predictions.

## Current Status

The repository currently provides:

- a DeepWuKong CWE-119 inference baseline and checkpoint;
- three source-level perturbation actions;
- ten C source samples;
- one archived end-to-end experiment from 2026-07-10;
- flattened Joern node/edge artifacts and consolidated prediction results.

The integrated pipeline, automated minimal-flip search, serialized XFG export,
and graph visualization are not implemented yet. Their directories contain
scope documentation only.

## Workflow

```text
input_sources
  -> demo_b/perturbations.py
  -> artifacts/perturbed_sources
  -> Joern nodes.csv and edges.csv
  -> DeepWuKong PDG/XFG generation
  -> vulnerability prediction
  -> outputs comparison tables
```

## Repository Layout

| Path | Purpose |
|---|---|
| `demo_b/` | Active perturbation code and action documentation. |
| `baselines/deepwukong/` | DeepWuKong wrapper, configuration, checkpoint, and model documentation. |
| `input_sources/` | Original C samples used by the current experiment. |
| `artifacts/perturbed_sources/` | Generated source variants and manifests. |
| `artifacts/joern_csv/` | Baseline and perturbed Joern graph tables. |
| `outputs/` | Consolidated predictions and experiment summaries. |
| `legacy/perturbation/references/` | Papers used when designing the initial actions. |
| `tests/` | Test scope documentation; automated tests are not implemented yet. |

## Quick Start

From the repository root, generate all currently implemented perturbations:

```powershell
python demo_b\perturbations.py
```

The generated files are written to:

```text
artifacts/perturbed_sources/generated/
```

Generate selected actions only:

```powershell
python demo_b\perturbations.py --actions dead_statement control_wrapper
```

## DeepWuKong Inference

Full inference requires Docker Desktop, NVIDIA GPU access from Docker, and the
local image configured as:

```text
deepwukong-rtx5060-cu128:experimental
```

The Docker image is not stored in this repository. After it has been loaded
locally, generate variants and run DeepWuKong for each applicable variant with:

```powershell
python demo_b\perturbations.py --run-deepwukong
```

New raw runs are written under `outputs/generated/` and are ignored by Git.
See `baselines/deepwukong/README.md` for direct baseline commands and runtime
requirements.

## Archived Experiment

The archived 2026-07-10 run contains 10 baseline samples and 23 perturbation
variants. All 23 variants completed Joern and DeepWuKong inference; none flipped
the predicted label. The maximum absolute vulnerability-probability change was
`0.147869`.

Start with `outputs/run_20260710/README.md` for the experiment summary and
`demo_b/PERTURBATIONS.md` for action semantics and limitations.
