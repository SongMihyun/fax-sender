#define AppName "FaxSender 자동처리"
#define AppVersion "1.0.0"
#define AppExeName "FaxSenderAutoProcessor.exe"

[Setup]
AppId={{AB8E5A38-42C4-4ED4-B943-5B58B8DAB348}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={localappdata}\FaxSenderAutoProcessor
DefaultGroupName={#AppName}
OutputDir=..\release
OutputBaseFilename=FaxSenderAutoProcessor-Setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
SetupIconFile=..\auto_processor\assets\faxsender.ico

[Files]
Source: "..\dist\FaxSenderAutoProcessor\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
Source: "..\auto_processor\assets\faxsender.ico"; DestDir: "{app}"; Flags: ignoreversion

[Code]
var
  WatchRootPage: TInputDirWizardPage;

procedure InitializeWizard;
begin
  WatchRootPage := CreateInputDirPage(
    wpSelectDir,
    '동의서 감시 폴더 선택',
    'PDF를 넣을 위치를 선택하세요',
    '선택한 폴더 안에 faxsender 폴더가 만들어집니다. 완성본은 faxsender에, 원본은 faxsender\\사용완료에 보관됩니다.',
    False,
    ''
  );
  WatchRootPage.Add('상위 폴더:');
  WatchRootPage.Values[0] := ExpandConstant('{userdocs}');
end;

function GetWatchRoot(Param: String): String;
begin
  Result := WatchRootPage.Values[0];
end;

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\faxsender.ico"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\faxsender.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Parameters: "--watch-root ""{code:GetWatchRoot}"""; Description: "{#AppName} 실행"; Flags: nowait postinstall skipifsilent

[Tasks]
Name: "desktopicon"; Description: "바탕 화면 아이콘 만들기"; Flags: unchecked
