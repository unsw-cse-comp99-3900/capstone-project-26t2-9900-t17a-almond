# Baselines

This directory contains vulnerability-detection baselines called by Demo B.
Each baseline owns its configuration, model files, wrappers, dependencies, and
interface documentation.

## Current Baseline

`deepwukong/` is currently the only implemented baseline. It exposes source-file
and directory inference through `scripts/run_demo_pipeline.py`.

Perturbation code, shared experiment reports, and generated runtime outputs do
not belong in this directory.
