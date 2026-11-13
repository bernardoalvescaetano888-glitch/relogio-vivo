# Gera os executáveis do Windows com PyInstaller.
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File build_windows.ps1
#   powershell -ExecutionPolicy Bypass -File build_windows.ps1 -Python "C:\Python312\python.exe"
#
# Se nenhum -Python for informado, o script procura todos os Pythons
# registrados no launcher "py" e gera um .exe para cada arquitetura
# encontrada (x64 e/ou ARM64).

param(
    [string]$Python = "",
    [string]$Name = "RelogioVivo"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$excludes = @(
    "--exclude-module", "numpy",
    "--exclude-module", "pygame",
    "--exclude-module", "psutil",
    "--exclude-module", "setuptools",
    "--exclude-module", "pip",
    "--exclude-module", "pytest",
    "--exclude-module", "unittest",
    "--exclude-module", "pydoc",
    "--exclude-module", "doctest",
    "--exclude-module", "lib2to3",
    "--exclude-module", "pdb",
    "--exclude-module", "tkinter.test"
)

function Get-ArchLabel([string]$Interpreter) {
    # sysconfig.get_platform() reflete a arquitetura do PROCESSO. No Windows
    # ARM, platform.machine() devolve "ARM64" até para o Python x64 emulado,
    # o que já fez o build x64 ser salvo com o nome errado.
    $plat = & $Interpreter -c "import sysconfig; print(sysconfig.get_platform())"
    $plat = $plat.Trim().ToLowerInvariant()
    switch -Regex ($plat) {
        "arm64" { return "arm64" }
        "amd64|x64" { return "x64" }
        "win32|x86" { return "x86" }
        default { return $plat }
    }
}

function Find-Pythons {
    if ($Python) { return @($Python) }

    $list = @()
    try {
        foreach ($line in (& py -0p 2>$null)) {
            if ($line -match '^\s*-V:\S+\s+\*?\s*(.+python\.exe)\s*$') {
                $list += $Matches[1].Trim()
            }
        }
    } catch {
        # launcher "py" indisponível
    }
    if ($list.Count -eq 0) {
        $cmd = Get-Command python -ErrorAction SilentlyContinue
        if ($cmd) { $list += $cmd.Source }
    }
    return $list
}

$interpreters = Find-Pythons
if ($interpreters.Count -eq 0) {
    throw "Nenhum Python encontrado. Instale em python.org e rode de novo."
}

$built = @()
foreach ($interpreter in $interpreters) {
    if (-not (Test-Path $interpreter)) { continue }
    $arch = Get-ArchLabel $interpreter
    $target = "$Name-win-$arch"
    if ($built -match "\\$target\.exe$") {
        Write-Host "==> Pulando ${target}: essa arquitetura já foi compilada"
        continue
    }
    Write-Host ""
    Write-Host "==> Compilando $target com $interpreter"

    & $interpreter -m pip install --quiet --upgrade "pyinstaller" "Pillow>=10.0"
    & $interpreter -m PyInstaller --noconfirm --windowed --onefile `
        --name $target `
        --icon (Join-Path $PSScriptRoot "assets\icon.ico") `
        --version-file (Join-Path $PSScriptRoot "assets\version_info.txt") `
        @excludes relogio_vivo.py

    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao compilar $target"
    }
    $built += (Join-Path $PSScriptRoot "dist\$target.exe")
}

Write-Host ""
Write-Host "Executáveis gerados:"
foreach ($file in $built) {
    $size = [math]::Round((Get-Item $file).Length / 1MB, 1)
    Write-Host ("  {0}  ({1} MB)" -f $file, $size)
}
Write-Host ""
Write-Host "O build -win-x64 roda em qualquer Windows 10/11 Intel ou AMD"
Write-Host "(e também em Windows ARM64, por emulação)."
Write-Host "O build -win-arm64 é nativo para Snapdragon/ARM e é menor."

exit 0
