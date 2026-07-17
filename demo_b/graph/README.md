# DeepWuKong Graph-Level Perturbations

The graph-level branch reads Joern output once, builds the same line-level
NetworkX PDG used by DeepWuKong, and modifies a copy of that graph in memory.
It does not edit the source file or overwrite Joern CSV files.

```text
source -> Joern -> PDG -> direct graph action -> perturbed PDG -> XFG -> model
```

## Implemented Actions

| Action | Direct PDG operation | Constraint |
|---|---|---|
| `node_add` | Add a synthetic node and connect it to an existing anchor. | Reuse the anchor's source line for tokenization. |
| `node_delete` | Remove a node and its incident edges. | Never select a supplied DeepWuKong key line. |
| `node_attribute_modify` | Remap a node's token source to another real source line. | Preserve topology and key-line nodes. |
| `edge_add` | Add a missing directed control or data edge. | No self-loop or duplicate ordered edge. |
| `edge_delete` | Remove an existing directed edge. | Preserve all nodes and supplied key lines. |
| `edge_reconnect` | Move an existing edge to a new target. | Preserve the original `c/d` edge type. |

All actions return a `GraphPerturbationResult` containing the modified graph,
applied count, operation audit, and validation errors. The input graph is never
modified.

## Target Selection

- `random`: choose a valid target with a reproducible random seed.
- `guided`: choose a valid target nearest to supplied DeepWuKong key lines,
  using node degree as a deterministic tie-breaker.

Guided mode requires the `key_line_map` returned by DeepWuKong `build_PDG`, or
an equivalent set of integer source lines.

## Python API

```python
from src.data_generator import build_PDG, build_XFG
from demo_b.graph.graph_perturbations import apply_graph_action

pdg, key_line_map = build_PDG(csv_root, sensi_api_path, source_path)
result = apply_graph_action(
    pdg,
    action="edge_reconnect",
    strategy="guided",
    key_lines=key_line_map,
    count=1,
    seed=42,
)

if not result.valid:
    raise RuntimeError(result.validation_errors)

xfg_dict = build_XFG(result.graph, key_line_map)
```

## CLI Audit Example

The standalone CLI loads archived Joern tables and exports the perturbed graph
plus its operation audit as JSON:

```powershell
python demo_b\graph\graph_perturbations.py `
  --csv-root artifacts\joern_csv\run_20260710\baseline\00_codexglue_devign_9763 `
  --action edge_delete `
  --strategy random `
  --count 1 `
  --seed 42 `
  --output outputs\generated\graph_perturbations\edge_delete.json
```

For guided mode:

```powershell
python demo_b\graph\graph_perturbations.py `
  --csv-root <joern-csv-directory> `
  --action node_delete `
  --strategy guided `
  --key-lines 42 57 `
  --output outputs\generated\graph_perturbations\node_delete_guided.json
```

## Validation

The module checks that:

- the result is a directed, non-multi NetworkX graph;
- node identifiers remain integers;
- synthetic or remapped nodes reference positive source lines;
- every edge has `c/d = c` or `c/d = d`;
- supplied key-line nodes remain present.

## Current Integration Limit

The graph API is ready to be called between DeepWuKong `build_PDG` and
`build_XFG`, and the symbolization wrapper now honors a node's optional
`source_line` attribute. The current host pipeline does not yet expose graph
action CLI flags or run a complete graph-action budget in one container.

Direct graph changes may not correspond to compilable source code. That is
expected for this experimental branch, but every result must be labelled as a
graph-only perturbation and kept separate from semantics-preserving code edits.
