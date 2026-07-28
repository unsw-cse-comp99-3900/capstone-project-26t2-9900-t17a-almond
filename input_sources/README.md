# Input Sources

Input samples are separated by source dataset so that experiment results do not
mix Devign, DeepWuKong CWE-119, and CVEfixes provenance.

| Directory | Contents |
|---|---|
| `devign/` | The 10 CodeXGLUE/Devign C samples used by the archived 2026-07-10 experiment. |
| `cwe119/` | A reproducible 10-sample subset of the official DeepWuKong CWE-119 data. |
| `cvefixes/` | Five complete C vulnerability/fix file pairs selected using CVEfixes metadata. |

The source perturbation and budget-search CLIs default to `devign/`. Run the
official vulnerable sample set explicitly with:

```powershell
python robustness_experiments\code\code_perturbations.py --input input_sources\cwe119\vulnerable
python robustness_experiments\code\run_budget_search.py --input input_sources\cwe119\vulnerable
```

Use `--input input_sources\cwe119 --recursive` when both labels should be
processed in one run.

For CVEfixes experiments, perturb only the vulnerable side unless a paired
comparison is explicitly intended:

```powershell
python robustness_experiments\code\code_perturbations.py --input input_sources\cvefixes\vulnerable
```

Each dataset directory should retain its own metadata. Filenames and model
predictions must not be treated as verified vulnerability labels unless the
metadata contains the original dataset annotation.

Generated variants are stored under `../artifacts/perturbed_sources/`.
