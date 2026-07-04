; ============================================================
;  Inno Setup script for WhisperDictation
;  Компіляція: відкрий цей файл в Inno Setup Compiler -> Build (F9)
;  Результат:  Output\WhisperDictationSetup.exe
; ============================================================

#define MyAppName "WhisperDictation"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Mrhetsko"
#define MyAppExeName "WhisperDictation.exe"
; Папка з PyInstaller-збіркою (--onedir): містить .exe + _internal
#define MySourceDir "dist\WhisperDictation"

[Setup]
; AppId має бути унікальним і НЕ мінятися між версіями (по ньому Windows розуміє,
; що це оновлення тієї самої програми, а не нова).
AppId={{C3989A36-B3DB-4FAA-94D7-CC6A1AE1F687}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; Per-user установка: без прав адміна, без UAC. {autopf} у цьому режимі ->
; %LocalAppData%\Programs, ярлики й автозапуск лягають у профіль користувача.
PrivilegesRequired=lowest
; Збірка тільки під 64-бітну Windows
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=Output
OutputBaseFilename=WhisperDictationSetup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Іконку .exe встановлювача та ярликів можна задати тут, коли зʼявиться .ico:
; SetupIconFile=assets\app.ico
UninstallDisplayName={#MyAppName}
; UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "ukrainian"; MessagesFile: "compiler:Languages\Ukrainian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "Запускати {#MyAppName} під час входу в Windows"; GroupDescription: "Автозапуск:"

[Files]
; Копіюємо весь вміст dist-папки (.exe + _internal з усіма бібліотеками)
Source: "{#MySourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Ярлик у меню Пуск
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
; Деінсталятор у меню Пуск
Name: "{group}\Видалити {#MyAppName}"; Filename: "{uninstallexe}"
; Ярлик на робочому столі (за галочкою)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
; Автозапуск при вході (за галочкою) — ярлик у папці Startup поточного користувача
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Run]
; Пропозиція запустити одразу після встановлення
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
