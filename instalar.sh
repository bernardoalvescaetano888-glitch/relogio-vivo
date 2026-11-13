#!/usr/bin/env bash
# Instalador do Relógio Vivo para Linux.
#
# Instala tudo sozinho: Python, Tkinter, Pillow, ferramentas de captura e de
# inatividade, o app, o atalho no menu, o ícone e a inicialização automática.
# Depois deixa o app rodando em segundo plano.
#
# Uso mais simples (não precisa baixar nada antes):
#   curl -fsSL https://raw.githubusercontent.com/bernardoalvescaetano888-glitch/relogio-vivo/main/instalar.sh | bash
#
# Opções:
#   --no-autostart   não inicia junto com o sistema
#   --no-start       instala mas não abre o app agora
#   --from ARQUIVO   instala a partir de um relogio_vivo.py local
#   --uninstall      remove o app (mantém suas configurações)
#   --help           mostra esta ajuda
#
# Também funciona local:  chmod +x instalar.sh && ./instalar.sh

set -uo pipefail

APP_ID="relogio-vivo"
APP_NAME="Relógio Vivo"
REPO="bernardoalvescaetano888-glitch/relogio-vivo"
BRANCH="${RV_BRANCH:-main}"
RAW="https://raw.githubusercontent.com/$REPO/$BRANCH"

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
INSTALL_DIR="$DATA_HOME/relogio-vivo"
BIN_DIR="$HOME/.local/bin"
LAUNCHER="$BIN_DIR/relogio-vivo"
DESKTOP_FILE="$DATA_HOME/applications/$APP_ID.desktop"
ICON_DIR="$DATA_HOME/icons/hicolor/256x256/apps"
ICON_FILE="$ICON_DIR/$APP_ID.png"
AUTOSTART_FILE="$CONFIG_HOME/autostart/$APP_ID.desktop"
LOG="${TMPDIR:-/tmp}/relogio-vivo-install.log"

LOCAL_SOURCE=""
DO_AUTOSTART=1
DO_START=1
DO_UNINSTALL=0

# ---------------------------------------------------------------- utilidades

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
ok() { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
fail() { printf '  \033[31m✗\033[0m %s\n' "$*" >&2; }
step() { printf '\n\033[36m▸\033[0m %s\n' "$*"; }

have() { command -v "$1" >/dev/null 2>&1; }

as_root() {
    if [ "$(id -u)" = "0" ]; then
        "$@"
    elif have sudo; then
        sudo "$@"
    else
        fail "preciso de sudo para instalar pacotes do sistema"
        return 1
    fi
}

fetch() { # fetch URL DESTINO
    if have curl; then
        curl -fsSL --retry 2 --max-time 60 "$1" -o "$2"
    elif have wget; then
        wget -q -T 60 -O "$2" "$1"
    else
        return 1
    fi
}

die() {
    fail "$*"
    if [ -s "$LOG" ]; then
        printf '\nÚltimas linhas do log (%s):\n' "$LOG" >&2
        tail -n 15 "$LOG" >&2
    fi
    exit 1
}

show_help() {
    cat <<'EOF'
Instalador do Relógio Vivo para Linux.

Instala tudo sozinho: Python, Tkinter, Pillow, ferramentas de captura e de
inatividade, o app, o atalho no menu, o ícone e a inicialização automática.
Depois deixa o app rodando em segundo plano.

Uso:
  curl -fsSL https://raw.githubusercontent.com/bernardoalvescaetano888-glitch/relogio-vivo/main/instalar.sh | bash

Opções:
  --no-autostart   não inicia junto com o sistema
  --no-start       instala mas não abre o app agora
  --from ARQUIVO   instala a partir de um relogio_vivo.py local
  --uninstall      remove o app (mantém suas configurações)
  --help           mostra esta ajuda

Local:
  chmod +x instalar.sh && ./instalar.sh
EOF
}

# ------------------------------------------------------------------- sistema

detect_pm() {
    if have apt-get; then echo apt
    elif have dnf; then echo dnf
    elif have pacman; then echo pacman
    elif have zypper; then echo zypper
    else echo none
    fi
}

pkg_update() {
    case "$1" in
        apt) LANG=C as_root apt-get update -qq ;;
        dnf) as_root dnf -q -y makecache ;;
        pacman) as_root pacman -Sy --noconfirm >/dev/null ;;
        zypper) as_root zypper --non-interactive refresh >/dev/null ;;
    esac
}

