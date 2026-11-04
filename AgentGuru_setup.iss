; Agent Guru - Inno Setup script: the small installer.
;
; It carries the frozen launcher (AgentGuru.spec) and the application source,
; and nothing else. Packages, models and voices are installed by GENESIS after
; the person approves a plan, so the download stays small and the install is
; complete. The old script installed per machine behind an admin prompt with
; everything frozen in.
;
; Per user, with no admin prompt. No startup entry, service, firewall rule or
; PATH change unless the person ticks an option that starts unticked.
; Uninstall removes the app and its private runtime and keeps the user's data,
; models and settings unless the person ticks the box. Not signed, so Windows
; SmartScreen will probably warn on first run.
;
; Build, from the repository root, after PyInstaller:
;   installer\windows\build_installer.ps1

#define MyAppName "Agent Guru"
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
#define MyAppPublisher "Suraj Sharma"
#define MyAppURL "https://github.com/Surajsharma0804/Agent_Guru"
#define MyAppExeName "AgentGuru.exe"
#ifndef DistDir
  #define DistDir "dist\AgentGuru"
#endif

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF0123456789}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
PrivilegesRequired=lowest
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=AgentGuru-{#MyAppVersion}-Setup
SetupIconFile=assets\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
VersionInfoVersion={#MyAppVersion}
VersionInfoDescription={#MyAppName} Setup
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startup"; Description: "Start Agent Guru when I sign in"; GroupDescription: "Optional:"; Flags: unchecked

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; The application source: what the private runtime runs. Tests are left out.
Source: "Agent_Guru\*"; DestDir: "{app}\app\Agent_Guru"; Excludes: "tests,__pycache__,*.pyc,test_*.py,conftest.py"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "main.py"; DestDir: "{app}\app"; Flags: ignoreversion
Source: "requirements-lock.txt"; DestDir: "{app}\app"; Flags: ignoreversion
Source: "assets\*"; DestDir: "{app}\app\assets"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "NOTICE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startup

[Run]
; Offered on the last page and never run silently: GENESIS asks before it
; downloads anything.
Filename: "{app}\{#MyAppExeName}"; Description: "Set up Agent Guru now"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; The private runtime, its download cache and the journal were made after
; install, so Inno Setup does not know them. Inside {app} only: user data,
; models and settings are outside it and stay.
Type: filesandordirs; Name: "{app}\runtime"

[Code]
var
  RemoveData: Boolean;

function InitializeUninstall(): Boolean;
begin
  RemoveData := MsgBox('Also delete your Agent Guru data?' + #13#10 + #13#10 +
    'This removes your memory, settings, reminders and downloaded models. ' +
    'Choose No to keep them. No is the safe choice.',
    mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES;
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and RemoveData then
    DelTree(ExpandConstant('{localappdata}\agent_guru'), True, True, True);
end;
