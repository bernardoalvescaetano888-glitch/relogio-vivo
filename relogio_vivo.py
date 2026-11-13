#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Relógio Vivo — protetor de tela com a hora e a data.

Depois de alguns minutos sem teclado/mouse, o app pode aparecer de dois jeitos:

* "Prévia da tela": captura a tela, escurece e desfoca a imagem como fundo e
  coloca um cartão com a hora e a data em baixo, deslizando pela tela.
* "Só o relógio": não captura nada. Mostra um relógio grande e a data sobre um
  fundo escuro, centralizado e com uma leve flutuação.

Plataformas: Windows, Linux (X11 e Wayland) e macOS.
Interface: Tkinter (stdlib). Dependência externa: Pillow.

Uso rápido:
    python relogio_vivo.py              # abre as configurações
    python relogio_vivo.py --background # roda escondido (usado na inicialização)
    python relogio_vivo.py --check      # diagnóstico do sistema
"""

from __future__ import annotations

import argparse
import ctypes
import io
import json
import math
import os
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    import tkinter as tk
    import tkinter.font as tkfont
    from tkinter import messagebox

    TK_AVAILABLE = True
    TK_ERROR = ""
except Exception as exc:  # noqa: BLE001 - Tk pode faltar no Linux
    tk = None  # type: ignore[assignment]
    tkfont = None  # type: ignore[assignment]
    messagebox = None  # type: ignore[assignment]
    TK_AVAILABLE = False
    TK_ERROR = str(exc)

try:
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageGrab
except ImportError:  # tratado com uma mensagem amigável em main()
    Image = None  # type: ignore[assignment]
    ImageFont = None  # type: ignore[assignment]

try:
    from PIL import ImageTk
except Exception:  # Pillow sem Tk ou Tk ausente
    ImageTk = None  # type: ignore[assignment]

APP_NAME = "Relógio Vivo"
APP_ID = "relogio-vivo"
APP_VERSION = "1.3.1"
AUTOSTART_NAME = "RelogioVivo"
AUTOSTART_LABEL = "com.relogiovivo.screensaver"

# Modos de exibição do protetor.
MODE_TELA = "tela"
MODE_RELOGIO = "relogio"
MODE_LABELS = {
    MODE_TELA: "Prévia da tela",
    MODE_RELOGIO: "Só o relógio",
}

# Cores da interface
BG = "#0b0f17"
CARD = "#121826"
CARD_ALT = "#1a2233"
BORDER = "#232d42"
TEXT = "#e8eefb"
MUTED = "#8b97ad"
ACCENT = "#5eead4"
ACCENT_HOVER = "#7ff2df"
DANGER = "#f87171"

DIAS = [
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
]
MESES = [
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
]


# ---------------------------------------------------------------------------
# Caminhos, log e configuração
# ---------------------------------------------------------------------------


def config_dir() -> Path:
    """Pasta de dados do app, adequada a cada sistema."""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "RelogioVivo"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "RelogioVivo"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / APP_ID


def config_file() -> Path:
    return config_dir() / "config.json"


def log_file() -> Path:
    return config_dir() / "relogio-vivo.log"


def request_file() -> Path:
    return config_dir() / "request.json"


def log(message: str) -> None:
    """Log simples em arquivo (importante no modo --background, sem console)."""
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}"
    try:
        config_dir().mkdir(parents=True, exist_ok=True)
        with open(log_file(), "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def trim_log() -> None:
    """Evita que o log cresça para sempre."""
    try:
        path = log_file()
        if path.exists() and path.stat().st_size > 512_000:
            data = path.read_bytes()[-200_000:]
            path.write_bytes(data)
    except OSError:
        pass


@dataclass
class Config:
    idle_minutes: int = 5
    autostart: bool = False
    mode: str = MODE_TELA

    @classmethod
    def load(cls) -> tuple["Config", bool]:
        path = config_file()
        existed = path.exists()
        cfg = cls()
        if existed:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                cfg.idle_minutes = int(data.get("idle_minutes", 5))
                cfg.autostart = bool(data.get("autostart", False))
                cfg.mode = str(data.get("mode", MODE_TELA))
            except (OSError, ValueError, TypeError):
                cfg = cls()
        cfg.idle_minutes = max(1, min(60, cfg.idle_minutes))
        if cfg.mode not in (MODE_TELA, MODE_RELOGIO):
            cfg.mode = MODE_TELA
        return cfg, existed

    def save(self) -> None:
        try:
            config_dir().mkdir(parents=True, exist_ok=True)
            path = config_file()
            tmp = path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(
                    {
                        "idle_minutes": self.idle_minutes,
                        "autostart": self.autostart,
                        "mode": self.mode,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            os.replace(tmp, path)
        except OSError as exc:
            log(f"Não foi possível salvar a configuração: {exc}")


# ---------------------------------------------------------------------------
# Inicialização automática com o sistema
# ---------------------------------------------------------------------------


def launch_command(background: bool = True) -> list[str]:
    """Comando que inicia o app (sem console no Windows, quando possível)."""
    if getattr(sys, "frozen", False):
        base = [sys.executable]
    else:
        exe = sys.executable
        if os.name == "nt":
            pythonw = Path(exe).with_name("pythonw.exe")
            if pythonw.exists():
                exe = str(pythonw)
        base = [exe, str(Path(__file__).resolve())]
    if background:
        base.append("--background")
    return base


def _linux_desktop_quote(arg: str) -> str:
    arg = arg.replace("%", "%%")
    if not re.search(r'[\s"\'\\`$]', arg):
        return arg
    escaped = (
        arg.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("`", "\\`")
        .replace("$", "\\$")
    )
    return f'"{escaped}"'


def autostart_path() -> Path:
    if os.name == "nt":
        return Path("HKCU")  # apenas informativo
    if sys.platform == "darwin":
        return Path.home() / "Library" / "LaunchAgents" / f"{AUTOSTART_LABEL}.plist"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "autostart" / f"{APP_ID}.desktop"


def _under_launchd() -> bool:
    """True quando este processo foi iniciado pelo launchd (macOS)."""
    if sys.platform != "darwin":
        return False
    try:
        out = subprocess.run(
            ["ps", "-o", "ppid=", "-p", str(os.getpid())],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        ).stdout.strip()
        return out == "1"
    except Exception:  # noqa: BLE001 - melhor assumir que não é launchd
        return False


def is_autostart_enabled() -> bool:
    try:
        if os.name == "nt":
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
            ) as key:
                winreg.QueryValueEx(key, AUTOSTART_NAME)
            return True
        return autostart_path().exists()
    except OSError:
        return False


def enable_autostart() -> str:
    """Cria a entrada de inicialização do sistema atual. Retorna um resumo."""
    cmd = launch_command(background=True)
    config_dir().mkdir(parents=True, exist_ok=True)

    if os.name == "nt":
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(
                key,
                AUTOSTART_NAME,
                0,
                winreg.REG_SZ,
                subprocess.list2cmdline(cmd),
            )
        return r"Registro do Windows (HKCU\...\Run)"

    if sys.platform == "darwin":
        path = autostart_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "Label": AUTOSTART_LABEL,
            "ProgramArguments": cmd,
            "RunAtLoad": True,
            "KeepAlive": False,
            "LimitLoadToSessionType": "Aqua",
            "ProcessType": "Interactive",
            "StandardOutPath": str(log_file()),
            "StandardErrorPath": str(log_file()),
        }
        with open(path, "wb") as fh:
            plistlib.dump(payload, fh)
        uid = os.getuid() if hasattr(os, "getuid") else 501
        if not _under_launchd():
            for args in (
                ["launchctl", "bootstrap", f"gui/{uid}", str(path)],
                ["launchctl", "load", "-w", str(path)],
            ):
                try:
                    subprocess.run(
                        args, capture_output=True, timeout=10, check=False
                    )
                except (OSError, subprocess.SubprocessError):
                    pass
        return str(path)

    path = autostart_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    exec_line = " ".join(_linux_desktop_quote(part) for part in cmd)
    content = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_NAME}\n"
        "Comment=Mostra a hora e a data depois de alguns minutos de inatividade\n"
        f"Exec={exec_line}\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n"
        "Hidden=false\n"
    )
    path.write_text(content, encoding="utf-8")
    return str(path)


def disable_autostart() -> None:
    if os.name == "nt":
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                winreg.DeleteValue(key, AUTOSTART_NAME)
        except FileNotFoundError:
            pass
        return

    path = autostart_path()
    if sys.platform == "darwin" and path.exists() and not _under_launchd():
        uid = os.getuid() if hasattr(os, "getuid") else 501
        for args in (
            ["launchctl", "bootout", f"gui/{uid}/{AUTOSTART_LABEL}"],
            ["launchctl", "unload", "-w", str(path)],
        ):
            try:
                subprocess.run(args, capture_output=True, timeout=10, check=False)
            except (OSError, subprocess.SubprocessError):
                pass
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError as exc:
        log(f"Não foi possível remover o autostart: {exc}")


# ---------------------------------------------------------------------------
# Detecção de inatividade (teclado/mouse) em cada sistema
# ---------------------------------------------------------------------------


class IdleMonitor:
    """Descobre o tempo sem entrada do usuário, tentando vários métodos."""

    def __init__(self) -> None:
        self.method = "indisponível"
        self._fn = None
        for name, fn in self._candidates():
            try:
                value = fn()
            except Exception:
                continue
            if value is not None and value >= 0:
                self.method = name
                self._fn = fn
                log(f"Detecção de inatividade: {name}")
                return
        log("Nenhum método de detecção de inatividade disponível")

    def seconds(self) -> float | None:
        if self._fn is None:
            return None
        try:
            value = float(self._fn())
            return max(0.0, value)
        except Exception:
            return None

    @staticmethod
    def _candidates():
        if os.name == "nt":
            yield "Windows (GetLastInputInfo)", _windows_idle
            return

        if sys.platform == "darwin":
            yield "macOS (IOHIDSystem)", _mac_idle
            return

        wayland = os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
        x11_ok = bool(os.environ.get("DISPLAY")) and not wayland

        if x11_ok and shutil.which("xprintidle"):
            yield "X11 (xprintidle)", _xprintidle
        if shutil.which("gdbus"):
            yield "GNOME (Mutter/D-Bus)", _mutter_idle
        if shutil.which("dbus-send"):
            yield "KDE (D-Bus)", _kde_idle
        if not wayland:
            yield "X11 (libXss)", _x11_idle
        if wayland and shutil.which("xprintidle") and os.environ.get("DISPLAY"):
            yield "XWayland (xprintidle)", _xprintidle


def _windows_idle() -> float | None:
    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    if not user32.GetLastInputInfo(ctypes.byref(info)):
        return None
    kernel32.GetTickCount64.restype = ctypes.c_uint64
    tick = int(kernel32.GetTickCount64())
    return ((tick - info.dwTime) & 0xFFFFFFFF) / 1000.0


def _mac_idle() -> float | None:
    out = subprocess.run(
        ["ioreg", "-c", "IOHIDSystem", "-d", "1"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=5,
        check=False,
    ).stdout
    match = re.search(r'"HIDIdleTime"\s*=\s*(\d+)', out)
    if not match:
        return None
    return int(match.group(1)) / 1_000_000_000.0


def _xprintidle() -> float | None:
    out = subprocess.run(
        ["xprintidle"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=5,
        check=False,
    ).stdout.strip()
    if not out.isdigit():
        return None
    return int(out) / 1000.0


def _mutter_idle() -> float | None:
    out = subprocess.run(
        [
            "gdbus",
            "call",
            "--session",
            "--dest",
            "org.gnome.Mutter.IdleMonitor",
            "--object-path",
            "/org/gnome/Mutter/IdleMonitor/Core",
            "--method",
            "org.gnome.Mutter.IdleMonitor.GetIdletime",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=5,
        check=False,
    ).stdout
    match = re.search(r"uint64\s+(\d+)", out)
    if not match:
        return None
    return int(match.group(1)) / 1000.0


def _kde_idle() -> float | None:
    out = subprocess.run(
        [
            "dbus-send",
            "--session",
            "--print-reply",
            "--dest=org.freedesktop.ScreenSaver",
            "/ScreenSaver",
            "org.freedesktop.ScreenSaver.GetSessionIdleTime",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=5,
        check=False,
    ).stdout
    match = re.search(r"uint32\s+(\d+)", out)
    if not match:
        return None
    return float(match.group(1))


def _x11_idle() -> float | None:
    if not os.environ.get("DISPLAY"):
        return None

    class XScreenSaverInfo(ctypes.Structure):
        _fields_ = [
            ("window", ctypes.c_ulong),
            ("state", ctypes.c_int),
            ("kind", ctypes.c_int),
            ("til_or_since", ctypes.c_ulong),
            ("idle", ctypes.c_ulong),
            ("eventMask", ctypes.c_ulong),
        ]

    try:
        x11 = ctypes.CDLL("libX11.so.6")
        xss = ctypes.CDLL("libXss.so.1")
    except OSError:
        return None

    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
    x11.XDefaultRootWindow.restype = ctypes.c_ulong
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    x11.XFree.argtypes = [ctypes.c_void_p]
    xss.XScreenSaverAllocInfo.restype = ctypes.POINTER(XScreenSaverInfo)
    xss.XScreenSaverQueryInfo.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.POINTER(XScreenSaverInfo),
    ]

    display = x11.XOpenDisplay(None)
    if not display:
        return None
    info = xss.XScreenSaverAllocInfo()
    if not info:
        x11.XCloseDisplay(display)
        return None
    try:
        root = x11.XDefaultRootWindow(display)
        if not xss.XScreenSaverQueryInfo(display, root, info):
            return None
        return info.contents.idle / 1000.0
    finally:
        x11.XFree(info)
        x11.XCloseDisplay(display)


# ---------------------------------------------------------------------------
# Captura de tela
# ---------------------------------------------------------------------------


class CaptureError(RuntimeError):
    pass


# Cada comando externo tem um limite curto. Se um deles travar (portal,
# diálogo de permissão etc.), o app desiste e usa o próximo método.
CAPTURE_TOOL_TIMEOUT = 8
# Limite total para a interface: passou disso, mostra só o relógio.
CAPTURE_UI_TIMEOUT = 10


def _gnome_dbus_available() -> bool:
    if os.name == "nt" or sys.platform == "darwin":
        return False
    if not shutil.which("gdbus"):
        return False
    desktop = (
        os.environ.get("XDG_CURRENT_DESKTOP")
        or os.environ.get("DESKTOP_SESSION")
        or ""
    ).lower()
    if "gnome" in desktop or "ubuntu" in desktop:
        return True
    return os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"


def available_capture_backends() -> list[str]:
    """Lista os métodos de captura na mesma ordem em que serão tentados."""
    try:
        return [name for name, _ in _capture_candidates(None)]
    except Exception:  # noqa: BLE001
        return []


def capture_screen(region: tuple[int, int, int, int] | None = None):
    """Captura a tela inteira usando o melhor método disponível."""
    if Image is None:
        raise CaptureError("Pillow não está instalado (pip install pillow)")

    errors: list[str] = []
    for name, fn in _capture_candidates(region):
        try:
            image = fn()
            return _validar_captura(image)
        except Exception as exc:  # noqa: BLE001 - queremos tentar o próximo
            errors.append(f"{name}: {exc}")
            log(f"Captura: {name} falhou: {exc}")
            continue
    detail = " | ".join(errors) if errors else "nenhum método disponível"
    raise CaptureError(detail)


def _validar_captura(image):
    if image is None:
        raise RuntimeError("imagem vazia")
    if image.width < 10 or image.height < 10:
        raise RuntimeError(f"imagem pequena demais ({image.width}x{image.height})")
    if image.mode != "RGB":
        image = image.convert("RGB")
    # Captura 100% preta costuma ser falha do XWayland/sem permissão.
    if image.getbbox() is None:
        raise RuntimeError("captura saiu toda preta (falta permissão?)")
    return image


def _bounded_call(fn, seconds: float, rotulo: str):
    """Executa fn() numa thread e desiste depois de `seconds`.

    Serve para bibliotecas que não aceitam timeout (caso do ImageGrab no
    Linux, que pode chamar um comando externo e travar).
    """
    resultado: dict[str, object] = {}

    def worker() -> None:
        try:
            resultado["valor"] = fn()
        except BaseException as exc:  # noqa: BLE001
            resultado["erro"] = exc

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(seconds)
    if thread.is_alive():
        raise RuntimeError(f"{rotulo} demorou mais de {seconds:.0f}s")
    if "erro" in resultado:
        erro = resultado["erro"]
        if isinstance(erro, Exception):
            raise erro
        raise RuntimeError(str(erro))
    return resultado.get("valor")


def _capture_candidates(region):
    if os.name == "nt":
        yield "Pillow", _grab_pillow
        return

    if sys.platform == "darwin":
        yield "screencapture", lambda: _grab_tool_macos(region)
        yield "Pillow", _grab_pillow
        return

    wayland = os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
    tools = [
        ("grim", lambda path: ["grim", path]),
        ("gnome-screenshot", lambda path: ["gnome-screenshot", "-f", path]),
        ("spectacle", lambda path: ["spectacle", "-b", "-n", "-o", path]),
        ("scrot", lambda path: ["scrot", path]),
        ("maim", lambda path: ["maim", path]),
        ("import", lambda path: ["import", "-window", "root", path]),
        (
            "xfce4-screenshooter",
            lambda path: ["xfce4-screenshooter", "-f", "-s", path],
        ),
    ]

    def tool_candidate(name, builder):
        if not shutil.which(name):
            return None
        return lambda: _grab_tool(builder, name)

    if wayland:
        # No GNOME/Wayland o grim não funciona; o caminho certo é o D-Bus do
        # GNOME Shell (sem diálogo) e, depois, ferramentas do ambiente.
        if _gnome_dbus_available():
            yield "GNOME Shell (D-Bus)", _grab_gnome_dbus
        for name, builder in tools:
            candidate = tool_candidate(name, builder)
            if candidate:
                yield name, candidate
        # XWayland costuma sair preto; fica como último recurso.
        yield "Pillow (XWayland)", _grab_pillow_seguro
    else:
        yield "Pillow (X11)", _grab_pillow_seguro
        if _gnome_dbus_available():
            yield "GNOME Shell (D-Bus)", _grab_gnome_dbus
        for name, builder in tools:
            candidate = tool_candidate(name, builder)
            if candidate:
                yield name, candidate


def _grab_pillow_seguro():
    return _bounded_call(_grab_pillow, CAPTURE_TOOL_TIMEOUT, "ImageGrab")


def _grab_pillow():
    try:
        image = ImageGrab.grab()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"ImageGrab falhou ({exc})") from exc
    if image is None or image.width < 10 or image.height < 10:
        raise RuntimeError("imagem vazia")
    return image


def _grab_gnome_dbus():
    """Captura no GNOME (X11 ou Wayland) pela API D-Bus do Shell."""
    with tempfile.TemporaryDirectory(prefix="relogio-vivo-") as tmp:
        path = os.path.join(tmp, "capture.png")
        cmd = [
            "gdbus",
            "call",
            "--session",
            "--dest",
            "org.gnome.Shell",
            "--object-path",
            "/org/gnome/Shell/Screenshot",
            "--method",
            "org.gnome.Shell.Screenshot.Screenshot",
            "false",
            "false",
            path,
        ]
        out = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=CAPTURE_TOOL_TIMEOUT,
            check=False,
        )
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            detalhe = (out.stderr or out.stdout or "").strip()[:200]
            raise RuntimeError(f"GNOME não gerou imagem ({detalhe})")
        with Image.open(path) as image:
            image.load()
            return image.convert("RGB")


def _grab_tool_macos(region):
    with tempfile.TemporaryDirectory(prefix="relogio-vivo-") as tmp:
        path = os.path.join(tmp, "capture.png")
        cmd = ["screencapture", "-x", "-t", "png"]
        if region:
            x, y, w, h = region
            cmd += ["-R", f"{x},{y},{w},{h}"]
        cmd.append(path)
        subprocess.run(
            cmd, capture_output=True, timeout=CAPTURE_TOOL_TIMEOUT, check=False
        )
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            raise RuntimeError(
                "screencapture não gerou imagem (permissão de Gravação de Tela?)"
            )
        with Image.open(path) as image:
            image.load()
            return image.convert("RGB")


def _grab_tool(builder, nome="ferramenta"):
    with tempfile.TemporaryDirectory(prefix="relogio-vivo-") as tmp:
        path = os.path.join(tmp, "capture.png")
        out = subprocess.run(
            builder(path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=CAPTURE_TOOL_TIMEOUT,
            check=False,
        )
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            detalhe = (out.stderr or out.stdout or "").strip()[:200]
            raise RuntimeError(f"{nome} não gerou imagem ({detalhe})")
        with Image.open(path) as image:
            image.load()
            return image.convert("RGB")


# ---------------------------------------------------------------------------
# Composição visual (fundo + cartão com sombra)
# ---------------------------------------------------------------------------


@dataclass
class Scene:
    background: object
    card: object
    screen_w: int
    screen_h: int
    card_w: int
    card_h: int
    pad: int
    bar_h: int
    time_px: int
    date_px: int
    margin: int
    bob: int
    mode: str = MODE_TELA


def _fit_cover(image, width: int, height: int):
    scale = max(width / image.width, height / image.height)
    new_w = max(1, math.ceil(image.width * scale))
    new_h = max(1, math.ceil(image.height * scale))
    resized = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = max(0, (new_w - width) // 2)
    top = max(0, (new_h - height) // 2)
    return resized.crop((left, top, left + width, top + height))


def _rounded_mask(size: tuple[int, int], radius: int):
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return mask


def format_date(lt: time.struct_time) -> str:
    weekday = DIAS[lt.tm_wday].capitalize()
    return f"{weekday}, {lt.tm_mday} de {MESES[lt.tm_mon - 1]} de {lt.tm_year}"


def build_scene(shot, screen_w: int, screen_h: int) -> Scene:
    """Monta o fundo desfocado e o cartão que vai deslizar pela tela."""
    card_w = int(min(screen_w * 0.62, screen_h * 1.15))
    card_h = int(card_w / 1.6)
    max_h = int(screen_h * 0.76)
    if card_h > max_h:
        card_h = max_h
        card_w = int(card_h * 1.6)
    card_w = max(260, min(card_w, screen_w - 40))
    card_h = max(170, min(card_h, screen_h - 40))
    pad = max(16, card_w // 38)
    bar_h = int(card_h * 0.30)
    time_px = max(26, int(card_h * 0.135))
    date_px = max(11, int(card_h * 0.042))
    margin = max(24, int(screen_w * 0.035))
    bob = max(5, int(screen_h * 0.012))

    # Fundo: captura cobrindo a tela, desfocada, escurecida e com vinheta.
    background = _fit_cover(shot, screen_w, screen_h)
    background = background.filter(ImageFilter.GaussianBlur(min(36, max(10, screen_w // 90))))
    background = ImageEnhance.Brightness(background).enhance(0.34)
    background = background.convert("RGBA")
    background = Image.alpha_composite(
        background, Image.new("RGBA", (screen_w, screen_h), (8, 13, 24, 70))
    )
    try:
        vignette = Image.radial_gradient("L").resize((screen_w, screen_h))
        shade = Image.new("RGBA", (screen_w, screen_h), (0, 0, 0, 0))
        shade.putalpha(vignette.point(lambda value: int(value * 0.55)))
        background = Image.alpha_composite(background, shade)
    except Exception:
        pass
    background = background.convert("RGB")

    # Cartão: a captura em tamanho menor, com uma barra escura embaixo.
    card = _fit_cover(shot, card_w, card_h)
    card = ImageEnhance.Brightness(card).enhance(0.92)
    card = ImageEnhance.Color(card).enhance(1.04).convert("RGBA")

    gradient = Image.new("RGBA", (card_w, bar_h), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(gradient)
    for row in range(bar_h):
        t = row / max(1, bar_h - 1)
        alpha = int(30 + 190 * (t ** 1.6))
        gdraw.line([(0, row), (card_w, row)], fill=(4, 7, 13, alpha))
    gdraw.line([(0, 0), (card_w, 0)], fill=(255, 255, 255, 28), width=1)
    card.alpha_composite(gradient, (0, card_h - bar_h))

    radius = max(10, int(card_h * 0.045))
    card.putalpha(_rounded_mask((card_w, card_h), radius))

    border = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
    ImageDraw.Draw(border).rounded_rectangle(
        (0, 0, card_w - 1, card_h - 1),
        radius=radius,
        outline=(255, 255, 255, 42),
        width=max(1, card_w // 500),
    )
    card = Image.alpha_composite(card, border)

    # Sombra suave atrás do cartão.
    total = (card_w + pad * 2, card_h + pad * 2)
    composed = Image.new("RGBA", total, (0, 0, 0, 0))
    shadow = Image.new("RGBA", total, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (pad, pad + 10, pad + card_w, pad + card_h + 10),
        radius=radius,
        fill=(0, 0, 0, 165),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(max(8, pad * 0.55)))
    composed.alpha_composite(shadow)
    composed.alpha_composite(card, (pad, pad))

    return Scene(
        background=background,
        card=composed,
        screen_w=screen_w,
        screen_h=screen_h,
        card_w=card_w,
        card_h=card_h,
        pad=pad,
        bar_h=bar_h,
        time_px=time_px,
        date_px=date_px,
        margin=margin,
        bob=bob,
    )


def _clock_background(screen_w: int, screen_h: int):
    """Fundo escuro em degradê com um brilho suave atrás do relógio.

    Não usa captura de tela — funciona igual em qualquer sistema e não
    precisa de permissão de gravação de tela.
    """
    image = Image.new("RGB", (screen_w, screen_h), (5, 8, 15))
    draw = ImageDraw.Draw(image)
    top = (12, 20, 38)
    bottom = (3, 5, 10)
    for y in range(screen_h):
        t = y / max(1, screen_h - 1)
        color = tuple(
            int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)
        )
        draw.line([(0, y), (screen_w, y)], fill=color)

    try:
        glow = Image.new("RGBA", (screen_w, screen_h), (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glow)
        radius = int(min(screen_w, screen_h) * 0.46)
        cx, cy = screen_w // 2, screen_h // 2
        steps = 26
        for step in range(steps, 0, -1):
            r = max(1, int(radius * step / steps))
            fade = 1 - step / steps
            alpha = int(2 + 26 * (fade ** 1.6))
            gdraw.ellipse(
                (cx - r, cy - r, cx + r, cy + r),
                fill=(94, 234, 212, alpha),
            )
        glow = glow.filter(ImageFilter.GaussianBlur(max(10, radius // 10)))
        image = Image.alpha_composite(
            image.convert("RGBA"), glow
        ).convert("RGB")
    except Exception:
        pass

    return image


def build_clock_scene(screen_w: int, screen_h: int) -> Scene:
    """Monta a cena do modo "só o relógio" (sem captura da tela)."""
    time_px = max(56, int(screen_h * 0.235))
    date_px = max(14, int(screen_h * 0.042))
    return Scene(
        background=_clock_background(screen_w, screen_h),
        card=Image.new("RGBA", (4, 4), (0, 0, 0, 0)),
        screen_w=screen_w,
        screen_h=screen_h,
        card_w=int(screen_w * 0.92),
        card_h=int(screen_h * 0.55),
        pad=0,
        bar_h=0,
        time_px=time_px,
        date_px=date_px,
        margin=0,
        bob=max(3, int(screen_h * 0.009)),
        mode=MODE_RELOGIO,
    )


def _preview_font(size: int):
    """Fonte aproximada para a prévia em PNG (sem depender da Tk)."""
    if ImageFont is None:
        return None
    candidates = (
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "DejaVuSans-Bold.ttf",
        "Arial Bold.ttf",
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except (OSError, ValueError):
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()
    except Exception:
        return None


def save_snapshot(path: str, mode: str = MODE_TELA) -> Path:
    """Diagnóstico: salva a cena do modo escolhido em um PNG."""
    if Image is None:
        raise CaptureError("Pillow não está instalado (pip install pillow)")
    if mode == MODE_RELOGIO:
        try:
            screen_w = int(os.environ.get("RELOGIO_VIVO_SNAPSHOT_W") or 0)
            screen_h = int(os.environ.get("RELOGIO_VIVO_SNAPSHOT_H") or 0)
        except ValueError:
            screen_w, screen_h = 0, 0
        if screen_w <= 0 or screen_h <= 0:
            try:
                probe = tk.Tk()
                probe.withdraw()
                screen_w = probe.winfo_screenwidth()
                screen_h = probe.winfo_screenheight()
                probe.destroy()
            except Exception:
                screen_w, screen_h = 1920, 1080
        scene = build_clock_scene(screen_w, screen_h)
        canvas = scene.background.convert("RGBA")
        draw = ImageDraw.Draw(canvas)
        clock = time.strftime("%H:%M:%S", time.localtime())
        date = format_date(time.localtime())
        time_font = _preview_font(scene.time_px)
        date_font = _preview_font(scene.date_px)
        center_x = screen_w // 2
        time_y = int(screen_h * 0.46)
        date_y = int(screen_h * 0.61)
        if time_font is not None:
            draw.text(
                (center_x + 3, time_y + 3),
                clock,
                font=time_font,
                anchor="mm",
                fill=(0, 0, 0, 170),
            )
            draw.text(
                (center_x, time_y),
                clock,
                font=time_font,
                anchor="mm",
                fill=(255, 255, 255, 255),
            )
        if date_font is not None:
            draw.text(
                (center_x, date_y),
                date,
                font=date_font,
                anchor="mm",
                fill=(198, 210, 228, 255),
            )
    else:
        shot = capture_screen()
        scene = build_scene(shot, shot.width, shot.height)
        canvas = scene.background.convert("RGBA")
        x = (scene.screen_w - scene.card_w) // 2 - scene.pad
        y = (scene.screen_h - scene.card_h) // 2 - scene.pad
        canvas.alpha_composite(scene.card, (x, y))
    out = Path(path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out)
    return out


# ---------------------------------------------------------------------------
# Janela do protetor de tela
# ---------------------------------------------------------------------------


def pick_family(root) -> str:
    try:
        available = {name.lower(): name for name in tkfont.families(root)}
    except tk.TclError:
        return "TkDefaultFont"
    for candidate in (
        "Segoe UI Variable Text",
        "Segoe UI",
        "SF Pro Text",
        "SF Pro Display",
        "Helvetica Neue",
        "Inter",
        "DejaVu Sans",
        "Noto Sans",
        "Ubuntu",
        "Liberation Sans",
        "Arial",
    ):
        if candidate.lower() in available:
            return available[candidate.lower()]
    try:
        return tkfont.nametofont("TkDefaultFont").actual("family")
    except tk.TclError:
        return "TkDefaultFont"


class ScreensaverWindow:
    """Tela cheia com o relógio ao vivo.

    No modo "prévia da tela" o cartão desliza sobre a captura desfocada.
    No modo "só o relógio" a hora grande e a data ficam centralizadas,
    flutuando de leve sobre um fundo escuro (sem captura).
    """

    def __init__(
        self, master, scene: Scene, family: str, on_close, idle_probe=None
    ) -> None:
        self.master = master
        self.scene = scene
        self.clock_only = scene.mode == MODE_RELOGIO
        self.on_close = on_close
        self.idle_probe = idle_probe
        self.closed = False
        self._after_id = None
        self._fade_id = None
        self._baseline_idle = None
        if idle_probe is not None:
            try:
                self._baseline_idle = idle_probe()
            except Exception:
                self._baseline_idle = None
        self._idle_check_at = time.monotonic() + 1.5

        self.top = tk.Toplevel(master)
        self.top.title(APP_NAME)
        self.top.configure(bg="#05070c")
        self.top.withdraw()

        self.canvas = tk.Canvas(
            self.top,
            width=scene.screen_w,
            height=scene.screen_h,
            bg="#05070c",
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)

        self.bg_photo = ImageTk.PhotoImage(scene.background, master=self.top)
        self.canvas.create_image(0, 0, anchor="nw", image=self.bg_photo)
        if self.clock_only:
            self.card_photo = None
            self.card_item = None
        else:
            self.card_photo = ImageTk.PhotoImage(scene.card, master=self.top)
            self.card_item = self.canvas.create_image(
                0, 0, anchor="nw", image=self.card_photo
            )

        self.time_font = tkfont.Font(
            family=family, size=-scene.time_px, weight="bold"
        )
        date_px = scene.date_px
        self.date_font = tkfont.Font(family=family, size=-date_px)
        sample = format_date(time.localtime())
        date_limit = (
            scene.screen_w * 0.90 if self.clock_only else scene.card_w * 0.90
        )
        while self.date_font.measure(sample) > date_limit and date_px > 10:
            date_px -= 1
            self.date_font.configure(size=-date_px)
        self.hint_font = tkfont.Font(
            family=family, size=-max(12, scene.screen_h // 85)
        )

        self.time_shadow = self.canvas.create_text(
            0, 0, text="", fill="#000000", font=self.time_font, anchor="center"
        )
        self.time_text = self.canvas.create_text(
            0, 0, text="", fill="#ffffff", font=self.time_font, anchor="center"
        )
        self.date_shadow = self.canvas.create_text(
            0, 0, text="", fill="#000000", font=self.date_font, anchor="center"
        )
        self.date_text = self.canvas.create_text(
            0, 0, text="", fill="#dfe7f5", font=self.date_font, anchor="center"
        )
        self.hint = self.canvas.create_text(
            scene.screen_w // 2,
            scene.screen_h - max(24, scene.screen_h // 32),
            text="Mova o mouse ou pressione qualquer tecla para sair",
            fill="#7d879b",
            font=self.hint_font,
            anchor="center",
        )

        self._place_window()
        self._bind_input()

        self.t0 = time.monotonic()
        self.last_frame = self.t0
        self.last_clock = 0.0
        self.x = float(scene.margin)
        self.direction = 1
        self.speed = max(45.0, scene.screen_w * 0.045)
        self.start_pointer = self.top.winfo_pointerxy()
        self.input_armed_at = time.monotonic() + 0.6

        self._update_clock()
        self.top.deiconify()
        self.top.lift()
        try:
            self.top.focus_force()
        except tk.TclError:
            pass
        try:
            self.top.configure(cursor="none")
        except tk.TclError:
            pass

        self._fade_in()
        self._animate()

    # -- janela ---------------------------------------------------------
    def _place_window(self) -> None:
        scene = self.scene
        self.top.geometry(f"{scene.screen_w}x{scene.screen_h}+0+0")
        if sys.platform == "darwin":
            try:
                self.top.attributes("-fullscreen", True)
            except tk.TclError:
                pass
        else:
            try:
                self.top.overrideredirect(True)
            except tk.TclError:
                pass
        try:
            self.top.attributes("-topmost", True)
        except tk.TclError:
            pass

    def _bind_input(self) -> None:
        for sequence in ("<KeyPress>", "<ButtonPress>", "<MouseWheel>"):
            self.top.bind(sequence, self._on_input)
        self.top.bind("<Button-4>", self._on_input)
        self.top.bind("<Button-5>", self._on_input)
        self.top.bind("<Motion>", self._on_motion)
        self.top.bind("<Escape>", self._on_input)

    def _fade_in(self) -> None:
        try:
            self.top.attributes("-alpha", 0.0)
        except tk.TclError:
            return

        def step(level: int = 1) -> None:
            if self.closed:
                return
            try:
                self.top.attributes("-alpha", min(1.0, level / 10))
            except tk.TclError:
                return
            if level < 10:
                self._fade_id = self.top.after(28, step, level + 1)

        self._fade_id = self.top.after(20, step)

    # -- entrada --------------------------------------------------------
    def _on_input(self, _event=None) -> None:
        if time.monotonic() < self.input_armed_at:
            return
        self.close()

    def _on_motion(self, _event=None) -> None:
        if time.monotonic() < self.input_armed_at:
            return
        try:
            x, y = self.top.winfo_pointerxy()
        except tk.TclError:
            return
        if abs(x - self.start_pointer[0]) + abs(y - self.start_pointer[1]) > 28:
            self.close()

    # -- animação -------------------------------------------------------
    def _animate(self) -> None:
        if self.closed:
            return
        scene = self.scene
        now = time.monotonic()
        dt = min(0.06, max(0.001, now - self.last_frame))
        self.last_frame = now
        elapsed = now - self.t0

        min_x = float(scene.margin)
        max_x = float(max(min_x, scene.screen_w - scene.card_w - scene.margin))

        if self.clock_only:
            # Relógio grande centralizado, com uma flutuação bem leve.
            bob = math.sin(elapsed * 0.55) * scene.bob
            center_x = scene.screen_w / 2
            time_y = scene.screen_h * 0.465 + bob
            date_y = scene.screen_h * 0.615 + bob
        else:
            self.x += self.speed * self.direction * dt
            if self.x >= max_x:
                self.x = max_x
                self.direction = -1
            elif self.x <= min_x:
                self.x = min_x
                self.direction = 1

            bob = math.sin(elapsed * 0.9) * scene.bob
            y = (scene.screen_h - scene.card_h) / 2 + bob

            if self.card_item is not None:
                self.canvas.coords(
                    self.card_item, self.x - scene.pad, y - scene.pad
                )
            center_x = self.x + scene.card_w / 2
            time_y = y + scene.card_h - scene.bar_h * 0.60
            date_y = y + scene.card_h - scene.bar_h * 0.22

        self.canvas.coords(self.time_shadow, center_x, time_y + 2)
        self.canvas.coords(self.time_text, center_x, time_y)
        self.canvas.coords(self.date_shadow, center_x, date_y + 2)
        self.canvas.coords(self.date_text, center_x, date_y)

        if now - self.last_clock > 0.2:
            self.last_clock = now
            self._update_clock()

        # Rede de segurança: se o sistema voltou a receber entrada mas o evento
        # não chegou ao Tk (foco do Wayland, por exemplo), fecha mesmo assim.
        if (
            self.idle_probe is not None
            and self._baseline_idle is not None
            and self._baseline_idle >= 5
            and now >= self._idle_check_at
        ):
            self._idle_check_at = now + 1.5
            try:
                current = self.idle_probe()
            except Exception:
                current = None
            if current is not None and current < 1.5:
                self.close()
                return

        self._after_id = self.top.after(33, self._animate)

    def _update_clock(self) -> None:
        if self.closed:
            return
        lt = time.localtime()
        clock = time.strftime("%H:%M:%S", lt)
        date = format_date(lt)
        for item in (self.time_shadow, self.time_text):
            self.canvas.itemconfigure(item, text=clock)
        for item in (self.date_shadow, self.date_text):
            self.canvas.itemconfigure(item, text=date)

    # -- fim ------------------------------------------------------------
    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        for after_id in (self._after_id, self._fade_id):
            if after_id:
                try:
                    self.top.after_cancel(after_id)
                except tk.TclError:
                    pass
        try:
            self.top.destroy()
        except tk.TclError:
            pass
        try:
            self.on_close()
        except Exception:
            log("Erro ao fechar o protetor:\n" + traceback.format_exc())


# ---------------------------------------------------------------------------
# Janela de configurações
# ---------------------------------------------------------------------------


def _fmt_seconds(value: float) -> str:
    total = max(0, int(value))
    minutes, seconds = divmod(total, 60)
    if minutes and minutes >= 60:
        hours, minutes = divmod(minutes, 60)
        return f"{hours} h {minutes} min"
    if minutes:
        return f"{minutes} min {seconds:02d} s"
    return f"{seconds} s"


class SettingsWindow:
    def __init__(self, app) -> None:
        self.app = app
        self.root = app.root
        self.family = app.ui_family
        self._save_job = None
        self._built = False

        self.root.title(f"{APP_NAME} · configurações")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.hide)
        self._build()
        self._center()
        self._refresh_autostart()
        self._refresh_status()
        self._built = True

    # -- construção -----------------------------------------------------
    def _build(self) -> None:
        shell = tk.Frame(self.root, bg=BG)
        shell.pack(fill="both", expand=True)

        self.footer = tk.Frame(shell, bg=BG)
        self.footer.pack(side="bottom", fill="x", padx=28, pady=(4, 14))
        self._button(
            self.footer, "Encerrar app", self.app.quit_app, danger=True
        ).pack(side="right")
        self._button(self.footer, "Fechar janela", self.hide).pack(
            side="right", padx=(0, 8)
        )
        tk.Label(
            self.footer,
            text="Continua ativo em segundo plano.",
            bg=BG,
            fg=MUTED,
            font=(self.family, 9),
        ).pack(side="left")

        holder = tk.Frame(shell, bg=BG)
        holder.pack(side="top", fill="both", expand=True)
        self.body = tk.Canvas(
            holder, bg=BG, highlightthickness=0, bd=0, yscrollincrement=22
        )
        self.scrollbar = tk.Scrollbar(
            holder,
            orient="vertical",
            command=self.body.yview,
            bg=CARD_ALT,
            troughcolor=BG,
            activebackground=BORDER,
            bd=0,
            highlightthickness=0,
            width=10,
        )
        self.body.configure(yscrollcommand=self._scroll_set)
        self.body.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.body, bg=BG)
        self._inner_window = self.body.create_window(
            (0, 0), window=self.inner, anchor="nw"
        )
        self.inner.bind("<Configure>", self._inner_configured)
        self.body.bind("<Configure>", self._body_configured)
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.root.bind(sequence, self._on_wheel)

        wrap = tk.Frame(self.inner, bg=BG)
        wrap.pack(fill="both", expand=True, padx=28, pady=(20, 6))
        tk.Label(
            wrap,
            text="PROTETOR DE TELA",
            bg=BG,
            fg=ACCENT,
            font=(self.family, 9, "bold"),
        ).pack(anchor="w")
        tk.Label(
            wrap,
            text=APP_NAME,
            bg=BG,
            fg=TEXT,
            font=(self.family, 26, "bold"),
        ).pack(anchor="w", pady=(2, 0))
        tk.Label(
            wrap,
            text="Depois de alguns minutos sem tocar no teclado ou mouse,\n"
            "o protetor aparece com a prévia da sua tela ou só com o relógio.",
            bg=BG,
            fg=MUTED,
            font=(self.family, 10),
            justify="left",
        ).pack(anchor="w", pady=(4, 18))

        self._build_mode_card(wrap)
        self._build_idle_card(wrap)
        self._build_autostart_card(wrap)
        self._build_test_card(wrap)

        self.status_lbl = tk.Label(
            wrap,
            text="",
            bg=BG,
            fg=MUTED,
            font=(self.family, 9),
            anchor="w",
            justify="left",
            wraplength=600,
        )
        self.status_lbl.pack(fill="x", pady=(0, 10))

    def _scroll_set(self, first: str, last: str) -> None:
        if float(first) <= 0.0 and float(last) >= 1.0:
            self.scrollbar.pack_forget()
        else:
            self.scrollbar.pack(side="right", fill="y")

    def _inner_configured(self, _event=None) -> None:
        self.body.configure(scrollregion=self.body.bbox("all"))

    def _body_configured(self, event) -> None:
        self.body.itemconfigure(self._inner_window, width=event.width)

    def _on_wheel(self, event) -> None:
        first, last = self.body.yview()
        if first <= 0.0 and last >= 1.0:
            return
        if getattr(event, "num", None) == 4:
            step = -1
        elif getattr(event, "num", None) == 5:
            step = 1
        else:
            step = -1 if event.delta > 0 else 1
        self.body.yview_scroll(step, "units")

    def _card(self, parent) -> tk.Frame:
        outer = tk.Frame(
            parent, bg=CARD, highlightbackground=BORDER, highlightthickness=1
        )
        outer.pack(fill="x", pady=(0, 12))
        inner = tk.Frame(outer, bg=CARD)
        inner.pack(fill="x", padx=18, pady=14)
        return inner

    def _button(self, parent, text, command, primary=False, danger=False) -> tk.Button:
        if primary:
            normal, hover, fg = ACCENT, ACCENT_HOVER, "#071019"
        elif danger:
            normal, hover, fg = CARD_ALT, "#3a1d24", DANGER
        else:
            normal, hover, fg = CARD_ALT, BORDER, TEXT
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=normal,
            fg=fg,
            activebackground=hover,
            activeforeground=fg,
            relief="flat",
            bd=0,
            padx=16,
            pady=8,
            font=(self.family, 10, "bold"),
            cursor="hand2",
            highlightthickness=0,
        )
        button.bind("<Enter>", lambda _e: button.configure(bg=hover))
        button.bind("<Leave>", lambda _e: button.configure(bg=normal))
        return button

    def _chip(self, parent, text, command) -> tk.Button:
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=CARD_ALT,
            fg=MUTED,
            activebackground=BORDER,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            padx=9,
            pady=3,
            font=(self.family, 9),
            cursor="hand2",
            highlightthickness=0,
        )
        button.bind("<Enter>", lambda _e: button.configure(fg=TEXT))
        button.bind("<Leave>", lambda _e: button.configure(fg=MUTED))
        return button

    def _build_mode_card(self, parent) -> None:
        card = self._card(parent)
        tk.Label(
            card,
            text="Estilo do protetor",
            bg=CARD,
            fg=TEXT,
            font=(self.family, 11, "bold"),
        ).pack(anchor="w")

        self.mode_var = tk.StringVar(value=self.app.cfg.mode)
        options = (
            (
                MODE_TELA,
                "Prévia da tela",
                "Captura a tela antes de ativar, escurece e desfoca a imagem "
                "e coloca a hora e a data em um cartão que desliza.",
            ),
            (
                MODE_RELOGIO,
                "Só o relógio",
                "Não captura nada. Mostra a hora grande e a data no centro, "
                "sobre um fundo escuro. Funciona em qualquer sistema, sem "
                "pedir permissão de gravação de tela.",
            ),
        )
        for value, title, description in options:
            row = tk.Frame(card, bg=CARD)
            row.pack(fill="x", pady=(10, 0))
            tk.Radiobutton(
                row,
                text=title,
                variable=self.mode_var,
                value=value,
                command=self._apply_mode,
                bg=CARD,
                fg=TEXT,
                activebackground=CARD,
                activeforeground=TEXT,
                selectcolor=ACCENT,
                font=(self.family, 10, "bold"),
                bd=0,
                highlightthickness=0,
                anchor="w",
                cursor="hand2",
            ).pack(anchor="w")
            tk.Label(
                card,
                text=description,
                bg=CARD,
                fg=MUTED,
                font=(self.family, 9),
                wraplength=520,
                justify="left",
            ).pack(anchor="w", padx=(24, 0), pady=(1, 0))

    def _apply_mode(self) -> None:
        self.app.set_mode(self.mode_var.get())
        self._refresh_mode_hint()

    def _refresh_mode_hint(self) -> None:
        if self.app.cfg.mode == MODE_RELOGIO:
            text = (
                "Abre o protetor só com o relógio grande, sem capturar a tela. "
                "Mova o mouse ou pressione qualquer tecla para sair."
            )
        else:
            text = (
                "Captura a tela e abre o protetor com a prévia desfocada. "
                "Mova o mouse ou pressione qualquer tecla para sair."
            )
            if not available_capture_backends():
                text += (
                    "\nNenhum método de captura encontrado. Rode de novo o "
                    "instalador (ele instala o que falta) ou escolha "
                    "“Só o relógio”."
                )
        self.test_help.configure(text=text)

    def _build_idle_card(self, parent) -> None:
        card = self._card(parent)
        row = tk.Frame(card, bg=CARD)
        row.pack(fill="x")
        tk.Label(
            row,
            text="Ativar depois de",
            bg=CARD,
            fg=TEXT,
            font=(self.family, 11, "bold"),
        ).pack(side="left")
        self.value_lbl = tk.Label(
            row,
            text="",
            bg=CARD,
            fg=ACCENT,
            font=(self.family, 17, "bold"),
        )
        self.value_lbl.pack(side="right")

        self.scale = tk.Scale(
            card,
            from_=1,
            to=60,
            orient="horizontal",
            resolution=1,
            showvalue=0,
            command=self._on_scale,
            bg=CARD,
            fg=TEXT,
            troughcolor="#070a10",
            activebackground=ACCENT,
            highlightthickness=0,
            bd=0,
            sliderrelief="flat",
            sliderlength=20,
            width=8,
        )
        self.scale.pack(fill="x", pady=(10, 8))
        self.scale.set(self.app.cfg.idle_minutes)

        presets = tk.Frame(card, bg=CARD)
        presets.pack(fill="x")
        for minutes in (1, 3, 5, 10, 15, 30):
            self._chip(
                presets, f"{minutes} min", lambda m=minutes: self._set_minutes(m)
            ).pack(side="left", padx=(0, 6))

        tk.Label(
            card,
            text="O relógio aparece após esse tempo sem teclado ou mouse. "
            "Ajuste de 1 a 60 minutos.",
            bg=CARD,
            fg=MUTED,
            font=(self.family, 9),
            wraplength=540,
            justify="left",
        ).pack(anchor="w", pady=(10, 0))
        self._refresh_value()

    def _build_autostart_card(self, parent) -> None:
        card = self._card(parent)
        row = tk.Frame(card, bg=CARD)
        row.pack(fill="x")
        self.autostart_var = tk.BooleanVar(value=self.app.cfg.autostart)
        self.autostart_cb = tk.Checkbutton(
            row,
            text="Iniciar com o computador",
            variable=self.autostart_var,
            command=self._toggle_autostart,
            bg=CARD,
            fg=TEXT,
            activebackground=CARD,
            activeforeground=TEXT,
            selectcolor=ACCENT,
            font=(self.family, 11, "bold"),
            bd=0,
            highlightthickness=0,
            anchor="w",
            cursor="hand2",
        )
        self.autostart_cb.pack(side="left")
        self.autostart_state = tk.Label(
            row, text="", bg=CARD, fg=MUTED, font=(self.family, 9)
        )
        self.autostart_state.pack(side="right")
        tk.Label(
            card,
            text="Cria o arquivo de inicialização automática do seu sistema "
            "(Windows, Ubuntu ou macOS). O app pede sua permissão antes de ativar.",
            bg=CARD,
            fg=MUTED,
            font=(self.family, 9),
            wraplength=540,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

    def _build_test_card(self, parent) -> None:
        card = self._card(parent)
        row = tk.Frame(card, bg=CARD)
        row.pack(fill="x")
        tk.Label(
            row,
            text="Ver como fica",
            bg=CARD,
            fg=TEXT,
            font=(self.family, 11, "bold"),
        ).pack(side="left")
        self._button(row, "Testar agora", self.app.start_test, primary=True).pack(
            side="right"
        )
        self.test_help = tk.Label(
            card,
            text="",
            bg=CARD,
            fg=MUTED,
            font=(self.family, 9),
            wraplength=540,
            justify="left",
        )
        self.test_help.pack(anchor="w", pady=(6, 0))
        self._refresh_mode_hint()

    def _center(self) -> None:
        self.root.update_idletasks()
        width = max(
            660,
            self.inner.winfo_reqwidth() + 16,
            self.footer.winfo_reqwidth() + 8,
        )
        content_height = self.inner.winfo_reqheight()
        footer_height = self.footer.winfo_reqheight()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width = min(width, max(320, screen_w - 40))
        height = min(
            content_height + footer_height + 22, max(360, screen_h - 90)
        )
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2 - 20)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.update_idletasks()
        self._inner_configured()

    # -- ações ----------------------------------------------------------
    def _on_scale(self, value) -> None:
        minutes = max(1, min(60, int(round(float(value)))))
        self._refresh_value(minutes)
        self.app.set_idle_minutes(minutes)
        self._refresh_status()
        if self._built:
            self._schedule_save()

    def _set_minutes(self, minutes: int) -> None:
        self.scale.set(minutes)
        self._on_scale(minutes)

    def _refresh_value(self, minutes: int | None = None) -> None:
        value = self.app.cfg.idle_minutes if minutes is None else minutes
        self.value_lbl.configure(text=f"{value} min")

    def _schedule_save(self) -> None:
        if self._save_job is not None:
            try:
                self.root.after_cancel(self._save_job)
            except tk.TclError:
                pass
        self._save_job = self.root.after(350, self.app.save_config)

    def _refresh_autostart(self) -> None:
        enabled = is_autostart_enabled()
        self.autostart_var.set(enabled)
        self.app.cfg.autostart = enabled
        self.autostart_state.configure(
            text="Ativo" if enabled else "Desativado",
            fg=ACCENT if enabled else MUTED,
        )

    def _toggle_autostart(self) -> None:
        want = bool(self.autostart_var.get())
        try:
            if want:
                enable_autostart()
            else:
                disable_autostart()
        except Exception as exc:  # noqa: BLE001
            log(f"Falha ao configurar autostart: {exc}")
            messagebox.showerror(
                APP_NAME,
                "Não foi possível alterar a inicialização automática:\n\n"
                f"{exc}",
                parent=self.root,
            )
            self.autostart_var.set(not want)
            return
        self.app.cfg.autostart = want
        self.app.save_config()
        self._refresh_autostart()
        self._refresh_status()

    def _refresh_status(self) -> None:
        idle = self.app.last_idle
        threshold = self.app.cfg.idle_minutes * 60
        if idle is None:
            text = (
                "Não foi possível detectar a inatividade neste sistema. "
                "Use “Testar agora” para ver o protetor."
            )
        else:
            remaining = max(0, threshold - idle)
            when = "agora" if remaining <= 0 else f"em {_fmt_seconds(remaining)}"
            text = (
                f"Inatividade: {_fmt_seconds(idle)}  ·  aparece {when}  ·  "
                f"{self.app.monitor.method}"
            )
        self.status_lbl.configure(text=text)

    def refresh_status(self) -> None:
        self._refresh_status()

    # -- janela ---------------------------------------------------------
    def show(self) -> None:
        self.root.deiconify()
        self.root.lift()
        try:
            self.root.attributes("-topmost", True)
            self.root.after(250, lambda: self._drop_topmost())
        except tk.TclError:
            pass
        self._refresh_autostart()
        self._refresh_value()
        self._refresh_status()
        self.root.after(650, self._first_run_prompt)

    def _drop_topmost(self) -> None:
        try:
            self.root.attributes("-topmost", False)
        except tk.TclError:
            pass

    def hide(self) -> None:
        self.app.save_config()
        self.root.withdraw()
        self.app.settings_hidden()

    def _first_run_prompt(self) -> None:
        if not self.app.first_run:
            return
        self.app.first_run = False
        self.app.save_config()
        answer = messagebox.askyesno(
            APP_NAME,
            "Deseja que o Relógio Vivo inicie automaticamente quando o "
            "computador ligar?\n\n"
            "Você pode mudar isso a qualquer momento nesta janela.",
            parent=self.root,
        )
        if answer:
            self.autostart_var.set(True)
            self._toggle_autostart()
        else:
            self._refresh_autostart()


# ---------------------------------------------------------------------------
# Instância única e pedidos entre processos
# ---------------------------------------------------------------------------


class SingleInstance:
    """Trava o app para não abrir dois protetores ao mesmo tempo."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._fh = None

    def acquire(self) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = open(self.path, "a+b")
            self._fh.seek(0, os.SEEK_END)
            if self._fh.tell() == 0:
                self._fh.write(b"\0")
                self._fh.flush()
            self._fh.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            self.release()
            return False

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                try:
                    self._fh.seek(0)
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            self._fh.close()
        except OSError:
            pass
        self._fh = None