pkg_install() { # pkg_install PM PACOTES...
    local pm="$1"; shift
    [ $# -eq 0 ] && return 0
    case "$pm" in
        apt)
            DEBIAN_FRONTEND=noninteractive as_root \
                apt-get install -y -qq --no-install-recommends "$@" ;;
        dnf) as_root dnf -q -y install "$@" ;;
        pacman) as_root pacman -S --noconfirm --needed "$@" >/dev/null ;;
        zypper) as_root zypper --non-interactive --quiet install "$@" >/dev/null ;;
        *) return 1 ;;
    esac
}

core_packages() {
    case "$1" in
        apt) echo "python3 python3-tk python3-pil python3-pil.imagetk" ;;
        dnf) echo "python3 python3-tkinter python3-pillow python3-pillow-tk" ;;
        pacman) echo "python tk python-pillow" ;;
        zypper) echo "python3 python3-tk python3-Pillow python3-Pillow-tk" ;;
    esac
}

extra_packages() {
    case "$1" in
        apt) echo "libxss1 xprintidle" ;;
        dnf) echo "libXScrnSaver xprintidle" ;;
        pacman) echo "libxss xprintidle" ;;
        zypper) echo "libXss1 xprintidle" ;;
    esac
}

wayland_tools() {
    case "$1" in
        apt) echo "grim" ;;
        dnf) echo "grim" ;;
        pacman) echo "grim" ;;
        zypper) echo "grim" ;;
    esac
}

# ---------------------------------------------------------------- argumentos

while [ $# -gt 0 ]; do
    case "$1" in
        --no-autostart) DO_AUTOSTART=0 ;;
        --no-start) DO_START=0 ;;
        --from)
            shift
            LOCAL_SOURCE="${1:-}"
            [ -n "$LOCAL_SOURCE" ] || die "--from precisa de um caminho"
            ;;
        --uninstall) DO_UNINSTALL=1 ;;
        -h | --help)
            show_help
            exit 0
            ;;
        *) die "opção desconhecida: $1 (use --help)" ;;
    esac
    shift
done

# --------------------------------------------------------------- desinstalar

if [ "$DO_UNINSTALL" = "1" ]; then
    bold "Removendo o $APP_NAME"
    if [ -x "$LAUNCHER" ]; then
        "$LAUNCHER" --quit >/dev/null 2>&1 || true
    fi
    rm -f "$LAUNCHER" "$DESKTOP_FILE" "$AUTOSTART_FILE" "$ICON_FILE"
    rm -rf "$INSTALL_DIR"
    have update-desktop-database && update-desktop-database "$DATA_HOME/applications" >/dev/null 2>&1 || true
    if have gtk-update-icon-cache && [ -d "$DATA_HOME/icons/hicolor" ]; then
        gtk-update-icon-cache -q -t -f "$DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true
    fi
    ok "app removido"
    warn "suas configurações continuam em $CONFIG_HOME/relogio-vivo"
    exit 0
fi

# ------------------------------------------------------------------ instalar

printf '\n'
bold "Relógio Vivo — instalador"
printf 'Tudo é instalado em %s\n' "$INSTALL_DIR"
printf 'O progresso detalhado fica em %s\n' "$LOG"
: >"$LOG"

step "Verificando o sistema"
PM="$(detect_pm)"
if [ "$PM" = "none" ]; then
    die "não reconheci o gerenciador de pacotes (apt, dnf, pacman ou zypper)"
fi
ok "$(uname -s) $(uname -m) — gerenciador: $PM"

