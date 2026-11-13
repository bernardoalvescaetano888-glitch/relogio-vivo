#!/usr/bin/env bash
# Gera o instalador .pkg do Relógio Vivo para macOS.
# Precisa ser rodado EM UM MAC, depois de build_macos.sh.
#
# Uso:
#   ./build_macos.sh
#   bash installer/macos/build_pkg.sh              # gera o .pkg
#   bash installer/macos/build_pkg.sh --dmg        # gera .pkg + .dmg
#
# Resultado:
#   dist/RelogioVivo-Setup-<versao>-macos-<arch>.pkg
#   dist/RelogioVivo-<versao>-macos-<arch>.dmg     (com --dmg)
#
# O .pkg instala o app em /Applications, com ícone, e o desinstalador
# fica disponível removendo o app. Na primeira execução o próprio app
# pergunta se pode iniciar junto com o sistema (LaunchAgent).
#
# O pacote não é assinado nem notarizado (não temos conta Apple Developer).
# O usuário abre com clique direito > Abrir na primeira vez.

set -euo pipefail
cd "$(dirname "$0")/../.."

FACA_DMG=0
[ "${1:-}" = "--dmg" ] && FACA_DMG=1

APP="dist/RelogioVivo.app"
if [ ! -d "$APP" ]; then
    echo "Erro: $APP não existe. Rode ./build_macos.sh primeiro." >&2
    exit 1
fi

VERSION="$(python3 -c '
import re, pathlib
texto = pathlib.Path("relogio_vivo.py").read_text(encoding="utf-8")
print(re.search(r"APP_VERSION = \"([^\"]+)\"", texto).group(1))
')"

case "$(uname -m)" in
    arm64) ARCH="arm64" ;;
    x86_64) ARCH="x64" ;;
    *) ARCH="$(uname -m)" ;;
esac

PKG_ID="com.relogiovivo.screensaver"
WORK="build/pkg-$ARCH"
RAIZ="$WORK/root"
SCRIPTS="$WORK/scripts"
OUT="dist/RelogioVivo-Setup-$VERSION-macos-$ARCH.pkg"

rm -rf "$WORK"
mkdir -p "$RAIZ/Applications" "$SCRIPTS"

# Copia preservando recursos e remove a quarentena do download.
ditto "$APP" "$RAIZ/Applications/RelogioVivo.app"
xattr -cr "$RAIZ/Applications/RelogioVivo.app" 2>/dev/null || true

cat >"$SCRIPTS/postinstall" <<'EOF'
#!/bin/sh
# Remove a marca de quarentena para reduzir os avisos do Gatekeeper.
xattr -dr com.apple.quarantine /Applications/RelogioVivo.app 2>/dev/null || true
exit 0
EOF
chmod 755 "$SCRIPTS/postinstall"

pkgbuild \
    --root "$RAIZ" \
    --identifier "$PKG_ID" \
    --version "$VERSION" \
    --install-location / \
    --scripts "$SCRIPTS" \
    "$WORK/RelogioVivo-component.pkg"

cat >"$WORK/distribution.xml" <<EOF
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2">
    <title>Relógio Vivo $VERSION</title>
    <organization>com.relogiovivo</organization>
    <domains enable_localSystem="true" enable_currentUserHome="false" enable_anywhere="false"/>
    <options customize="never" require-scripts="false" hostArchitectures="$ARCH"/>
    <pkg-ref id="$PKG_ID"/>
    <choices-outline>
        <line choice="default">
            <line choice="$PKG_ID"/>
        </line>
    </choices-outline>
    <choice id="default"/>
    <choice id="$PKG_ID" visible="false">
        <pkg-ref id="$PKG_ID"/>
    </choice>
    <pkg-ref id="$PKG_ID" version="$VERSION" onConclusion="none">RelogioVivo-component.pkg</pkg-ref>
</installer-gui-script>
EOF

productbuild \
    --distribution "$WORK/distribution.xml" \
    --package-path "$WORK" \
    "$OUT" >/dev/null

echo
echo "Pacote gerado: $OUT"

if [ "$FACA_DMG" = "1" ]; then
    DMG="dist/RelogioVivo-$VERSION-macos-$ARCH.dmg"
    DMG_DIR="$WORK/dmg"
    rm -rf "$DMG_DIR"
    mkdir -p "$DMG_DIR"
    ditto "$APP" "$DMG_DIR/RelogioVivo.app"
    ln -s /Applications "$DMG_DIR/Aplicações"
    rm -f "$DMG"
    hdiutil create -volname "Relógio Vivo $VERSION" \
        -srcfolder "$DMG_DIR" -ov -format UDZO "$DMG" >/dev/null
    echo "Imagem gerada: $DMG"
fi

echo
echo "Instalar:   abra o .pkg com dois cliques"
echo "Ou:         sudo installer -pkg \"$OUT\" -target /"
echo
echo "Observação: o pacote não é assinado. Na primeira vez, clique com o"
echo "botão direito no .pkg > Abrir (ou Ajustes do Sistema > Privacidade)."
