param(
    [string]$PythonExe = "d:/git/Media-Player/.venv/Scripts/python.exe",
    [string]$MpvSource = "",
    [string]$MpvRuntimeArchive = "",
    [string]$ArchiveName = "KeyTune-windows.zip"
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Require-Command {
    param(
        [string]$Cmd,
        [string]$Description
    )

    if (-not (Get-Command $Cmd -ErrorAction SilentlyContinue)) {
        throw "$Description não encontrado: $Cmd. Certifique-se que está instalado e disponível no PATH."
    }
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

    # Se não foi fornecido source/archive, tentar baixar o runtime mais recente do mpv-winbuild
    try {
        Write-Step "Tentando baixar runtime do mpv-winbuild (se disponível)"
        $release = Invoke-RestMethod -Headers @{ "User-Agent" = "GitHub-Actions" } -Uri "https://api.github.com/repos/zhongfly/mpv-winbuild/releases/latest"
        $preferredAssetPattern = '^mpv-dev-x86_64-\d{8}-git-[0-9a-f]+\.7z$'
        $asset = $release.assets |
            Where-Object { $_.name -match $preferredAssetPattern } |
            Sort-Object -Property name -Descending |
            Select-Object -First 1

        if ($asset) {
            $extractRoot = Join-Path $repoRoot "build\mpv-runtime"
            New-Item -Path $extractRoot -ItemType Directory -Force | Out-Null
            $outFile = Join-Path $extractRoot "libmpv.7z"
            Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $outFile
            & 7z x $outFile "-o$extractRoot\extracted" -y | Out-Null
            $mpvDll = Get-ChildItem -Path "$extractRoot\extracted" -Filter "libmpv-2.dll" -Recurse -ErrorAction SilentlyContinue |
                Select-Object -First 1
            if ($mpvDll) {
                return $mpvDll.Directory.FullName
            }
        }
    } catch {
        Write-Host "Aviso: falha ao tentar baixar runtime do mpv-winbuild: $_" -ForegroundColor Yellow
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

# Verifica se 7z está disponível (utilizado para extrair runtimes .7z)
Require-Command -Cmd "7z" -Description "7-Zip (7z)"

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

$MpvSource = Resolve-MpvSource -PreferredPath $MpvSource -PreferredArchive $MpvRuntimeArchive

Write-Step "Gerando executável principal"
& $PythonExe -m PyInstaller --noconfirm --windowed --name KeyTune --collect-submodules accessible_output2 --collect-data accessible_output2 --collect-data ytmusicapi --collect-submodules winrt --collect-submodules winrt.windows.media --collect-submodules winrt.windows.media.playback --collect-submodules winrt.windows.foundation src/main.py
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

Write-Step "Copiando runtime do MPV"
$targetRoot = "dist\KeyTune\mpv"
New-Item -Path $targetRoot -ItemType Directory -Force | Out-Null
Copy-Item -Path "$MpvSource\*" -Destination $targetRoot -Recurse -Force

$licenseDir = "dist\KeyTune\THIRD_PARTY_LICENSES"
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
Compress-Archive -Path "dist\KeyTune\*" -DestinationPath $ArchiveName

Write-Step "Gerando checksum"
$hash = (Get-FileHash -Path $ArchiveName -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -Path "$ArchiveName.sha256" -Value "$hash  $ArchiveName" -Encoding ascii

Write-Step "Release local gerada com sucesso"
Write-Host "Arquivo: $ArchiveName"
Write-Host "Checksum: $ArchiveName.sha256"
