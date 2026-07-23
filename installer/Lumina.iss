#ifndef MyAppVersion
  #define MyAppVersion "0.1.0"
#endif
#ifdef QaBuild
  #define MyAppName "Lumina QA"
  #define MyAppId "{{D1CFEEC2-A10C-4C6A-8628-4AD25950BCE8}"
  #define MyDataDirName "Lumina-QA"
  #define MyAppPort 8127
  #define MyOutputBase "install_Lumina-QA-"
#else
  #define MyAppName "Lumina"
  #define MyAppId "{{5A7946E2-7B9A-4F4A-9C18-3F5F4F6DA5C1}"
  #define MyDataDirName "Lumina"
  #define MyAppPort 8000
  #define MyOutputBase "install_Lumina-"
#endif

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Lumina
AppPublisherURL=https://github.com/Throb7777/lumina-study-coach
AppSupportURL=https://github.com/Throb7777/lumina-study-coach/issues
AppUpdatesURL=https://github.com/Throb7777/lumina-study-coach/releases
VersionInfoCompany=Lumina Contributors
VersionInfoDescription=Lumina local learning flow coach
VersionInfoProductName=Lumina
VersionInfoProductVersion={#MyAppVersion}
VersionInfoVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
DisableDirPage=no
UsePreviousAppDir=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
WizardStyle=modern
SetupIconFile=..\launcher\assets\lumina.ico
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\Lumina.exe
UninstallFilesDir={app}\uninstall_Lumina
LicenseFile=..\LICENSE
OutputDir=..\output\installer
OutputBaseFilename={#MyOutputBase}{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
CloseApplications=no
RestartApplications=no
Uninstallable=yes
CreateUninstallRegKey=yes
ChangesAssociations=no
ChangesEnvironment=no
SetupLogging=yes

[Languages]
Name: "chinesesimp"; MessagesFile: "languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式："

[Files]
Source: "..\output\release-package\Lumina\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\Lumina.exe"; WorkingDir: "{app}"
Name: "{group}\停止 {#MyAppName}"; Filename: "{app}\Lumina.exe"; Parameters: "--stop"; WorkingDir: "{app}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\Lumina.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\Lumina.exe"; Parameters: "--initialize-install"; Flags: runhidden waituntilterminated
Filename: "{app}\Lumina.exe"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\install-config.json"
Type: filesandordirs; Name: "{app}\_internal"
Type: dirifempty; Name: "{app}\uninstall_Lumina"
Type: dirifempty; Name: "{app}"

[Code]
var
  DeleteUserData: Boolean;
  UserDataBackupSucceeded: Boolean;

function JsonEscape(Value: String): String;
begin
  Result := Value;
  StringChangeEx(Result, '\', '\\', True);
  StringChangeEx(Result, '"', '\"', True);
end;

function DataDirectory(): String;
begin
  Result := ExpandConstant('{localappdata}\{#MyDataDirName}');
end;

function AppExecutable(): String;
begin
  Result := ExpandConstant('{app}\Lumina.exe');
end;

function RunLumina(Parameters: String; var ResultCode: Integer): Boolean;
begin
  Result := Exec(AppExecutable(), Parameters, ExpandConstant('{app}'), SW_HIDE,
    ewWaitUntilTerminated, ResultCode);
end;

function StopLuminaForUninstall(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  if not FileExists(AppExecutable()) then
    Exit;

  repeat
    Result :=
      RunLumina('--stop --silent', ResultCode) and (ResultCode = 0);
    if Result then
      Exit;
    if UninstallSilent then
      Exit;
  until MsgBox(
    'Lumina 尚未完全关闭，程序文件仍在使用中。' + #13#10 + #13#10 +
    '请结束正在运行的任务后重试，或取消本次卸载。',
    mbError, MB_RETRYCANCEL or MB_DEFBUTTON1) <> IDRETRY;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
  BackupDirectory: String;
begin
  Result := '';
  if not FileExists(AppExecutable()) then
    Exit;

  if not RunLumina('--stop --silent', ResultCode) or (ResultCode <> 0) then
  begin
    Result := 'Lumina 未能完全关闭，安装已停止。请稍后重试。';
    Exit;
  end;
  BackupDirectory := AddBackslash(DataDirectory()) + 'backups';
  if not ForceDirectories(BackupDirectory) then
  begin
    Result := '无法创建升级备份目录，安装已停止。';
    Exit;
  end;
  if not RunLumina('--backup-data "' + BackupDirectory + '"', ResultCode) or
     (ResultCode <> 0) then
    Result := '现有学习数据备份失败，安装已停止，原数据未修改。';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigText: String;
begin
  if CurStep <> ssPostInstall then
    Exit;
  ConfigText := '{"data_dir":"' + JsonEscape(DataDirectory()) +
    '","port":{#MyAppPort}}';
  if not SaveStringToFile(ExpandConstant('{app}\install-config.json'),
    ConfigText, False) then
    RaiseException('无法写入 Lumina 安装配置。');
end;

function InitializeUninstall(): Boolean;
var
  ResultCode: Integer;
  BackupDirectory: String;
begin
  Result := True;
  DeleteUserData := False;
  UserDataBackupSucceeded := False;
  if not UninstallSilent then
  begin
    if MsgBox(
      '默认只卸载程序并保留课程、材料和设置。' + #13#10 + #13#10 +
      '是否同时删除全部本地学习数据？',
      mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DeleteUserData :=
        MsgBox(
          '这会删除全部课程、记录、材料、设置、日志和本地索引。' + #13#10 +
          '卸载器会先在“文档\Lumina Backups”创建完整备份。' + #13#10#13#10 +
          '确定继续吗？',
          mbError, MB_YESNO or MB_DEFBUTTON2) = IDYES;
  end;

  Result := StopLuminaForUninstall();
  if not Result then
    Exit;

  if DeleteUserData then
  begin
    BackupDirectory := ExpandConstant('{userdocs}\Lumina Backups');
    if ForceDirectories(BackupDirectory) and
       RunLumina('--backup-data "' + BackupDirectory + '"', ResultCode) and
       (ResultCode = 0) then
      UserDataBackupSucceeded := True
    else
    begin
      DeleteUserData := False;
      MsgBox(
        '学习数据备份失败。程序将继续卸载，但本地学习数据会完整保留。',
        mbError, MB_OK);
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and DeleteUserData and
     UserDataBackupSucceeded then
    DelTree(DataDirectory(), True, True, True);
end;
