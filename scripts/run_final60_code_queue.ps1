param(
    [string]$ProjectRoot = "D:\capstone-project-26t2-9900-t17a-almond"
)

$ErrorActionPreference = "Stop"
$runStamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logDir = Join-Path $ProjectRoot "outputs\run_final60_code_queue_$runStamp"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$jobs = @(
    @{ Dataset = "cwe119"; Input = "input_sources\cwe119" },
    @{ Dataset = "devign"; Input = "input_sources\devign" },
    @{ Dataset = "cvefixes"; Input = "input_sources\cvefixes" }
)
$resultRoots = @{}

foreach ($job in $jobs) {
    $dataset = $job.Dataset
    $resultDir = Join-Path $ProjectRoot "outputs\run_final60_code_$dataset`_$runStamp"
    $resultRoots[$dataset] = $resultDir
    $logFile = Join-Path $logDir "$dataset.log"
    "[$(Get-Date -Format o)] START $dataset" | Tee-Object -FilePath $logFile -Append
    Push-Location $ProjectRoot
    & python robustness_experiments\code\run_budget_search.py `
        --input $job.Input `
        --target-mode winner-xfg `
        --winner-xfg-top-k 3 `
        --target-window-radius 3 `
        --actions data_flow_alias dead_statement xfg_targeted_dead_code control_wrapper temp_variable_split `
        --counts 1 3 5 `
        --run-round 1 `
        --timeout-seconds 900 `
        --output $resultDir 2>&1 | Tee-Object -FilePath $logFile -Append
    $exitCode = $LASTEXITCODE
    Pop-Location
    "[$(Get-Date -Format o)] END $dataset exit_code=$exitCode" | Tee-Object -FilePath $logFile -Append
    if ($exitCode -ne 0) { exit $exitCode }
}

$manifestPath = Join-Path $logDir "code_run_manifest.json"
@{
    run_stamp = $runStamp
    cwe119 = $resultRoots["cwe119"]
    devign = $resultRoots["devign"]
    cvefixes = $resultRoots["cvefixes"]
} | ConvertTo-Json | Set-Content -LiteralPath $manifestPath -Encoding utf8
"[$(Get-Date -Format o)] QUEUE_COMPLETE" | Tee-Object -FilePath (Join-Path $logDir "queue.log") -Append
