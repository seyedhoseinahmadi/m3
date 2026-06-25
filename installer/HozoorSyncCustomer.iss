#define MyAppName "Hozoor Sync"
#define MyAppVersion "0.2.5"
#define MyAppPublisher "Avaye Farda Media"
#define MyAppURL "https://avayefardamedia.com"
#define MyAppExeName "HozoorSyncCustomer.exe"

[Setup]
AppId={{B5B49748-7D5A-4E75-91F2-HOZOOR024}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\Avaye Farda\Hozoor Sync
DefaultGroupName=Avaye Farda\Hozoor Sync
DisableProgramGroupPage=yes
OutputDir=..\Output
OutputBaseFilename=HozoorSyncCustomer_Setup_v0_2_5
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
SetupLogging=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: checkedonce
Name: "startup"; Description: "Run Hozoor Sync automatically when Windows starts"; GroupDescription: "Startup:"; Flags: checkedonce

[Files]
Source: "..\dist\HozoorSyncCustomer.exe"; DestDir: "{app}"; DestName: "{#MyAppExeName}"; Flags: ignoreversion
Source: "..\README_INSTALLER_FA.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README_MARKET_PRODUCT_FA.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\UI_FINAL_GUIDE_FA.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\customer_settings.example.json"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Hozoor Sync"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall Hozoor Sync"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Hozoor Sync"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Hozoor Sync"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Hozoor Sync"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\HozoorSyncCustomer\temp"
