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
