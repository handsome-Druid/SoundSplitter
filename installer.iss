#define AppName   ExecAndGetFirstLine("uv", "run python -c print(__import__('xml.etree.ElementTree',fromlist=['x']).parse('src/ss/integration/app/ui/main_window.ui').getroot().find('widget/property/string').text)", SourcePath)
#define AppVer    ExecAndGetFirstLine("uv", "run python -c print(__import__('tomllib').load(open('pyproject.toml','rb'))['project']['version'])", SourcePath)
#define AppAuthor ExecAndGetFirstLine("uv", "run python -c print(__import__('tomllib').load(open('pyproject.toml','rb'))['project']['authors'][0]['name'])", SourcePath)
#define AppUrl    ExecAndGetFirstLine("uv", "run python -c print(__import__('tomllib').load(open('pyproject.toml','rb'))['project']['urls']['Repository'])", SourcePath)

#define Rcc      Exec("uv", "run pyside6-rcc src\ss\integration\app\resources\resources.qrc -o src\ss\integration\app\resources\resources_rc.py", SourcePath)
#define UicMain  Exec("uv", "run pyside6-uic src\ss\integration\app\ui\main_window.ui -o src\ss\integration\app\ui\main_window_ui.py", SourcePath)
#define UicPref  Exec("uv", "run pyside6-uic src\ss\integration\app\ui\preferences.ui -o src\ss\integration\app\ui\preferences_ui.py", SourcePath)
#define LRelease Exec("uv", "run pyside6-lrelease translation\zh_CN.ts -o translation\zh_CN.qm", SourcePath)
#define Nuitka   Exec("uv", "run nuitka --mode=standalone --python-flag=-m --follow-imports --output-dir=build --enable-plugin=pyside6 --noinclude-custom-mode=pydantic.v1:bytecode --include-module=av._cyutil --windows-console-mode=hide --windows-icon-from-ico=resources\icon.ico --include-windows-runtime-dlls=no src\ss", SourcePath)
#define Bin      Exec("cmd.exe", "/c rmdir /s /q build\bin 2>nul & move build\ss.dist build\bin", SourcePath)
#define I18n     Exec("cmd.exe", "/c mkdir build\translation 2>nul & copy /Y translation\*.qm build\translation\", SourcePath)

#if Rcc + UicMain + UicPref + LRelease + Nuitka + Bin + I18n != 0
  #error Failed to build the application.
#endif

[Setup]
AppId=6986C195-6F0C-4D3B-B6C0-9FA39D2E97AE
AppName={#AppName}
AppVersion={#AppVer}
AppPublisher={#AppAuthor}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}/issues
AppUpdatesURL={#AppUrl}/releases
DefaultDirName={commonpf}\{#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=LICENSE
SetupIconFile=resources\icon.ico
UninstallDisplayIcon={app}\bin\ss.exe
SourceDir={#SourcePath}
OutputDir=build
OutputBaseFilename={#AppName}-{#AppVer}-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "build\bin\*"; DestDir: "{app}\bin"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "build\translation\*.qm"; DestDir: "{app}\translation"; Flags: ignoreversion

[Icons]
Name: "{commonprograms}\{#AppName}"; Filename: "{app}\bin\ss.exe"

[Run]
Filename: "{app}\bin\ss.exe"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
Filename: "https://vb-audio.com/Cable/"; Description: "VB-CABLE is not installed. Open its download page"; Flags: shellexec postinstall nowait skipifsilent; Check: not VbCableInstalled

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\{#AppName}"; Check: ShouldDeleteLocalData

[Code]
var
  DeleteLocalDataPage: TInputOptionWizardPage;

function VbCableInstalled: Boolean;
begin
  Result := RegKeyExists(HKEY_LOCAL_MACHINE, 'SYSTEM\CurrentControlSet\Services\VBAudioVACMME');
end;

function ShouldDeleteLocalData: Boolean;
begin
  Result := DeleteLocalDataPage.Values[0];
end;

procedure InitializeUninstallWizard;
begin
  DeleteLocalDataPage := CreateInputOptionPage(
    wpWelcome,
    'Remove Local Data',
    'Choose whether to remove local data',
    'If selected, SoundSplitter configuration and local settings will also be removed.',
    False,
    False
  );
  DeleteLocalDataPage.Add('Remove local data');
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    if RegValueExists(
      HKEY_CURRENT_USER,
      'Software\Microsoft\Windows\CurrentVersion\Run',
      '{#AppName}'
    ) then
    begin
      RegDeleteValue(
        HKEY_CURRENT_USER,
        'Software\Microsoft\Windows\CurrentVersion\Run',
        '{#AppName}'
      );
    end;
  end;
end;

