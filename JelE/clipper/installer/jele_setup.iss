; JelE Clipper setup (Inno Setup 6). Built by the GitHub release workflow:
;   iscc /DMyVersion=6.20 /DSrc=<folder with clipper and python> installer\jele_setup.iss
; Puts its own Python inside the app (nothing else to install), lets you pick Light or Full before installing,
; makes the shortcuts with the J icon and has a clean uninstaller that asks before it removes your shorts.

#ifndef MyVersion
  #define MyVersion "0.0"
#endif
#ifndef Src
  #define Src "..\.."
#endif

[Setup]
AppId={{CE9E2ACB-8389-4AD2-AC65-6C5E0ABB49F7}
AppName=JelE Clipper
AppVersion={#MyVersion}
AppPublisher=JelE Studio
DefaultDirName=C:\JelE
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=JelE_Clipper_Setup
SetupIconFile={#Src}\clipper\jele.ico
UninstallDisplayIcon={app}\clipper\jele.ico
UninstallDisplayName=JelE Clipper
#if Ver >= EncodeVer(6,6,0)
WizardStyle=modern dark
WizardBackColor=$271811
#else
WizardStyle=modern
#endif
WizardImageFile={#SourcePath}img\side_0.bmp,{#SourcePath}img\side_1.bmp,{#SourcePath}img\side_2.bmp,{#SourcePath}img\side_3.bmp,{#SourcePath}img\side_4.bmp,{#SourcePath}img\side_5.bmp
WizardSmallImageFile={#SourcePath}img\small_0.bmp,{#SourcePath}img\small_1.bmp,{#SourcePath}img\small_2.bmp,{#SourcePath}img\small_3.bmp,{#SourcePath}img\small_4.bmp,{#SourcePath}img\small_5.bmp
DisableWelcomePage=no
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=no

[Messages]
WelcomeLabel1=Welcome to JelE Clipper
WelcomeLabel2=From stream to short.%n%nThe Clipper finds the best moments of your stream by itself and turns them into vertical shorts with captions, ready to post.%n%nInstalling takes a few minutes and needs an internet connection.
FinishedHeadingLabel=JelE Clipper is ready
FinishedLabel=Start it with the JelE Clipper icon on your desktop or in the start menu.%n%nIt keeps running as a small J icon next to the clock, so it can catch your clips while you stream.
ClickFinish=Click Finish to close the setup.

[Files]
Source: "{#Src}\clipper\*"; DestDir: "{app}\clipper"; Excludes: "data\*,shorts\*,__pycache__,tests\*,.venv\*,config.js,installer\Output\*"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "{#Src}\get-pip.py"; DestDir: "{app}\clipper\python"; Flags: ignoreversion

[Icons]
Name: "{autodesktop}\JelE Clipper"; Filename: "{app}\clipper\python\pythonw.exe"; Parameters: """{app}\clipper\launcher.pyw"""; WorkingDir: "{app}\clipper"; IconFilename: "{app}\clipper\jele.ico"
Name: "{autoprograms}\JelE Clipper"; Filename: "{app}\clipper\python\pythonw.exe"; Parameters: """{app}\clipper\launcher.pyw"""; WorkingDir: "{app}\clipper"; IconFilename: "{app}\clipper\jele.ico"

[Run]
Filename: "{app}\clipper\python\pythonw.exe"; Parameters: """{app}\clipper\launcher.pyw"""; WorkingDir: "{app}\clipper"; Description: "Start JelE Clipper now"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\clipper\python"
Type: filesandordirs; Name: "{app}\clipper\engine"
Type: filesandordirs; Name: "{app}\clipper\app\__pycache__"
Type: filesandordirs; Name: "{app}\clipper\__pycache__"

[Code]
var
  EdPage: TWizardPage;
  RbLight, RbFull: TNewRadioButton;
  HasNvidia: Boolean;

function NvidiaFound(): Boolean;
begin
  { NVIDIA, AMD or Intel Arc graphics card: their drivers leave these files }
  Result := FileExists(ExpandConstant('{sys}\nvidia-smi.exe')) or
            FileExists(ExpandConstant('{commonpf64}\NVIDIA Corporation\NVSMI\nvidia-smi.exe')) or
            FileExists(ExpandConstant('{sys}\amdxc64.dll')) or FileExists(ExpandConstant('{sys}\amdvlk64.dll'));
end;

function Txt(Top: Integer; Caption: String; Bold: Boolean; Size: Integer; Color: Integer; Indent: Integer): TNewStaticText;
begin
  Result := TNewStaticText.Create(EdPage);
  Result.Parent := EdPage.Surface;
  Result.Left := ScaleX(Indent);
  Result.Top := Top;
  Result.Width := EdPage.SurfaceWidth - ScaleX(Indent);
  Result.WordWrap := True;
  Result.AutoSize := True;
  if Bold then Result.Font.Style := [fsBold];
  if Size > 0 then Result.Font.Size := Size;
  if Color >= 0 then Result.Font.Color := Color;
  Result.Caption := Caption;
end;

function Choice(Top: Integer; Title, Fit, Body: String; Rec: Boolean): TNewRadioButton;
var
  T: TNewStaticText;
begin
  Result := TNewRadioButton.Create(EdPage);
  Result.Parent := EdPage.Surface;
  Result.Left := 0;
  Result.Top := Top;
  Result.Width := EdPage.SurfaceWidth;
  Result.Height := ScaleY(22);
  Result.Font.Style := [fsBold];
  Result.Font.Size := 11;
  if Rec then Result.Caption := Title + '   (recommended for this PC)'
  else Result.Caption := Title;
  T := Txt(Top + ScaleY(26), Fit, True, 0, -1, 22);
  T := Txt(T.Top + T.Height + ScaleY(3), Body, False, 0, -1, 22);
end;

procedure InitializeWizard();
var
  N: TNewStaticText;
begin
  HasNvidia := NvidiaFound();
  EdPage := CreateCustomPage(wpWelcome, 'Light or Full?', 'Pick the version that fits your PC. Both have the same features.');
  RbLight := Choice(0, 'Light', 'About 0.5 GB  -  for laptops and PCs without a gaming graphics card',
    'Installs the Clipper with everything it needs. The speech model for captions downloads by itself the first time you need it.', not HasNvidia);
  RbFull := Choice(ScaleY(118), 'Full', 'About 1 to 4 GB  -  for gaming PCs with a graphics card (NVIDIA, AMD or Intel Arc)',
    'Also installs graphics card support for the speech model (much faster, best captions) and downloads the speech models right away, so your first short is quick.', HasNvidia);
  N := Txt(ScaleY(240), 'You can switch later by running this setup again.', False, 0, clGray, 0);
  RbFull.Checked := HasNvidia;
  RbLight.Checked := not HasNvidia;
end;

function IsFull(): Boolean;
begin
  Result := RbFull.Checked;
end;

function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo, MemoTypeInfo, MemoComponentsInfo, MemoGroupInfo, MemoTasksInfo: String): String;
begin
  Result := MemoDirInfo + NewLine + NewLine + 'Version:' + NewLine + Space;
  if IsFull() then Result := Result + 'Full (graphics card support and speech models, about 1 to 4 GB)'
  else Result := Result + 'Light (about 0.5 GB, the speech model downloads when you first need it)';
  Result := Result + NewLine + NewLine + 'This needs an internet connection: the setup downloads the parts the Clipper uses.';
end;

procedure StopRunningClipper();
var
  Code: Integer;
begin
  { a running Clipper keeps files open: close only the Clipper, no other Python programs }
  Exec('powershell.exe', '-NoProfile -NonInteractive -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like ''*' +
       ExpandConstant('{app}') + '\clipper\*'' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"',
       '', SW_HIDE, ewWaitUntilTerminated, Code);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopRunningClipper();
  Result := '';
end;

function Step(Msg, Exe, Params: String): Boolean;
var
  Code: Integer;
begin
  WizardForm.StatusLabel.Caption := Msg;
  WizardForm.FilenameLabel.Caption := '';
  Result := Exec(Exe, Params, ExpandConstant('{app}\clipper'), SW_HIDE, ewWaitUntilTerminated, Code) and (Code = 0);
  if not Result then
    Log('Step failed: ' + Msg + ' (code ' + IntToStr(Code) + ')');
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Py, LogF, Ed: String;
  Ok: Boolean;
begin
  if CurStep <> ssPostInstall then Exit;
  Py := ExpandConstant('{app}\clipper\python\python.exe');
  LogF := ExpandConstant('{app}\clipper\data\setup.log');
  ForceDirectories(ExpandConstant('{app}\clipper\data'));
  if IsFull() then Ed := 'full' else Ed := 'light';
  WizardForm.ProgressGauge.Style := npbstMarquee;
  Ok := Step('Getting the package installer ready...', Py, '"' + ExpandConstant('{app}\clipper\python\get-pip.py') + '" --no-warn-script-location -q');
  if Ok then
    Ok := Step('Downloading and installing the parts the Clipper uses (a few minutes)...', 'cmd.exe',
      '/c ""' + Py + '" -m pip install --no-warn-script-location --disable-pip-version-check -r requirements.txt > "' + LogF + '" 2>&1"');
  if Ok then
    Ok := Step('Setting up your version (' + Ed + ')' + '. Full downloads the speech models, this can take a while...', 'cmd.exe',
      '/c ""' + Py + '" installer\setup_edition.py ' + Ed + ' >> "' + LogF + '" 2>&1"');
  WizardForm.ProgressGauge.Style := npbstNormal;
  if not Ok then
    SuppressibleMsgBox('Part of the install did not work (is the internet on?).' + #13#10#13#10 +
           'The Clipper is installed, and it tries to finish this the first time it starts. ' +
           'If it keeps going wrong, send the file clipper\data\setup.log along.', mbError, MB_OK, IDOK);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    StopRunningClipper();
  if CurUninstallStep = usPostUninstall then
  begin
    if SuppressibleMsgBox('Also delete your shorts, settings and what the Clipper learned?' + #13#10#13#10 +
              'Choose No to keep them (handy if you install the Clipper again later).', mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES then
    begin
      DelTree(ExpandConstant('{app}\clipper\data'), True, True, True);
      DelTree(ExpandConstant('{app}\clipper\shorts'), True, True, True);
    end;
  end;
end;
