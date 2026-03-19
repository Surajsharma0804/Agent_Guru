; Agent Guru - Windows NSIS Installer Script
; Requires NSIS 3.x (https://nsis.sourceforge.io/)
;
; Build command:
;   makensis installer\windows\agent_guru.nsi
;
; Output: installer\windows\AgentGuru-Setup-x64.exe

!define APP_NAME "Agent Guru"
!define APP_VERSION "1.0.0"
!define APP_PUBLISHER "Agent Guru Team"
!define APP_URL "https://github.com/agent-guru/agent-guru"
!define APP_EXE "agent_guru.exe"
!define APP_ICON "..\..\assets\icon.ico"
!define INSTALL_DIR "$PROGRAMFILES64\Agent Guru"
!define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\AgentGuru"
!define REGISTRY_KEY "Software\AgentGuru"

; Compression
SetCompressor /SOLID lzma
SetCompressorDictSize 32

; Metadata
Name "${APP_NAME} ${APP_VERSION}"
OutFile "AgentGuru-Setup-x64.exe"
InstallDir "${INSTALL_DIR}"
InstallDirRegKey HKLM "${REGISTRY_KEY}" "InstallDir"
RequestExecutionLevel admin
ShowInstDetails show
ShowUnInstDetails show

; Modern UI
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"

; UI Settings
!define MUI_ABORTWARNING
!define MUI_ICON "${APP_ICON}"
!define MUI_UNICON "${APP_ICON}"

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\..\LICENSE"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "Launch Agent Guru"
!define MUI_FINISHPAGE_SHOWREADME "$INSTDIR\README.txt"
!insertmacro MUI_PAGE_FINISH

; Uninstaller pages
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; Languages
!insertmacro MUI_LANGUAGE "English"

; Version info
VIProductVersion "${APP_VERSION}.0"
VIAddVersionKey /LANG=${LANG_ENGLISH} "ProductName" "${APP_NAME}"
VIAddVersionKey /LANG=${LANG_ENGLISH} "ProductVersion" "${APP_VERSION}"
VIAddVersionKey /LANG=${LANG_ENGLISH} "CompanyName" "${APP_PUBLISHER}"
VIAddVersionKey /LANG=${LANG_ENGLISH} "FileDescription" "${APP_NAME} Installer"
VIAddVersionKey /LANG=${LANG_ENGLISH} "FileVersion" "${APP_VERSION}"
VIAddVersionKey /LANG=${LANG_ENGLISH} "LegalCopyright" "Copyright (C) 2026 ${APP_PUBLISHER}"

; ============================================================
; Sections
; ============================================================

Section "Core Application" SecCore
  SectionIn RO  ; Required - cannot be deselected

  SetOutPath "$INSTDIR"

  ; Main executable and Python runtime
  File /r "..\..\dist\windows\*.*"

  ; Models directory
  SetOutPath "$INSTDIR\models"
  File /r "..\..\models\*.*"

  ; Assets
  SetOutPath "$INSTDIR\assets"
  File /r "..\..\assets\*.*"

  ; Write registry entries
  WriteRegStr HKLM "${REGISTRY_KEY}" "InstallDir" "$INSTDIR"
  WriteRegStr HKLM "${REGISTRY_KEY}" "Version" "${APP_VERSION}"

  ; Write uninstaller
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; Add/Remove Programs entry
  WriteRegStr HKLM "${UNINSTALL_KEY}" "DisplayName" "${APP_NAME}"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "Publisher" "${APP_PUBLISHER}"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "URLInfoAbout" "${APP_URL}"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKLM "${UNINSTALL_KEY}" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
  WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoModify" 1
  WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoRepair" 1
  WriteRegStr HKLM "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\${APP_EXE}"

  ; Estimate install size (KB)
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD HKLM "${UNINSTALL_KEY}" "EstimatedSize" "$0"

SectionEnd

Section "Desktop Shortcut" SecDesktop
  CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
SectionEnd

Section "Start Menu Shortcuts" SecStartMenu
  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Auto-start on Login" SecAutoStart
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "AgentGuru" '"$INSTDIR\${APP_EXE}" --minimized'
SectionEnd

; Section descriptions
!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecCore} "Core Agent Guru application files (required)"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} "Create a desktop shortcut"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecStartMenu} "Create Start Menu shortcuts"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecAutoStart} "Start Agent Guru automatically when Windows starts"
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; ============================================================
; Installer Functions
; ============================================================

Function .onInit
  ; Check 64-bit Windows
  ${IfNot} ${RunningX64}
    MessageBox MB_OK|MB_ICONSTOP "Agent Guru requires a 64-bit version of Windows."
    Abort
  ${EndIf}

  ; Check Windows 10 or later
  ${If} ${AtLeastWin10}
    ; OK
  ${Else}
    MessageBox MB_OK|MB_ICONSTOP "Agent Guru requires Windows 10 or later."
    Abort
  ${EndIf}

  ; Check for existing installation
  ReadRegStr $0 HKLM "${REGISTRY_KEY}" "InstallDir"
  ${If} $0 != ""
    MessageBox MB_YESNO|MB_ICONQUESTION \
      "Agent Guru is already installed at $0.$\n$\nDo you want to upgrade/reinstall?" \
      IDYES continue
    Abort
    continue:
  ${EndIf}
FunctionEnd

Function .onInstSuccess
  ; Create user data directories
  CreateDirectory "$APPDATA\AgentGuru"
  CreateDirectory "$APPDATA\AgentGuru\logs"
  CreateDirectory "$APPDATA\AgentGuru\memory"
  CreateDirectory "$APPDATA\AgentGuru\config"
FunctionEnd

; ============================================================
; Uninstaller
; ============================================================

Section "Uninstall"
  ; Remove auto-start entry
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "AgentGuru"

  ; Remove shortcuts
  Delete "$DESKTOP\${APP_NAME}.lnk"
  RMDir /r "$SMPROGRAMS\${APP_NAME}"

  ; Remove installed files
  RMDir /r "$INSTDIR"

  ; Remove registry entries
  DeleteRegKey HKLM "${REGISTRY_KEY}"
  DeleteRegKey HKLM "${UNINSTALL_KEY}"

  ; Optionally remove user data
  MessageBox MB_YESNO|MB_ICONQUESTION \
    "Do you want to remove your Agent Guru data (conversation history, settings)?$\n$\nSelect No to keep your data." \
    IDNO skip_data
  RMDir /r "$APPDATA\AgentGuru"
  skip_data:

SectionEnd
