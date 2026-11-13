# Relógio Vivo

Protetor de tela em **Python + Tkinter** para **Windows, Ubuntu/Linux e macOS**.

Depois de alguns minutos sem teclado ou mouse, o app aparece em um dos dois
estilos (escolhido nas configurações):

**Prévia da tela**

1. captura a tela;
2. usa a captura desfocada e escurecida como fundo;
3. monta um cartão com a hora (ao vivo) e a data em português na parte de baixo;
4. faz esse cartão deslizar de um lado para o outro no centro da tela;
5. sai com qualquer tecla, clique ou movimento do mouse.

**Só o relógio**

1. não captura a tela (não pede permissão de gravação);
2. desenha um fundo escuro em degradê;
3. mostra a hora grande e a data no centro, com uma leve flutuação;
4. sai com qualquer tecla, clique ou movimento do mouse.

O modo "só o relógio" funciona igual em Windows, Linux e macOS, inclusive em
Wayland, onde a captura de tela costuma exigir ferramentas extras.

Na primeira execução ele **pede permissão** para iniciar junto com o computador.
Se você aceitar, ele cria sozinho o arquivo de inicialização do sistema atual
(Registro do Windows, `.desktop` no Linux ou LaunchAgent no macOS).

## Instaladores completos (recomendado)

### Baixar em um ZIP só

Na página da release há **apenas dois ZIPs**:

| ZIP | Conteúdo |
|---|---|
| `install.zip` | pastas `windows/`, `mac/`, `linux/` e `debian/` com os instaladores + `LEIA-ME.txt` |
| `portatil.zip` | pastas `windows/`, `mac/` e `linux/` com as versões sem instalação |

Depois de extrair, é só abrir a pasta do seu sistema. O `LEIA-ME.txt` na raiz
explica cada arquivo.

Cada sistema tem um instalador próprio que cria atalho, ícone, entrada no menu
e desinstalador — sem precisar de Python nem de terminal.

| Sistema | Arquivo | O que faz |
|---|---|---|
| Windows 10/11 Intel/AMD | `windows/RelogioVivo-Setup-1.3.0-win-x64.exe` | instala, cria atalhos no Menu Iniciar e na Área de Trabalho, ativa o autostart e registra o desinstalador |
| Windows ARM (Snapdragon) | `windows/RelogioVivo-Setup-1.3.0-win-arm64.exe` | idem, nativo para ARM |
| Debian/Ubuntu/Mint/Pop!_OS | `debian/relogio-vivo_1.3.0_all.deb` | instala comando, menu, ícone e dependências pelo `apt` |
| Qualquer Linux | `linux/instalar.sh` | instala dependências, comando e atalho sem precisar de pacote |
| macOS Apple Silicon | `mac/RelogioVivo-Setup-1.3.0-macos-arm64.pkg` | instala em `/Applications` |
| macOS Intel | `mac/RelogioVivo-Setup-1.3.0-macos-x64.pkg` | instala em `/Applications` |

### Windows

Baixe o `.exe` do Setup e abra. Ele **não pede administrador**: instala em
`%LOCALAPPDATA%\Programs\Relogio Vivo` e cria os atalhos para o seu usuário.
Na tela de tarefas você escolhe:

- atalho na Área de Trabalho;
- iniciar junto com o Windows;
- abrir o app ao terminar.

Para desinstalar: **Configurações → Aplicativos → Relógio Vivo → Desinstalar**
(ou o atalho "Desinstalar o Relógio Vivo" no Menu Iniciar).

Instalação silenciosa, útil em script:

```powershell
.\RelogioVivo-Setup-1.3.0-win-x64.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
```

### Debian / Ubuntu

```bash
sudo apt install ./relogio-vivo_1.3.0_all.deb
```

O `apt` resolve sozinho `python3`, `python3-tk` e `python3-pil.imagetk`. O
comando `relogio-vivo` fica disponível no terminal e o atalho no menu de
aplicativos. Se você instalou com `sudo`, a inicialização automática também é
ativada para o seu usuário.

