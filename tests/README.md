# Tests

This directory is intended for host-side unit tests, CLI smoke tests, small
fixtures, and optional Docker integration tests.

## Current Status

No automated test files are implemented yet. Current migration checks were run
manually and are not a substitute for a committed test suite.

Future tests should cover perturbation applicability, manifest fields, path
handling, graph/prediction comparison, and report generation. Long-running GPU
tests should be optional and clearly marked.
