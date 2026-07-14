# Demo B

This is the active integration area for the perturbation experiment.

## Current Files

| File | Purpose |
|---|---|
| `perturbations.py` | CLI and implementations for the three active actions. |
| `PERTURBATIONS.md` | Action semantics, safety constraints, examples, and planned work. |
| `__init__.py` | Python package marker. |

Generate all applicable variants from the repository root:

```powershell
python demo_b\perturbations.py
```

Implemented actions:

- `dead_statement`
- `control_wrapper`
- `temp_variable_split`

## Not Implemented Yet

The integrated pipeline controller, baseline adapter, graph comparison module,
minimal-flip search, report generator, and visualization module are planned but
do not yet exist. Add those modules here when they become active code rather
than placing prototypes in `legacy/`.
