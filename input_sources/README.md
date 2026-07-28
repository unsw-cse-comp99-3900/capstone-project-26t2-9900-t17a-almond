# Full-Test Input Sources

`input_sources` is the single input set for the Almond full test. It contains
exactly 60 C/C++ function samples, with the provenance and labels recorded in
`sample_manifest.csv`.

| Directory | Samples | Dataset |
|---|---:|---|
| `cwe119/` | 20 | DeepWuKong CWE-119 |
| `devign/` | 20 | Devign |
| `cvefixes/` | 20 | CVEfixes |

The console's **Run Full Test** command recursively discovers every supported
source file (`.c`, `.cc`, `.cpp`, `.cxx`) under this directory. For each
source it runs one baseline DeepWuKong prediction and the two configured
source-level perturbations: `dead_statement` and `xfg_targeted_dead_code`.
It then stages the baseline PDG/XFG data and runs random graph perturbations
plus Winner-XFG-targeted graph perturbations. The targeted graph phase needs a
`0`/`1` ground-truth label in `sample_manifest.csv`; newly added unlabelled
sources still receive the code and random-graph phases, but are omitted from
that targeted success-rate calculation.

The exact input list used by each full-test run is saved as `input_manifest.csv`
inside that run's output directory. Do not add unrelated C/C++ files here if
you want the full test to remain the fixed 60-sample experiment.
