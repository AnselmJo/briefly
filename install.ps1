param(
    [switch]$DryRun,
    [alias("d")] [switch]$d
)

$IsDryRun = $DryRun -or $d

function Run-Command {
    param(
        [string]$Description,
        [scriptblock]$Script
    )
    if ($IsDryRun) {
        Write-Host "[DRY RUN] Would: $Description" -ForegroundColor Yellow
    } else {
        Write-Host "Running: $Description" -ForegroundColor Cyan
        & $Script
    }
}

Write-Host "=== Briefly Windows Installer ==="
if ($IsDryRun) {
    Write-Host "Running in DRY RUN mode. No changes will be made to your system." -ForegroundColor Yellow
}

# 1. Check and install system packages via winget
$packages = @()
if (!(Get-Command python -ErrorAction SilentlyContinue)) { $packages += "Python.Python.3.12" }
if (!(Get-Command ffmpeg -ErrorAction SilentlyContinue)) { $packages += "Gyan.FFmpeg" }
if (!(Get-Command ollama -ErrorAction SilentlyContinue)) { $packages += "Ollama.Ollama" }
if (!(Get-Command git -ErrorAction SilentlyContinue)) { $packages += "Git.Git" }

if ($packages.Count -gt 0) {
    Write-Host "Missing packages detected: $($packages -join ', ')"
    foreach ($pkg in $packages) {
        Run-Command "install winget package $pkg" { winget install --silent --accept-source-agreements --accept-package-agreements $pkg }
    }
    if (!$IsDryRun) {
        Write-Host "Please restart PowerShell and re-run this script to complete installation." -ForegroundColor Yellow
        exit
    }
} else {
    Write-Host "All system packages (Python, FFmpeg, Ollama, Git) are already present." -ForegroundColor Green
}

# 2. Determine project folder
if (Test-Path "src/briefly/__init__.py") {
    $projectDir = (Get-Item .).FullName
    Write-Host "Running from an existing checkout at $projectDir."
} else {
    $devDir = "$Home\Developer"
    if (!(Test-Path $devDir)) {
        Run-Command "create Developer directory" { New-Item -ItemType Directory -Path $devDir | Out-Null }
    }
    $projectDir = "$devDir\briefly"
    if (!(Test-Path $projectDir)) {
        Run-Command "clone Briefly repository" { git clone https://github.com/AnselmJo/briefly.git $projectDir }
    } else {
        Write-Host "Using existing repository checkout at $projectDir."
    }
}

# 3. Setup virtual environment
if (!(Test-Path "$projectDir\.venv")) {
    Run-Command "create virtual environment" { python -m venv "$projectDir\.venv" }
} else {
    Write-Host "Virtual environment already exists." -ForegroundColor Green
}

# 4. Set execution policy
Run-Command "set execution policy for current user" { Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force }

# 5. Install Briefly dependencies
Run-Command "install Briefly dependencies" {
    if (!$IsDryRun) {
        Set-Location $projectDir
    }
    & "$projectDir\.venv\Scripts\pip.exe" install -e .
}

# 6. Run setup assistant
Run-Command "run Briefly setup assistant" {
    & "$projectDir\.venv\Scripts\briefly.exe" install
}

Write-Host "=== Briefly Setup Completed successfully ===" -ForegroundColor Green
