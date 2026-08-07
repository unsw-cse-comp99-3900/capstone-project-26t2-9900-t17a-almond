param(
    [string]$InputPath = ".\inputs",
    [string]$Output = ".\outputs",
    [string]$Config = ".\configs\runtime_config.json",
    [string]$Pattern = "*.c",
    [switch]$NoTimestampOutput
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$ArgsList = @(
    (Join-Path $PSScriptRoot "run_pipeline.py"),
    "--input", $InputPath,
    "--output", $Output,
    "--config", $Config,
    "--pattern", $Pattern
)
if ($NoTimestampOutput) {
    $ArgsList += "--no-timestamp-output"
}
python @ArgsList
