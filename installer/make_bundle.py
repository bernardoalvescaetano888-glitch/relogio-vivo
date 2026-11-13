#!/usr/bin/env python3
"""Monta os dois ZIPs divulgados na release.

    install.zip    -> instaladores: windows/, mac/, linux/, debian/
    portatil.zip   -> sem instalação: windows/, mac/, linux/

Os arquivos são procurados em dist/ e, se não estiverem lá, dentro de
artifacts/ (é onde o GitHub Actions deixa os artefatos do build). O script
também organiza as mesmas pastas dentro de dist/ e remove os ZIPs antigos
com nome por versão.

Uso:
    python3 installer/make_bundle.py
    python3 installer/make_bundle.py --version 1.3.1 --out dist
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------- conteúdo

INSTALL = {
    "windows": [
        "RelogioVivo-Setup-{v}-win-x64.exe",
        "RelogioVivo-Setup-{v}-win-arm64.exe",
    ],
    "mac": [
        "RelogioVivo-Setup-{v}-macos-arm64.pkg",
        "RelogioVivo-Setup-{v}-macos-x64.pkg",
    ],
    "linux": [
        "instalar.sh",
    ],
    "debian": [
        "relogio-vivo_{v}_all.deb",
    ],
}

PORTATIL = {
    "windows": [
        "RelogioVivo-win-x64.exe",
        "RelogioVivo-win-arm64.exe",
    ],
    "mac": [
        "RelogioVivo-macos-arm64.zip",
        "RelogioVivo-macos-x64.zip",
    ],
    "linux": [
        "RelogioVivo-linux-x64.tar.gz",
        "RelogioVivo-linux-arm64.tar.gz",
    ],
}

LEIA_ME_INSTALL = """\
Relógio Vivo {versao} — instaladores
====================================

Escolha UMA pasta de acordo com o seu sistema e abra o instalador.

  windows/
    RelogioVivo-Setup-{versao}-win-x64.exe     -> PC Windows Intel ou AMD
    RelogioVivo-Setup-{versao}-win-arm64.exe   -> PC Windows ARM (Snapdragon)
    (na dúvida, use o x64; ele também funciona em Windows ARM por emulação)

  mac/
    RelogioVivo-Setup-{versao}-macos-arm64.pkg -> Mac com chip Apple (M1/M2/M3/M4)
    RelogioVivo-Setup-{versao}-macos-x64.pkg   -> Mac com processador Intel
    Abra o .pkg com dois cliques. Se o macOS reclamar, clique com o botão
    direito > Abrir.

  linux/
    instalar.sh -> instala tudo sozinho em qualquer distribuição Linux
    Instale com:  bash instalar.sh

  debian/
    relogio-vivo_{versao}_all.deb -> Debian, Ubuntu, Mint, Pop!_OS, Zorin
    Instale com:  sudo apt install ./relogio-vivo_{versao}_all.deb

O que os instaladores fazem
---------------------------
  Windows : instala em %LOCALAPPDATA%\\Programs\\Relogio Vivo, cria atalhos no
            Menu Iniciar e na Área de Trabalho, ativa o início com o Windows
            e registra o desinstalador.
  Linux   : instala o comando "relogio-vivo", o atalho no menu, o ícone e as
            dependências (python3, python3-tk, python3-pil.imagetk).
  macOS   : instala o app em /Applications.

Dois estilos de protetor
------------------------
  Em Configurações você escolhe:
    - Prévia da tela: captura a tela antes de ativar e usa a imagem desfocada
      como fundo, com a hora e a data em um cartão que desliza.
    - Só o relógio: não captura nada. Mostra a hora grande e a data no centro
      sobre um fundo escuro. Ideal para qualquer sistema e para quem não quer
      dar permissão de gravação de tela.

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

  windows/
    RelogioVivo-win-x64.exe     -> PC Windows Intel ou AMD
    RelogioVivo-win-arm64.exe   -> PC Windows ARM (Snapdragon)
    Dê dois cliques. Na primeira vez ele pergunta se pode iniciar com o
    computador.

  mac/
    RelogioVivo-macos-arm64.zip -> Mac Apple Silicon (M1/M2/M3/M4)
    RelogioVivo-macos-x64.zip   -> Mac Intel
    Descompacte e arraste o RelogioVivo.app para Aplicativos.
    Se o Gatekeeper bloquear:
        xattr -dr com.apple.quarantine RelogioVivo.app

  linux/
    RelogioVivo-linux-x64.tar.gz   -> Linux x86_64 (Intel/AMD)
    RelogioVivo-linux-arm64.tar.gz -> Linux ARM64 (Raspberry Pi, notebooks ARM)
    Extraia e execute:
        tar -xzf RelogioVivo-linux-x64.tar.gz
        ./RelogioVivo-linux-x64

