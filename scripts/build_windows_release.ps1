param(
    [string]$PythonExe = "d:/git/Media-Player/.venv/Scripts/python.exe",
    [string]$MpvSource = "",
    [string]$MpvRuntimeArchive = "",
    [ValidateSet("stable", "nightly")]
    [string]$YtDlpChannel = "stable",
    [string]$AppVersion = "2.0.3"
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
& $PythonExe scripts\build_optional_resources.py --output-dir "dist\optional-resources" --app-version $AppVersion
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao gerar os pacotes de recursos opcionais."
}
$PythonStableAbiDll = & $PythonExe -c "import pathlib, sys; print(pathlib.Path(sys.base_prefix) / 'python3.dll')"
Require-Path -Path $PythonStableAbiDll -Description "DLL da ABI estável do Python"
& $PythonExe -m PyInstaller --noconfirm --windowed --name KeyTune --hidden-import mpv --hidden-import webbrowser --collect-all mpv --collect-submodules accessible_output2 --collect-data accessible_output2 --collect-submodules winrt --collect-submodules winrt.windows.media --collect-submodules winrt.windows.media.playback --collect-submodules winrt.windows.foundation --exclude-module ytmusicapi --exclude-module librosa --exclude-module numpy --exclude-module scipy --exclude-module numba --exclude-module av --add-binary "$PythonStableAbiDll;." --add-data "src\player\autodj\sounds;player\autodj\sounds" src/main.py
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao gerar o executável principal."
}

Write-Step "Validando controles de mídia do sistema no executável"
$smtcSmokeProcess = Start-Process `
    -FilePath (Resolve-Path "dist\KeyTune\KeyTune.exe") `
    -ArgumentList "--smtc-smoke-test" `
    -Wait `
    -PassThru `
    -WindowStyle Hidden
if ($smtcSmokeProcess.ExitCode -ne 0) {
    throw "O executável não conseguiu inicializar os controles de mídia do sistema."
}

Write-Step "Validando dependências opcionais do YouTube no executável"
$youtubeSmokeAppData = Join-Path (Resolve-Path "build") "youtube-resource-smoke"
$youtubeSmokeResourceDir = Join-Path $youtubeSmokeAppData "KeyTune\resources\youtube_music\youtube"
Expand-Archive -LiteralPath "dist\optional-resources\KeyTune-YouTubePython-win-x64.zip" -DestinationPath $youtubeSmokeResourceDir
$savedAppData = $env:APPDATA
try {
    $env:APPDATA = $youtubeSmokeAppData
    $youtubeSmokeProcess = Start-Process `
        -FilePath (Resolve-Path "dist\KeyTune\KeyTune.exe") `
        -ArgumentList "--youtube-dependencies-smoke-test" `
        -Wait `
        -PassThru `
        -WindowStyle Hidden
    if ($youtubeSmokeProcess.ExitCode -ne 0) {
        throw "As dependências opcionais do YouTube não puderam ser importadas."
    }
} finally {
    $env:APPDATA = $savedAppData
}

Write-Step "Baixando yt-dlp oficial ($YtDlpChannel)"
& $PythonExe scripts\download_yt_dlp_release.py --channel $YtDlpChannel --output-dir "dist\KeyTune"
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao baixar o yt-dlp oficial."
}

Write-Step "Compilando catálogos de tradução"
& $PythonExe scripts\i18n.py compile
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao compilar os catálogos de tradução."
}

Write-Step "Empacotando catálogos de tradução"
if (Test-Path "locale") {
    Copy-Item -Path "locale" -Destination "dist\KeyTune\locale" -Recurse -Force
}

Write-Step "Renderizando documentação de plugins em HTML (por idioma)"
foreach ($guide in Get-ChildItem -Path "docs" -Filter "plugins*.md") {
    & $PythonExe scripts\render_manual.py $guide.FullName ("dist\KeyTune\docs\" + $guide.BaseName + ".html")
    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao renderizar documentação de plugins: $($guide.Name)."
    }
}

Write-Step "Renderizando manual em HTML (por idioma)"
& $PythonExe scripts\render_manual.py docs\manual.md dist\KeyTune\docs\manual.html
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao renderizar o manual em HTML."
}
foreach ($manual in Get-ChildItem -Path "docs" -Filter "manual.*.md" -ErrorAction SilentlyContinue) {
    & $PythonExe scripts\render_manual.py $manual.FullName ("dist\KeyTune\docs\" + $manual.BaseName + ".html")
    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao renderizar o manual traduzido: $($manual.Name)."
    }
}

Write-Step "Gerando créditos de bibliotecas e contribuidores (por idioma)"
& $PythonExe scripts\generate_credits.py --language pt_BR --language en --language es
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao gerar os créditos."
}

Write-Step "Renderizando créditos em HTML (por idioma)"
& $PythonExe scripts\render_manual.py docs\credits.md dist\KeyTune\docs\credits.html
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao renderizar os créditos em HTML."
}
foreach ($credit in Get-ChildItem -Path "docs" -Filter "credits.*.md" -ErrorAction SilentlyContinue) {
    & $PythonExe scripts\render_manual.py $credit.FullName ("dist\KeyTune\docs\" + $credit.BaseName + ".html")
    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao renderizar os créditos traduzidos: $($credit.Name)."
    }
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
