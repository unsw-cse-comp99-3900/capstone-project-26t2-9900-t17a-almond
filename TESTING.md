# ALMOND Testing Guide

This document is the complete testing and acceptance procedure for the ALMOND
DeepWuKong robustness evaluation system. Run the commands from the extracted
repository root in PowerShell unless a step says otherwise.

## 1. Test objectives

The test process verifies:

- all submission-critical files and the final archived Run are present;
- the separately delivered Docker runtime TAR is complete and authentic;
- Docker, Graphviz, Joern, the checkpoint, and NVIDIA GPU inference work;
- code-level and graph-level perturbation modules handle happy and sad cases;
- fixed budgets, seeds, paired statistics, reruns, dashboards, and the PDG Atlas
  preserve their data contracts;
- the console and browser-facing result workflow are usable end to end.

## 2. Required environment

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

## 3. Required-file completeness check

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

## 4. Runtime archive, image, and GPU checks

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

## 5. Automated unit and integration suite

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

### 5.1 `test_code_perturbations.py` - 3 tests

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

### 5.2 `test_compare_deepwukong.py` - 1 test

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

### 5.3 `test_dashboard_menu.py` - 3 tests

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

### 5.4 `test_graph_experiment_design.py` - 4 tests

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

### 5.5 `test_graph_perturbations.py` - 13 tests

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

### 5.6 `test_smoke_test.py` - 2 tests

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

### 5.7 `test_random_graph_rerun.py` - 2 tests

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

### 5.8 `test_showcase_rendering.py` - 20 tests

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

### 5.9 `test_visualize_results.py` - 15 tests

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

### 5.10 `test_xfg_targeted_experiment.py` - 3 tests

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

### 5.11 Complete-suite acceptance

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

## 6. Per-module verification matrix

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

## 7. Smoke Test

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

## 8. Full end-to-end test

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

## 9. Happy, sad, and external-dependency cases

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

## 10. Final acceptance record

Record the date, commit hash, Docker image ID, GPU name, TAR digest, `Ran 66
tests / OK` output, Smoke Test result, and dashboard URLs. The submission is
ready only when all required-file checks, archive verification, container tests,
GPU inference, and browser inspection pass in the same final commit.
