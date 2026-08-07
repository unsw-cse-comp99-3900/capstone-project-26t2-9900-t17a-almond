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
  ".\scripts\verify_runtime_archive.py",
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
  ".\tests\run_quick_test.py"
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

Verify the complete TAR with the same Python logic used by console Smoke Test:

```powershell
python .\scripts\verify_runtime_archive.py
```

Expected final line:

```text
Runtime archive verification passed: the download is complete.
```

Load and inspect the verified base image:

```powershell
$RuntimeArchive = ".\baselines\deepwukong\module_tranning\deepwukong-rtx5060-cu128-experimental.tar"
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
| `test_quick_test.py` | 2 | valid inference output and invalid/missing output fields |
| `test_random_graph_rerun.py` | 2 | safe Run selection and non-destructive summary updates |
| `test_showcase_rendering.py` | 20 | source/PDG rendering, focus evidence, cache and staged provenance |
| `test_visualize_results.py` | 15 | paired cohorts, ASR/statistics, budgets, dashboards and indexes |
| `test_xfg_targeted_experiment.py` | 3 | metadata and effective Winner-XFG node selection |

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
| Runtime delivery | `scripts/verify_runtime_archive.py` | Corrupt/copy-truncate a separate test file and confirm rejection | Exact size and SHA accepted; altered files rejected |
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

Direct container equivalent:

```powershell
docker compose -f scripts/docker/compose.yaml run --rm --entrypoint python almond tests/run_quick_test.py
```

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