```bash
relogio-vivo --test
sudo apt remove relogio-vivo
```

### macOS

Abra o `.pkg` com dois cliques. Se o Gatekeeper reclamar (o pacote não é
assinado), clique com o botão direito → **Abrir**, ou:

```bash
xattr -dr com.apple.quarantine RelogioVivo-Setup-1.3.0-macos-arm64.pkg
```

O app vai para `/Applications`. Na primeira execução ele pergunta se pode
iniciar junto com o sistema. A permissão de **Gravação de Tela** só é pedida
quando você usa o estilo "Prévia da tela".

## Requisitos

- Python 3.9 ou mais novo (testado com 3.14).
- Pillow (única dependência externa).
- Tkinter:
  - Windows e macOS: já vem com o Python.
  - Ubuntu/Debian: `sudo apt install python3-tk`
- Linux com Wayland: um capturador de tela, por exemplo
  `sudo apt install grim` (ou `gnome-screenshot` / `spectacle`).
- Linux X11: opcionalmente `xprintidle` e `libxss1` para detectar inatividade
  sem depender do ambiente gráfico.

## Linux: instalação em um comando (sem pacote)

Um comando instala **tudo** (Python, Tkinter, Pillow com ImageTk, grim no
Wayland, xprintidle/libxss), cria o atalho no menu, o ícone, a inicialização
automática e já deixa o app rodando em segundo plano:

```bash
curl -fsSL https://raw.githubusercontent.com/bernardoalvescaetano888-glitch/relogio-vivo/main/instalar.sh | bash
```

Depois:

```bash
relogio-vivo            # abre as configurações
relogio-vivo --test     # mostra o protetor agora
relogio-vivo --check    # diagnóstico
```

Opções do instalador: `--no-autostart`, `--no-start`, `--from ARQUIVO`,
`--uninstall`. Ele pergunta a senha do `sudo` uma vez e guarda todo o
detalhamento em `/tmp/relogio-vivo-install.log`.

Se você baixou o `.tar.gz` da release, ele já vem com o bit de execução:

```bash
tar -xzf RelogioVivo-linux-x64.tar.gz
./RelogioVivo-linux-x64
```

Quem clonou o repositório pode rodar o instalador apontando para o código
local (assim ele também instala as dependências):

```bash
./instalar.sh --from relogio_vivo.py
```

## Instalar e executar (manual)

```bash
cd relogio-vivo
python -m pip install -r requirements.txt
python relogio_vivo.py
```

Na janela:

- **Estilo do protetor**: "Prévia da tela" (captura desfocada) ou
  "Só o relógio" (fundo escuro, sem captura).
- **Ativar depois de**: 1 a 60 minutos de inatividade (slider e atalhos).
- **Iniciar com o computador**: ativa/desativa a inicialização automática.
- **Testar agora**: abre o protetor imediatamente no estilo escolhido.
- **Fechar janela**: o app continua rodando em segundo plano.
- **Encerrar app**: desliga o protetor até você abrir o app de novo.

Para abrir as configurações de novo, execute o app outra vez. A segunda
instância detecta a primeira e manda abrir a janela nela (não duplica o
protetor).

## Linha de comando

```bash
python relogio_vivo.py                  # configurações
python relogio_vivo.py --background     # escondido (usado na inicialização)
python relogio_vivo.py --test           # mostra o protetor agora
python relogio_vivo.py --quit           # encerra a instância em execução
python relogio_vivo.py --check          # diagnóstico do sistema
python relogio_vivo.py --snapshot p.png # prévia da cena em PNG
python relogio_vivo.py --mode relogio   # define o estilo e abre as configurações
python relogio_vivo.py --test --mode tela  # testa o estilo escolhido
python relogio_vivo.py --install-autostart
python relogio_vivo.py --uninstall-autostart
```