def write_request(command: str, mode: str | None = None) -> None:
    try:
        config_dir().mkdir(parents=True, exist_ok=True)
        path = request_file()
        tmp = path.with_suffix(".tmp")
        payload: dict[str, object] = {"cmd": command, "ts": time.time()}
        if mode in (MODE_TELA, MODE_RELOGIO):
            payload["mode"] = mode
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        log(f"Não foi possível gravar o pedido {command}: {exc}")


def notify(message: str) -> None:
    try:
        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes("-topmost", True)
        except tk.TclError:
            pass
        messagebox.showinfo(APP_NAME, message, parent=root)
        root.destroy()
    except Exception:
        print(message)


def desktop_notify(title: str, message: str) -> None:
    """Aviso não bloqueante: nunca trava a interface do app.

    No Linux usa notify-send; nos outros sistemas (e se ele não existir)
    apenas registra no log e no console.
    """
    if sys.platform.startswith("linux") and shutil.which("notify-send"):
        try:
            subprocess.Popen(
                [
                    "notify-send",
                    "--app-name",
                    APP_NAME,
                    "--icon",
                    "dialog-warning",
                    "--expire-time",
                    "15000",
                    title,
                    message,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        except OSError:
            pass
    log(f"{title}: {message}")
    if has_console():
        print(f"{title}: {message}")


IS_FROZEN = bool(getattr(sys, "frozen", False))


def has_console() -> bool:
    """True quando existe uma saída padrão utilizável.

    No build do Windows com --windowed, sys.stdout é None (não há console).
    No Linux/macOS o binário continua imprimindo mesmo com pipe/redirecionamento,
    por isso o critério é "existe e está aberto", não isatty().
    """
    try:
        stream = sys.stdout
        return stream is not None and not stream.closed
    except Exception:  # noqa: BLE001
        return False


def show_text_dialog(title: str, text: str) -> None:
    """Janela somente leitura com a saída da linha de comando."""
    try:
        root = tk.Tk()
        root.title(f"{APP_NAME} — {title}")
        root.minsize(600, 360)
        try:
            root.attributes("-topmost", True)
        except tk.TclError:
            pass

        frame = tk.Frame(root, padx=12, pady=12)
        frame.pack(fill="both", expand=True)

        box = tk.Text(
            frame,
            width=78,
            height=18,
            wrap="word",
            font="TkFixedFont",
            relief="flat",
            background=root.cget("background"),
            highlightthickness=0,
        )
        bar = tk.Scrollbar(frame, orient="vertical", command=box.yview)
        box.configure(yscrollcommand=bar.set)
        box.insert("1.0", text)
        box.configure(state="disabled")
        box.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")

        buttons = tk.Frame(root, padx=12, pady=8)
        buttons.pack(fill="x")

        def copy() -> None:
            try:
                root.clipboard_clear()
                root.clipboard_append(text)
            except tk.TclError:
                pass

        tk.Button(buttons, text="Copiar", command=copy, width=12).pack(side="left")
        tk.Button(buttons, text="Fechar", command=root.destroy, width=12).pack(
            side="right"
        )

        root.update_idletasks()
        root.geometry(
            f"+{max(0, (root.winfo_screenwidth() - 640) // 2)}"
            f"+{max(0, (root.winfo_screenheight() - 460) // 3)}"
        )
        root.mainloop()
    except Exception:  # noqa: BLE001
        log(f"Saída da linha de comando:\n{text}")


class CliReport:
    """Guarda a saída da linha de comando e a mostra numa janela quando
    o executável foi gerado sem console (PyInstaller --windowed)."""

    def __init__(self, title: str = "linha de comando"):
        self.title = title
        self.buffer: io.StringIO | None = None
        self.original = None

    def __enter__(self) -> "CliReport":
        if IS_FROZEN and not has_console():
            self.buffer = io.StringIO()
            self.original = sys.stdout
            sys.stdout = self.buffer
        return self

    def __exit__(self, *exc_info) -> bool:
        if self.buffer is None:
            return False
        sys.stdout = self.original
        text = self.buffer.getvalue().strip()
        if text:
            show_text_dialog(self.title, text)
        return False


def enable_dpi_awareness() -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _set_icon(root) -> None:
    if Image is None:
        return
    try:
        size = 64
        icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(icon)
        draw.rounded_rectangle(
            (1, 1, size - 2, size - 2), radius=15, fill="#0f1522"
        )
        draw.ellipse((12, 12, size - 12, size - 12), outline=ACCENT, width=4)
        draw.line((size // 2, size // 2, size // 2, 19), fill=ACCENT, width=4)
        draw.line((size // 2, size // 2, 44, 38), fill=ACCENT, width=4)
        photo = ImageTk.PhotoImage(icon, master=root)
        root.iconphoto(True, photo)
        root._icon_photo = photo  # type: ignore[attr-defined]
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Controlador do app
# ---------------------------------------------------------------------------


class RelogioVivo:
    def __init__(
        self,
        root: tk.Tk,
        cfg: Config,
        start_hidden: bool,
        first_run: bool,
        lock: SingleInstance | None = None,
    ) -> None:
        self.root = root
        self.cfg = cfg
        self.lock = lock
        self.first_run = first_run
        self.monitor = IdleMonitor()
        self.last_idle = self.monitor.seconds()
        self.saver: ScreensaverWindow | None = None
        self.settings: SettingsWindow | None = None
        self.ui_family = pick_family(root)

        self._settings_visible = False
        self._preparing = False
        self._shutting_down = False
        self._reopen_settings = False
        self._suppress_until = 0.0
        self._capture_block_until = 0.0
        self._capture_warned = False
        self._capture_token = 0
        self._capture_result: dict[str, object] | None = None
        self._tick_count = 0
        self._after_id = None

        self.root.title(APP_NAME)
        self.root.configure(bg=BG)
        self.root.report_callback_exception = self._report_exception
        _set_icon(self.root)

        if start_hidden:
            self.root.withdraw()
            log("Rodando em segundo plano")
        self._schedule_tick()

    # -- ciclo principal -------------------------------------------------
    def _schedule_tick(self) -> None:
        self._after_id = self.root.after(1000, self._tick)

    def _tick(self) -> None:
        if self._shutting_down:
            return
        self._after_id = self.root.after(1000, self._tick)
        try:
            self._handle_request()
            if self._shutting_down:
                return
            if self.saver is not None:
                return

            self._tick_count += 1
            if self._tick_count % 2 == 1:
                self.last_idle = self.monitor.seconds()

            if self._settings_visible and self.settings is not None:
                self.settings.refresh_status()

            if self._preparing:
                return
            now = time.monotonic()
            # O bloqueio só vale para o modo que captura a tela. No modo
            # "só o relógio" não há captura, então nada impede a ativação.
            captura_bloqueada = (
                self.cfg.mode == MODE_TELA
                and now < self._capture_block_until
            )
            if now < self._suppress_until or captura_bloqueada:
                return
            if self.last_idle is None:
                return
            if self.last_idle >= self.cfg.idle_minutes * 60:
                self.start_screensaver()
        except Exception:
            log("Erro no ciclo principal:\n" + traceback.format_exc())

    def _handle_request(self) -> None:
        path = request_file()
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            path.unlink()
        except (OSError, ValueError):
            try:
                path.unlink()
            except OSError:
                pass
            return
        if time.time() - float(data.get("ts", 0)) > 30:
            return
        mode = data.get("mode")
        if mode in (MODE_TELA, MODE_RELOGIO):
            self.set_mode(mode)
        command = data.get("cmd")
        if command == "settings":
            self.open_settings()
        elif command == "test":
            self.start_test()
        elif command == "quit":
            self.quit_app(confirm=False)

    # -- configurações ---------------------------------------------------
    def open_settings(self) -> None:
        if self._shutting_down or self.saver is not None:
            return
        if self.settings is None:
            self.settings = SettingsWindow(self)
        self._settings_visible = True
        self.settings.show()

    def settings_hidden(self) -> None:
        self._settings_visible = False

    def set_idle_minutes(self, minutes: int) -> None:
        self.cfg.idle_minutes = max(1, min(60, int(minutes)))

    def set_mode(self, mode: str) -> None:
        if mode not in (MODE_TELA, MODE_RELOGIO):
            mode = MODE_TELA
        self.cfg.mode = mode
        self.save_config()

    def save_config(self) -> None:
        self.cfg.save()

    def start_test(self) -> None:
        if self.saver is not None or self._preparing or self._shutting_down:
            return
        self._reopen_settings = self._settings_visible
        self.start_screensaver(force=True)

    # -- protetor --------------------------------------------------------
    def start_screensaver(self, force: bool = False) -> None:
        if self.saver is not None or self._preparing or self._shutting_down:
            return
        if not force:
            now = time.monotonic()
            if now < self._suppress_until:
                return
            if self.cfg.mode == MODE_TELA and now < self._capture_block_until:
                return
            if self.last_idle is None or self.last_idle < self.cfg.idle_minutes * 60:
                return

        self._reopen_settings = self._settings_visible
        self._preparing = True
        self._settings_visible = False
        self.root.withdraw()
        self.root.after(320, self._present_saver)

    def _present_saver(self) -> None:
        if self._shutting_down:
            return
        width = self.root.winfo_screenwidth()
        height = self.root.winfo_screenheight()
        if self.cfg.mode == MODE_RELOGIO:
            self._preparing = False
            try:
                scene = build_clock_scene(width, height)
                self._show_saver_scene(scene, "só o relógio")
            except Exception:  # noqa: BLE001
                log(
                    "Falha ao mostrar o relógio:\n" + traceback.format_exc()
                )
                self._restore_after_saver()
            return

        # Modo "prévia da tela": captura em segundo plano. _preparing fica
        # True até a imagem aparecer (ou até o tempo esgotar), então nenhum
        # outro protetor é iniciado no meio do caminho.
        self._start_capture(width, height)

    def _start_capture(self, width: int, height: int) -> None:
        self._capture_token += 1
        token = self._capture_token
        self._capture_result = None
        threading.Thread(
            target=self._capture_worker,
            args=(token, width, height),
            daemon=True,
        ).start()
        deadline = time.monotonic() + CAPTURE_UI_TIMEOUT
        self.root.after(120, self._watch_capture, token, deadline)

    def _capture_worker(self, token: int, width: int, height: int) -> None:
        payload: dict[str, object] = {"token": token}
        try:
            shot = capture_screen((0, 0, width, height))
            payload["scene"] = build_scene(shot, width, height)
        except BaseException as exc:  # noqa: BLE001 - a thread não pode morrer
            payload["error"] = exc
            payload["traceback"] = traceback.format_exc()
        if self._capture_token == token:
            self._capture_result = payload

    def _watch_capture(self, token: int, deadline: float) -> None:
        if self._shutting_down or token != self._capture_token:
            return
        if self.saver is not None:
            return
        result = self._capture_result
        if result is not None and result.get("token") == token:
            self._capture_result = None
            scene = result.get("scene")
            if scene is not None:
                self._show_saver_scene(scene, "prévia da tela")
            else:
                self._capture_failed(
                    result.get("error"),
                    str(result.get("traceback") or ""),
                )
            return
        if time.monotonic() >= deadline:
            self._capture_failed(
                TimeoutError(
                    f"a captura demorou mais de {CAPTURE_UI_TIMEOUT}s"
                ),
                "",
            )
            return
        self.root.after(120, self._watch_capture, token, deadline)

    def _show_saver_scene(self, scene, rotulo: str) -> None:
        self._preparing = False
        if self._shutting_down:
            return
        try:
            self.saver = ScreensaverWindow(
                self.root,
                scene,
                self.ui_family,
                self._on_saver_closed,
                idle_probe=self.monitor.seconds,
            )
            log(f"Protetor exibido ({rotulo})")
        except Exception:  # noqa: BLE001
            log("Falha ao mostrar o protetor:\n" + traceback.format_exc())
            self._restore_after_saver()

    def _capture_failed(self, exc: object, detalhe: str = "") -> None:
        # Invalida qualquer resultado que ainda chegue da thread.
        self._capture_token += 1
        self._capture_result = None
        mensagem = f"{type(exc).__name__}: {exc}" if exc else "tempo esgotado"
        if detalhe:
            log("Captura de tela falhou:\n" + detalhe)
        else:
            log("Captura de tela falhou: " + mensagem)

        # Não insiste em capturar por 2 minutos; o relógio aparece normalmente.
        self._capture_block_until = time.monotonic() + 120
        if not self._capture_warned:
            self._capture_warned = True
            desktop_notify(
                APP_NAME,
                "Não foi possível capturar a tela.\n"
                f"{mensagem}\n\n"
                f"{_capture_hint()}\n\n"
                "Mostrando só o relógio. Para usar a prévia, rode de novo o "
                "instalador (ele instala o que falta) ou escolha "
                "“Só o relógio” em Configurações.",
            )

        # Em vez de travar/ficar sem imagem, mostra o relógio.
        width = self.root.winfo_screenwidth()
        height = self.root.winfo_screenheight()
        try:
            scene = build_clock_scene(width, height)
            self._show_saver_scene(scene, "só o relógio (captura indisponível)")
        except Exception:  # noqa: BLE001
            log("Falha ao mostrar o relógio:\n" + traceback.format_exc())
            self._restore_after_saver()

    def _restore_after_saver(self) -> None:
        self._suppress_until = time.monotonic() + 3
        self.last_idle = 0.0
        if self._reopen_settings and not self._shutting_down:
            self._reopen_settings = False
            self.open_settings()
        else:
            self.root.withdraw()

    def _on_saver_closed(self) -> None:
        self.saver = None
        if self._shutting_down:
            return
        self._restore_after_saver()

    # -- encerramento ----------------------------------------------------
    def quit_app(self, confirm: bool = True) -> None:
        if self._shutting_down:
            return
        if confirm:
            parent = self.root if self._settings_visible else None
            if not messagebox.askyesno(
                APP_NAME,
                "Encerrar o Relógio Vivo?\n\n"
                "O protetor só voltará quando você abrir o app de novo.",
                parent=parent,
            ):
                return
        self._shutting_down = True
        try:
            if self.saver is not None:
                self.saver.close()
        except Exception:
            pass
        try:
            if self._after_id is not None:
                self.root.after_cancel(self._after_id)
        except tk.TclError:
            pass
        try:
            self.root.quit()
            self.root.destroy()
        except tk.TclError:
            pass
        log("App encerrado")

    def _report_exception(self, exc_type, value, tb) -> None:
        log(
            "Erro não tratado:\n"
            + "".join(traceback.format_exception(exc_type, value, tb))
        )
        if self._settings_visible:
            try:
                messagebox.showerror(
                    APP_NAME, f"Ocorreu um erro:\n\n{value}", parent=self.root
                )
            except tk.TclError:
                pass


def _capture_hint() -> str:
    if sys.platform == "darwin":
        return (
            "No macOS, autorize Gravação de Tela em Ajustes do Sistema > "
            "Privacidade e Segurança > Gravação de Tela e abra o app novamente."
        )
    if os.name == "nt":
        return "Verifique se o Pillow está instalado (pip install pillow)."
    wayland = os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
    if wayland:
        return (
            "No Wayland, o caminho certo é o GNOME Shell (D-Bus). Instale com: "
            "sudo apt install libglib2.0-bin gnome-screenshot grim; depois saia "
            "e entre de novo na sessão (ou reinicie) para valer."
        )
    if not shutil.which("gdbus"):
        return (
            "No Ubuntu/Debian instale: sudo apt install python3-pil "
            "python3-tk python3-pil.imagetk libglib2.0-bin xprintidle "
            "gnome-screenshot. O instalador do Relógio Vivo já faz isso."
        )
    return (
        "Instale as ferramentas de captura com: sudo apt install "
        "gnome-screenshot grim libglib2.0-bin xprintidle libxss1. "
        "O instalador do Relógio Vivo já faz isso automaticamente."
    )


# ---------------------------------------------------------------------------
# Diagnóstico e linha de comando
# ---------------------------------------------------------------------------


def run_check() -> int:
    import platform

    enable_dpi_awareness()
    print(f"{APP_NAME} {APP_VERSION} — diagnóstico")
    print(f"Sistema: {platform.platform()}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Pillow: {getattr(Image, '__version__', 'não instalado')}")
    if Image is not None:
        if ImageTk is not None:
            print("ImageTk: OK")
        else:
            print(
                "ImageTk: FALTANDO — no Ubuntu/Debian: sudo apt install "
                "python3-pil.imagetk"
            )

    try:
        root = tk.Tk()
        root.withdraw()
        print(f"Tk: {root.tk.call('info', 'patchlevel')}")
        print(
            f"Tela principal: {root.winfo_screenwidth()}x"
            f"{root.winfo_screenheight()}"
        )
        print(f"Fonte da interface: {pick_family(root)}")
        root.destroy()
    except Exception as exc:  # noqa: BLE001
        print(f"Tkinter indisponível: {exc}")

    monitor = IdleMonitor()
    current = monitor.seconds()
    if current is None:
        print(f"Inatividade: indisponível ({monitor.method})")
    else:
        print(f"Inatividade: {monitor.method} — agora {current:.1f} s")

    backends = available_capture_backends()
    print("Captura de tela: " + (", ".join(backends) if backends else "indisponível"))
    if os.name != "nt" and sys.platform != "darwin":
        session = os.environ.get("XDG_SESSION_TYPE") or (
            "wayland" if os.environ.get("WAYLAND_DISPLAY") else "x11"
        )
        desktop = os.environ.get("XDG_CURRENT_DESKTOP") or "?"
        print(f"Sessão: {session} · desktop: {desktop}")
        for cmd in ("gdbus", "gnome-screenshot", "grim", "notify-send", "xprintidle"):
            estado = "OK" if shutil.which(cmd) else "FALTANDO"
            print(f"  {cmd}: {estado}")

    cfg, _ = Config.load()
    print(f"Modo do protetor: {MODE_LABELS.get(cfg.mode, cfg.mode)}")
    print(f"Ativar após: {cfg.idle_minutes} min de inatividade")

    print(f"Configuração: {config_file()}")
    print(f"Log: {log_file()}")
    if is_autostart_enabled():
        target = "Registro do Windows" if os.name == "nt" else str(autostart_path())
        print(f"Iniciar com o computador: ATIVO ({target})")
    else:
        print("Iniciar com o computador: desativado")
    return 0


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="relogio_vivo.py",
        description="Protetor de tela com a hora e a data (Tkinter).",
    )
    parser.add_argument(
        "--background",
        action="store_true",
        help="roda escondido (usado na inicialização automática)",
    )
    parser.add_argument(
        "--settings", action="store_true", help="abre as configurações"
    )
    parser.add_argument(
        "--test", action="store_true", help="mostra o protetor imediatamente"
    )
    parser.add_argument(
        "--quit", action="store_true", help="encerra uma instância em execução"
    )
    parser.add_argument(
        "--check", action="store_true", help="mostra um diagnóstico do sistema"
    )
    parser.add_argument(
        "--snapshot",
        metavar="ARQUIVO.png",
        help="salva uma prévia da cena em PNG (diagnóstico)",
    )
    parser.add_argument(
        "--mode",
        choices=(MODE_TELA, MODE_RELOGIO),
        help="define o estilo do protetor: 'tela' (prévia da tela) ou "
        "'relogio' (só o relógio)",
    )
    parser.add_argument(
        "--install-autostart",
        action="store_true",
        help="ativa a inicialização automática",
    )
    parser.add_argument(
        "--uninstall-autostart",
        action="store_true",
        help="desativa a inicialização automática",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream is not None:
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    args = parse_args(argv)
    trim_log()

    with CliReport("diagnóstico" if args.check else "linha de comando"):
        if args.check:
            return run_check()

        if args.snapshot:
            try:
                cfg, _ = Config.load()
                out = save_snapshot(args.snapshot, args.mode or cfg.mode)
            except Exception as exc:  # noqa: BLE001
                print(f"Falha ao gerar a prévia: {exc}")
                return 1
            print(f"Prévia salva em: {out}")
            return 0

        if args.install_autostart:
            try:
                target = enable_autostart()
            except Exception as exc:  # noqa: BLE001
                print(f"Não foi possível ativar a inicialização automática: {exc}")
                return 1
            print(f"Inicialização automática ativada: {target}")
            return 0

        if args.uninstall_autostart:
            try:
                disable_autostart()
            except Exception as exc:  # noqa: BLE001
                print(f"Não foi possível desativar a inicialização automática: {exc}")
                return 1
            print("Inicialização automática desativada.")
            return 0

    if Image is None:
        message = (
            "O Pillow é necessário para capturar e compor a imagem.\n\n"
            "Instale com:  pip install pillow"
        )
        print(message)
        try:
            notify(message)
        except Exception:
            pass
        return 1

    cfg, existed = Config.load()
    if args.mode:
        cfg.mode = args.mode
        cfg.save()
    if not existed:
        cfg.save()

    if args.background:
        action = "background"
    elif args.test:
        action = "test"
    elif args.quit:
        action = "quit"
    else:
        action = "settings"

    lock = SingleInstance(config_dir() / "instance.lock")

    if action == "quit":
        if lock.acquire():
            print("O Relógio Vivo não está em execução.")
            return 0
        write_request("quit")
        print("Pedido de encerramento enviado.")
        return 0

    if not lock.acquire():
        if action == "background":
            return 0
        if action in ("settings", "test"):
            write_request(action, mode=args.mode)
        if action == "settings":
            notify(
                "O Relógio Vivo já está em execução.\n"
                "As configurações foram abertas na instância existente."
            )
        else:
            print("O Relógio Vivo já está em execução.")
        return 0

    if not TK_AVAILABLE:
        message = (
            "O Tkinter não está disponível neste Python.\n\n"
            "No Ubuntu/Debian, instale com:  sudo apt install python3-tk\n"
            "No Windows/macOS, reinstale o Python marcando a opção Tcl/Tk.\n\n"
            f"Detalhe: {TK_ERROR}"
        )
        print(message)
        return 1

    if ImageTk is None:
        message = (
            "O Pillow está instalado, mas sem o suporte a Tkinter (ImageTk).\n\n"
            "Ubuntu/Debian:  sudo apt install python3-pil.imagetk\n"
            "Fedora:         sudo dnf install python3-pillow-tk\n"
            "Ou:             pip install --user --break-system-packages pillow\n\n"
            "O instalador faz isso sozinho:\n"
            "  curl -fsSL https://raw.githubusercontent.com/"
            "bernardoalvescaetano888-glitch/relogio-vivo/main/instalar.sh | bash"
        )
        print(message)
        try:
            notify(message)
        except Exception:
            pass
        return 1

    enable_dpi_awareness()
    root = tk.Tk()
    root.withdraw()
    app = RelogioVivo(
        root,
        cfg,
        start_hidden=(action == "background"),
        first_run=(not existed),
        lock=lock,
    )

    if action == "background":
        log("Iniciado com o sistema")
    else:
        app.open_settings()
        if action == "test":
            root.after(500, app.start_test)

    try:
        root.mainloop()
    finally:
        lock.release()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



