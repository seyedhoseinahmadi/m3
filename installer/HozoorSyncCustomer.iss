#define MyAppName "HiMate Sync"
#define MyAppVersion GetEnv("HOZOOR_APP_VERSION")
#if MyAppVersion == ""
  #define MyAppVersion "0.4.2"
#endif
#define MyAppPublisher "Avaye Farda Media"
#define MyAppExeName "HiMateSync.exe"

[Setup]
AppId={{A7AFB883-8062-4B40-A5A9-7D740F474164}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Avaye Farda\HiMate Sync
DefaultGroupName=Avaye Farda\HiMate Sync
DisableProgramGroupPage=yes
OutputDir=..\Output
OutputBaseFilename=HiMateSync_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName=HiMate Sync
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked
Name: "startup"; Description: "Run HiMate Sync automatically when Windows starts"; GroupDescription: "Startup:"; Flags: checkedonce

[Files]
Source: "..\dist\HiMateSync.exe"; DestDir: "{app}"; DestName: "{#MyAppExeName}"; Flags: ignoreversion

[Icons]
Name: "{group}\HiMate Sync"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall HiMate Sync"; Filename: "{uninstallexe}"
Name: "{autodesktop}\HiMate Sync"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "HiMate Sync"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch HiMate Sync"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\HiMateSync\temp"
