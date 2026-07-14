# DeepWuKong Baseline

This directory provides the DeepWuKong CWE-119 baseline used by Demo B. It
contains the host-side wrapper, configuration, checkpoint, and minimal
compatibility modules. It does not contain the Docker image or training dataset.

## Layout

```text
baselines/deepwukong/
  configs/       Runtime and model-path configuration
  models/        DeepWuKong checkpoint
  scripts/       Single-file and batch inference entry points
  src/           Minimal host-side compatibility modules
  MODEL_CARD.md  Model scope, output semantics, and limitations
```

## Requirements

Host-side wrappers use the Python standard library. Full inference additionally
requires:

- Docker Desktop running;
- NVIDIA GPU access from Docker;
- the local image `deepwukong-rtx5060-cu128:experimental`;
- `models/deepwukong/deepwukong_cwe119_best.ckpt`.

The Docker image is not included in Git. The checkpoint is included in this
baseline directory.

## Run One Source File

Relative `--input`, `--output`, and `--config` paths are resolved from
`baselines/deepwukong/`. The clearest usage is therefore to run from this
directory:

```powershell
Push-Location baselines\deepwukong
python .\scripts\run_demo_pipeline.py `
  --input ..\..\input_sources\00_codexglue_devign_9763.c `
  --output ..\..\outputs\generated\deepwukong\00_codexglue_devign_9763 `
  --config .\configs\demo_config.json `
  --no-timestamp-output
Pop-Location
```

Use a directory for `--input` to run a batch. `scripts/run_demo.ps1` provides a
PowerShell wrapper for the same baseline.

## Raw Output

A single raw inference directory contains:

- `predictions.json`: prediction and XFG-level details;
- `predictions.csv`: flattened prediction fields;
- `run_metadata.json`: Joern, graph, timing, and warning metadata;
- `demo_report.md`: a short human-readable report;
- Docker command and log files produced by the host wrapper.

New raw runs belong under `../../outputs/generated/` and are ignored by Git.
Archived experiments consolidate each sample into one JSON under
`../../outputs/run_<id>/runs/`.

## Inference Semantics

```text
C/C++ source -> Joern tables -> PDG -> XFG -> tokenized graph -> DeepWuKong
```

A source file may generate multiple XFGs. The file-level vulnerability
probability is the maximum vulnerable probability across its XFGs, with `0.5`
as the default decision threshold. If no sensitive XFG seed is found, inference
returns probability `0.0`, label `0`, and a warning.

## Limitations

- The checkpoint targets CWE-119 and should not be treated as a universal
  vulnerability detector.
- Output is function/source-level, not precise vulnerable-line localization.
- Reproducing inference requires the separately distributed Docker image.
- `src/models/lexical.py` is a compatibility module, not the DeepWuKong graph
  model itself.

See `MODEL_CARD.md` for additional model details.
