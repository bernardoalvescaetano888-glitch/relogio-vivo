# Gera os instaladores .exe do Windows com Inno Setup.
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File installer\windows\build_setup.ps1
#   powershell -ExecutionPolicy Bypass -File installer\windows\build_setup.ps1 -Arch x64
#
# Pré-requisitos:
#   - os binários em dist\RelogioVivo-win-x64.exe e/ou dist\RelogioVivo-win-arm64.exe
#   - Inno Setup 6.3 ou mais novo (winget install JRSoftware.InnoSetup)
#
# Resultado:
#   dist\RelogioVivo-Setup-<versao>-win-x64.exe
#   dist\RelogioVivo-Setup-<versao>-win-arm64.exe

param(
    [ValidateSet("x64", "arm64", "both")]
    [string]$Arch = "both",
    [string]$Version = "",
    [string]$Iscc = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $root

function Find-Iscc {
    if ($Iscc) {
        if (Test-Path $Iscc) { return (Resolve-Path $Iscc).Path }
        throw "ISCC.exe não encontrado em $Iscc"
    }
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { return $c }
    }
    $cmd = Get-Command iscc -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "Inno Setup não encontrado. Instale com: winget install JRSoftware.InnoSetup"
}

if (-not $Version) {
    $match = Select-String -Path "relogio_vivo.py" -Pattern '^APP_VERSION = "([^"]+)"' |
        Select-Object -First 1
    if (-not $match) { throw "Não achei APP_VERSION em relogio_vivo.py" }
    $Version = $match.Matches[0].Groups[1].Value
}

$iscc = Find-Iscc
Write-Host "Inno Setup : $iscc"
Write-Host "Versão     : $Version"

$targets = if ($Arch -eq "both") { @("x64", "arm64") } else { @($Arch) }
$built = @()

foreach ($target in $targets) {
    $source = Join-Path $root "dist\RelogioVivo-win-$target.exe"
    if (-not (Test-Path $source)) {
        Write-Warning "Pulando ${target}: $source não existe (rode build_windows.ps1 primeiro)"
        continue
    }

    Write-Host ""
    Write-Host "==> Gerando instalador Windows $target"
    & $iscc "/DArch=$target" "/DAppVersion=$Version" "installer\windows\relogio-vivo.iss"
    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao gerar o instalador $target"
    }
    $built += (Join-Path $root "dist\RelogioVivo-Setup-$Version-win-$target.exe")
}

if ($built.Count -eq 0) {
    throw "Nenhum instalador foi gerado"
}

Write-Host ""
Write-Host "Instaladores gerados:"
foreach ($file in $built) {
    $size = [math]::Round((Get-Item $file).Length / 1MB, 1)
    Write-Host ("  {0}  ({1} MB)" -f $file, $size)
}
