param(
    [string]$PythonExe = "d:/git/Media-Player/.venv/Scripts/python.exe",
    [string]$MpvSource = "",
    [string]$MpvRuntimeArchive = "",
    [ValidateSet("stable", "nightly")]
    [string]$YtDlpChannel = "stable",
    [string]$AppVersion = "1.0.0"
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

Write-Step "Gerando créditos de bibliotecas e contribuidores"
& $PythonExe scripts\generate_credits.py
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao gerar docs\credits.md."
}

Write-Step "Renderizando créditos em HTML"
& $PythonExe scripts\render_manual.py docs\credits.md dist\KeyTune\docs\credits.html
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao renderizar os créditos em HTML."
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

Write-Step "Compilando instalador (Inno Setup)"
$isccCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    Write-Host "ISCC.exe não encontrado — instalador não foi gerado. Instale com: choco install innosetup" -ForegroundColor Yellow
    Write-Step "Release local gerada (sem instalador)"
} else {
    & $iscc "/DAppVersion=$AppVersion" "installer\keytune.iss"
    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao compilar o instalador."
    }
    $setupPath = "dist\KeyTune-Setup.exe"
    $setupHash = (Get-FileHash -Path $setupPath -Algorithm SHA256).Hash.ToLowerInvariant()
    Set-Content -Path "$setupPath.sha256" -Value "$setupHash  KeyTune-Setup.exe" -Encoding ascii
    Write-Step "Release local gerada com sucesso"
    Write-Host "Instalador: $setupPath"
    Write-Host "Checksum: $setupPath.sha256"
}
