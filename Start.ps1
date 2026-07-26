# Main launch workflow. Start.exe invokes this script when launched by double-click.
param(
    [switch]$NoBuild
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSCommandPath
$ComposeFile = Join-Path $ProjectRoot "scripts\docker\compose.yaml"
$BridgePort = 8765
$BridgeUrl = "http://host.docker.internal:$BridgePort/open"
$BridgeProcess = $null
$PreviousBridgeUrl = $env:ALMOND_BROWSER_BRIDGE_URL
$ExitCode = 1

function Get-TerminalWidth {
    try {
        return [Math]::Max(50, [Console]::WindowWidth)
    } catch {
        return 80
    }
}

function Get-TerminalHeight {
    try {
        return [Math]::Max(30, [Console]::WindowHeight)
    } catch {
        return 30
    }
}

function Initialize-LoadingDisplay {
    $script:LoadingHeaderHeight = 6
    $height = Get-TerminalHeight
    $scrollStart = $script:LoadingHeaderHeight + 1
    $escape = [char]27

    Clear-Host
    [Console]::Write("${escape}[${scrollStart};${height}r")
    [Console]::Write("${escape}[?25l")
    [Console]::Write("${escape}[${scrollStart};1H")
    $script:LoadingDisplayActive = $true
}

function Complete-LoadingDisplay {
    if (-not $script:LoadingDisplayActive) {
        return
    }

    $escape = [char]27
    [Console]::Write("${escape}[r${escape}[?25h")
    $script:LoadingDisplayActive = $false
}

function Show-LoadingRabbit {
    param([int]$Frame)

    $width = Get-TerminalWidth
    $margin = 2
    $trackWidth = [Math]::Max(46, $width - ($margin * 2))
    $faces = @(
        "( ='.'= )",
        "( =-.-= )",
        "( =^.^= )",
        "( =^.^= )",
        "( =o.o= )",
        "( ='.'= )",
        "( =o.o= )",
        "( ='.'= )"
    )
    $pose = $Frame % $faces.Count
    $rabbit = @(
        '  (\_/)',
        $faces[$pose],
        ' ( > < )',
        '(")___(")'
    )
    $rabbitWidth = [int](($rabbit | Measure-Object -Property Length -Maximum).Maximum)
    $travelDistance = [Math]::Max(1, $trackWidth - $rabbitWidth)
    $travelCycle = $travelDistance * 2
    $cyclePosition = $Frame % $travelCycle
    $runningRight = $cyclePosition -le $travelDistance
    $rabbitPosition = if ($runningRight) {
        $cyclePosition
    } else {
        $travelCycle - $cyclePosition
    }
    $track = -join ("=" * $trackWidth)
    # Land with the feet directly above the track; lift one row while hopping.
    $topRow = @(2, 2, 1, 1, 1, 2, 2, 2)[$pose]
    $trackRow = $script:LoadingHeaderHeight
    $escape = [char]27

    [Console]::Write("${escape}[s")
    for ($row = 1; $row -le $script:LoadingHeaderHeight; $row++) {
        [Console]::Write("${escape}[${row};1H${escape}[2K")
    }
    for ($index = 0; $index -lt $rabbit.Count; $index++) {
        $rabbitLine = $rabbit[$index]
        $column = $margin + $rabbitPosition + 1
        $row = $topRow + $index
        [Console]::Write("${escape}[${row};${column}H$rabbitLine")
    }
    [Console]::Write("${escape}[${trackRow};$($margin + 1)H$track")
    [Console]::Write("${escape}[u")
}

function Wait-ForBackgroundBuild {
    param([System.Diagnostics.Process]$Process)

    $frame = 0
    $animationClock = [System.Diagnostics.Stopwatch]::StartNew()
    $outputClosed = $false
    $errorClosed = $false
    $outputTask = $Process.StandardOutput.ReadLineAsync()
    $errorTask = $Process.StandardError.ReadLineAsync()
    while (-not ($Process.HasExited -and $outputClosed -and $errorClosed)) {
        if ($animationClock.ElapsedMilliseconds -ge 220) {
            $frame++
            Show-LoadingRabbit -Frame $frame
            $animationClock.Restart()
        }
        while (-not $outputClosed -and $outputTask.IsCompleted) {
            $line = $outputTask.GetAwaiter().GetResult()
            if ($null -eq $line) {
                $outputClosed = $true
            } else {
                [Console]::WriteLine($line)
                $outputTask = $Process.StandardOutput.ReadLineAsync()
            }
        }
        while (-not $errorClosed -and $errorTask.IsCompleted) {
            $line = $errorTask.GetAwaiter().GetResult()
            if ($null -eq $line) {
                $errorClosed = $true
            } else {
                [Console]::WriteLine($line)
                $errorTask = $Process.StandardError.ReadLineAsync()
            }
        }
        Start-Sleep -Milliseconds 80
        $Process.Refresh()
    }
    $Process.WaitForExit()
    Complete-LoadingDisplay

    if ($Process.ExitCode -eq 0) {
        return $true
    }

    Write-Host "Docker image build failed (exit code $($Process.ExitCode))." -ForegroundColor Red
    return $false
}

Push-Location -LiteralPath $ProjectRoot
try {
    Initialize-LoadingDisplay
    Show-LoadingRabbit -Frame 0
    $BridgeProcess = Start-Process -FilePath "python" `
        -ArgumentList "scripts/host_browser_bridge.py --port $BridgePort" `
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
        Show-LoadingRabbit -Frame $attempt
        if ($attempt -eq 19) { throw "The host browser bridge did not start." }
    }

    $env:ALMOND_BROWSER_BRIDGE_URL = $BridgeUrl
    $buildSucceeded = $true
    if (-not $NoBuild) {
        $buildArguments = "compose -f `"$ComposeFile`" build almond"
        $buildStartInfo = [System.Diagnostics.ProcessStartInfo]::new()
        $buildStartInfo.FileName = "docker"
        $buildStartInfo.Arguments = $buildArguments
        $buildStartInfo.WorkingDirectory = $ProjectRoot
        $buildStartInfo.UseShellExecute = $false
        $buildStartInfo.CreateNoWindow = $true
        $buildStartInfo.RedirectStandardOutput = $true
        $buildStartInfo.RedirectStandardError = $true
        $buildProcess = [System.Diagnostics.Process]::new()
        $buildProcess.StartInfo = $buildStartInfo
        [void]$buildProcess.Start()
        $buildSucceeded = Wait-ForBackgroundBuild -Process $buildProcess
        if (-not $buildSucceeded) {
            $ExitCode = $buildProcess.ExitCode
            pause "Press Enter to close this failed build..."
        }
    }

    if ($buildSucceeded) {
        Complete-LoadingDisplay
        Clear-Host
        $ComposeArgs = @("compose", "-f", $ComposeFile, "run", "--rm", "--service-ports", "almond")
        & docker @ComposeArgs
        $ExitCode = $LASTEXITCODE
    }
} finally {
    Complete-LoadingDisplay
    $env:ALMOND_BROWSER_BRIDGE_URL = $PreviousBridgeUrl
    if ($BridgeProcess -and -not $BridgeProcess.HasExited) {
        Stop-Process -Id $BridgeProcess.Id -Force
    }
    Pop-Location
}

exit $ExitCode
