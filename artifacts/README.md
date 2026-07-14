# Artifacts

This directory stores inspectable intermediate products generated between the
source files and the final experiment report.

## Current Contents

| Path | Status |
|---|---|
| `perturbed_sources/` | Contains the archived 2026-07-10 source variants and manifest. |
| `joern_csv/` | Contains flattened Joern node and edge tables for the archived run. |
| `graphs/` | Reserved for graph visualizations; no graph files are stored yet. |
| `xfg/` | Reserved for serialized XFG data; no XFG files are stored yet. |

Archived runs may be committed when they support a reported experiment.
Regenerable local outputs use `generated/` directories and are ignored by Git.

Do not place model checkpoints, original datasets, pipeline source code, or
final user-facing reports in this directory.
