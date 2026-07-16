# DeepWuKong PDG Showcase

This folder contains a standalone HTML view for comparing an original DeepWuKong program dependence graph (PDG) with three source perturbations:

- `dead_statement`
- `control_wrapper`
- `temp_variable_split`

## Requirements

Install or provide the following before generating the page:

- `uv`
- Docker with NVIDIA GPU access
- Docker image `deepwukong-rtx5060-cu128:experimental`
- Graphviz (`dot` must be available on `PATH`)

## Generate the Showcase

Run this command from the project root:

```bash
uv run demo_b/showcase/generate_showcase.py
```

The command runs fresh inference for the original source and all three perturbations, then writes:

```text
demo_b/showcase/deepwukong_pdg_showcase.html
```

Open the HTML file directly in a browser. It is self-contained and does not require a web server or internet connection.

## Use a Different Source File

```bash
uv run demo_b/showcase/generate_showcase.py \
  --source path/to/source.c \
  --output path/to/showcase.html
```

The source must support all three perturbations. Generation stops if an action cannot be applied exactly once or if Joern or DeepWuKong inference fails.

## Page Controls

- Select an action with the tabs above the graphs.
- Use `+` and `-` to zoom a graph.
- Drag a graph after zooming in to pan across it.
- Use `Reset` to restore the original graph position and scale.
- Hover over or focus a line node to highlight its dependencies.
- Read the inline diff below the graphs. Red lines were removed, green lines were added, and the `OLD` and `NEW` columns show line numbers before and after the perturbation.
