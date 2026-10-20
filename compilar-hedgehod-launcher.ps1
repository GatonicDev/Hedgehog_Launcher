$ErrorActionPreference = 'Stop'
$scriptPath = Join-Path $PSScriptRoot 'hedgehod_launcher.py'
$pythonCandidates = @()
if ($env:HEDGEHOD_PYTHON) { $pythonCandidates += $env:HEDGEHOD_PYTHON }
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCommand) { $pythonCandidates += $pythonCommand.Source }
$userPythonRoot = Join-Path $env:LOCALAPPDATA 'Python'
if (Test-Path -LiteralPath $userPythonRoot) {
    $pythonCandidates += Get-ChildItem -LiteralPath $userPythonRoot -Directory -Filter 'pythoncore-*' |
        ForEach-Object { Join-Path $_.FullName 'python.exe' }
}
$installedPythonRoot = Join-Path (Join-Path $env:USERPROFILE 'AppData\Local') 'Python'
if (Test-Path -LiteralPath $installedPythonRoot) {
    $pythonCandidates += Get-ChildItem -LiteralPath $installedPythonRoot -Directory -Filter 'pythoncore-*' |
        ForEach-Object { Join-Path $_.FullName 'python.exe' }
}
$python = $null
foreach ($candidate in $pythonCandidates) {
    if (Test-Path -LiteralPath $candidate) {
        try {
            & $candidate -c 'import sys'
            if ($LASTEXITCODE -eq 0) { $python = $candidate; break }
        } catch {
            continue
        }
    }
}
if (-not $python) { throw 'No encontré python.exe. Define HEDGEHOD_PYTHON con la ruta del intérprete.' }
$buildRoot = Join-Path $PSScriptRoot '..\work\pyinstaller-build'
$buildRoot = [IO.Path]::GetFullPath($buildRoot)
$workPath = Join-Path $buildRoot 'work'
$specPath = Join-Path $buildRoot 'spec'
New-Item -ItemType Directory -Path $workPath, $specPath -Force | Out-Null

& $python -c 'import PyInstaller'
if ($LASTEXITCODE -ne 0) {
    Write-Host 'PyInstaller no está instalado en este Python.' -ForegroundColor Yellow
    Write-Host 'Instala PyInstaller en un intérprete con pip, o define HEDGEHOD_PYTHON con esa ruta.'
    Write-Host 'Comando: python -m pip install pyinstaller'
    exit 1
}

& $python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name HedgehodLauncher `
    --distpath $PSScriptRoot `
    --workpath $workPath `
    --specpath $specPath `
    $scriptPath
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Listo: $(Join-Path $PSScriptRoot 'HedgehodLauncher.exe')" -ForegroundColor Green
Write-Host 'Game Data y las imágenes permanecen como archivos externos junto al ejecutable.'
