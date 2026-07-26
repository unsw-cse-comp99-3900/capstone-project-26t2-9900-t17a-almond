# Tests

This directory is intended for host-side unit tests, CLI smoke tests, small
fixtures, and optional Docker integration tests.

## Current Status

The host-side suite covers code perturbation guards, all six direct graph
actions, Joern-PDG loading, prediction comparison, showcase rendering, and
offline report generation.

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

Docker/GPU inference remains an optional integration test and is not executed
by the default unit-test command.

## Console Quick Test

Menu option `2` (**Run Smoke Test**) runs `run_quick_test.py`. It performs one real baseline
inference and validates the returned prediction, probability, and graph size.
It uses a temporary output directory and is not part of the default unit suite.
