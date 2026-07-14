# Input Sources

This directory contains the original C/C++ source files used as inputs to the
perturbation and inference workflow.

## Current Dataset

The repository currently includes 10 small C samples selected for the first
DeepWuKong perturbation experiment. Their filenames retain the CodeXGLUE/Devign
sample identifiers used during selection.

These files are experiment inputs, not generated variants. They do not provide
independent ground-truth labels in this directory, so filenames and model
predictions must not be treated as verified vulnerability labels.

Generated variants are stored under `../artifacts/perturbed_sources/`.
