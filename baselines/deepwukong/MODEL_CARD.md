# Model Card

## Model

DeepWuKong XFG vulnerability detector, CWE119 checkpoint.

## Intended Use

Batch or single-file C/C++ vulnerability screening inside Demo A. Inputs are
source files; outputs are prediction CSV/JSON/Markdown artifacts.

## Interface

Primary command:

```powershell
python .\scripts\run_demo_pipeline.py --input .\inputs --output .\outputs
```

Demo A adapter command:

```powershell
python .\scripts\run_demo_pipeline.py --input <source-file> --output <run-dir> --config .\configs\demo_config.json --no-timestamp-output
```

## Runtime Dependency

Full inference requires Docker image:

```text
deepwukong-rtx5060-cu128:experimental
```

The image was validated on the local RTX 5060 Laptop GPU with PyTorch
`2.9.0+cu128` and CUDA `12.8`.

## Limitations

- Output is source/function-level, not line-level localization.
- Source-level score is aggregated as `max(XFG vulnerable probability)`.
- Joern preprocessing must succeed for full DeepWuKong inference.
- The lexical mode exists only to satisfy Demo A compatibility paths and is not
  the primary baseline.
