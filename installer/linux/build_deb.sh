#!/usr/bin/env bash
# Gera o pacote .deb do Relógio Vivo (Debian, Ubuntu, Mint, Pop!_OS, Zorin...).
#
# Uso:
#   bash installer/linux/build_deb.sh            # gera dist/relogio-vivo_<versao>_all.deb
#   bash installer/linux/build_deb.sh --version <versao>
#
# Precisa de: dpkg-deb (vem com o dpkg). Funciona em qualquer Debian/Ubuntu.
#
# O pacote instala:
#   /usr/bin/relogio-vivo                      comando no PATH
#   /usr/share/relogio-vivo/relogio_vivo.py    aplicativo
#   /usr/share/applications/relogio-vivo.desktop   atalho no menu
#   /usr/share/icons/hicolor/256x256/apps/relogio-vivo.png   ícone
#
# Dependências resolvidas automaticamente pelo apt:
#   python3, python3-tk, python3-pil.imagetk, libglib2.0-bin (gdbus)
# Recomendadas:
#   gnome-screenshot, grim, imagemagick (captura no Wayland/X11),
#   xprintidle, libxss1 (detecção de inatividade), libnotify-bin (avisos)

set -euo pipefail
cd "$(dirname "$0")/../.."

VERSION=""
while [ $# -gt 0 ]; do
    case "$1" in
        --version)
            shift
            VERSION="${1:-}"
            ;;
        -h | --help)
            sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "Opção desconhecida: $1" >&2
            exit 1
            ;;
    esac
    shift
done

if [ -z "$VERSION" ]; then
    VERSION="$(python3 -c '
import re, pathlib
texto = pathlib.Path("relogio_vivo.py").read_text(encoding="utf-8")
print(re.search(r"APP_VERSION = \"([^\"]+)\"", texto).group(1))
')"
fi

PKG="relogio-vivo"
BUILD="build/deb"
OUT="dist/${PKG}_${VERSION}_all.deb"

rm -rf "$BUILD"
mkdir -p \
    "$BUILD/DEBIAN" \
    "$BUILD/usr/bin" \
    "$BUILD/usr/share/$PKG" \
    "$BUILD/usr/share/applications" \
    "$BUILD/usr/share/icons/hicolor/256x256/apps" \
    "$BUILD/usr/share/doc/$PKG"

# ------------------------------------------------------------------ arquivos

install -m 644 relogio_vivo.py "$BUILD/usr/share/$PKG/relogio_vivo.py"
install -m 644 assets/icon.png "$BUILD/usr/share/icons/hicolor/256x256/apps/$PKG.png"

cat >"$BUILD/usr/bin/$PKG" <<'EOF'
#!/bin/sh
# Lançador do Relógio Vivo.
exec python3 /usr/share/relogio-vivo/relogio_vivo.py "$@"
EOF
chmod 755 "$BUILD/usr/bin/$PKG"

cat >"$BUILD/usr/share/applications/$PKG.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Relógio Vivo
Comment=Protetor de tela com a hora e a data
Exec=/usr/bin/relogio-vivo
Icon=relogio-vivo
Terminal=false
Categories=Utility;
Keywords=screensaver;clock;relogio;protetor;
StartupNotify=false
EOF

cat >"$BUILD/usr/share/doc/$PKG/copyright" <<'EOF'
Relógio Vivo
https://github.com/bernardoalvescaetano888-glitch/relogio-vivo

Protetor de tela em Python + Tkinter que mostra a hora e a data
depois de alguns minutos de inatividade.

Distribuído gratuitamente. Veja os termos no repositório acima.
EOF

# ------------------------------------------------------------------- scripts

cat >"$BUILD/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor >/dev/null 2>&1 || true
fi

# Ativa a inicialização automática para quem instalou com sudo.
usuario="${SUDO_USER:-}"
if [ -n "$usuario" ] && [ "$usuario" != "root" ]; then
    casa="$(getent passwd "$usuario" | cut -d: -f6)"
    if [ -n "$casa" ] && [ -d "$casa" ]; then
        pasta="$casa/.config/autostart"
        mkdir -p "$pasta"
        cat >"$pasta/relogio-vivo.desktop" <<AUTOSTART
[Desktop Entry]
Type=Application
Name=Relógio Vivo
Comment=Mostra a hora e a data depois de alguns minutos de inatividade
Exec=/usr/bin/relogio-vivo --background
Terminal=false
X-GNOME-Autostart-enabled=true
Hidden=false
AUTOSTART
        chown -R "$usuario": "$pasta/relogio-vivo.desktop" 2>/dev/null || true
    fi
fi

exit 0
EOF

cat >"$BUILD/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor >/dev/null 2>&1 || true
fi

exit 0
EOF

chmod 755 "$BUILD/DEBIAN/postinst" "$BUILD/DEBIAN/postrm"

TAMANHO="$(du -sk "$BUILD/usr" | cut -f1)"

cat >"$BUILD/DEBIAN/control" <<EOF
Package: $PKG
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.9), python3-tk, python3-pil.imagetk, libglib2.0-bin
Recommends: gnome-screenshot, grim, imagemagick, scrot, xprintidle, libxss1, libnotify-bin
Installed-Size: $TAMANHO
Maintainer: Relógio Vivo <bernardoalvescaetano888-glitch@users.noreply.github.com>
Homepage: https://github.com/bernardoalvescaetano888-glitch/relogio-vivo
Description: protetor de tela com a hora e a data
 Mostra a hora e a data depois de alguns minutos sem teclado ou mouse.
 Usa a própria tela como fundo desfocado, desenha um cartão com a hora
 ao vivo e a data em português e o faz deslizar pela tela.
 .
 Sai com qualquer tecla, clique ou movimento do mouse e pode iniciar
 junto com o sistema.
EOF

# ------------------------------------------------------------------- empacote

mkdir -p dist
rm -f "$OUT"
dpkg-deb --root-owner-group --build "$BUILD" "$OUT" >/dev/null

echo
echo "Pacote gerado: $OUT"
echo
echo "Instalar:   sudo apt install ./$(basename "$OUT")"
echo "Remover:    sudo apt remove $PKG"
echo
dpkg-deb --info "$OUT" | sed 's/^/  /'
