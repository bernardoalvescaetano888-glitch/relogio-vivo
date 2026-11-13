; Instalador do Relógio Vivo para Windows (Inno Setup 6.3+).
;
; Gera um Setup .exe completo:
;   - instala em Program Files (ou por usuário, sem pedir administrador);
;   - atalho no Menu Iniciar e na Área de Trabalho;
;   - atalhos "Ver protetor agora" e "Diagnóstico";
;   - inicialização automática com o Windows (opcional);
;   - desinstalador no Menu Iniciar e em Aplicativos instalados.
;
; Uso:
;   iscc /DArch=x64   installer\windows\relogio-vivo.iss
;   iscc /DArch=arm64 installer\windows\relogio-vivo.iss
;
; Ou simplesmente: powershell -ExecutionPolicy Bypass -File installer\windows\build_setup.ps1

#ifndef AppVersion
  #define AppVersion "1.3.1"
#endif

#ifndef Arch
  #define Arch "x64"
#endif

#if Arch == "arm64"
  #define SourceExe "..\..\dist\RelogioVivo-win-arm64.exe"
  #define ArchAllowed "arm64"
#else
  #define SourceExe "..\..\dist\RelogioVivo-win-x64.exe"
  #define ArchAllowed "x64compatible"
#endif

[Setup]
AppId={{D8C1B9E4-5A2F-4C3B-9E1D-7F6A0B2C4D5E}
AppName=Relógio Vivo
AppVersion={#AppVersion}
AppVerName=Relógio Vivo {#AppVersion}
AppPublisher=Relógio Vivo
AppPublisherURL=https://github.com/bernardoalvescaetano888-glitch/relogio-vivo
AppSupportURL=https://github.com/bernardoalvescaetano888-glitch/relogio-vivo/issues
AppUpdatesURL=https://github.com/bernardoalvescaetano888-glitch/relogio-vivo/releases
DefaultDirName={autopf}\Relogio Vivo
DefaultGroupName=Relógio Vivo
DisableProgramGroupPage=yes
OutputDir=..\..\dist
OutputBaseFilename=RelogioVivo-Setup-{#AppVersion}-win-{#Arch}
SetupIconFile=..\..\assets\icon.ico
UninstallDisplayIcon={app}\RelogioVivo.exe
UninstallDisplayName=Relógio Vivo {#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed={#ArchAllowed}
ArchitecturesInstallIn64BitMode={#ArchAllowed}
MinVersion=10.0
CloseApplications=no
UsePreviousAppDir=yes
UsePreviousTasks=yes
AllowNoIcons=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar um atalho na Área de Trabalho"; GroupDescription: "Atalhos:"; Flags: checkedonce
Name: "autostart"; Description: "Iniciar o Relógio Vivo junto com o Windows"; GroupDescription: "Inicialização:"; Flags: checkedonce

[Files]
Source: "{#SourceExe}"; DestDir: "{app}"; DestName: "RelogioVivo.exe"; Flags: ignoreversion

[Icons]
Name: "{group}\Relógio Vivo"; Filename: "{app}\RelogioVivo.exe"; WorkingDir: "{app}"
Name: "{group}\Ver protetor agora"; Filename: "{app}\RelogioVivo.exe"; Parameters: "--test"; WorkingDir: "{app}"
Name: "{group}\Diagnóstico"; Filename: "{app}\RelogioVivo.exe"; Parameters: "--check"; WorkingDir: "{app}"
Name: "{group}\Desinstalar o Relógio Vivo"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Relógio Vivo"; Filename: "{app}\RelogioVivo.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "RelogioVivo"; ValueData: """{app}\RelogioVivo.exe"" --background"; Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "{app}\RelogioVivo.exe"; Parameters: "--background"; Description: "Abrir o Relógio Vivo agora"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\RelogioVivo.exe"; Parameters: "--quit"; Flags: runhidden skipifdoesntexist; RunOnceId: "QuitRelogioVivo"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  { Fecha a instância em execução para poder substituir o .exe. }
  if CurStep = ssInstall then
  begin
    if FileExists(ExpandConstant('{app}\RelogioVivo.exe')) then
      Exec(ExpandConstant('{app}\RelogioVivo.exe'), '--quit', '', SW_HIDE,
        ewWaitUntilTerminated, ResultCode);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    if FileExists(ExpandConstant('{app}\RelogioVivo.exe')) then
      Exec(ExpandConstant('{app}\RelogioVivo.exe'), '--quit', '', SW_HIDE,
        ewWaitUntilTerminated, ResultCode);
  end;
end;
