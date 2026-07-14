#define MyAppName "GolfHub Perth"
#define MyAppVersion "4.0.0"
#define MyAppPublisher "GolfHub Perth"
#define MyAppExeName "GolfHub Perth.exe"

[Setup]
AppId={{3A5B6F39-F2DA-4B0A-AF37-7D2F1C7C4B31}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\GolfHub Perth
DefaultGroupName=GolfHub Perth
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
OutputDir=..\installer
OutputBaseFilename=GolfHub_Perth_Setup_v4
SetupIconFile=..\assets\golfhub_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Files]
Source: "..\dist\GolfHub Perth\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\GolfHub Perth"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\GolfHub Perth"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: checkedonce

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch GolfHub Perth"; Flags: nowait postinstall skipifsilent