## Onde ficam os arquivos

| O que | Windows | Linux | macOS |
|---|---|---|---|
| Configuração | `%APPDATA%\RelogioVivo\config.json` | `~/.config/relogio-vivo/config.json` | `~/Library/Application Support/RelogioVivo/config.json` |
| Log | `%APPDATA%\RelogioVivo\relogio-vivo.log` | `~/.config/relogio-vivo/relogio-vivo.log` | `~/Library/Application Support/RelogioVivo/relogio-vivo.log` |
| Inicialização | Registro `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` | `~/.config/autostart/relogio-vivo.desktop` | `~/Library/LaunchAgents/com.relogiovivo.screensaver.plist` |

Se você mover a pasta do app depois de ativar a inicialização automática,
desative e ative de novo para atualizar o caminho.

## Observações por sistema

### Windows

- Funciona em Windows 10/11 com Python normal ou Microsoft Store.
- A inicialização automática usa o `pythonw.exe` quando disponível, então
  não aparece janela de console.
- A captura usa o Pillow (`ImageGrab`) na tela principal.

### Ubuntu / Linux

- **X11**: a inatividade é detectada por `xprintidle`, `libXss` ou pelo
  D-Bus do ambiente. A captura usa o Pillow.
- **Wayland**: a inatividade é detectada pelo D-Bus do GNOME (Mutter) ou do
  KDE. Como o Wayland não permite captura direta, o app usa `grim`,
  `gnome-screenshot`, `spectacle`, `scrot`, `maim` ou `import`.
  Instale pelo menos um deles.
- O arquivo `.desktop` é criado em `~/.config/autostart/`.

### macOS

- Autorize **Gravação de Tela** em
  **Ajustes do Sistema → Privacidade e Segurança → Gravação de Tela**.
  Sem isso, a captura pode sair em branco ou mostrar só o papel de parede.
  Isso vale só para o estilo "Prévia da tela"; o estilo "Só o relógio" não
  captura nada.
- A inatividade vem do `ioreg` (`IOHIDSystem`).
- A inicialização usa um LaunchAgent em `~/Library/LaunchAgents/`.
- Em telas Retina a imagem é reduzida automaticamente para o tamanho lógico.

### Vários monitores

O protetor cobre e captura a **tela principal**. Se quiser suporte a todos os
monitores, isso pode ser evoluído, mas o comportamento atual evita imagens
esticadas entre telas.

### Vídeos e jogos

Como o critério é a inatividade do teclado/mouse, o protetor também aparece
se você estiver só assistindo a um vídeo. Aumente os minutos nas
configurações se isso incomodar.

## Diagnóstico de problemas

```bash
python relogio_vivo.py --check
```

Ele mostra a versão do Python/Tk/Pillow, o método de detecção de inatividade,
os capturadores disponíveis, o caminho da configuração e se a inicialização
automática está ativa.

- **Não aparece**: confira se o app está em execução e veja o log.
- **Captura preta no macOS**: falta a permissão de Gravação de Tela.
- **Captura falha no Wayland**: instale `grim` ou `gnome-screenshot`.
- **Inatividade indisponível**: no Linux instale `xprintidle` e `libxss1`;
  no GNOME/KDE o D-Bus normalmente já resolve.
- **Quero ver a imagem sem abrir o protetor**:
  `python relogio_vivo.py --snapshot previa.png` (a prévia segue o estilo
  configurado; use `--snapshot p.png --mode relogio` para o relógio sozinho)
- **Linux: "Permission denied"** ao rodar o binário baixado do GitHub: o
  GitHub não guarda o bit de execução. Use o `.tar.gz` (já vem certo) ou
  `chmod +x RelogioVivo-linux-x64`.
- **Linux: "GLIBC_2.xx not found"**: o binário foi compilado numa versão mais
  nova que a sua. Use o instalador (`curl ... | bash`), que roda com o Python
  do seu sistema e não depende de glibc.
