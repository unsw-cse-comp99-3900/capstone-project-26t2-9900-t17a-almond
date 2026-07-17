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

## Winner-XFG-Targeted Actions

The targeted experiment first scores the baseline XFGs, selects the XFG with
the maximum vulnerability probability, and applies a macro action within that
slice. Each action and budget starts from a fresh copy of the baseline PDG.

| Action | Targeted operation |
|---|---|
| `winner_xfg_edge_attack` | Cut winner-XFG edges when targeting label 0, or bridge the winner key line to high-priority XFG nodes when targeting label 1. |
| `winner_xfg_feature_mask` | Remap high-priority winner-XFG node features to a neutral source line or duplicate the winner key-line feature. |
| `targeted_subgraph_injection` | Inject a three-node control/data motif around the winner key line for each budget step. |

Run all three actions at maximum budgets 1, 3, and 5 inside the DeepWuKong container:

```powershell
python /repo/demo_b/graph/run_xfg_targeted_experiment.py `
  --source-root /input `
  --csv-root /csv `
  --metadata /input/metadata.csv `
  --checkpoint /baseline/models/deepwukong/deepwukong_cwe119_best.ckpt `
  --output-dir /output `
  --actions winner_xfg_edge_attack winner_xfg_feature_mask targeted_subgraph_injection `
  --budgets 1 3 5 `
  --seed 42
```

By default, the runner attacks only baseline-correct samples. It records both
prediction flips and attack success, where attack success means that the
perturbed prediction no longer matches the unchanged source label.
If a small graph has fewer legal targets than the requested budget, the runner
scores the partially applied result and records the actual `applied_count`.
If the winning XFG contains no materialized PDG nodes, the runner targets up to
five PDG nodes nearest to its key line and records
`winner_fallback=nearest_pdg_nodes` in the result.

Actions are independently selectable. For example, this runs only the edge
attack at budgets 1 and 3:

```powershell
python /repo/demo_b/graph/run_xfg_targeted_experiment.py `
  <required path arguments> `
  --actions winner_xfg_edge_attack `
  --budgets 1 3
```

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
  --output outputs\run_20260717_graph_devign_round1\audits\edge_delete.json
```

For guided mode:

```powershell
python demo_b\graph\graph_perturbations.py `
  --csv-root <joern-csv-directory> `
  --action node_delete `
  --strategy guided `
  --key-lines 42 57 `
  --output outputs\run_20260717_graph_devign_round1\audits\node_delete_guided.json
```

## Validation

The module checks that:

- the result is a directed, non-multi NetworkX graph;
- node identifiers remain integers;
- synthetic or remapped nodes reference positive source lines;
- every edge has `c/d = c` or `c/d = d`;
- supplied key-line nodes remain present.

## Current Integration Limit

The primitive graph CLI exports JSON audit records without model inference. The
winner-XFG experiment runner performs complete graph-action budgets in one
DeepWuKong container, but it currently requires explicit Docker mounts for the
source files, Joern CSV tables, checkpoint, repository, and output directory.

Direct graph changes may not correspond to compilable source code. That is
expected for this experimental branch, but every result must be labelled as a
graph-only perturbation and kept separate from semantics-preserving code edits.
