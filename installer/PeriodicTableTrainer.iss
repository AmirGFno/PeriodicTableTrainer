#ifndef MyAppVersion
  #define MyAppVersion "1.1.7"
#endif

#define MyAppName "Periodic Table Trainer"
#define MyAppExeName "PeriodicTableTrainer.exe"

[Setup]
AppId={{4e8fe372-e3c0-432f-b418-970ccc3d8e8f}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Periodic Table Trainer
AppPublisherURL=https://github.com/AmirGFno/PeriodicTableTrainer
DefaultDirName={autopf}\PeriodicTableTrainer
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=..\app.ico
OutputDir=..\dist\installer
OutputBaseFilename=PeriodicTableTrainer-Setup-{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: checkedonce

[Files]
Source: "..\dist\PeriodicTableTrainer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; WorkingDir: "{app}"; Flags: postinstall nowait skipifsilent
