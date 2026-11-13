# Instaladores

Cada sistema tem um formato próprio de instalador. Não existe "um .exe que
instala em tudo": o Windows não executa `.pkg`, o macOS não executa `.exe` e
o Linux usa `.deb`/`.rpm`. Por isso a release publica um arquivo para cada
sistema, e o GitHub Actions gera todos automaticamente.

| Sistema | Formato | Ferramenta | Arquivo gerado |
|---|---|---|---|
| Windows | `.exe` (Setup) | Inno Setup 6.3+ | `RelogioVivo-Setup-<versao>-win-x64.exe` / `-win-arm64.exe` |
| Debian/Ubuntu | `.deb` | `dpkg-deb` | `relogio-vivo_<versao>_all.deb` |
| macOS | `.pkg` | `pkgbuild` + `productbuild` | `RelogioVivo-Setup-<versao>-macos-arm64.pkg` / `-x64.pkg` |
| Linux (qualquer) | script | `bash` | `instalar.sh` |

## O que cada instalador faz

### Windows — `windows/relogio-vivo.iss`

- Instala em `%LOCALAPPDATA%\Programs\Relogio Vivo` (sem pedir administrador;
  quem quiser pode escolher "para todos os usuários" na primeira tela).
- Atalho no Menu Iniciar, na Área de Trabalho (opcional) e atalhos de
  **Ver protetor agora** e **Diagnóstico**.
- Ativa a inicialização com o Windows (opcional, marcado por padrão) via
  `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.
- Fecha a instância em execução antes de substituir o `.exe`.
- Registra desinstalador em **Aplicativos instalados** e no Menu Iniciar.

Regenerar:

```powershell
winget install JRSoftware.InnoSetup
powershell -ExecutionPolicy Bypass -File installer\windows\build_setup.ps1
```

### Debian/Ubuntu — `linux/build_deb.sh`

- `Architecture: all` (só Python + ícone + `.desktop`), funciona em x86_64,
  ARM64 e qualquer outra.
- `Depends: python3, python3-tk, python3-pil.imagetk` — o `apt` instala tudo.
- `Recommends: xprintidle, libxss1, grim` (detecção de inatividade e captura
  no Wayland).
- Instala `/usr/bin/relogio-vivo`, o app em `/usr/share/relogio-vivo`, o
  atalho e o ícone.
- No `postinst`, ativa a inicialização automática para o usuário que rodou
  `sudo apt install` (via `SUDO_USER`). Sem `sudo`, o app pergunta na
  primeira execução.

Regenerar (em qualquer Debian/Ubuntu):

```bash
bash installer/linux/build_deb.sh
dpkg-deb --contents dist/relogio-vivo_*_all.deb
```

### macOS — `macos/build_pkg.sh`

- Instala `RelogioVivo.app` em `/Applications`.
- O `postinstall` remove a marca de quarentena.
- Na primeira execução o app pede a permissão de Gravação de Tela e pergunta
  se pode iniciar junto com o sistema.
- `--dmg` também gera uma imagem de disco com o app + atalho para
  `/Applications`.

Regenerar (em um Mac, depois de `./build_macos.sh`):

```bash
bash installer/macos/build_pkg.sh --dmg
```

## Assinatura de código

Nenhum dos instaladores é assinado. Consequências:

- **Windows SmartScreen**: "O Windows protegeu o computador" → **Mais
  informações → Executar assim mesmo**. Para remover de vez seria preciso um
  certificado de assinatura de código (pago).
- **macOS Gatekeeper**: clique com o botão direito → **Abrir** na primeira
  vez (ou `xattr -dr com.apple.quarantine <arquivo>`). Para remover de vez
  seria preciso uma conta Apple Developer + notarização.
- **Linux**: `.deb` local pede confirmação do `apt` por não estar num
  repositório assinado; use `sudo apt install ./arquivo.deb`.

## Publicação

Numa tag `v*`, o workflow `.github/workflows/build.yml` compila em máquinas
nativas (Windows, Linux e macOS), gera os instaladores e anexa na release.
O job `windows-arm64` usa o runner `windows-11-arm` do GitHub; se ele não
estiver disponível no momento, o build ARM64 pode ser feito localmente com
`build_windows.ps1` + `installer/windows/build_setup.ps1 -Arch arm64`.
