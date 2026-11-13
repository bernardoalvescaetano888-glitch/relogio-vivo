#!/usr/bin/env python3
"""Monta os dois ZIPs divulgados na release.

    RelogioVivo-<versao>-setup.zip      -> instaladores (Windows, Linux, macOS)
    RelogioVivo-<versao>-portatil.zip   -> versões sem instalação

Os arquivos são procurados em dist/ e, se não estiverem lá, dentro de
artifacts/ (é onde o GitHub Actions deixa os artefatos do build).

Uso:
    python3 installer/make_bundle.py
    python3 installer/make_bundle.py --version 1.2.0 --out dist
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------- conteúdo

SETUP = {
    "windows": [
        "RelogioVivo-Setup-{v}-win-x64.exe",
        "RelogioVivo-Setup-{v}-win-arm64.exe",
    ],
    "linux": [
        "relogio-vivo_{v}_all.deb",
        "instalar.sh",
    ],
    "macos": [
        "RelogioVivo-Setup-{v}-macos-arm64.pkg",
        "RelogioVivo-Setup-{v}-macos-x64.pkg",
    ],
}

PORTATIL = {
    "windows": [
        "RelogioVivo-win-x64.exe",
        "RelogioVivo-win-arm64.exe",
    ],
    "linux": [
        "RelogioVivo-linux-x64.tar.gz",
        "RelogioVivo-linux-arm64.tar.gz",
    ],
    "macos": [
        "RelogioVivo-macos-arm64.zip",
        "RelogioVivo-macos-x64.zip",
    ],
}

LEIA_ME_SETUP = """\
Relógio Vivo {versao} — instaladores
====================================

Escolha UMA pasta de acordo com o seu sistema e abra o instalador.

  setup/windows/
    RelogioVivo-Setup-{versao}-win-arm64.exe   -> PC Windows ARM (Snapdragon)
    RelogioVivo-Setup-{versao}-win-x64.exe     -> PC Windows Intel ou AMD
    (na dúvida, use o x64; ele também funciona em Windows ARM por emulação)

  setup/linux/
    relogio-vivo_{versao}_all.deb              -> Debian, Ubuntu, Mint, Pop!_OS
        Instale com:  sudo apt install ./relogio-vivo_{versao}_all.deb
    instalar.sh                                -> qualquer Linux, instala tudo sozinho
        Instale com:  bash instalar.sh

  setup/macos/
    RelogioVivo-Setup-{versao}-macos-arm64.pkg -> Mac com chip Apple (M1/M2/M3/M4)
    RelogioVivo-Setup-{versao}-macos-x64.pkg   -> Mac com processador Intel
        Abra o .pkg com dois cliques. Se o macOS reclamar, clique com o botão
        direito > Abrir.

O que os instaladores fazem
---------------------------
  Windows : instala em %LOCALAPPDATA%\\Programs\\Relogio Vivo, cria atalhos no
            Menu Iniciar e na Área de Trabalho, ativa o início com o Windows
            e registra o desinstalador.
  Linux   : instala o comando "relogio-vivo", o atalho no menu, o ícone e as
            dependências (python3, python3-tk, python3-pil.imagetk).
  macOS   : instala o app em /Applications.

Observação: nenhum instalador é assinado. O Windows pode mostrar o aviso do
SmartScreen ("Mais informações > Executar assim mesmo") e o macOS pode pedir
confirmação no primeiro clique. Isso é normal para programas sem certificado
pago.

Se o antivírus reclamar do .exe, é um falso positivo comum de programas
empacotados com PyInstaller. O código-fonte é aberto: você pode conferir e
compilar você mesmo com build_windows.ps1.

Mais informações:
https://github.com/bernardoalvescaetano888-glitch/relogio-vivo
"""

LEIA_ME_PORTATIL = """\
Relógio Vivo {versao} — versões sem instalação (portáteis)
==========================================================