- **Linux: "Pillow sem suporte a Tkinter"**: falta o `ImageTk`.
  `sudo apt install python3-pil.imagetk` (o instalador já cuida disso).

## Executáveis

O PyInstaller **não faz compilação cruzada**: cada sistema gera o seu próprio
binário. Por isso existem três scripts, um para cada plataforma.

### Baixar pronto

Todos os binários são gerados em `dist/` e publicados nos **dois ZIPs** da
release: <https://github.com/bernardoalvescaetano888-glitch/relogio-vivo/releases/latest>
(`install.zip` para instaladores, `portatil.zip` para as versões sem instalação).
No Linux, prefira o **instalador** acima; o `.tar.gz` já vem com o bit de
execução certo.

| Sistema | Arquivo (dentro do ZIP) | Observação |
|---|---|---|
| Windows 10/11 Intel ou AMD | `RelogioVivo-Setup-*-win-x64.exe` | **instalador completo** |
| Windows ARM (Snapdragon) | `RelogioVivo-Setup-*-win-arm64.exe` | instalador nativo |
| Windows (portátil) | `RelogioVivo-win-x64.exe` / `-win-arm64.exe` | sem instalar nada |
| Debian/Ubuntu | `relogio-vivo_*_all.deb` | instalador completo |
| Ubuntu/Debian x86_64 | `RelogioVivo-linux-x64.tar.gz` | binário portátil |
| Linux ARM64 | `RelogioVivo-linux-arm64.tar.gz` | Raspberry Pi, notebooks ARM |
| macOS Apple Silicon | `RelogioVivo-Setup-*-macos-arm64.pkg` | instalador completo |
| macOS Intel | `RelogioVivo-Setup-*-macos-x64.pkg` | instalador completo |
| macOS (portátil) | `RelogioVivo-macos-arm64.zip` / `-x64.zip` | `.app` solto |

```bash
tar -xzf RelogioVivo-linux-x64.tar.gz     # já sai executável
./RelogioVivo-linux-x64
```

No macOS, se o Gatekeeper bloquear:

```bash
xattr -dr com.apple.quarantine RelogioVivo.app
```

### Windows (já gerado)

`dist\RelogioVivo-win-x64.exe` e `dist\RelogioVivo-win-arm64.exe`.

- `-win-x64` roda em qualquer Windows 10/11 Intel ou AMD — **use este** na
  maioria dos casos. Também funciona em Windows ARM64, por emulação.
- `-win-arm64` é nativo para Snapdragon/ARM (menor e mais rápido).

Os dois já saem com ícone próprio e propriedades de versão (`1.3.0.0`), então
o Explorer mostra "Relógio Vivo" em vez de "python".

Para regerar os portáteis:

```powershell
powershell -ExecutionPolicy Bypass -File build_windows.ps1
```

### Windows: gerar o instalador

Depois de compilar os `.exe`, com o **Inno Setup 6.3+** instalado
(`winget install JRSoftware.InnoSetup`):

```powershell
powershell -ExecutionPolicy Bypass -File installer\windows\build_setup.ps1
```

Gera `dist\RelogioVivo-Setup-<versao>-win-x64.exe` e `-win-arm64.exe`. O
script do Inno fica em `installer/windows/relogio-vivo.iss` e pode ser aberto
na interface do Inno Setup para editar textos e comportamentos.

### Linux (rodar no Linux)

```bash
sudo apt install python3 python3-venv python3-tk   # Ubuntu/Debian
chmod +x build_linux.sh
./build_linux.sh
```

Gera `dist/RelogioVivo-linux-x64` (ou `-arm64`, conforme a máquina). No
Wayland, instale também `grim` (ou `gnome-screenshot`/`spectacle`).

