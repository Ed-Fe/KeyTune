param(
    [string]$PythonExe = "d:/git/Media-Player/.venv/Scripts/python.exe",
    [string]$MpvSource = "",
    [string]$MpvRuntimeArchive = "",
    [string]$ArchiveName = "MediaPlayer-windows.zip"
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

function Resolve-MpvSource {
    param(
        [string]$PreferredPath,
        [string]$PreferredArchive
    )

    if ($PreferredPath -and (Test-Path $PreferredPath)) {
        return (Resolve-Path $PreferredPath).Path
    }

    if ($PreferredArchive -and (Test-Path $PreferredArchive)) {
        $extractRoot = Join-Path $repoRoot "build\mpv-runtime"
        Remove-Item -Path $extractRoot -Recurse -Force -ErrorAction SilentlyContinue
        New-Item -Path $extractRoot -ItemType Directory -Force | Out-Null
        & 7z x $PreferredArchive "-o$extractRoot" -y | Out-Null
        $mpvDll = Get-ChildItem -Path $extractRoot -Filter "libmpv-2.dll" -Recurse -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($mpvDll) {
            return $mpvDll.Directory.FullName
        }
    }

    $mpvDll = Get-ChildItem -Path "C:\ProgramData\chocolatey\lib" -Filter "libmpv-2.dll" -Recurse -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($mpvDll) {
        return $mpvDll.Directory.FullName
    }

    throw "Runtime do MPV não encontrado. Informe -MpvSource apontando para uma pasta com libmpv-2.dll ou -MpvRuntimeArchive com um arquivo mpv-dev-*.7z."
}

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Step "Validando pré-requisitos"
Require-Path -Path $PythonExe -Description "Python do ambiente virtual"

& $PythonExe -m PyInstaller --version | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller não está disponível no ambiente virtual atual."
}

Write-Step "Limpando artefatos anteriores"
Remove-Item -Path "build" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "dist" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path $ArchiveName -Force -ErrorAction SilentlyContinue
Remove-Item -Path "$ArchiveName.sha256" -Force -ErrorAction SilentlyContinue

$MpvSource = Resolve-MpvSource -PreferredPath $MpvSource -PreferredArchive $MpvRuntimeArchive

Write-Step "Gerando executável principal"
& $PythonExe -m PyInstaller --noconfirm --windowed --name MediaPlayer --collect-submodules accessible_output2 --collect-data accessible_output2 --collect-data ytmusicapi --collect-submodules winrt --collect-submodules winrt.windows.media --collect-submodules winrt.windows.media.playback --collect-submodules winrt.windows.foundation src/main.py
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao gerar o executável principal."
}

Write-Step "Gerando atualizador externo"
& $PythonExe -m PyInstaller --noconfirm --onefile --windowed --name MediaPlayerUpdater src/updater_main.py
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao gerar o atualizador externo."
}

Write-Step "Copiando atualizador para a pasta da release"
Copy-Item -Path "dist\MediaPlayerUpdater.exe" -Destination "dist\MediaPlayer\MediaPlayerUpdater.exe" -Force

Write-Step "Copiando runtime do MPV"
$targetRoot = "dist\MediaPlayer\mpv"
New-Item -Path $targetRoot -ItemType Directory -Force | Out-Null
Copy-Item -Path "$MpvSource\*" -Destination $targetRoot -Recurse -Force

$licenseDir = "dist\MediaPlayer\THIRD_PARTY_LICENSES"
New-Item -Path $licenseDir -ItemType Directory -Force | Out-Null
$possibleLicenseFiles = @(
    "$MpvSource\LICENSE.txt",
    "$MpvSource\COPYING.txt",
    "$MpvSource\COPYING"
)

foreach ($file in $possibleLicenseFiles) {
    if (Test-Path $file) {
        Copy-Item -Path $file -Destination $licenseDir -Force
    }
}

Write-Step "Empacotando release"
Compress-Archive -Path "dist\MediaPlayer\*" -DestinationPath $ArchiveName

Write-Step "Gerando checksum"
$hash = (Get-FileHash -Path $ArchiveName -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -Path "$ArchiveName.sha256" -Value "$hash  $ArchiveName" -Encoding ascii

Write-Step "Release local gerada com sucesso"
Write-Host "Arquivo: $ArchiveName"
Write-Host "Checksum: $ArchiveName.sha256"
