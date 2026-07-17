# DeepWuKong Code-Level Perturbations

The code-level branch applies source transformations without directly reading
or editing the PDG. Every generated source variant is sent through Joern again
to produce its own PDG, XFG slices, and prediction.

```text
original source -> code action -> perturbed source -> Joern -> PDG -> XFG -> model
```

## Implemented Actions

| Action | Source transformation | Expected graph effect |
|---|---|---|
| `pattern_dead_code` | Insert an unreachable pointer/array/length pattern near sensitive or structural source lines. | Add pattern-shaped nodes and dependencies. |
| `data_flow_alias` | Insert an alias-preserving no-op near call arguments; fall back to a temporary split. | Add or reroute local data dependencies. |
| `xfg_targeted_dead_code` | Insert an unreachable no-op near source patterns likely to seed an XFG. | Add nodes near sensitive regions. |
| `dead_statement` | Insert harmless dummy integer statements after the first function brace. | Add statement and local definition/use nodes. |
| `control_wrapper` | Wrap safe statements with `if (1)`. | Add control structure and `CONTROLS` edges. |
| `temp_variable_split` | Rewrite simple assignments through a temporary integer. | Add temporary nodes and change `REACHES` dependencies. |

These actions currently select deterministic source candidates, usually the
first matching locations. Their `graph_action` manifest field records the
expected effect; it is not a direct graph edit.

## Usage

```powershell
python demo_b\code\code_perturbations.py
python demo_b\code\code_perturbations.py --actions dead_statement control_wrapper
python demo_b\code\code_perturbations.py --counts 1 2 3 5
python demo_b\code\code_perturbations.py --run-deepwukong
```

Generated source variants and their manifest are written under:

```text
artifacts/perturbed_sources/generated/
```

Minimal-flip search writes its tables under:

```text
outputs/generated/budget_search/
```

Run it with:

```powershell
python demo_b\code\run_budget_search.py --counts 1 2 3 5
```

## Measurement

The primary result is:

```text
flipped = original_predicted_label != perturbed_predicted_label
```

Also record probability delta, applied action count, node/edge deltas, XFG
count, skipped actions, and Joern/model failures. Each count budget is generated
from the original source rather than from a previously perturbed variant.

## Limitations

- Regex-based C/C++ rewrites do not cover every syntax form.
- Some samples do not provide a safe candidate for every action.
- Source-pattern targeting is not the same as reading the actual PDG/XFG.
- Each unique source variant currently runs Joern and model inference separately.
