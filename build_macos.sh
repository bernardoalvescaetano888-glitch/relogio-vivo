#!/usr/bin/env bash
# Gera o app do macOS com PyInstaller.
# Precisa ser rodado EM UM MAC (PyInstaller não compila para macOS a partir
# do Windows ou do Linux).
#
# Uso:
#   chmod +x build_macos.sh
#   ./build_macos.sh
#
# Resultado: dist/RelogioVivo.app

set -euo pipefail
cd "$(dirname "$0")"

case "$(uname -m)" in
    arm64) SUFFIX="arm64" ;;
    x86_64) SUFFIX="x64" ;;
    *) SUFFIX="$(uname -m)" ;;
esac

TARGET="RelogioVivo"

# Gera o .icns a partir do PNG (o macOS não aceita .ico no bundle).
ICON_ICNS="assets/icon.icns"
if [ ! -f "$ICON_ICNS" ] && [ -f "assets/icon.png" ]; then
    ICONSET="build/icon.iconset"
    rm -rf "$ICONSET"
    mkdir -p "$ICONSET"
    for size in 16 32 64 128 256 512; do
        sips -z "$size" "$size" assets/icon.png \
            --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
        sips -z "$((size * 2))" "$((size * 2))" assets/icon.png \
            --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
    done
    iconutil -c icns "$ICONSET" -o "$ICON_ICNS"
    echo "Ícone gerado: $ICON_ICNS"
fi

ICON_ARG=()
if [ -f "$ICON_ICNS" ]; then
    ICON_ARG=(--icon "$ICON_ICNS")
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
    --osx-bundle-identifier "com.relogiovivo.screensaver" \
    ${ICON_ARG[@]+"${ICON_ARG[@]}"} \
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
echo "Gerado: dist/$TARGET.app ($SUFFIX)"
echo
echo "Para testar:"
echo "  ./dist/$TARGET.app/Contents/MacOS/$TARGET --check"
echo "  open dist/$TARGET.app"
echo
echo "Na primeira execução o macOS pede permissão de Gravação de Tela."
echo "Autorize em Ajustes do Sistema > Privacidade e Segurança."
