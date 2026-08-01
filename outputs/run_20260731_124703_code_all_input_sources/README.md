# Live DeepWuKong Full Test

This run scores every C/C++ source file under `input_sources` using a baseline prediction and the configured source-level perturbations, then runs random and Winner-XFG-targeted graph perturbations from the resulting baseline PDG/XFG inputs. Both graph families use nested budgets 1/3/5/7/9/11/13/15/20/25 and 10 fixed random seeds. `input_manifest.csv` records the exact input set.