Não instala nada: é só extrair e executar. Ideal para pendrive ou para
testar sem mexer no sistema.

  portatil/windows/
    RelogioVivo-win-arm64.exe   -> PC Windows ARM (Snapdragon)
    RelogioVivo-win-x64.exe     -> PC Windows Intel ou AMD
        Dê dois cliques. Na primeira vez ele pergunta se pode iniciar com o
        computador.

  portatil/linux/
    RelogioVivo-linux-x64.tar.gz    -> Linux x86_64 (Intel/AMD)
    RelogioVivo-linux-arm64.tar.gz  -> Linux ARM64 (Raspberry Pi, notebooks ARM)
        Extraia e execute:
            tar -xzf RelogioVivo-linux-x64.tar.gz
            ./RelogioVivo-linux-x64

  portatil/macos/
    RelogioVivo-macos-arm64.zip  -> Mac Apple Silicon (M1/M2/M3/M4)
    RelogioVivo-macos-x64.zip    -> Mac Intel
        Descompacte e arraste o RelogioVivo.app para Aplicativos.
        Se o Gatekeeper bloquear:
            xattr -dr com.apple.quarantine RelogioVivo.app

No Linux, o binário portátil pode não abrir em distribuições muito antigas
(erro "GLIBC_2.xx not found"). Nesse caso use o instalador da versão setup.

Se o antivírus reclamar do .exe, é um falso positivo comum de programas
empacotados com PyInstaller. O código-fonte é aberto: você pode conferir e
compilar você mesmo com build_windows.ps1.

Mais informações:
https://github.com/bernardoalvescaetano888-glitch/relogio-vivo
"""


# ------------------------------------------------------------------ helpers


def versao_do_app() -> str:
    texto = (RAIZ / "relogio_vivo.py").read_text(encoding="utf-8")
    achado = re.search(r'APP_VERSION = "([^"]+)"', texto)
    if not achado:
        raise SystemExit("Não encontrei APP_VERSION em relogio_vivo.py")
    return achado.group(1)


def achar(nome: str, pastas: list[Path]) -> Path | None:
    for pasta in pastas:
        candidato = pasta / nome
        if candidato.is_file():
            return candidato
    for pasta in pastas:
        if not pasta.is_dir():
            continue
        for candidato in pasta.rglob(nome):
            if candidato.is_file():
                return candidato
    return None


def montar_zip(
    destino: Path,
    pasta_interna: str,
    grupos: dict[str, list[str]],
    pastas: list[Path],
    leia_me: str,
    versao: str,
) -> tuple[int, list[str]]:
    raiz_zip = f"RelogioVivo-{versao}"
    total = 0
    faltando: list[str] = []

    with zipfile.ZipFile(
        destino, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as zf:
        # BOM + CRLF para o Bloco de Notas do Windows abrir sem acentos quebrados.
        zf.writestr(
            f"{raiz_zip}/LEIA-ME.txt",
            "\ufeff" + leia_me.replace("\n", "\r\n"),
        )
        for sistema, nomes in grupos.items():
            for padrao in nomes:
                nome = padrao.format(v=versao)
                origem = achar(nome, pastas)
                if origem is None:
                    faltando.append(nome)
                    continue
                zf.write(origem, f"{raiz_zip}/{pasta_interna}/{sistema}/{nome}")
                total += 1

    return total, faltando


# --------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Monta os ZIPs da release.")
    parser.add_argument("--version", default="")
    parser.add_argument("--out", default=str(RAIZ / "dist"))
    args = parser.parse_args(argv)

    versao = args.version or versao_do_app()
    saida = Path(args.out)
    saida.mkdir(parents=True, exist_ok=True)

    pastas = [RAIZ / "dist", RAIZ / "artifacts", RAIZ]
    vazios = 0

    for sufixo, grupos, modelo in (
        ("setup", SETUP, LEIA_ME_SETUP),
        ("portatil", PORTATIL, LEIA_ME_PORTATIL),
    ):
        destino = saida / f"RelogioVivo-{versao}-{sufixo}.zip"
        quantidade, faltando = montar_zip(
            destino,
            sufixo,
            grupos,
            pastas,
            modelo.format(versao=versao),
            versao,
        )
        tamanho = destino.stat().st_size / 1024 / 1024
        print(f"{destino.name}: {quantidade} arquivos, {tamanho:.1f} MB")
        for nome in faltando:
            print(f"  aviso: não achei {nome}", file=sys.stderr)
        if quantidade == 0:
            print(f"  erro: {destino.name} ficou vazio", file=sys.stderr)
            vazios += 1

    return 1 if vazios else 0


if __name__ == "__main__":
    raise SystemExit(main())