O `dist/RelogioVivo-linux-arm64` incluído foi compilado num Ubuntu ARM64
(WSL) e serve para ARM (Raspberry Pi, notebooks Snapdragon, servidores ARM).
Para Ubuntu/Debian x86_64 comum, rode `build_linux.sh` num Linux x64 ou use
o workflow do GitHub.

### Linux: gerar o pacote .deb

Em qualquer Debian/Ubuntu, com `dpkg-deb` (já vem no sistema):

```bash
bash installer/linux/build_deb.sh
# dist/relogio-vivo_<versao>_all.deb

sudo apt install ./dist/relogio-vivo_*.deb
```

O pacote é `Architecture: all` (só arquivos Python + ícone + `.desktop`) e
declara as dependências `python3`, `python3-tk` e `python3-pil.imagetk`, então
o `apt` instala tudo sozinho. Ao remover com `apt remove relogio-vivo`, os
arquivos do sistema somem e as configurações do usuário são mantidas.

### macOS: gerar o instalador .pkg

```bash
./build_macos.sh                    # gera dist/RelogioVivo.app
bash installer/macos/build_pkg.sh   # gera o .pkg
bash installer/macos/build_pkg.sh --dmg   # gera também um .dmg
```

O `.pkg` instala em `/Applications`. Ele não é assinado (seria preciso uma
conta Apple Developer), então o primeiro clique deve ser com o botão direito →
**Abrir**.

### macOS (rodar no Mac)

```bash
chmod +x build_macos.sh
./build_macos.sh
```

Gera `dist/RelogioVivo.app`. Como o app não é assinado, o Gatekeeper pode
bloquear na primeira abertura:

```bash
xattr -dr com.apple.quarantine dist/RelogioVivo.app
```

### Gerar os três sem ter Linux/Mac: GitHub Actions

O workflow `.github/workflows/build.yml` compila Windows (x64 e ARM64), Linux
x64 e macOS (arm64 e Intel) em máquinas nativas, gera **os instaladores**
(`.exe`, `.deb` e `.pkg`) e sobe tudo como artefatos. Numa tag, publica
automaticamente na release.

1. Suba a pasta para um repositório no GitHub.
2. Aba **Actions → Gerar executáveis → Run workflow**.
3. Baixe os artefatos ao final, ou crie uma tag para publicar na release:

```bash
git tag v1.3.0
git push origin v1.3.0
```

### Depois de gerar

Com os instaladores, o autostart e os atalhos já ficam prontos. Nos binários
portáteis, abra o executável uma vez e ative a inicialização automática pela
janela (o comando de autostart aponta para o executável quando o app está
empacotado).

### Linha de comando no executável

O build é `--windowed` (sem console). Se você passar um argumento como
`--check` ou `--snapshot`, a saída aparece numa janela com botão **Copiar**,
porque não há terminal para imprimir.

## Como o código está organizado

Tudo em `relogio_vivo.py`:

- `Config` e caminhos por sistema;
- `enable_autostart` / `disable_autostart` (Windows, Linux e macOS);
- `IdleMonitor` (GetLastInputInfo, ioreg, D-Bus, xprintidle, libXss);
- captura de tela com fallback por ferramenta;
- `build_scene` (fundo + cartão com sombra e barra);
- `ScreensaverWindow` (animação, relógio ao vivo e saída por input);
- `SettingsWindow` (interface Tkinter);
- `RelogioVivo` (ciclo de inatividade, instância única e pedidos);
- `CliReport` / `show_text_dialog` (saída da CLI em janela, para o build sem console);
- CLI e diagnóstico.

Os instaladores ficam em `installer/`:

- `installer/windows/relogio-vivo.iss` — script do Inno Setup;
- `installer/windows/build_setup.ps1` — gera os `Setup .exe`;
- `installer/linux/build_deb.sh` — gera o `.deb`;
- `installer/macos/build_pkg.sh` — gera o `.pkg` (e `.dmg` opcional);
- `installer/README.md` — o que cada um instala e como publicar.
