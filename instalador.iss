#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
; Este identificador NO debe cambiar nunca: es lo que permite que cada version nueva reemplace a la anterior.
AppId={{5727CCB4-70EA-45AD-A938-C707C8C610DA}
AppName=Dream & Travel Calculadora
AppVersion={#AppVersion}
AppPublisher=Dream & Travel
DefaultDirName={autopf}\Dream Travel Calculadora
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=Calculadora_Dream_Travel_Setup
SetupIconFile=icono_calculadora.ico
UninstallDisplayIcon={app}\Calculadora_Dream_Travel.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
#if FileExists(CompilerPath + "Languages\Spanish.isl")
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
#endif

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; Flags: unchecked

[Files]
Source: "dist\Calculadora_Dream_Travel.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Dream & Travel Calculadora"; Filename: "{app}\Calculadora_Dream_Travel.exe"
Name: "{autodesktop}\Dream & Travel Calculadora"; Filename: "{app}\Calculadora_Dream_Travel.exe"; Tasks: desktopicon

[InstallDelete]
; Limpia restos de versiones anteriores antes de copiar la nueva.
Type: files; Name: "{app}\Calculadora_Dream_Travel*.exe"
Type: filesandordirs; Name: "{app}\_internal"

[Run]
; Instalacion normal: pregunta si abrir el programa al terminar.
Filename: "{app}\Calculadora_Dream_Travel.exe"; Description: "Abrir la calculadora"; Flags: nowait postinstall skipifsilent
; Actualizacion automatica (modo silencioso): vuelve a abrir el programa sola.
Filename: "{app}\Calculadora_Dream_Travel.exe"; Flags: nowait skipifnotsilent

[Code]
function SetEnvironmentVariable(lpName, lpValue: String): Boolean;
  external 'SetEnvironmentVariableW@kernel32.dll stdcall';

function InitializeSetup(): Boolean;
begin
  { El programa reabierto no debe heredar la carpeta temporal del anterior (error "Failed to load Python DLL"). }
  SetEnvironmentVariable('PYINSTALLER_RESET_ENVIRONMENT', '1');
  Result := True;
end;
