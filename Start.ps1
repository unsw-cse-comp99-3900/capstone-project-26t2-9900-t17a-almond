param(
    [switch]$NoBuild
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSCommandPath
$BridgePort = 8765
$BridgeUrl = "http://host.docker.internal:$BridgePort/open"
$BridgeProcess = $null
$PreviousBridgeUrl = $env:ALMOND_BROWSER_BRIDGE_URL
$ExitCode = 1

Push-Location -LiteralPath $ProjectRoot
try {
    $BridgeProcess = Start-Process -FilePath "python" `
        -ArgumentList "scripts/host_browser_bridge.py", "--port", $BridgePort `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Hidden `
        -PassThru

    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        try {
            $health = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$BridgePort/health" -TimeoutSec 1
            if ($health.StatusCode -eq 200) { break }
        } catch {
            Start-Sleep -Milliseconds 150
        }
        if ($attempt -eq 19) { throw "The host browser bridge did not start." }
    }

    $env:ALMOND_BROWSER_BRIDGE_URL = $BridgeUrl
    $ComposeArgs = @("compose", "run", "--rm", "--service-ports")
    if (-not $NoBuild) { $ComposeArgs += "--build" }
    $ComposeArgs += "almond"
    & docker @ComposeArgs
    $ExitCode = $LASTEXITCODE
} finally {
    $env:ALMOND_BROWSER_BRIDGE_URL = $PreviousBridgeUrl
    if ($BridgeProcess -and -not $BridgeProcess.HasExited) {
        Stop-Process -Id $BridgeProcess.Id -Force
    }
    Pop-Location
}

exit $ExitCode
