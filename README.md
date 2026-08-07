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
       |                               +-> budgets 1 / 3 / 5 / 7 / 9 / 11 / 13 / 15 / 20 / 25
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
  `5`, `7`, `9`, `11`, `13`, `15`, `20`, and `25`.
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

The large DeepWuKong runtime image is not stored in Git. Download the verified
Docker delivery package from the
[UNSW OneDrive delivery folder](https://unsw-my.sharepoint.com/:f:/g/personal/z5462057_ad_unsw_edu_au/IgCDusTbCoy4TIvZjFGzW6nFAUVNNinwLIUlanldfyHryZs?e=zckK4M).

Create the local-only runtime directory, then use the browser download dialog to
save the required archive at:

```text
baselines/deepwukong/module_tranning/deepwukong-rtx5060-cu128-experimental.tar
```

The `module_tranning/` directory is excluded from Git and the Docker build
context. The archive is 4,766,494,208 bytes and its expected SHA-256 is:

```text
0482EA09F89569072427344B1DADA5E72878DF2E7BC99F878F5895B17DAF6B1D
```

Verify and load it before starting:

```powershell
docker version
$RuntimeDir = ".\baselines\deepwukong\module_tranning"
$RuntimeArchive = Join-Path $RuntimeDir "deepwukong-rtx5060-cu128-experimental.tar"
New-Item -ItemType Directory -Force $RuntimeDir | Out-Null
(Get-Item $RuntimeArchive).Length
(Get-FileHash $RuntimeArchive -Algorithm SHA256).Hash
docker load -i $RuntimeArchive
docker image inspect deepwukong-rtx5060-cu128:experimental
```

The calculated checksum must match the value above. Loading the archive restores
the exact tag expected by Docker Compose. See
[`docs/DOCKER_IMAGE_DELIVERY.md`](docs/DOCKER_IMAGE_DELIVERY.md) for the complete
assessor workflow and troubleshooting guidance.

If the image uses a different local tag, set it for the current PowerShell
session:

```powershell
$env:DEEPWUKONG_IMAGE = "your-local-image:tag"
```

### Docker Console

From the repository root:

```powershell
.\robustness_experiments\Start.ps1
```

Alternatively, run `Start.exe` from the repository root (or double-click it in
File Explorer). Both entry points provide the same workflow. The launcher builds
`t17a-almond:latest`, starts the interactive console, serves the dashboards, and
keeps generated `outputs/` on the host.

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

Rerun only the random graph stage of an existing Full Test, preserving the
code-level and Winner-XFG results:

```powershell
docker compose -f scripts/docker/compose.yaml run --rm almond `
  rerun-random-graph --run-dir outputs/<full-test-run>
```

The command writes to a temporary directory first. On success, it archives the
old `graph_random/` directory, installs the replacement, and regenerates all
run dashboards including the paired graph-family comparison.

Use `docker compose ... run`, not `docker compose ... up`, for the interactive
console because it requires direct terminal input.

### Host Tools

Install the lightweight host dependency and run the console directly:

```powershell
python -m pip install -r requirements.txt
python deepwukong_console.py
```

To serve the static dashboards without the Docker launcher:

```powershell
python -m http.server 8000
```

Then open:

- `http://localhost:8000/outputs/index.html`
- `http://localhost:8000/robustness_experiments/showcase/deepwukong_pdg_showcase.html`

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
python robustness_experiments\code\code_perturbations.py `
  --input input_sources\devign `
  --dataset devign `
  --actions data_flow_alias dead_statement xfg_targeted_dead_code `
  --counts 1 3 5 `
  --output artifacts\perturbed_sources\code_smoke
```

### Run a Global Budget Search

```powershell
python robustness_experiments\code\run_budget_search.py `
  --input input_sources\devign `
  --target-mode global `
  --actions data_flow_alias dead_statement xfg_targeted_dead_code `
  --counts 1 3 5 `
  --run-round 1
```

### Run a Winner-XFG Budget Search

```powershell
python robustness_experiments\code\run_budget_search.py `
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
python robustness_experiments\graph\graph_perturbations.py `
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
--budgets 1 3 5 7 9 11 13 15 20 25
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
- independent-sample any-seed success and mean within-sample seed success;
- per-seed success rates with mean, standard deviation, and range;
- paired graph-family results restricted to common scoreable
  `(sample, budget, seed)` keys;
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
graph deltas, budget-response comparisons, coverage, and per-seed stability.
Graph dashboards keep full variant evidence in linked CSV files so large runs
remain responsive. They remain reporting interfaces rather than a single
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
| `sample_level_summary.csv` | Independent-sample outcomes after collapsing repeated seeds. |
| `seed_level_summary.csv` | Per-seed coverage, ASR, and probability movement. |
| `paired_common_summary.csv` | Random-versus-Winner comparison on common scoreable sample/budget/seed keys. |

Graph transformations that leave no scoreable XFG are recorded as `no_xfg`.
They remain visible in coverage statistics but are excluded from model flip
and ASR denominators; `no_xfg` is not interpreted as a model prediction of
label 0.

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

These are small research runs under different protocols. They show the
pipeline and should not be interpreted as DeepWuKong accuracy estimates or
combined into one overall robustness score.

## Repository Layout

| Path | Purpose |
|---|---|
| `baselines/deepwukong/` | DeepWuKong wrapper, configuration, checkpoint, and inference scripts. |
| `baselines/deepwukong/module_tranning/` | Local-only location for the verified runtime TAR; ignored by Git and the Docker build context. |
| `robustness_experiments/code/` | Source actions, dataset adapters, variant generation, and budget search. |
| `robustness_experiments/graph/` | Primitive PDG actions and winner-XFG-targeted graph experiments. |
| `robustness_experiments/showcase/` | Interactive function/source PDG atlas generation. |
| `robustness_experiments/compare_deepwukong.py` | Paired baseline and perturbation comparison. |
| `robustness_experiments/visualize_results.py` | Run dashboard and shared index generation. |
| `input_sources/` | Dataset-separated C/C++ samples and metadata. |
| `artifacts/` | Generated sources, Joern tables, CPG validation data, and XFG references. |
| `outputs/` | Archived predictions, comparisons, summaries, and dashboards. |
| `scripts/docker/` | Dockerfile, Compose configuration, and container entrypoint. |
| `tests/` | Unit and integration-oriented tests. |

## Testing

This section is the complete testing and acceptance procedure for the ALMOND
DeepWuKong robustness evaluation system. Run the commands from the extracted
repository root in PowerShell unless a step says otherwise.

### 1. Test objectives

The test process verifies:

- all submission-critical files and the final archived Run are present;
- the separately delivered Docker runtime TAR is complete and authentic;
- Docker, Graphviz, Joern, the checkpoint, and NVIDIA GPU inference work;
- code-level and graph-level perturbation modules handle happy and sad cases;
- fixed budgets, seeds, paired statistics, reruns, dashboards, and the PDG Atlas
  preserve their data contracts;
- the console and browser-facing result workflow are usable end to end.

### 2. Required environment

| Requirement | Acceptance condition |
|---|---|
| Windows | Windows 10/11 64-bit with PowerShell 5.1 or 7 |
| Docker | `docker version` reports a running Linux Docker engine |
| GPU | `nvidia-smi` succeeds and Docker exposes an NVIDIA GPU |
| Runtime TAR | Exact path, size, and SHA-256 listed below |
| Project image | `t17a-almond:latest` builds from `scripts/docker/Dockerfile` |
| Graphviz | Container command `dot -V` succeeds |

The runtime archive must be stored locally at:

```text
baselines/deepwukong/module_tranning/deepwukong-rtx5060-cu128-experimental.tar
```

Expected metadata:

```text
Size:    4,766,494,208 bytes
SHA-256: 0482EA09F89569072427344B1DADA5E72878DF2E7BC99F878F5895B17DAF6B1D
Tag:     deepwukong-rtx5060-cu128:experimental
```

`module_tranning/` is intentionally ignored by Git and excluded from the Docker
build context. Docker Compose mounts it read-only only so the Smoke Test can
verify the local download.

### 3. Required-file completeness check

Run this check before creating the Moodle ZIP or GitHub release:

```powershell
$RequiredFiles = @(
  ".\README.md",
  ".\TESTING.md",
  ".\ALMOND_Installation_Manual.pdf",
  ".\Start.exe",
  ".\robustness_experiments\Start.ps1",
  ".\deepwukong_console.py",
  ".\scripts\docker\Dockerfile",
  ".\scripts\docker\Dockerfile.dockerignore",
  ".\scripts\docker\compose.yaml",
  ".\scripts\docker\docker_entrypoint.py",
  ".\scripts\run_full_test.py",
  ".\baselines\deepwukong\scripts\run_pipeline.py",
  ".\baselines\deepwukong\scripts\run_pipeline.ps1",
  ".\baselines\deepwukong\configs\runtime_config.json",
  ".\baselines\deepwukong\configs\runtime_config_source_only.json",
  ".\baselines\deepwukong\models\deepwukong\deepwukong_cwe119_best.ckpt",
  ".\robustness_experiments\code\code_perturbations.py",
  ".\robustness_experiments\code\run_budget_search.py",
  ".\robustness_experiments\graph\graph_perturbations.py",
  ".\robustness_experiments\graph\experiment_design.py",
  ".\robustness_experiments\graph\run_random_graph_experiment.py",
  ".\robustness_experiments\graph\run_xfg_targeted_experiment.py",
  ".\robustness_experiments\showcase\generate_showcase.py",
  ".\robustness_experiments\visualize_results.py",
  ".\tests\run_smoke_test.py"
)
$MissingFiles = $RequiredFiles | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) }
if ($MissingFiles) { $MissingFiles; throw "Required project files are missing." }
"Required project files: OK"
```

Check the retained final Run separately:

```powershell
$FinalRun = ".\outputs\run_20260731_124703_code_all_input_sources"
$RequiredEvidence = @(
  "dashboard.html", "summary.json", "input_manifest.csv",
  "baseline_summary.csv", "action_summary.csv",
  "prediction_comparison.csv", "sample_level_summary.csv",
  "graph_inputs", "graph_random", "graph_targeted",
  "graph_comparison", "variants"
)
$MissingEvidence = $RequiredEvidence | Where-Object {
  -not (Test-Path -LiteralPath (Join-Path $FinalRun $_))
}
if ($MissingEvidence) { $MissingEvidence; throw "Final Run evidence is incomplete." }
"Final Run evidence: OK"
```

Expected result: both checks print `OK` and list no missing paths.

### 4. Runtime archive, image, and GPU checks

Before loading the base image, verify the downloaded TAR from PowerShell:

```powershell
$RuntimeArchive = ".\baselines\deepwukong\module_tranning\deepwukong-rtx5060-cu128-experimental.tar"
(Get-Item $RuntimeArchive).Length
(Get-FileHash $RuntimeArchive -Algorithm SHA256).Hash
```

The size must be `4,766,494,208` bytes and the SHA-256 must be:

```text
0482EA09F89569072427344B1DADA5E72878DF2E7BC99F878F5895B17DAF6B1D
```

Load and inspect the verified base image:

```powershell
docker load -i $RuntimeArchive
docker image inspect deepwukong-rtx5060-cu128:experimental
```

Build the ALMOND image and check its key external dependencies:

```powershell
docker compose -f scripts/docker/compose.yaml build almond
docker run --rm --entrypoint dot t17a-almond:latest -V
docker run --rm --gpus all --entrypoint python t17a-almond:latest `
  -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

Acceptance conditions:

- the image build exits with code 0;
- Graphviz prints a version instead of `FileNotFoundError`;
- `torch.cuda.is_available()` prints `True` and a GPU name is printed.

### 5. Automated unit and integration suite

The authoritative run is inside the project image:

```powershell
docker compose -f scripts/docker/compose.yaml run --rm almond tests
```

Expected result:

```text
Ran 66 tests
OK
```

The 66 tests are distributed as follows:

| Test file | Count | Principal coverage |
|---|---:|---|
| `test_code_perturbations.py` | 3 | dataset IDs, safe candidate selection, declaration handling |
| `test_compare_deepwukong.py` | 1 | prediction reduction and ID-based paired joins |
| `test_dashboard_menu.py` | 3 | shared budgets, dashboard selection, graph-comparison menu |
| `test_graph_experiment_design.py` | 4 | ten budgets, ten seeds, legacy arguments, scoreability |
| `test_graph_perturbations.py` | 13 | copy safety, actions, targeting, fallbacks, nested budgets, PDG loading |
| `test_smoke_test.py` | 2 | valid inference output and invalid/missing output fields |
| `test_random_graph_rerun.py` | 2 | safe Run selection and non-destructive summary updates |
| `test_showcase_rendering.py` | 20 | source/PDG rendering, focus evidence, cache and staged provenance |
| `test_visualize_results.py` | 15 | paired cohorts, ASR/statistics, budgets, dashboards and indexes |
| `test_xfg_targeted_experiment.py` | 3 | metadata and effective Winner-XFG node selection |

Use `-v` in the commands below so that every test method is printed. A normal
passing method ends in `... ok`. The elapsed time is machine-dependent, but the
reported test count and final `OK` must match this document. Docker may print
`Container ... Creating` and `Container ... Created` before the Python output;
those lines are normal.

Result meanings:

| Result | Meaning | Acceptance action |
|---|---|---|
| `ok` | The test method completed and all assertions passed | Accept |
| `FAIL` | The method ran, but an actual value did not match the required value | Investigate the named assertion; do not accept |
| `ERROR` | Setup, import, external command, or the method itself raised an exception | Read the traceback; do not accept |
| `skipped` | A test was deliberately not executed | Record the reason; the final container run is expected to have no skips |

#### 5.1 `test_code_perturbations.py` - 3 tests

Run only this file:

```powershell
docker compose -f scripts/docker/compose.yaml run --rm --entrypoint python almond -m unittest discover -s tests -p "test_code_perturbations.py" -v
```

What it verifies:

- a dataset slug is derived consistently from either an input directory or the
  parent directory of a single input file;
- custom-type declarations are not selected for unsafe control-wrapper
  perturbations;
- ordinary non-declaration expression statements remain valid perturbation
  candidates instead of being filtered out with declarations.

Normal result:

```text
Ran 3 tests in <time>s

OK
```

This means dataset provenance and the positive/negative candidate-selection
rules all behaved as required.

#### 5.2 `test_compare_deepwukong.py` - 1 test

Run only this file:

```powershell
docker compose -f scripts/docker/compose.yaml run --rm --entrypoint python almond -m unittest discover -s tests -p "test_compare_deepwukong.py" -v
```

What it verifies:

- duplicate XFG predictions for a source are reduced using the maximum score;
- original and perturbed predictions are paired by sample ID, not accidental
  CSV row order.

Normal result:

```text
Ran 1 test in <time>s

OK
```

The passing result confirms the comparison output uses the intended prediction
reduction and stable ID-based join.

#### 5.3 `test_dashboard_menu.py` - 3 tests

Run only this file:

```powershell
docker compose -f scripts/docker/compose.yaml run --rm --entrypoint python almond -m unittest discover -s tests -p "test_dashboard_menu.py" -v
```

What it verifies:

- the console displays the shared final graph budgets
  `1, 3, 5, 7, 9, 11, 13, 15, 20, 25`;
- selecting a dashboard opens the requested page and then returns to the
  dashboard menu;
- a newly available graph-comparison dashboard is added dynamically without
  changing or removing the existing choices.

Normal result:

```text
Ran 3 tests in <time>s

OK
```

The passing result confirms the console and result-menu navigation agree with
the final experiment configuration.

#### 5.4 `test_graph_experiment_design.py` - 4 tests

Run only this file:

```powershell
docker compose -f scripts/docker/compose.yaml run --rm --entrypoint python almond -m unittest discover -s tests -p "test_graph_experiment_design.py" -v
```

What it verifies:

- the default design contains all ten final budgets and ten fixed seeds;
- plural budget/seed arguments override their legacy scalar aliases;
- the old scalar argument remains supported for backwards compatibility;
- an empty XFG tensor is rejected as unscoreable instead of producing a false
  prediction.

Normal result:

```text
Ran 4 tests in <time>s

OK
```

The passing result confirms deterministic experiment expansion, CLI
compatibility, and the empty-input error rule.

#### 5.5 `test_graph_perturbations.py` - 13 tests

Run only this file:

```powershell
docker compose -f scripts/docker/compose.yaml run --rm --entrypoint python almond -m unittest discover -s tests -p "test_graph_perturbations.py" -v
```

What it verifies:

- every graph action modifies a copy and leaves the source graph unchanged;
- added nodes carry real source-line metadata for symbolization;
- node-attribute modification changes the feature source without changing
  topology;
- guided edge deletion selects the edge nearest the key line and rejects input
  with no key lines;
- Winner-XFG actions preserve the original graph and key-line metadata;
- targeted edge attacks respect the required edge direction;
- each targeted-subgraph budget step injects exactly three nodes;
- a missing seed node uses the defined fallback anchor, while a missing genuine
  Winner-XFG target is rejected;
- random and Winner-XFG budgets are nested prefixes, so a larger budget extends
  rather than regenerates a smaller-budget action sequence;
- Joern PDG loading retains only control-dependency and data-dependency edges.

Normal result:

```text
Ran 13 tests in <time>s

OK
```

The passing result confirms graph mutation safety, targeting rules, budget
nesting, and PDG edge filtering.

#### 5.6 `test_smoke_test.py` - 2 tests

Run only this file:

```powershell
docker compose -f scripts/docker/compose.yaml run --rm --entrypoint python almond -m unittest discover -s tests -p "test_smoke_test.py" -v
```

What it verifies:

- a complete inference result is accepted when it has a valid label, a
  probability in `[0, 1]`, and positive node and edge counts;
- missing fields, invalid labels/probabilities, and invalid graph counts are
  reported instead of being accepted.

Normal result:

```text
Ran 2 tests in <time>s

OK
```

These are fast unit tests for the inference-output contract. They do **not**
hash the 4.44 GiB runtime TAR or perform live GPU inference. The separate
end-to-end Smoke Test that performs those checks is documented in Section 7.

#### 5.7 `test_random_graph_rerun.py` - 2 tests

Run only this file:

```powershell
docker compose -f scripts/docker/compose.yaml run --rm --entrypoint python almond -m unittest discover -s tests -p "test_random_graph_rerun.py" -v
```

What it verifies:

- rerun-directory resolution accepts only direct children of `outputs/` and
  rejects unsafe or unrelated paths;
- a partial random-graph rerun updates its own summary while preserving the
  existing code and targeted-graph stage summaries.

Normal result:

```text
Ran 2 tests in <time>s

OK
```

The passing result confirms reruns cannot escape the result root or overwrite
unrelated completed stages.

#### 5.8 `test_showcase_rendering.py` - 20 tests

Run only this file:

```powershell
docker compose -f scripts/docker/compose.yaml run --rm --entrypoint python almond -m unittest discover -s tests -p "test_showcase_rendering.py" -v
```

What it verifies:

- inline source diffs keep full non-blank source, preserve original/selected
  line numbers, and attach graph-navigation markers;
- large and dense PDG views keep the focused nodes/edges, cap browser payloads,
  and reserve visible capacity for both CDG and DDG edges;
- added and removed edges remain exact in action focus, deleted-node views keep
  surviving context, and rendered focus edges retain their dependency type;
- statement classification does not mistake comparison calls for assignments;
- wide graphs use compact source-order lanes;
- cached renders refresh source metadata even when graph topology is unchanged;
- serialized PDGs retain complete dependency evidence;
- all thirteen code actions are configured;
- catalog and discovery use staged-manifest provenance for inference sources;
- effective winner nodes prefer recorded XFG members and otherwise fall back to
  nodes nearest the key line;
- a variant without an XFG is not displayed as if it had a prediction;
- partially applied targeted budgets display the actual applied count.

Normal result:

```text
Ran 20 tests in <time>s

OK
```

The passing result confirms the PDG Atlas and source-comparison pages preserve
evidence, provenance, focus, and browser-size constraints. This file includes
the rendering checks that require Graphviz; use the container result for final
acceptance.

#### 5.9 `test_visualize_results.py` - 15 tests

Run only this file:

```powershell
docker compose -f scripts/docker/compose.yaml run --rm --entrypoint python almond -m unittest discover -s tests -p "test_visualize_results.py" -v
```

What it verifies:

- fixed-budget reports compare one variable at a time;
- budget reports use one line per method, share the same budgets, and keep a
  coverage chart when coverage varies;
- attempted and scored counts remain distinct;
- multi-seed ASR includes only baseline-eligible rows and does not count seeds
  as additional samples;
- paired-common summaries exclude keys that either attack family could not
  score;
- Wilson confidence intervals are bounded and contain the measured rate;
- graph-budget input schemas are normalized;
- multi-budget seed reports use CSV evidence without redundant chart bars;
- combined reports save paired-common cohort evidence and accept only rows with
  matching budgets and seeds;
- result pages use one dropdown with the current page selected;
- the retained full Run and available subreports render successfully;
- the result index links to every generated dashboard.

Normal result:

```text
Ran 15 tests in <time>s

OK
```

The passing result confirms the reported counts, ASR, confidence intervals,
paired comparisons, generated dashboards, and navigation are internally
consistent.

#### 5.10 `test_xfg_targeted_experiment.py` - 3 tests

Run only this file:

```powershell
docker compose -f scripts/docker/compose.yaml run --rm --entrypoint python almond -m unittest discover -s tests -p "test_xfg_targeted_experiment.py" -v
```

What it verifies:

- metadata files with a UTF-8 byte-order mark are read correctly;
- recorded Winner-XFG nodes that genuinely exist in the PDG are preserved;
- when recorded XFG nodes are unavailable, selection falls back to the nearest
  eligible PDG nodes.

Normal result:

```text
Ran 3 tests in <time>s

OK
```

The passing result confirms robust metadata loading and both the primary and
fallback Winner-XFG targeting paths.

#### 5.11 Complete-suite acceptance

After the ten files pass separately, run them together to detect import-order
or shared-state problems:

```powershell
docker compose -f scripts/docker/compose.yaml run --rm almond tests
```

Required final lines:

```text
Ran 66 tests in <time>s

OK
```

Any count other than 66 means a test was not discovered or the test set has
changed; update and revalidate this document before submission.

For a quick host-side diagnostic, use:

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

Host-side Graphviz failures are environmental. The final acceptance result must
come from the container, which installs Graphviz in its Dockerfile.

### 6. Per-module verification matrix

| Module | Automated evidence | Manual/integration method | Pass condition |
|---|---|---|---|
| Docker packaging | Complete 66-test run | Build image; inspect base tag; run `dot -V` | Build and dependency checks pass |
| Runtime delivery | Integrated `tests/run_smoke_test.py` archive check | Console option 2, plus a separate corrupt/truncated test copy | Exact size and SHA accepted; missing or altered files print errors and stop the test |
| Baseline inference | output-contract unit tests | Console option 2 | Joern creates a graph and checkpoint returns label, probability, nodes, edges |
| Code perturbations | 3 code tests plus visualization tests | Run a small input through `run_budget_search.py` | Variants are generated, originals remain unchanged, evidence CSV is written |
| Random graph perturbations | 13 graph tests | Run random family for one sample/seed/budget | Nested operations and prediction evidence are produced |
| Winner-XFG targeting | graph and XFG tests | Run targeted family and inspect winner-node provenance | Real/fallback target rules and budget metadata are recorded |
| Experiment design | 4 design tests | Inspect generated command/summary | Budgets are `1,3,5,7,9,11,13,15,20,25`; seeds remain fixed |
| Paired statistics | comparison and visualization tests | Inspect graph-comparison CSV and dashboard | Only matched sample/action/budget/seed rows enter paired comparison |
| Rerun workflow | 2 rerun tests | Rerun random graph stage against a copied Run | Other stages remain intact and replacement occurs only on success |
| Dashboard/index | dashboard and visualization tests | Open index, final dashboard, graph comparison | Links work and totals agree with CSV/JSON evidence |
| PDG Atlas | 20 showcase tests | Open sample pages; inspect source and CDG/DDG edges | Graph is legible and highlighted evidence matches source rows |
| Launchers/console | dashboard-menu tests | Run both `Start.exe` and `Start.ps1` | Same menu appears; exit is clean; host outputs persist |
| Final Run archive | required-evidence check | Open all retained CSV/JSON/HTML evidence | Final Run is readable without temporary `_work` or per-variant JSON directories |

### 7. Smoke Test

Start the console:

```powershell
.\Start.exe
```

Select `2. Run Smoke Test`. The test performs these stages in order:

1. locate the TAR under `baselines/deepwukong/module_tranning/`;
2. require exactly 4,766,494,208 bytes;
3. stream the complete file through SHA-256 and require the documented digest;
4. confirm the sample, checkpoint, and inference script are present;
5. run Joern, build PDG/XFG data, load the CWE-119 checkpoint, and infer once;
6. validate label, probability range, positive node count, and edge count.

The Smoke Test passes only if both archive verification and live inference pass.
It deliberately writes no persistent experiment Run.
There is no separate Python archive-check command: missing files, wrong byte
counts, checksum mismatches, missing inference inputs, and inference failures
are printed directly in the same terminal before the test exits with code 1.

Direct container equivalent:

```powershell
docker compose -f scripts/docker/compose.yaml run --rm --entrypoint python almond tests/run_smoke_test.py
```

`run_smoke_test.py` is an integration runner rather than a `test_*.py` unit-test
module, so `unittest discover` does not count it among the 66 tests. Its normal
terminal result contains the following lines (the prediction values depend on
the bundled sample and checkpoint):

```text
Verifying runtime archive: <project-root>/baselines/deepwukong/module_tranning/deepwukong-rtx5060-cu128-experimental.tar
Archive size is correct (4,766,494,208 bytes); calculating SHA-256...
Archive SHA-256 is correct (0482EA09F89569072427344B1DADA5E72878DF2E7BC99F878F5895B17DAF6B1D).
Runtime archive verification passed.

Smoke Test sample: <sample-id>
Running one baseline inference (Joern -> PDG/XFG -> DeepWuKong)...
Smoke Test passed.
Predicted label: <label>
Vulnerability probability: <value-from-0.000000-to-1.000000>
Graph size: <positive-node-count> nodes, <positive-edge-count> edges
```

The normal exit code is `0`. A missing, truncated, or altered TAR prints an
`[ERROR] Run Smoke Test stopped: runtime archive verification failed.` message,
identifies the missing path, wrong byte count, or SHA-256 mismatch, and exits
with code `1` before inference. Missing inference inputs or an invalid
prediction likewise print an `[ERROR]` reason and exit with code `1`.

### 8. Full end-to-end test

From the console, select `1. Run Full Test`. This is the slow GPU-backed system
test and should be performed once in the final target environment.

Confirm that:

- every baseline completes or records an explicit failure reason;
- generated variants preserve dataset/sample provenance;
- graph experiments retain action, budget, seed, target mode, and target rank;
- `summary.json`, metrics CSV, prediction CSV, and dashboards are generated;
- the browser menus open the experiment index, PDG Atlas, and graph comparison;
- closing the one-off container leaves the new Run under host `outputs/`.

Do not replace the retained final evidence Run unless the new full Run completes
successfully and has been independently checked.

### 9. Happy, sad, and external-dependency cases

The automated suite covers valid data as well as missing fields, invalid
probabilities, unscoreable XFGs, absent key lines, fallback anchors, unsafe Run
paths, partial reruns, mismatched comparison cohorts, and rendering limits.

Before submission, also exercise these operational failures:

| Failure injected | Expected behaviour |
|---|---|
| Rename the TAR temporarily | Smoke Test fails before inference and reports the required path |
| Verify a separate truncated TAR copy | Verifier reports byte-count mismatch and does not hash/load it |
| Alter a same-size test copy | Verifier reports SHA-256 mismatch and warns not to load it |
| Stop Docker Desktop | Launcher/build reports Docker failure rather than claiming success |
| Hide GPU access | GPU check prints `False`; full inference is not accepted |
| Remove a required result file from a copied Run | Completeness check identifies the exact missing entry |
| Run host rendering without Graphviz | README explains the dependency; container suite remains authoritative |

Never modify the verified delivery TAR to perform negative tests. Work on a
separate temporary copy and delete that copy afterwards.

### 10. Final acceptance record

Record the date, commit hash, Docker image ID, GPU name, TAR digest, `Ran 66
tests / OK` output, Smoke Test result, and dashboard URLs. The submission is
ready only when all required-file checks, archive verification, container tests,
GPU inference, and browser inspection pass in the same final commit.

## Limitations

- The included checkpoint targets CWE-119 and is not a universal
  vulnerability detector.
- The separately distributed Docker runtime image from the documented UNSW
  OneDrive delivery folder is required for reproducible Joern and model
  inference; the archive checksum must be verified before use.
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
