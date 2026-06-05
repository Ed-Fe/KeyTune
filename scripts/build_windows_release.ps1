param(
    [string]$PythonExe = "d:/git/Media-Player/.venv/Scripts/python.exe",
    [string]$MpvSource = "",
    [string]$MpvRuntimeArchive = "",
    [string]$ArchiveName = "KeyTune-windows.zip",
    [ValidateSet("stable", "nightly")]
    [string]$YtDlpChannel = "stable"
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Require-Path {
    param(
        [string]$Path,
        [string]$Description
    )

    if (-not (Test-Path $Path)) {
        throw "$Description não encontrado em: $Path"
    }
}

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Step "Validando pré-requisitos"
Require-Path -Path $PythonExe -Description "Python do ambiente virtual"

Write-Step "Instalando dependências no venv"
& $PythonExe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao atualizar pip no venv."
}
& $PythonExe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao instalar dependências do requirements.txt."
}
& $PythonExe -m pip install pyinstaller
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao instalar PyInstaller no venv."
}

& $PythonExe -m PyInstaller --version | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller não está disponível no ambiente virtual atual.";
}

Write-Step "Limpando artefatos anteriores"
Remove-Item -Path "build" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "dist" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path $ArchiveName -Force -ErrorAction SilentlyContinue
Remove-Item -Path "$ArchiveName.sha256" -Force -ErrorAction SilentlyContinue

Write-Step "Baixando runtime do MPV"
$mpvScriptArgs = @("scripts\download_mpv_runtime.py", "--output-dir", "build\mpv-runtime")
if ($MpvSource) {
    $mpvScriptArgs += @("--source-path", $MpvSource)
}
if ($MpvRuntimeArchive) {
    $mpvScriptArgs += @("--source-archive", $MpvRuntimeArchive)
}
& $PythonExe @mpvScriptArgs
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao baixar ou extrair o runtime do MPV."
}

Write-Step "Gerando executável principal"
& $PythonExe -m PyInstaller --noconfirm --windowed --name KeyTune --hidden-import mpv --collect-all mpv --collect-submodules accessible_output2 --collect-data accessible_output2 --collect-data ytmusicapi --collect-submodules winrt --collect-submodules winrt.windows.media --collect-submodules winrt.windows.media.playback --collect-submodules winrt.windows.foundation src/main.py
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao gerar o executável principal."
}

Write-Step "Gerando atualizador externo"
& $PythonExe -m PyInstaller --noconfirm --onefile --windowed --name KeyTuneUpdater src/updater_main.py
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao gerar o atualizador externo."
}

Write-Step "Copiando atualizador para a pasta da release"
Copy-Item -Path "dist\KeyTuneUpdater.exe" -Destination "dist\KeyTune\KeyTuneUpdater.exe" -Force

Write-Step "Baixando yt-dlp oficial ($YtDlpChannel)"
& $PythonExe scripts\download_yt_dlp_release.py --channel $YtDlpChannel --output-dir "dist\KeyTune"
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao baixar o yt-dlp oficial."
}

Write-Step "Renderizando manual em HTML"
& $PythonExe scripts\render_manual.py docs\manual.md dist\KeyTune\docs\manual.html
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao renderizar o manual em HTML."
}

Write-Step "Copiando runtime do MPV"
$MpvRuntimeDir = "build\mpv-runtime"
$targetRoot = "dist\KeyTune\mpv"
New-Item -Path $targetRoot -ItemType Directory -Force | Out-Null
Copy-Item -Path "$MpvRuntimeDir\*" -Destination $targetRoot -Recurse -Force

$licenseDir = "dist\KeyTune\THIRD_PARTY_LICENSES"
New-Item -Path $licenseDir -ItemType Directory -Force | Out-Null
$possibleLicenseFiles = @(
    "$MpvRuntimeDir\LICENSE.txt",
    "$MpvRuntimeDir\COPYING.txt",
    "$MpvRuntimeDir\COPYING"
)

foreach ($file in $possibleLicenseFiles) {
    if (Test-Path $file) {
        Copy-Item -Path $file -Destination $licenseDir -Force
    }
}

Write-Step "Empacotando release"
Compress-Archive -Path "dist\KeyTune\*" -DestinationPath $ArchiveName

Write-Step "Gerando checksum"
$hash = (Get-FileHash -Path $ArchiveName -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -Path "$ArchiveName.sha256" -Value "$hash  $ArchiveName" -Encoding ascii

Write-Step "Release local gerada com sucesso"
Write-Host "Arquivo: $ArchiveName"
Write-Host "Checksum: $ArchiveName.sha256"
