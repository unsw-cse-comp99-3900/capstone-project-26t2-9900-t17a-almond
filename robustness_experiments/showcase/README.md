# DeepWuKong PDG Perturbation Atlas

This folder contains a static browser atlas for the 60 staged source files enumerated in `input_sources/sample_manifest.csv`: 20 CWE-119, 20 Devign, and 20 CVEfixes samples. Each entry is analyzed as the complete staged translation unit, matching the current full-test input semantics.

The generated inventory covers:

- All 13 source-level actions registered in `OPERATORS`: data-flow alias, dead statement, XFG-targeted dead code, range clamp, safe source substitution, sink bound guard, postcondition validation, integer overflow guard, array index bound guard, wide-character sink guard, pattern dead code, control wrapper, and temporary-variable split
- 6 ordinary random PDG actions: node add/delete/attribute modification and edge add/delete/reconnect
- 9 Winner-XFG PDG configurations: edge attack, feature mask, and targeted subgraph injection at budgets 1, 3, and 5
- One deterministic application for each ordinary action with `seed=42`

Sample labels, source kinds, function metadata, and staged paths come directly from the manifest. The generated catalog preserves that provenance alongside every prediction.

An action that cannot be applied, cannot produce a usable PDG/XFG, or cannot complete inference is recorded as skipped instead of stopping the batch; only successful sample/action pairs become selectable comparisons. Samples without an original XFG prediction remain in the catalog as analysis unavailable rather than displaying a synthetic score. Winner-XFG configurations retain their requested budget and report the actual applied operation count when the graph admits fewer valid mutations.

## Requirements

- `uv`
- Docker with NVIDIA GPU access
- Docker image `deepwukong-rtx5060-cu128:experimental`
- Graphviz (`dot` on `PATH`)

## Generate or Refresh the Atlas

Run from the project root:

```bash
uv run robustness_experiments/showcase/generate_showcase.py
```

The generator reuses matching static conclusions. Force Joern and model inference to run again when an inference input changes:

```bash
uv run robustness_experiments/showcase/generate_showcase.py --refresh
```

Render the browser pages without running inference:

```bash
uv run robustness_experiments/showcase/generate_showcase.py --render-only
```

Static conclusions and generated source variants are retained under:

```text
outputs/run_showcase_cache/
```

The browser artifact consists of:

```text
robustness_experiments/showcase/deepwukong_pdg_showcase.html
robustness_experiments/showcase/deepwukong_pdg_showcase_pages/
```

Open the index HTML directly. No web server or internet connection is required.

## Page Controls

- Search the source catalog by sample ID, path, dataset, or state.
- Open a source and search its available perturbation actions by name or effect.
- Use `+`, `-`, and `Reset` to control each PDG. Zoom steps continue from the current located or manually adjusted view and are capped at 12×.
- Drag a graph whenever either viewBox dimension is focused inside the complete graph.
- Use `Changes` for the control context plus changed or affected data edges in each rendered slice.
- Use `Full PDG` to inspect every rendered slice edge, with independent `Control` and `Data` filters.
- Use `Matrix` to inspect every node and effective edge from the complete PDG as a source-by-target adjacency matrix.
- Select an SVG node, SVG edge, or matrix cell to inspect complete incoming and outgoing dependencies and jump to the corresponding source line.
- Use `Locate changes` to highlight and return both graphs or matrices to the changed or directly affected elements.
- Use `Clear highlight` to restore normal styling without changing the current zoom, pan, filters, or matrix position.
- Read the complete staged source file with removals and additions shown inline.
- Return to the full catalog from every detail page.

Metrics and matrices describe the complete source-level line PDG. Dense SVG graphs display a change-centered neighborhood capped at 40 nodes and 72 type-balanced edges. Wide layered layouts automatically switch to deterministic source-order lanes, while the inline source view and dependency inspector retain complete evidence.
