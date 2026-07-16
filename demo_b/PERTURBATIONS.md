# DeepWuKong Perturbation Actions

This folder contains a small source-level perturbation toolkit for testing the
prediction stability of the DeepWuKong pipeline.

The experiment does not manually edit PDG/XFG files. Instead, each perturbation
modifies the source code, then the DeepWuKong pipeline regenerates Joern CSVs,
PDGs, XFGs, and model predictions from the perturbed source.

## Experiment Flow

```text
original source
  -> DeepWuKong pipeline
  -> Joern nodes.csv / edges.csv
  -> PDG
  -> XFG slices
  -> model prediction

perturbed source
  -> DeepWuKong pipeline
  -> regenerated Joern nodes.csv / edges.csv
  -> regenerated PDG
  -> regenerated XFG slices
  -> model prediction

compare original vs perturbed outputs
```

The main metric is whether the model prediction flips:

```text
flipped = original_predicted_label != perturbed_predicted_label
```

Additional useful metrics include probability change, confidence change, node
count change, edge count change, and XFG count change.

The first completed local experiment is summarized in
[`outputs/run_20260710/README.md`](../outputs/run_20260710/README.md).

## Implemented Actions

The current script implements three conservative source transformations. Each
action is designed as a source-level approximation of a graph-level action.

| Action | Graph action | Source transformation | Expected graph effect |
|---|---|---|---|
| `dead_statement` | `node_add` | Insert harmless dummy integer statements after the first function brace. | Adds statement nodes and local definition/use structure. |
| `control_wrapper` | `control_edge_add` | Wrap selected single-line statements with `if (1) { ... }`. | Adds a control structure and may affect `CONTROLS` edges. |
| `temp_variable_split` | `data_edge_rewire` | Rewrite simple assignments through temporary variables. | Adds temporary variable nodes and may change `DEF`/`USE`/`REACHES` data dependencies. |

Each action can now be applied with an explicit repeat budget. Every budget is
generated directly from the original source file, not by repeatedly editing a
previously perturbed variant. This keeps the experiment reproducible and makes
`action x count` comparisons easier to interpret. These actions are intentionally
simple. The goal is to get a reliable first pipeline running before introducing
complex C/C++ rewrites.

## Usage

Generate perturbed sources from the default DeepWuKong input folder:

```powershell
python demo_b\perturbations.py
```

Default input:

```text
input_sources
```

Default output:

```text
artifacts/perturbed_sources/generated
```

Generate only selected actions:

```powershell
python demo_b\perturbations.py --actions dead_statement control_wrapper
```

Generate a small perturbation-budget sweep:

```powershell
python demo_b\perturbations.py --counts 1 2 3 5
```

Generate one action at one budget:

```powershell
python demo_b\perturbations.py --action dead_statement --count 3
```

Generate variants and run DeepWuKong for each generated file:

```powershell
python demo_b\perturbations.py --counts 1 2 3 5 --run-deepwukong
```

The `--run-deepwukong` mode requires the DeepWuKong Docker runtime to be
available, because the current DeepWuKong wrapper runs full inference through
Docker.

Run minimal flip search:

```powershell
python demo_b\run_budget_search.py --counts 1 2 3 5
```

This mode first runs the original sample, then applies each action at increasing
budgets. For each `sample + action`, it stops at the first count that changes
the DeepWuKong predicted label and records that row as the minimal observed flip
budget for that action.

## Output Files

Generated perturbed source files are written under:

```text
artifacts/perturbed_sources/generated/sources
```

The manifest is written to:

```text
artifacts/perturbed_sources/generated/manifest.csv
```

The manifest records:

```text
source_file
variant_file
action
count
graph_action
expected_graph_effect
applied_count
status
notes
deepwukong_command
```

The `deepwukong_command` column contains the command that can be used to run the
DeepWuKong pipeline on each generated variant.

Minimal flip search writes:

```text
outputs/generated/budget_search/budget_search.csv
outputs/generated/budget_search/budget_search.json
```

## Design Notes

The actions are source-code transformations, but they are described using
graph-level action names. This keeps the experiment aligned with the project
goal: perturb the graph representation indirectly through valid source changes.

The current implementation is deliberately conservative:

- It does not overwrite original DeepWuKong input files.
- It skips files when no safe rewrite location is found.
- It avoids complex C/C++ parsing.
- It records skipped variants in the manifest.

This means some samples may not receive all perturbation types, especially
`temp_variable_split`, which currently only handles simple assignment patterns.

## Suggested Evaluation Table

After running DeepWuKong on original and perturbed files, use a table like:

```text
sample_id
action
count
original_label
perturbed_label
flipped
original_probability
perturbed_probability
probability_delta
original_num_nodes
perturbed_num_nodes
original_num_edges
perturbed_num_edges
original_xfg_count
perturbed_xfg_count
```

This is enough for the first robustness experiment. More detailed PDG/XFG
analysis can be added later if needed.

## TODO: Possible Future Actions

Potential extensions, ordered from easier to harder:

1. `identifier_rename` -> `node_feature_modify`
   Rename local variables while preserving the original program behavior. This
   should mostly affect node token features rather than graph topology.

2. `constant_equivalent_rewrite` -> `node_feature_modify`
   Rewrite constants in equivalent forms, for example `0` to `(1 - 1)` or `1`
   to `(2 - 1)`. This may alter expression nodes and token features.

3. `expression_split` -> `data_edge_rewire`
   Split more expression forms into temporary variables, including pointer,
   array, and function-call expressions. This is a stronger data-flow
   perturbation than the current simple assignment split.

4. `statement_reorder` -> `edge_rewire`
   Reorder independent statements when data dependencies allow it. This is more
   realistic but requires dependency checks to avoid changing semantics.

5. `guarded_dead_branch` -> `control_node_add`
   Insert branches such as `if (0) { ... }` or compile-time unreachable code.
   This may add control-flow structure, but Joern/model behavior must be checked
   because some tools may still parse unreachable code.

6. `loop_wrapper` -> `control_edge_add`
   Wrap a statement with a single-iteration loop, such as `do { ... } while (0);`.
   This can create stronger control-flow changes than `if (1)`.

7. `api_nearby_noop` -> `xfg_affecting_node_add`
   Insert no-op statements near sensitive API calls, pointer operations, array
   indexing, or arithmetic expressions. This targets regions more likely to be
   included in DeepWuKong XFG slices.

8. `remove_inserted_node` -> `node_delete`
   Delete dummy nodes that were previously inserted by our own perturbation
   actions. This is safer than deleting arbitrary original code.

9. `unwrap_inserted_control` -> `control_edge_delete`
   Remove control wrappers introduced by our own actions. This can support
   ablation tests for control-edge effects.

10. `direct_graph_ablation` -> `edge_delete` / `node_mask`
    Directly perturb generated graph objects instead of source code. This is
    useful for pure model analysis, but it is less realistic because the graph
    may no longer correspond to valid source code.

For the first project milestone, the recommended path is to keep the source-level
actions simple, run DeepWuKong before and after perturbation, and measure model
prediction flips.
