; Script de Inno Setup: genera Instalar_LaPampa.exe (se compila con CREAR_INSTALADOR.bat)
[Setup]
AppName=La Pampa
AppVersion=2.1
AppPublisher=La Pampa
DefaultDirName={localappdata}\Programs\LaPampa
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Instalador
OutputBaseFilename=Instalar_LaPampa
SetupIconFile=icono.ico
UninstallDisplayIcon={app}\LaPampa.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "dist\LaPampa.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autodesktop}\La Pampa"; Filename: "{app}\LaPampa.exe"; IconFilename: "{app}\LaPampa.exe"
Name: "{autoprograms}\La Pampa"; Filename: "{app}\LaPampa.exe"

[Run]
Filename: "{app}\LaPampa.exe"; Description: "Abrir La Pampa ahora"; Flags: nowait postinstall skipifsilent