SESSION="${XDG_SESSION_TYPE:-}"
if [ -z "$SESSION" ]; then
    if [ -n "${WAYLAND_DISPLAY:-}" ]; then SESSION="wayland"; else SESSION="x11"; fi
fi
ok "sessão gráfica: $SESSION"

step "Instalando dependências (pode pedir sua senha do sudo)"
pkg_update "$PM" >>"$LOG" 2>&1 || warn "não consegui atualizar a lista de pacotes; seguindo"

# shellcheck disable=SC2046
if ! pkg_install "$PM" $(core_packages "$PM") >>"$LOG" 2>&1; then
    warn "a instalação de alguns pacotes falhou; vou tentar do mesmo jeito"
fi

# shellcheck disable=SC2046
pkg_install "$PM" $(extra_packages "$PM") >>"$LOG" 2>&1 || true

if [ "$SESSION" = "wayland" ]; then
    # shellcheck disable=SC2046
    pkg_install "$PM" $(wayland_tools "$PM") >>"$LOG" 2>&1 \
        || warn "não instalei o grim; a captura no Wayland pode falhar"
fi

if ! have python3; then
    die "o python3 não está disponível depois da instalação"
fi
ok "python3 $(python3 -c 'import sys; print(sys.version.split()[0])')"

step "Conferindo Tkinter e Pillow"
if ! python3 -c 'import tkinter' >/dev/null 2>&1; then
    case "$PM" in
        apt) pkg_install apt python3-tk >>"$LOG" 2>&1 || true ;;
        dnf) pkg_install dnf python3-tkinter >>"$LOG" 2>&1 || true ;;
        pacman) pkg_install pacman tk >>"$LOG" 2>&1 || true ;;
        zypper) pkg_install zypper python3-tk >>"$LOG" 2>&1 || true ;;
    esac
fi
python3 -c 'import tkinter' >/dev/null 2>&1 \
    || die "Tkinter não instalou. No Ubuntu: sudo apt install python3-tk"
ok "Tkinter disponível"

if ! python3 -c 'import PIL' >/dev/null 2>&1; then
    case "$PM" in
        apt) pkg_install apt python3-pil >>"$LOG" 2>&1 || true ;;
        dnf) pkg_install dnf python3-pillow >>"$LOG" 2>&1 || true ;;
        pacman) pkg_install pacman python-pillow >>"$LOG" 2>&1 || true ;;
        zypper) pkg_install zypper python3-Pillow >>"$LOG" 2>&1 || true ;;
    esac
fi
if ! python3 -c 'from PIL import ImageTk' >/dev/null 2>&1; then
    case "$PM" in
        apt) pkg_install apt python3-pil.imagetk >>"$LOG" 2>&1 || true ;;
        dnf) pkg_install dnf python3-pillow-tk >>"$LOG" 2>&1 || true ;;
        pacman) pkg_install pacman python-pillow >>"$LOG" 2>&1 || true ;;
        zypper) pkg_install zypper python3-Pillow-tk >>"$LOG" 2>&1 || true ;;
    esac
fi
if ! python3 -c 'from PIL import ImageTk' >/dev/null 2>&1; then
    python3 -m pip install --user --break-system-packages --quiet --upgrade "Pillow>=10.0" \
        >>"$LOG" 2>&1 || python3 -m pip install --user --quiet --upgrade "Pillow>=10.0" \
        >>"$LOG" 2>&1 || true
fi
if python3 -c 'from PIL import ImageTk' >/dev/null 2>&1; then
    ok "Pillow $(python3 -c 'import PIL; print(PIL.__version__)') com ImageTk"
else
    die "o Pillow não tem o módulo ImageTk. Ubuntu: sudo apt install python3-pil.imagetk"
fi

step "Baixando o aplicativo"
mkdir -p "$INSTALL_DIR" || die "não consegui criar $INSTALL_DIR"

SOURCE=""
if [ -n "$LOCAL_SOURCE" ]; then
    SOURCE="$LOCAL_SOURCE"
