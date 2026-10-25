param(
    [string]$PythonPath = "python",
    [switch]$SkipInstall,
    [string]$Version = "1.0.0"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$releaseRoot = Join-Path $repoRoot "release"
$stageName = "KomariDesktop-v$Version-win10-x64"
$stage = Join-Path $releaseRoot $stageName
$pyinstallerDist = Join-Path $releaseRoot "_pyinstaller"

if (-not $SkipInstall) {
    & $PythonPath -m pip install --upgrade pip
    & $PythonPath -m pip install -r (Join-Path $repoRoot "requirements-dev.txt")
}

if (Test-Path -LiteralPath $releaseRoot) {
    Remove-Item -LiteralPath $releaseRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $releaseRoot | Out-Null

& $PythonPath -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --windowed `
    --name KomariDesktop `
    --distpath $pyinstallerDist `
    --workpath (Join-Path $repoRoot ".build") `
    --specpath (Join-Path $repoRoot ".build") `
    (Join-Path $repoRoot "main.py")

New-Item -ItemType Directory -Force -Path $stage | Out-Null
Copy-Item -Path (Join-Path $pyinstallerDist "KomariDesktop\*") -Destination $stage -Recurse -Force
Copy-Item -LiteralPath (Join-Path $repoRoot "README.md"), (Join-Path $repoRoot "LICENSE"), (Join-Path $repoRoot "NOTICE.md"), (Join-Path $repoRoot "SECURITY.md"), (Join-Path $repoRoot "run-KomariDesktop.cmd"), (Join-Path $repoRoot "open-settings.cmd"), (Join-Path $repoRoot "run-debug.cmd") -Destination $stage -Force

$zipPath = Join-Path $releaseRoot "$stageName.zip"
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zipPath -CompressionLevel Optimal
$hash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
"$hash  $([IO.Path]::GetFileName($zipPath))" | Set-Content -LiteralPath (Join-Path $releaseRoot "SHA256SUMS.txt") -Encoding ascii

Remove-Item -LiteralPath $pyinstallerDist -Recurse -Force
Write-Host "BUILD_OK $stage"
Write-Host "ZIP_OK $zipPath"
Write-Host "SHA256 $hash"

