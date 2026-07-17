# CVEfixes C Sample Pairs

This directory contains five C vulnerability/fix pairs selected from the
[`hitoshura25/cvefixes`](https://huggingface.co/datasets/hitoshura25/cvefixes)
dataset metadata.

The Hugging Face `vulnerable_code` and `fixed_code` fields contain patch
fragments rather than standalone translation units. To provide Joern with
complete inputs, each file in `vulnerable/` was retrieved from the parent of
the recorded fix commit, and the matching file in `fixed/` was retrieved from
the fix commit itself.

Selection criteria:

- `language == C`
- one modified `.c` file in the dataset record
- both the parent and fixed file are publicly retrievable
- a single-parent fix commit
- memory-safety-related CWE coverage: CWE-119, CWE-120, CWE-125, CWE-190, and
  CWE-787

`metadata.csv` records the exact commits, original paths, changed functions,
upstream licenses, and SHA-256 hashes. Use `vulnerable/` as the perturbation
input and retain `fixed/` as the paired reference:

```powershell
python demo_b\perturbations.py --input input_sources\cvefixes\vulnerable
python demo_b\run_budget_search.py --input input_sources\cvefixes\vulnerable
```

The vulnerable/fixed designation is inherited from the CVE fix record. It is
not a guarantee that every function in a complete file is vulnerable or that
the fixed file will receive a non-vulnerable prediction from DeepWuKong.
When comparing predictions, prefer XFGs associated with `changed_functions`
over an unqualified file-level maximum, which can be dominated by unrelated
functions in large files.

The dataset card is licensed under Apache-2.0. The complete source files retain
their respective upstream project licenses, listed in `metadata.csv`; those
licenses must be considered before redistributing these files.
