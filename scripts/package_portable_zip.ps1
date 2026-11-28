param(
    [Parameter(Mandatory = $true)][string]$SourceDir,
    [Parameter(Mandatory = $true)][string]$DestinationZip,
    # Fica na raiz do zip, sem entrar na pasta que o instalador empacota.
    [string]$ExtraFile = ""
)

$ErrorActionPreference = "Stop"

function Find-SevenZip {
    $command = Get-Command 7z -ErrorAction SilentlyContinue
    if ($command -and $command.Source -and (Test-Path -LiteralPath $command.Source)) {
        return $command.Source
    }
    foreach ($candidate in @(
        (Join-Path $env:ProgramFiles "7-Zip\7z.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "7-Zip\7z.exe")
    )) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return $candidate
        }
    }
    return $null
}

if (-not (Test-Path -LiteralPath $SourceDir)) {
    throw "Pasta do aplicativo não encontrada: $SourceDir"
}

$source = (Resolve-Path -LiteralPath $SourceDir).Path
$destination = [System.IO.Path]::GetFullPath($DestinationZip)
$destinationParent = Split-Path -Parent $destination
if (-not (Test-Path -LiteralPath $destinationParent)) {
    New-Item -ItemType Directory -Path $destinationParent | Out-Null
}
if (Test-Path -LiteralPath $destination) {
    Remove-Item -LiteralPath $destination -Force
}
$checksumPath = "$destination.sha256"
if (Test-Path -LiteralPath $checksumPath) {
    Remove-Item -LiteralPath $checksumPath -Force
}

$markerDir = Join-Path ([System.IO.Path]::GetTempPath()) ("keytune-portable-marker-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $markerDir | Out-Null
$markerFile = Join-Path $markerDir "portable.ini"
New-Item -ItemType File -Path $markerFile | Out-Null

try {
    $sevenZip = Find-SevenZip
    if ($sevenZip) {
        Push-Location -LiteralPath $source
        try {
            # -x!data evita levar uma pasta data de teste que esteja ao lado do exe.
            & $sevenZip a -tzip -mx=5 -y "-x!data" $destination "*"
            if ($LASTEXITCODE -ne 0) {
                throw "7z falhou ao criar o zip portátil (código $LASTEXITCODE)."
            }
        } finally {
            Pop-Location
        }
        if (-not (Test-Path -LiteralPath (Join-Path $source "portable.ini"))) {
            Push-Location -LiteralPath $markerDir
            try {
                & $sevenZip a -tzip -y $destination "portable.ini"
                if ($LASTEXITCODE -ne 0) {
                    throw "7z falhou ao incluir o portable.ini (código $LASTEXITCODE)."
                }
            } finally {
                Pop-Location
            }
        }
    } else {
        $paths = @(
            Get-ChildItem -LiteralPath $source -Force |
                Where-Object { $_.Name -ne "data" } |
                ForEach-Object { $_.FullName }
        )
        $hasMarker = $false
        foreach ($path in $paths) {
            if ((Split-Path -Leaf $path) -eq "portable.ini") {
                $hasMarker = $true
            }
        }
        if (-not $hasMarker) {
            $paths += $markerFile
        }
        if ($paths.Count -eq 0) {
            throw "A pasta do aplicativo está vazia: $source"
        }
        Compress-Archive -Path $paths -DestinationPath $destination -CompressionLevel Optimal
    }
} finally {
    Remove-Item -LiteralPath $markerDir -Recurse -Force -ErrorAction SilentlyContinue
}

if (-not (Test-Path -LiteralPath $destination)) {
    throw "O zip portátil não foi gerado: $destination"
}

if ($ExtraFile) {
    if (-not (Test-Path -LiteralPath $ExtraFile)) {
        throw "Arquivo extra do zip portátil não encontrado: $ExtraFile"
    }
    $extraFull = (Resolve-Path -LiteralPath $ExtraFile).Path
    $extraLeaf = Split-Path -Leaf $extraFull
    $extraDir = Split-Path -Parent $extraFull
    $sevenZipForExtra = Find-SevenZip
    if ($sevenZipForExtra) {
        Push-Location -LiteralPath $extraDir
        try {
            & $sevenZipForExtra a -tzip -y $destination $extraLeaf
            if ($LASTEXITCODE -ne 0) {
                throw "7z falhou ao incluir $extraLeaf no zip portátil (código $LASTEXITCODE)."
            }
        } finally {
            Pop-Location
        }
    } else {
        Push-Location -LiteralPath $extraDir
        try {
            Compress-Archive -Path $extraLeaf -DestinationPath $destination -Update
        } finally {
            Pop-Location
        }
    }
}

$hash = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
$leaf = Split-Path -Leaf $destination
Set-Content -LiteralPath $checksumPath -Value "$hash  $leaf" -Encoding ascii
Write-Host "Portátil: $destination"
Write-Host "Checksum: $checksumPath"
