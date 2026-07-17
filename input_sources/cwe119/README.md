# DeepWuKong CWE-119 Samples

This directory contains ten samples selected from the official DeepWuKong
CWE-119 test split with seed 42. The selection is balanced: five vulnerable
and five non-vulnerable samples.

## Layout

| Path | Contents |
|---|---|
| `vulnerable/` | Five label-1 source files for primary perturbation experiments. |
| `non_vulnerable/` | Five label-0 source files for false-positive robustness checks. |
| `metadata.csv` | Flat sample index with labels, key lines, hashes, and artifact paths. |
| `selection.json` | Detailed selection provenance and flaw/mixed line annotations. |
| `../../artifacts/xfg/cwe119_official/` | The matching official non-empty XFG pickles. |
| `../../artifacts/joern_cpg/cwe119_validation/` | Joern validation CPGs and logs. |

The set contains five C files and five C++ files. All ten sources have already
passed Joern parsing, and every sample has a non-empty official XFG.

## Run Perturbations

Run the five vulnerable samples:

```powershell
python demo_b\code\code_perturbations.py --input input_sources\cwe119\vulnerable
```

Run the five non-vulnerable samples:

```powershell
python demo_b\code\code_perturbations.py --input input_sources\cwe119\non_vulnerable
```

Run all ten samples in one command:

```powershell
python demo_b\code\code_perturbations.py --input input_sources\cwe119 --recursive
```

For minimal-flip searches, start with `vulnerable/` so the primary event is a
vulnerable-to-non-vulnerable prediction flip. Use `non_vulnerable/` separately
to measure perturbation-induced false positives.

The numeric label and key line come from the official XFG entry. A source file
can contain code outside that XFG, so file-level model aggregation should not
be interpreted as a verified label for every function in the file.
