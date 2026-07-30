# ALMOND: DeepWuKong Robustness Evaluation

ALMOND is a reproducible research prototype for measuring how controlled
source-code and program-graph perturbations affect
[DeepWuKong](https://github.com/jumormt/DeepWukong) vulnerability predictions.
It connects C/C++ samples, Joern graph extraction, PDG/XFG construction,
DeepWuKong inference, perturbation-budget search, result comparison, and
interactive reporting in one repository.

The project studies model robustness rather than training a new vulnerability
detector. Its central experiment is a paired comparison:

```text
same sample + same baseline
  -> apply one action at a controlled budget
  -> run the corresponding inference path
  -> measure graph change, probability change, and prediction flip
```

## Contents

- [Project Scope](#project-scope)
- [System Architecture](#system-architecture)
- [Implemented Capabilities](#implemented-capabilities)
- [Quick Start](#quick-start)
- [Code-Level Perturbations](#code-level-perturbations)
- [Graph-Level Perturbations](#graph-level-perturbations)
- [Running Controlled Experiments](#running-controlled-experiments)
- [Measurement and Interpretation](#measurement-and-interpretation)
- [Datasets](#datasets)
- [Outputs and Dashboards](#outputs-and-dashboards)
- [Archived Experiments](#archived-experiments)
- [Repository Layout](#repository-layout)
- [Testing](#testing)
- [Limitations](#limitations)

## Project Scope

DeepWuKong converts source code into a program dependence graph (PDG), extracts
sensitive XFG slices, and scores those XFGs with a graph neural network. ALMOND
tests how stable that prediction is under two distinct perturbation branches:

1. **Code level:** modify source code, then rerun Joern and the complete
   DeepWuKong pipeline.
2. **Graph level:** run Joern once, modify an in-memory NetworkX PDG, rebuild
   XFGs, and run model inference without rewriting the source.

These branches answer different questions. Code-level experiments test
realizable source transformations and include Joern's response to each change.
Graph-level experiments isolate the model's sensitivity to its graph
representation, but a modified graph is not guaranteed to correspond to
compilable source code.

## System Architecture

```text
                                +---------------------------+
                                | DeepWuKong CWE-119 model |
                                +-------------+-------------+
                                              ^
                                              |
                         PDG -> sensitive XFGs -> prediction
                                              ^
                                              |
 C/C++ source -> Joern -> nodes.csv / edges.csv
       |                         |
       |                         +-> NetworkX PDG
       |                               |
       |                               +-> graph action
       |                               +-> budget 1 / 3 / 5
       |                               +-> rebuild XFGs
       |
       +-> code action -> new source -> rerun Joern
               |
               +-> global or winner-XFG targeting
               +-> budget 1 / 2 / 3 / 5
```

A source file may produce multiple XFGs. The baseline wrapper uses the maximum
vulnerability probability across those XFGs as the file-level score, with
`0.5` as the default decision threshold.

## Implemented Capabilities

- DeepWuKong CWE-119 inference with file-level and XFG-level predictions.
- Thirteen selectable source-code perturbation actions.
- Global and winner-XFG-targeted source candidate selection.
- Source-level budget search and minimal `1 -> 0` evasion detection.
- Six primitive PDG node/edge actions with random or key-line-guided targeting.
- Three winner-XFG-targeted graph macro actions with nested budgets `1`, `3`,
  and `5`.
- Ten fixed graph seeds shared by primitive-random and Winner-XFG experiments.
- Validation and audit records for requested versus applied graph operations.
- Devign, official DeepWuKong CWE-119, and paired CVEfixes sample layouts.
- Archived code-level and graph-level experiment runs.
- A normalized console view for heterogeneous result formats.
- Offline HTML experiment dashboards and an interactive function-level PDG
  atlas.
- Docker packaging, a Windows launcher, and host-side unit tests.

## Quick Start

### Prerequisites

Full inference requires:

- Docker Desktop with the WSL 2 backend;
- NVIDIA GPU access from Docker;
- the local runtime image `deepwukong-rtx5060-cu128:experimental`;
- the included checkpoint at
  `baselines/deepwukong/models/deepwukong/deepwukong_cwe119_best.ckpt`.

Regenerating the PDG atlas or running its host-side rendering test also
requires Graphviz with `dot` available on `PATH`:

```powershell
dot -V
```

The large DeepWuKong runtime image is not stored in Git. Verify it before
starting:

```powershell
docker version
docker image inspect deepwukong-rtx5060-cu128:experimental
```

If the image uses a different local tag, set it for the current PowerShell
session:

```powershell
$env:DEEPWUKONG_IMAGE = "your-local-image:tag"
```

### Docker Console

From the repository root:

```powershell
.\Start.ps1
```

`Start.exe` provides the same workflow for double-click launch. The launcher
builds `t17a-almond:latest`, starts the interactive console, serves the
dashboards, and keeps generated `outputs/` on the host.

The console provides:

1. Full live baseline-plus-perturbation test.
2. One-baseline smoke test.
3. Results summary.
4. Normalized perturbation impact analysis.
5. Sample-level result inspection.
6. Experiment dashboard, PDG atlas, and latest graph-family comparison access.

Run the test suite through the same image:

```powershell
docker compose -f scripts/docker/compose.yaml run --rm almond tests
```

Use `docker compose ... run`, not `docker compose ... up`, for the interactive
console because it requires direct terminal input.

### Host Tools

Install the lightweight host dependency and run the console directly:

```powershell
python -m pip install -r requirements.txt
python deepwukong_demo_console_v4.py
```

To serve the static dashboards without the Docker launcher:

```powershell
python -m http.server 8000
```

Then open:

- `http://localhost:8000/outputs/index.html`
- `http://localhost:8000/demo_b/showcase/deepwukong_pdg_showcase.html`

## Code-Level Perturbations

Code-level actions always create a new source variant. Model inference then
reruns Joern, PDG construction, XFG extraction, and DeepWuKong:

```text
original source
  -> source action
  -> perturbed source
  -> Joern
  -> PDG/XFG
  -> DeepWuKong
  -> paired baseline comparison
```

### Actions

The registered actions are divided by experimental intent:

| Group | Actions | Purpose |
|---|---|---|
| Structure-oriented | `data_flow_alias`, `dead_statement`, `xfg_targeted_dead_code`, `pattern_dead_code`, `control_wrapper`, `temp_variable_split` | Change local control/data-flow or add no-op structure while attempting to preserve runtime behaviour. |
| Repair-like | `range_clamp`, `safe_source_substitution`, `sink_bound_guard`, `postcondition_validation`, `integer_overflow_guard`, `array_index_bound_guard`, `wide_char_sink_guard` | Add checks or substitutions resembling vulnerability repairs; these are not assumed to be semantics-preserving. |

The transformations are syntax-pattern based. Applicability varies by sample,
so reports retain both the requested budget and `applied_count`.

### Target Modes

| Mode | Behaviour |
|---|---|
| `global` | Select legal source candidates across the complete file. |
| `winner-xfg` | Run the baseline first, select the highest-probability XFGs at distinct key lines, and prioritize legal source candidates nearest each target line. |

Winner-XFG mode is still a source-level experiment. It does not directly edit
an XFG. After each source change, the runner rebuilds the graph and verifies
whether an XFG of the same category still covers the mapped target window.

### Budgets

A code budget is the requested number of applications of one action in one
source variant. Every action-budget pair starts from the original source:

```text
original -> dead_statement x1
original -> dead_statement x3
original -> dead_statement x5
```

The runner does not build budget `5` by adding changes to the budget `3`
variant, and it does not combine different actions automatically.

### Generate Variants Without Inference

```powershell
python demo_b\code\code_perturbations.py `
  --input input_sources\devign `
  --dataset devign `
  --actions data_flow_alias dead_statement xfg_targeted_dead_code `
  --counts 1 3 5 `
  --output artifacts\perturbed_sources\code_smoke
```

### Run a Global Budget Search

```powershell
python demo_b\code\run_budget_search.py `
  --input input_sources\devign `
  --target-mode global `
  --actions data_flow_alias dead_statement xfg_targeted_dead_code `
  --counts 1 3 5 `
  --run-round 1
```

### Run a Winner-XFG Budget Search

```powershell
python demo_b\code\run_budget_search.py `
  --input input_sources\cwe119\vulnerable `
  --target-mode winner-xfg `
  --winner-xfg-top-k 3 `
  --target-window-radius 3 `
  --actions data_flow_alias dead_statement xfg_targeted_dead_code `
  --counts 1 3 5 `
  --run-round 1
```

The code search runs the baseline once per sample. By default, only samples
with `baseline_label = 1` continue to the evasion search. A successful code
attack is specifically a `1 -> 0` prediction change.

## Graph-Level Perturbations

The graph branch loads Joern tables, builds the same line-level NetworkX PDG
used by DeepWuKong, and modifies `pdg.copy()` in memory. It does not overwrite
the source, `nodes.csv`, or `edges.csv`.

```text
source -> Joern once -> NetworkX PDG
                         -> graph action
                         -> perturbed PDG
                         -> rebuild XFGs
                         -> DeepWuKong
```

### Primitive Actions

| Action | PDG operation |
|---|---|
| `node_add` | Add a synthetic node connected to an existing anchor. |
| `node_delete` | Delete a non-protected node and its incident edges. |
| `node_attribute_modify` | Remap a node feature to another real source line. |
| `edge_add` | Add a missing directed control or data edge. |
| `edge_delete` | Remove an existing directed edge. |
| `edge_reconnect` | Move an edge while preserving its control/data type. |

Primitive actions support:

- `random`: reproducible selection using `--seed`;
- `guided`: deterministic selection near supplied DeepWuKong key lines.

Apply one action and export its validated graph audit:

```powershell
python demo_b\graph\graph_perturbations.py `
  --csv-root artifacts\joern_csv\run_20260710\baseline\00_codexglue_devign_9763 `
  --action edge_delete `
  --strategy random `
  --count 1 `
  --seed 42 `
  --output outputs\edge_delete_audit.json
```

### Winner-XFG Macro Actions

The targeted graph runner first scores baseline XFGs, selects the XFG with the
maximum vulnerability probability, and independently evaluates each action and
budget from a fresh baseline PDG.

| Action | Targeted operation |
|---|---|
| `winner_xfg_edge_attack` | Delete or bridge edges within the winner-XFG region according to the attack target. |
| `winner_xfg_feature_mask` | Remap high-priority winner-XFG node features to neutral or duplicated source-line features. |
| `targeted_subgraph_injection` | Inject a small control/data motif around the winner key line. |

The runner accepts:

```text
--actions winner_xfg_edge_attack winner_xfg_feature_mask targeted_subgraph_injection
--budgets 1 3 5
--seeds 7 17 29 42 61 73 89 101 137 2026
```

It requires source files, prepared Joern CSV tables, metadata, the checkpoint,
and output paths mounted into the DeepWuKong runtime container. Small graphs may
provide fewer legal operations than requested; such results remain scored with
their actual `applied_count`.

## Running Controlled Experiments

Use a fixed experiment matrix so that each comparison changes only one
independent variable:

| Dimension | Recommended values |
|---|---|
| Dataset | Report Devign, CWE119, and CVEfixes separately. |
| Sample | Stable sample ID and ground-truth label where available. |
| Level | `code` or `graph`; do not merge their raw budgets. |
| Target mode | `global` or `winner-xfg`. |
| Action | One action per variant. |
| Budget | Use a fixed schedule such as `1, 3, 5`. |
| Target | Use the same XFG target rank when comparing targeted actions. |
| Seed | Use and record the shared 10-seed schedule for both graph families. |

The primary paired comparisons are:

1. Same sample and action across budgets.
2. Same action and budget across samples.
3. Same sample and budget across actions.
4. Same code action and budget under `global` versus `winner-xfg`.
5. Code-level and graph-level trends reported separately.

Code budget `3` and graph budget `3` both mean three requested operations, but
they are not equivalent perturbation magnitudes. One source edit may create or
remove multiple PDG/XFG nodes and edges.

For reproducible evaluation:

- cache one baseline per sample;
- generate every budget from the unmodified source or PDG;
- keep B1 as an operation prefix of B3 and B3 as a prefix of B5 for each graph action/seed;
- record requested and applied budgets;
- exclude failed or invalid variants from the scored denominator;
- retain target-coverage status for winner-XFG source runs;
- separate baseline errors from successful perturbation attacks;
- keep dataset-level and action-level denominators visible.

## Measurement and Interpretation

The current reports expose:

- baseline and perturbed labels;
- baseline and perturbed vulnerability probabilities;
- signed and absolute probability change;
- prediction flip and flip direction;
- attack success when supported by the runner;
- requested and applied perturbation counts;
- node and edge deltas when available;
- generation, inference, and target-coverage status.

Recommended core metrics are:

```text
Flip rate          = flipped scored variants / scored variants
Mean delta P       = mean(perturbed probability - baseline probability)
Minimal budget     = first budget that produces the defined success condition
Validity rate      = scored valid variants / attempted variants
Target coverage    = rebuilt XFGs covering the target / targeted variants
```

Interpret flip direction explicitly:

- `1 -> 0`: an evasion or induced false negative when the baseline was a
  correct vulnerable prediction;
- `0 -> 1`: an induced false positive when the baseline was a correct
  non-vulnerable prediction;
- a flip from an already incorrect baseline is model instability, not
  automatically an attack success.

Code and graph runners do not use exactly the same attack-success
definition. Code budget search defines success as `baseline_label = 1` followed
by `perturbed_label = 0`. Both graph runners define success against the
unchanged source label and restrict ASR to baseline-correct samples.
Therefore, graph-random and Winner-XFG results can be compared under the shared
budget/seed design, but `ASR` values should not be aggregated with code results
until the final evaluation module applies one shared ground-truth-aware
definition.

The console and HTML dashboards normalize table columns and show attempts,
scored runs, failures, flips, ground-truth-aware ASR, probability movement,
graph deltas, horizontal fixed-budget comparisons, vertical budget responses,
and per-seed stability. They remain reporting interfaces rather than a single
weighted robustness rating.

## Datasets

| Directory | Contents |
|---|---|
| `input_sources/devign/` | Ten CodeXGLUE/Devign C samples used by the initial archived experiment. |
| `input_sources/cwe119/` | Ten official DeepWuKong CWE-119 samples, separated into vulnerable and non-vulnerable subsets with selection metadata. |
| `input_sources/cvefixes/` | Five complete C vulnerability/fix file pairs with metadata. |

For ordinary robustness experiments, perturb the vulnerable side of CVEfixes
unless the experiment explicitly compares vulnerable and fixed pairs. Dataset
labels and model predictions are separate concepts; a filename or prediction
must not be treated as ground truth without dataset metadata.

## Outputs and Dashboards

Experiment runs are stored directly under `outputs/`:

```text
outputs/run_<YYYYMMDD>_<level>_<dataset>_round<N>/
```

Winner-XFG runs may include `_winner_xfg` before `_round<N>`.

Common result files are:

| File | Purpose |
|---|---|
| `baseline_predictions.csv` | One baseline record per sample. |
| `baseline_eligibility.csv` | Baseline samples included in or excluded from an attack search. |
| `perturbation_results.csv` | Detailed action, budget, target, status, and prediction records. |
| `prediction_comparison.csv` | Paired baseline-versus-variant rows. |
| `action_summary.csv` | Aggregates by action and, where available, budget. |
| `summary.json` | Compact machine-readable run summary. |
| `details.json` | Full metadata, errors, and result details. |
| `dashboard.html` | Offline dashboard for one run. |
| `graph_comparison/dashboard.html` | Random graph versus Winner-XFG budget and seed comparison for a Full Test. |

Generated source files and Joern artifacts are kept separately:

```text
artifacts/perturbed_sources/
artifacts/joern_csv/
artifacts/joern_cpg/
artifacts/xfg/
```

New run directories are ignored by default. Deliberately archived experiments
must be reviewed before they are force-added to Git; Docker logs, temporary
Joern working directories, and regenerable intermediates should remain local.

## Archived Experiments

The repository includes representative completed runs:

| Run | Samples | Attempted | Scored | Flips / successes |
|---|---:|---:|---:|---:|
| `run_20260710_code_devign_round1` | 10 | 23 | 23 | 0 flips |
| `run_20260717_graph_devign_round1` | 10 | 60 | 57 | 1 flip |
| `run_20260717_graph_cwe119_round1` | 10 | 60 | 60 | 1 flip |
| `run_20260717_graph_cwe119_round2` | 10 baseline, 8 eligible | 72 | 72 | 8 attack successes |
| `run_20260723_code_devign_winner_xfg_round1` | 10 | 270 | 199 | 5 flips |
| `run_20260723_code_cwe119_winner_xfg_round1` | 5 | 178 | 153 | 3 flips |
| `run_20260723_code_cvefixes_winner_xfg_round1` | 5 | 188 | 168 | 1 flip |

These are small research runs under different protocols. They demonstrate the
pipeline and should not be interpreted as DeepWuKong accuracy estimates or
combined into one overall robustness score.

## Repository Layout

| Path | Purpose |
|---|---|
| `baselines/deepwukong/` | DeepWuKong wrapper, configuration, checkpoint, model card, and inference scripts. |
| `demo_b/code/` | Source actions, dataset adapters, variant generation, and budget search. |
| `demo_b/graph/` | Primitive PDG actions and winner-XFG-targeted graph experiments. |
| `demo_b/showcase/` | Interactive function/source PDG atlas generation. |
| `demo_b/compare_deepwukong.py` | Paired baseline and perturbation comparison. |
| `demo_b/visualize_results.py` | Run dashboard and shared index generation. |
| `input_sources/` | Dataset-separated C/C++ samples and metadata. |
| `artifacts/` | Generated sources, Joern tables, CPG validation data, and XFG references. |
| `outputs/` | Archived predictions, comparisons, summaries, and dashboards. |
| `scripts/docker/` | Dockerfile, Compose configuration, and container entrypoint. |
| `tests/` | Unit and integration-oriented tests. |
| `legacy/` | Superseded scripts and perturbation references retained for provenance. |

## Testing

Run all host-side tests:

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

The showcase rendering tests invoke Graphviz. If the suite reports
`FileNotFoundError` while starting `dot`, install Graphviz and reopen the
terminal so the updated `PATH` is visible.

Check the main experiment scripts without running inference:

```powershell
python -m py_compile `
  demo_b\code\code_perturbations.py `
  demo_b\code\run_budget_search.py `
  demo_b\graph\graph_perturbations.py `
  demo_b\graph\run_xfg_targeted_experiment.py `
  demo_b\visualize_results.py
```

## Limitations

- The included checkpoint targets CWE-119 and is not a universal
  vulnerability detector.
- The separately distributed Docker runtime image is required for reproducible
  Joern and model inference.
- Source transformations use syntax patterns rather than a complete C/C++
  parser, so action applicability and semantic preservation require auditing.
- Repair-like source actions may alter program behaviour and must not be mixed
  with semantics-preserving robustness claims.
- Direct PDG perturbations may not map back to compilable source code.
- DeepWuKong key lines are sensitive XFG seed locations, not guaranteed
  vulnerable-line annotations or gradient-based model explanations.
- Winner-XFG source targeting uses key-line proximity and reconstructed-XFG
  coverage checks; it is a heuristic, not exact node attribution.
- Existing archived runs use different action sets and success definitions.
  Controlled comparisons must retain the same dataset, action, budget, target
  mode, target rank, and seed.
- Code-level inference reruns Joern for every source variant and is therefore
  substantially slower than reusing prepared graph tables.
- The final cross-run evaluation and rating protocol remains future work; the
  current dashboard provides normalized descriptive statistics.
