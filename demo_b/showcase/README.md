# DeepWuKong PDG Perturbation Atlas

This folder contains a static browser atlas for the 30 source files under `input_sources/`. Each file contributes one independent target function; code and line-PDG perturbations never run across the rest of the translation unit.

The generated inventory covers:

- 13 code actions exposed by `demo_b/code/code_perturbations.py`
- 6 ordinary PDG actions: node add/delete/attribute modification and edge add/delete/reconnect
- One deterministic application per action with `seed=42`

Target functions are selected deterministically:

- Devign files already contain one function sample and are used as-is.
- CWE-119 uses the function containing `metadata.csv:key_line`.
- CVEfixes validates `metadata.csv:changed_functions` against the vulnerable/fixed function bodies. It selects the first listed function that actually differs; if the metadata is stale, it accepts only a unique changed function detected from the source pair.

Winner-XFG targeted graph actions are intentionally excluded. An action that cannot be applied or inferred is recorded as skipped instead of stopping the batch.

## Requirements

- `uv`
- Docker with NVIDIA GPU access
- Docker image `deepwukong-rtx5060-cu128:experimental`
- Graphviz (`dot` on `PATH`)

## Generate or Refresh the Atlas

Run from the project root:

```bash
uv run demo_b/showcase/generate_showcase.py
```

The generator reuses matching static conclusions. Force Joern and model inference to run again when an inference input changes:

```bash
uv run demo_b/showcase/generate_showcase.py --refresh
```

Render the browser pages without running inference:

```bash
uv run demo_b/showcase/generate_showcase.py --render-only
```

Static conclusions and generated source variants are retained under:

```text
outputs/run_showcase_cache/
```

The browser artifact consists of:

```text
demo_b/showcase/deepwukong_pdg_showcase.html
demo_b/showcase/deepwukong_pdg_showcase_pages/
```

Open the index HTML directly. No web server or internet connection is required.

## Page Controls

- Search the source catalog by sample ID, path, dataset, or state.
- Open a source and search its available perturbation actions by name or effect.
- Use `+`, `-`, and `Reset` to control each PDG; zoom is capped at 12×.
- Drag a graph after zooming in.
- Hover over or focus a line node to trace its dependencies.
- Read the complete target function with removals and additions shown inline.
- Return to the full catalog from every detail page.

Metrics always describe the complete function-level line PDG. For browser readability, a graph above 80 nodes displays a focused 80-node neighborhood around the perturbation.
