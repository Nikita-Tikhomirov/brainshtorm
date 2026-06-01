$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Port = 8501
$Url = "http://localhost:$Port"
$LogDir = Join-Path $RepoRoot "out\logs"
$StdoutPath = Join-Path $LogDir "streamlit.out.log"
$StderrPath = Join-Path $LogDir "streamlit.err.log"

function Test-LocalPort {
    param([int]$Port)

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $task = $client.ConnectAsync("127.0.0.1", $Port)
        if (-not $task.Wait(300)) {
            return $false
        }
        return $client.Connected
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

function Wait-LocalPort {
    param(
        [int]$Port,
        [int]$TimeoutSeconds
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if (Test-LocalPort -Port $Port) {
            return $true
        }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

Set-Location $RepoRoot
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

if (-not (Test-LocalPort -Port $Port)) {
    $arguments = @(
        "-m",
        "streamlit",
        "run",
        "src/brainshtorm/app.py",
        "--server.port",
        "$Port",
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false"
    )

    Start-Process `
        -FilePath "python" `
        -ArgumentList $arguments `
        -WorkingDirectory $RepoRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $StdoutPath `
        -RedirectStandardError $StderrPath

    if (-not (Wait-LocalPort -Port $Port -TimeoutSeconds 20)) {
        Write-Warning "Runet Niche Analyzer did not open port $Port. See $StderrPath."
    }
}

Start-Process $Url
Write-Host "Opened $Url"
