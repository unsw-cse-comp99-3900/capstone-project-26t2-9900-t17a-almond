# Demo B Perturbation Modules

`demo_b` contains two separate perturbation branches.

## Modules

| File | Purpose |
|---|---|
| `code_perturbations.py` | Six source-code transformations and the source-variant CLI. |
| `graph_perturbations.py` | Six direct NetworkX PDG actions with random/guided selectors. |
| `run_budget_search.py` | Minimal-flip search for source-code actions and count budgets. |
| `CODE_PERTURBATIONS.md` | Source-action semantics, usage, and limitations. |
| `GRAPH_PERTURBATIONS.md` | Direct graph-action semantics, usage, and limitations. |
| `compare_deepwukong.py` | Original-versus-perturbed prediction comparison. |
| `visualize_results.py` | Offline experiment dashboard generation. |
| `showcase/` | Interactive source and PDG comparison. |

## Code-Level Branch

```text
source -> code action -> new source -> Joern -> PDG -> XFG -> DeepWuKong
```

Implemented actions:

- `pattern_dead_code`
- `data_flow_alias`
- `xfg_targeted_dead_code`
- `dead_statement`
- `control_wrapper`
- `temp_variable_split`

Generate source variants:

```powershell
python demo_b\code_perturbations.py --counts 1 2 3 5
```

Run source-level minimal-flip search:

```powershell
python demo_b\run_budget_search.py --counts 1 2 3 5
```

## Graph-Level Branch

```text
Joern CSV -> NetworkX PDG -> direct node/edge action -> perturbed PDG -> XFG
```

Implemented actions:

- `node_add`
- `node_delete`
- `node_attribute_modify`
- `edge_add`
- `edge_delete`
- `edge_reconnect`

The library API always modifies `pdg.copy()`, never the original graph or Joern
CSV files. `random` uses a reproducible seed. `guided` ranks valid targets by
distance to DeepWuKong key lines.

```python
from demo_b.graph_perturbations import apply_graph_action

result = apply_graph_action(
    pdg,
    action="edge_delete",
    strategy="guided",
    key_lines=key_line_map,
    count=1,
)
xfg_dict = build_XFG(result.graph, key_line_map)
```

The graph CLI can load archived Joern tables and export a validated JSON audit
record. Direct graph-to-model batch inference is not wired into the host runner
yet.

## Verification

```powershell
python -m py_compile demo_b\code_perturbations.py demo_b\graph_perturbations.py demo_b\run_budget_search.py
python -m unittest tests.test_code_perturbations tests.test_graph_perturbations
```
