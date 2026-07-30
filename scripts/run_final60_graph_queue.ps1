param(
    [Parameter(Mandatory = $true)][string]$InputRoot,
    [string]$ProjectRoot = "D:\capstone-project-26t2-9900-t17a-almond"
)

$ErrorActionPreference = "Continue"
$runStamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logDir = Join-Path $ProjectRoot "outputs\run_final60_graph_queue_$runStamp"
$primitiveOutput = Join-Path $ProjectRoot "outputs\run_final60_graph_primitive_random_$runStamp"
$targetedOutput = Join-Path $ProjectRoot "outputs\run_final60_graph_targeted_$runStamp"
$image = "deepwukong-rtx5060-cu128:experimental"
$baseline = Join-Path $ProjectRoot "baselines\deepwukong"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

function Invoke-GraphContainer {
    param([string]$Name, [string[]]$ContainerArgs)
    $logFile = Join-Path $logDir "$Name.log"
    "[$(Get-Date -Format o)] START $Name" | Tee-Object -FilePath $logFile -Append
    & docker run --rm --gpus all --entrypoint python `
        -v "${ProjectRoot}:/repo" `
        -v "${baseline}:/baseline:ro" `
        $image @ContainerArgs 2>&1 | Tee-Object -FilePath $logFile -Append | Write-Host
    $exitCode = $LASTEXITCODE
    "[$(Get-Date -Format o)] END $Name exit_code=$exitCode" | Tee-Object -FilePath $logFile -Append
    return [int]$exitCode
}

$inputLeaf = Split-Path $InputRoot -Leaf
$primitiveCode = Invoke-GraphContainer -Name "primitive_random" -ContainerArgs @(
    "/repo/robustness_experiments/graph/run_random_graph_experiment.py",
    "--source-root", "/repo/artifacts/$inputLeaf/sources",
    "--csv-root", "/repo/artifacts/$inputLeaf/csv",
    "--metadata", "/repo/artifacts/$inputLeaf/metadata.csv",
    "--checkpoint", "/baseline/models/deepwukong/deepwukong_cwe119_best.ckpt",
    "--output-dir", "/repo/outputs/$(Split-Path $primitiveOutput -Leaf)",
    "--experiment", "final60_graph_primitive_random",
    "--dataset", "cwe119_devign_cvefixes_final60",
    "--strategy", "random",
    "--budgets", "1", "3", "5",
    "--seeds", "7", "17", "29", "42", "61", "73", "89", "101", "137", "2026"
)
if ($primitiveCode -ne 0) { exit $primitiveCode }

$targetedCode = Invoke-GraphContainer -Name "winner_xfg_targeted" -ContainerArgs @(
    "/repo/robustness_experiments/graph/run_xfg_targeted_experiment.py",
    "--source-root", "/repo/artifacts/$inputLeaf/sources",
    "--csv-root", "/repo/artifacts/$inputLeaf/csv",
    "--metadata", "/repo/artifacts/$inputLeaf/metadata.csv",
    "--checkpoint", "/baseline/models/deepwukong/deepwukong_cwe119_best.ckpt",
    "--output-dir", "/repo/outputs/$(Split-Path $targetedOutput -Leaf)",
    "--actions", "winner_xfg_edge_attack", "winner_xfg_feature_mask", "targeted_subgraph_injection",
    "--budgets", "1", "3", "5",
    "--seeds", "7", "17", "29", "42", "61", "73", "89", "101", "137", "2026"
)
if ($targetedCode -ne 0) { exit $targetedCode }
"[$(Get-Date -Format o)] QUEUE_COMPLETE" | Tee-Object -FilePath (Join-Path $logDir "queue.log") -Append