elif [ -f "$PWD/relogio_vivo.py" ]; then
    SOURCE="$PWD/relogio_vivo.py"
elif [ -f "$(dirname "$0")/relogio_vivo.py" ] 2>/dev/null; then
    SOURCE="$(dirname "$0")/relogio_vivo.py"
else
    SOURCE="$INSTALL_DIR/relogio_vivo.py"
    fetch "$RAW/relogio_vivo.py" "$SOURCE" >>"$LOG" 2>&1 \
        || die "não consegui baixar o relogio_vivo.py de $RAW"
fi

[ -f "$SOURCE" ] || die "arquivo não encontrado: $SOURCE"
if [ "$SOURCE" != "$INSTALL_DIR/relogio_vivo.py" ]; then
    cp "$SOURCE" "$INSTALL_DIR/relogio_vivo.py" || die "não consegui copiar o app"
fi
chmod 644 "$INSTALL_DIR/relogio_vivo.py"
ok "app instalado em $INSTALL_DIR"

step "Criando atalho, ícone e menu"
mkdir -p "$BIN_DIR" "$(dirname "$DESKTOP_FILE")" "$ICON_DIR"

cat >"$LAUNCHER" <<EOF
#!/bin/sh
exec python3 "$INSTALL_DIR/relogio_vivo.py" "\$@"
EOF
chmod 755 "$LAUNCHER"

TMP_ICON="$INSTALL_DIR/icon.png"
if fetch "$RAW/assets/icon.png" "$TMP_ICON" >>"$LOG" 2>&1; then
    mv "$TMP_ICON" "$ICON_FILE"
    if have gtk-update-icon-cache && [ -d "$DATA_HOME/icons/hicolor" ]; then
        gtk-update-icon-cache -q -t -f "$DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true
    fi
    ok "ícone instalado"
else
    warn "não baixei o ícone (o resto funciona igual)"
fi

cat >"$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=$APP_NAME
Comment=Protetor de tela com a hora e a data
Exec=$LAUNCHER
Icon=$APP_ID
Terminal=false
Categories=Utility;
StartupNotify=false
EOF

have update-desktop-database && update-desktop-database "$DATA_HOME/applications" >/dev/null 2>&1 || true
ok "atalho criado ($LAUNCHER)"

case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *)
        warn "$BIN_DIR não está no PATH"
        warn "adicione ao ~/.profile:  export PATH=\"\$HOME/.local/bin:\$PATH\""
        ;;
esac

step "Configurando a inicialização automática"
if [ "$DO_AUTOSTART" = "1" ]; then
    if "$LAUNCHER" --install-autostart >>"$LOG" 2>&1; then
        ok "vai iniciar junto com o sistema"
    else
        warn "não consegui ativar; dá para ativar depois pela janela do app"
    fi
else
    warn "mantido desligado (--no-autostart)"
fi

step "Teste rápido"
if "$LAUNCHER" --check 2>/dev/null | sed 's/^/    /'; then
    ok "diagnóstico concluído"
else
    warn "o diagnóstico falhou; veja $LOG"
fi

if [ "$DO_START" = "1" ]; then
    step "Abrindo o app em segundo plano"
    setsid nohup "$LAUNCHER" --background >/dev/null 2>&1 &
    sleep 2
    if pgrep -f "relogio_vivo.py --background" >/dev/null 2>&1; then
        ok "rodando agora; a janela abre com: relogio-vivo"
    else
        warn "não consegui iniciar sozinho; rode: relogio-vivo"
    fi
fi

printf '\n'
bold "Pronto!"
cat <<EOF

  Abrir as configurações :  relogio-vivo
  Ver o protetor agora   :  relogio-vivo --test
  Diagnóstico            :  relogio-vivo --check
  Desinstalar            :  curl -fsSL $RAW/instalar.sh | bash -s -- --uninstall

  Configurações e log    :  $CONFIG_HOME/relogio-vivo

EOF
