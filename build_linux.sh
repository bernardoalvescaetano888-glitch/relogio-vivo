#!/usr/bin/env bash
# Gera o executável do Linux com PyInstaller.
# Precisa ser rodado EM UM LINUX (PyInstaller não compila para Linux a partir
# do Windows ou do macOS).
#
# Uso:
#   chmod +x build_linux.sh
#   ./build_linux.sh
#
# Ubuntu/Debian, antes de rodar:
#   sudo apt install python3 python3-venv python3-tk
#
# Resultado: dist/RelogioVivo-linux-x64 (ou -arm64)

set -euo pipefail
cd "$(dirname "$0")"

case "$(uname -m)" in
    x86_64 | amd64) SUFFIX="x64" ;;
    aarch64 | arm64) SUFFIX="arm64" ;;
    *) SUFFIX="$(uname -m)" ;;
esac

TARGET="RelogioVivo-linux-$SUFFIX"

if ! python3 -c "import tkinter" >/dev/null 2>&1; then
    echo "Tkinter não encontrado. No Ubuntu/Debian: sudo apt install python3-tk" >&2
    exit 1
fi

if [ ! -d .venv-build ]; then
    python3 -m venv .venv-build
fi
# shellcheck disable=SC1091
. .venv-build/bin/activate

python -m pip install --quiet --upgrade pip
python -m pip install --quiet --upgrade pyinstaller "Pillow>=10.0"

python -m PyInstaller --noconfirm --windowed --onefile \
    --name "$TARGET" \
    --exclude-module numpy \
    --exclude-module pygame \
    --exclude-module psutil \
    --exclude-module setuptools \
    --exclude-module pip \
    --exclude-module pytest \
    --exclude-module unittest \
    --exclude-module pydoc \
    --exclude-module doctest \
    --exclude-module lib2to3 \
    --exclude-module pdb \
    --exclude-module tkinter.test \
    relogio_vivo.py

echo
echo "Gerado: dist/$TARGET"
echo
echo "Para testar:"
echo "  ./dist/$TARGET --check"
echo "  ./dist/$TARGET"
echo
echo "Lembrete: no Wayland instale um capturador (grim, gnome-screenshot ou"
echo "spectacle) e, no X11, xprintidle e libxss1 para detectar inatividade."