Dois estilos de protetor
------------------------
  Nas Configurações do app você escolhe:
    - Prévia da tela: captura a tela antes de ativar e usa a imagem desfocada
      como fundo, com a hora e a data em um cartão que desliza.
    - Só o relógio: não captura nada. Mostra a hora grande e a data no centro
      sobre um fundo escuro.

No Linux, o binário portátil pode não abrir em distribuições muito antigas
(erro "GLIBC_2.xx not found"). Nesse caso use o instalador da versão install.

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


def escrever_leia_me(destino: Path, texto: str) -> None:
    # BOM + CRLF para o Bloco de Notas do Windows abrir sem acentos quebrados.
    destino.write_bytes(("\ufeff" + texto.replace("\n", "\r\n")).encode("utf-8"))


def preparar_pasta(
    destino: Path,
    grupos: dict[str, list[str]],
    pastas: list[Path],
    leia_me: str,
    versao: str,
) -> tuple[int, list[str]]:
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True, exist_ok=True)
    escrever_leia_me(destino / "LEIA-ME.txt", leia_me.format(versao=versao))

    copiados = 0
    faltando: list[str] = []
    for sistema, nomes in grupos.items():
        pasta_sistema = destino / sistema
        pasta_sistema.mkdir(parents=True, exist_ok=True)
        for padrao in nomes:
            nome = padrao.format(v=versao)
            origem = achar(nome, pastas)
            if origem is None:
                faltando.append(nome)
                continue
            shutil.copy2(origem, pasta_sistema / nome)
            copiados += 1
    return copiados, faltando


def zipar(pasta: Path, destino: Path) -> None:
    """Compacta a pasta gravando as permissões Unix corretas.

    No Windows o sistema de arquivos não tem bit de execução, então copiar
    ``instalar.sh`` de lá deixaria o script sem permissão de execução ao
    extrair no Linux/macOS. Aqui o modo é gravado explicitamente.
    """
    with zipfile.ZipFile(destino, "w") as zf:
        for item in sorted(pasta.rglob("*")):
            if not item.is_file():
                continue
            arcname = item.relative_to(pasta).as_posix()
            info = zipfile.ZipInfo.from_file(item, arcname)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3  # Unix, para o modo abaixo ser respeitado
            modo = 0o755 if item.suffix.lower() == ".sh" else 0o644
            info.external_attr = (0o100000 | modo) << 16
            with open(item, "rb") as fh:
                zf.writestr(info, fh.read(), compresslevel=9)


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

    for nome_zip, grupos, modelo in (
        ("install", INSTALL, LEIA_ME_INSTALL),
        ("portatil", PORTATIL, LEIA_ME_PORTATIL),
    ):
        pasta = saida / nome_zip
        copiados, faltando = preparar_pasta(
            pasta, grupos, pastas, modelo, versao
        )
        destino = saida / f"{nome_zip}.zip"
        zipar(pasta, destino)
        tamanho = destino.stat().st_size / 1024 / 1024
        print(f"{destino.name}: {copiados} arquivos, {tamanho:.1f} MB")
        for nome in faltando:
            print(f"  aviso: não achei {nome}", file=sys.stderr)
        if copiados == 0:
            print(f"  erro: {destino.name} ficou vazio", file=sys.stderr)
            vazios += 1

    # Limpa os ZIPs do formato antigo (RelogioVivo-<versao>-setup.zip etc.).
    for antigo in saida.glob("RelogioVivo-*-setup.zip"):
        antigo.unlink(missing_ok=True)
    for antigo in saida.glob("RelogioVivo-*-portatil.zip"):
        antigo.unlink(missing_ok=True)

    return 1 if vazios else 0


if __name__ == "__main__":
    raise SystemExit(main())
