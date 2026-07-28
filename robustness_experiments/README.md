# Demo B Perturbation Modules

`robustness_experiments` separates code-level and graph-level perturbations into independent
Python packages. Comparison, visualization, and showcase tools remain shared.

## Modules

| Path | Purpose |
|---|---|
| `code/` | Source transformations, source-variant CLI, budget search, and documentation. |
| `graph/` | Direct NetworkX PDG actions, graph audit CLI, and documentation. |
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
python robustness_experiments\code\code_perturbations.py --counts 1 2 3 5
```

Run source-level minimal-flip search:

```powershell
python robustness_experiments\code\run_budget_search.py --counts 1 2 3 5
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
from robustness_experiments.graph.graph_perturbations import apply_graph_action

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
record. `graph/run_xfg_targeted_experiment.py` runs selectable winner-XFG macro
actions and budgets through DeepWuKong in one container.

## Verification

```powershell
python -m py_compile robustness_experiments\code\code_perturbations.py robustness_experiments\code\run_budget_search.py robustness_experiments\graph\graph_perturbations.py robustness_experiments\graph\run_xfg_targeted_experiment.py
python -m unittest discover -s tests -p "test_*.py"
```
