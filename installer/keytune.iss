; Inno Setup script for KeyTune.
;
; Builds KeyTune-Setup.exe from the PyInstaller folder output in dist\KeyTune.
; Supports BOTH installation scopes (the user chooses on the install dialog):
;   - per-user    -> {localappdata}\Programs\KeyTune  (no UAC)
;   - per-machine -> {autopf}\KeyTune (Program Files, requires admin)
; Registry roots use HKA (HKLM for all-users, HKCU for current-user) so the
; same script registers default-app Capabilities + file associations in either
; scope.
;
; Compile with: iscc installer\keytune.iss
;   /DAppVersion=1.2.3   overrides the version (the release workflow passes the tag).
;   /DSourceDir=...      overrides the PyInstaller payload folder (default ..\dist\KeyTune).

#ifndef AppVersion
  #define AppVersion "2.5.0"
#endif

#ifndef SourceDir
  #define SourceDir "..\dist\KeyTune"
#endif

#define AppName "KeyTune"
#define AppPublisher "Eduardo Ferreira"
#define AppExeName "KeyTune.exe"
#define AppId "{{A7F3C2E1-9B4D-4E6A-8C1F-2D5E7A9B3C4D}"
#define ProgId "KeyTune.MediaFile"
#define EnqueueVerb "KeyTune.enqueue"

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}
OutputDir=..\dist
OutputBaseFilename=KeyTune-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
; Show tree lines between the file-association category parents and their
; nested extensions on the "Select Additional Tasks" page.
ShowTasksTreeLines=yes
; Let the user pick the scope; default to the least-privilege (per-user) path.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
; During a silent in-app update, close a running KeyTune so files aren't locked.
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

; User-visible installer strings, per language. Inno resolves {cm:Name} to the
; language the user selects on the first wizard page. Keep both lists in sync.
[CustomMessages]
brazilianportuguese.DesktopIcon=Criar um atalho na área de trabalho
english.DesktopIcon=Create a desktop shortcut
spanish.DesktopIcon=Crear un acceso directo en el escritorio
brazilianportuguese.AdditionalShortcuts=Atalhos adicionais:
english.AdditionalShortcuts=Additional shortcuts:
spanish.AdditionalShortcuts=Accesos directos adicionales:
brazilianportuguese.FileAssocGroup=Associações de arquivo (opcional):
english.FileAssocGroup=File associations (optional):
spanish.FileAssocGroup=Asociaciones de archivo (opcional):
brazilianportuguese.AssocVideoAll=Associar todos os arquivos de vídeo
english.AssocVideoAll=Associate all video files
spanish.AssocVideoAll=Asociar todos los archivos de video
brazilianportuguese.AssocAudioAll=Associar todos os arquivos de áudio
english.AssocAudioAll=Associate all audio files
spanish.AssocAudioAll=Asociar todos los archivos de audio
brazilianportuguese.AssocPlaylistAll=Associar todos os arquivos de playlist
english.AssocPlaylistAll=Associate all playlist files
spanish.AssocPlaylistAll=Asociar todos los archivos de lista de reproducción
brazilianportuguese.MediaFileType=Arquivo de mídia — {#AppName}
english.MediaFileType=Media file — {#AppName}
spanish.MediaFileType=Archivo multimedia — {#AppName}
brazilianportuguese.OpenWithApp=Abrir no {#AppName}
english.OpenWithApp=Open with {#AppName}
spanish.OpenWithApp=Abrir con {#AppName}
brazilianportuguese.EnqueueWithApp=Adicionar à playlist do {#AppName}
english.EnqueueWithApp=Add to {#AppName} playlist
spanish.EnqueueWithApp=Añadir a la lista de {#AppName}
brazilianportuguese.AppDescription=Reprodutor de mídia acessível, controlado por teclado.
english.AppDescription=Accessible, keyboard-driven media player.
spanish.AppDescription=Reproductor multimedia accesible, controlado por teclado.
brazilianportuguese.UninstallShortcut=Desinstalar o {#AppName}
english.UninstallShortcut=Uninstall {#AppName}
spanish.UninstallShortcut=Desinstalar {#AppName}
brazilianportuguese.LaunchApp=Iniciar o {#AppName}
english.LaunchApp=Start {#AppName}
spanish.LaunchApp=Iniciar {#AppName}
brazilianportuguese.ReadManual=Ler o manual do {#AppName}
english.ReadManual=Read the {#AppName} manual
spanish.ReadManual=Leer el manual de {#AppName}

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopIcon}"; GroupDescription: "{cm:AdditionalShortcuts}"; Flags: unchecked

; File associations are opt-in: nothing is checked by default. Each category
; parent acts as a "select all" toggle for the extensions indented beneath it;
; the user can also pick individual extensions. This only registers KeyTune as
; a candidate handler — Windows still requires the user to confirm the default
; in Settings > Default apps.
; NOTE: these lists mirror VIDEO_EXTENSIONS + AUDIO_ONLY_EXTENSIONS in
; src/player/constants.py (+ .m3u/.m3u8). Keep both in sync.

Name: "assocvideo"; Description: "{cm:AssocVideoAll}"; GroupDescription: "{cm:FileAssocGroup}"; Flags: unchecked
Name: "assocvideo\mp4"; Description: ".mp4"; Flags: unchecked
Name: "assocvideo\m4v"; Description: ".m4v"; Flags: unchecked
Name: "assocvideo\mkv"; Description: ".mkv"; Flags: unchecked
Name: "assocvideo\avi"; Description: ".avi"; Flags: unchecked
Name: "assocvideo\mov"; Description: ".mov"; Flags: unchecked
Name: "assocvideo\webm"; Description: ".webm"; Flags: unchecked
Name: "assocvideo\flv"; Description: ".flv"; Flags: unchecked
Name: "assocvideo\wmv"; Description: ".wmv"; Flags: unchecked
Name: "assocvideo\mpg"; Description: ".mpg"; Flags: unchecked
Name: "assocvideo\mpeg"; Description: ".mpeg"; Flags: unchecked
Name: "assocvideo\3gp"; Description: ".3gp"; Flags: unchecked
Name: "assocvideo\ts"; Description: ".ts"; Flags: unchecked
Name: "assocvideo\m2ts"; Description: ".m2ts"; Flags: unchecked
Name: "assocvideo\mts"; Description: ".mts"; Flags: unchecked
Name: "assocvideo\ogv"; Description: ".ogv"; Flags: unchecked

Name: "assocaudio"; Description: "{cm:AssocAudioAll}"; GroupDescription: "{cm:FileAssocGroup}"; Flags: unchecked
Name: "assocaudio\mp3"; Description: ".mp3"; Flags: unchecked
Name: "assocaudio\wav"; Description: ".wav"; Flags: unchecked
Name: "assocaudio\flac"; Description: ".flac"; Flags: unchecked
Name: "assocaudio\aac"; Description: ".aac"; Flags: unchecked
Name: "assocaudio\ogg"; Description: ".ogg"; Flags: unchecked
Name: "assocaudio\oga"; Description: ".oga"; Flags: unchecked
Name: "assocaudio\m4a"; Description: ".m4a"; Flags: unchecked
Name: "assocaudio\opus"; Description: ".opus"; Flags: unchecked
Name: "assocaudio\wma"; Description: ".wma"; Flags: unchecked
Name: "assocaudio\aiff"; Description: ".aiff"; Flags: unchecked
Name: "assocaudio\aif"; Description: ".aif"; Flags: unchecked
Name: "assocaudio\ac3"; Description: ".ac3"; Flags: unchecked
Name: "assocaudio\mka"; Description: ".mka"; Flags: unchecked
Name: "assocaudio\wv"; Description: ".wv"; Flags: unchecked
Name: "assocaudio\ape"; Description: ".ape"; Flags: unchecked

Name: "assocplaylist"; Description: "{cm:AssocPlaylistAll}"; GroupDescription: "{cm:FileAssocGroup}"; Flags: unchecked
Name: "assocplaylist\m3u"; Description: ".m3u"; Flags: unchecked
Name: "assocplaylist\m3u8"; Description: ".m3u8"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallShortcut}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
; --- Install marker so the app knows it was installed (and in which scope). ---
Root: HKA; Subkey: "Software\{#AppName}"; ValueType: string; ValueName: "InstallDir"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\{#AppName}"; ValueType: string; ValueName: "InstallMode"; ValueData: "{code:GetInstallMode}"
Root: HKA; Subkey: "Software\{#AppName}"; ValueType: string; ValueName: "Version"; ValueData: "{#AppVersion}"

; --- ProgId used for the Open command and as the default handler. ---
Root: HKA; Subkey: "Software\Classes\{#ProgId}"; ValueType: string; ValueName: ""; ValueData: "{cm:MediaFileType}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\{#ProgId}\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExeName},0"
Root: HKA; Subkey: "Software\Classes\{#ProgId}\shell\open"; ValueType: string; ValueName: ""; ValueData: "{cm:OpenWithApp}"
Root: HKA; Subkey: "Software\Classes\{#ProgId}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""
; Player: Explorer runs this verb once and appends every selected file after
; %1 (legacy static verbs cap the selection at 100 items). Document, the
; default for a command verb, would start one process per file.
Root: HKA; Subkey: "Software\Classes\{#ProgId}\shell\enqueue"; Flags: deletekey
Root: HKA; Subkey: "Software\Classes\{#ProgId}\shell\{#EnqueueVerb}"; ValueType: string; ValueName: ""; ValueData: "{cm:EnqueueWithApp}"
Root: HKA; Subkey: "Software\Classes\{#ProgId}\shell\{#EnqueueVerb}"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"
Root: HKA; Subkey: "Software\Classes\{#ProgId}\shell\{#EnqueueVerb}\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" --enqueue ""%1"""

; --- Capabilities + RegisteredApplications root: always present so KeyTune is
;     a registered application; per-extension entries below are opt-in. ---
Root: HKA; Subkey: "Software\{#AppName}\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "{#AppName}"
Root: HKA; Subkey: "Software\{#AppName}\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "{cm:AppDescription}"
Root: HKA; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "{#AppName}"; ValueData: "Software\{#AppName}\Capabilities"; Flags: uninsdeletevalue

; --- Per-extension registration, gated by the opt-in [Tasks]. Each extension
;     adds an OpenWithProgids entry ("Open with" list) and a Capabilities
;     FileAssociation ("Default apps"). ---
Root: HKA; Subkey: "Software\Classes\.mp4\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assocvideo\mp4
Root: HKA; Subkey: "Software\Classes\.m4v\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assocvideo\m4v
Root: HKA; Subkey: "Software\Classes\.mkv\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assocvideo\mkv
Root: HKA; Subkey: "Software\Classes\.avi\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assocvideo\avi
Root: HKA; Subkey: "Software\Classes\.mov\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assocvideo\mov
Root: HKA; Subkey: "Software\Classes\.webm\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assocvideo\webm
Root: HKA; Subkey: "Software\Classes\.flv\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assocvideo\flv
Root: HKA; Subkey: "Software\Classes\.wmv\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assocvideo\wmv
Root: HKA; Subkey: "Software\Classes\.mpg\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assocvideo\mpg
Root: HKA; Subkey: "Software\Classes\.mpeg\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assocvideo\mpeg
Root: HKA; Subkey: "Software\Classes\.3gp\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assocvideo\3gp
Root: HKA; Subkey: "Software\Classes\.ts\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assocvideo\ts
Root: HKA; Subkey: "Software\Classes\.m2ts\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assocvideo\m2ts
Root: HKA; Subkey: "Software\Classes\.mts\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assocvideo\mts
Root: HKA; Subkey: "Software\Classes\.ogv\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assocvideo\ogv
Root: HKA; Subkey: "Software\Classes\.mp3\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assocaudio\mp3
Root: HKA; Subkey: "Software\Classes\.wav\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assocaudio\wav
Root: HKA; Subkey: "Software\Classes\.flac\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assocaudio\flac
Root: HKA; Subkey: "Software\Classes\.aac\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assocaudio\aac
Root: HKA; Subkey: "Software\Classes\.ogg\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assocaudio\ogg
Root: HKA; Subkey: "Software\Classes\.oga\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assocaudio\oga
Root: HKA; Subkey: "Software\Classes\.m4a\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assocaudio\m4a
Root: HKA; Subkey: "Software\Classes\.opus\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assocaudio\opus
Root: HKA; Subkey: "Software\Classes\.wma\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assocaudio\wma
Root: HKA; Subkey: "Software\Classes\.aiff\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assocaudio\aiff
Root: HKA; Subkey: "Software\Classes\.aif\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assocaudio\aif
Root: HKA; Subkey: "Software\Classes\.ac3\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assocaudio\ac3
Root: HKA; Subkey: "Software\Classes\.mka\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assocaudio\mka
Root: HKA; Subkey: "Software\Classes\.wv\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assocaudio\wv
Root: HKA; Subkey: "Software\Classes\.ape\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assocaudio\ape
Root: HKA; Subkey: "Software\Classes\.m3u\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assocplaylist\m3u
Root: HKA; Subkey: "Software\Classes\.m3u8\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Flags: uninsdeletevalue; Tasks: assocplaylist\m3u8

; Media verbs available even when another player owns the extension's ProgID.
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.mp4\shell\{#EnqueueVerb}"; ValueType: string; ValueName: ""; ValueData: "{cm:EnqueueWithApp}"; Flags: uninsdeletekey; Tasks: assocvideo\mp4
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.mp4\shell\{#EnqueueVerb}"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: assocvideo\mp4
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.mp4\shell\{#EnqueueVerb}\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" --enqueue ""%1"""; Tasks: assocvideo\mp4
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.m4v\shell\{#EnqueueVerb}"; ValueType: string; ValueName: ""; ValueData: "{cm:EnqueueWithApp}"; Flags: uninsdeletekey; Tasks: assocvideo\m4v
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.m4v\shell\{#EnqueueVerb}"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: assocvideo\m4v
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.m4v\shell\{#EnqueueVerb}\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" --enqueue ""%1"""; Tasks: assocvideo\m4v
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.mkv\shell\{#EnqueueVerb}"; ValueType: string; ValueName: ""; ValueData: "{cm:EnqueueWithApp}"; Flags: uninsdeletekey; Tasks: assocvideo\mkv
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.mkv\shell\{#EnqueueVerb}"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: assocvideo\mkv
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.mkv\shell\{#EnqueueVerb}\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" --enqueue ""%1"""; Tasks: assocvideo\mkv
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.avi\shell\{#EnqueueVerb}"; ValueType: string; ValueName: ""; ValueData: "{cm:EnqueueWithApp}"; Flags: uninsdeletekey; Tasks: assocvideo\avi
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.avi\shell\{#EnqueueVerb}"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: assocvideo\avi
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.avi\shell\{#EnqueueVerb}\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" --enqueue ""%1"""; Tasks: assocvideo\avi
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.mov\shell\{#EnqueueVerb}"; ValueType: string; ValueName: ""; ValueData: "{cm:EnqueueWithApp}"; Flags: uninsdeletekey; Tasks: assocvideo\mov
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.mov\shell\{#EnqueueVerb}"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: assocvideo\mov
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.mov\shell\{#EnqueueVerb}\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" --enqueue ""%1"""; Tasks: assocvideo\mov
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.webm\shell\{#EnqueueVerb}"; ValueType: string; ValueName: ""; ValueData: "{cm:EnqueueWithApp}"; Flags: uninsdeletekey; Tasks: assocvideo\webm
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.webm\shell\{#EnqueueVerb}"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: assocvideo\webm
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.webm\shell\{#EnqueueVerb}\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" --enqueue ""%1"""; Tasks: assocvideo\webm
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.flv\shell\{#EnqueueVerb}"; ValueType: string; ValueName: ""; ValueData: "{cm:EnqueueWithApp}"; Flags: uninsdeletekey; Tasks: assocvideo\flv
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.flv\shell\{#EnqueueVerb}"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: assocvideo\flv
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.flv\shell\{#EnqueueVerb}\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" --enqueue ""%1"""; Tasks: assocvideo\flv
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.wmv\shell\{#EnqueueVerb}"; ValueType: string; ValueName: ""; ValueData: "{cm:EnqueueWithApp}"; Flags: uninsdeletekey; Tasks: assocvideo\wmv
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.wmv\shell\{#EnqueueVerb}"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: assocvideo\wmv
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.wmv\shell\{#EnqueueVerb}\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" --enqueue ""%1"""; Tasks: assocvideo\wmv
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.mpg\shell\{#EnqueueVerb}"; ValueType: string; ValueName: ""; ValueData: "{cm:EnqueueWithApp}"; Flags: uninsdeletekey; Tasks: assocvideo\mpg
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.mpg\shell\{#EnqueueVerb}"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: assocvideo\mpg
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.mpg\shell\{#EnqueueVerb}\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" --enqueue ""%1"""; Tasks: assocvideo\mpg
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.mpeg\shell\{#EnqueueVerb}"; ValueType: string; ValueName: ""; ValueData: "{cm:EnqueueWithApp}"; Flags: uninsdeletekey; Tasks: assocvideo\mpeg
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.mpeg\shell\{#EnqueueVerb}"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: assocvideo\mpeg
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.mpeg\shell\{#EnqueueVerb}\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" --enqueue ""%1"""; Tasks: assocvideo\mpeg
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.3gp\shell\{#EnqueueVerb}"; ValueType: string; ValueName: ""; ValueData: "{cm:EnqueueWithApp}"; Flags: uninsdeletekey; Tasks: assocvideo\3gp
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.3gp\shell\{#EnqueueVerb}"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: assocvideo\3gp
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.3gp\shell\{#EnqueueVerb}\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" --enqueue ""%1"""; Tasks: assocvideo\3gp
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.ts\shell\{#EnqueueVerb}"; ValueType: string; ValueName: ""; ValueData: "{cm:EnqueueWithApp}"; Flags: uninsdeletekey; Tasks: assocvideo\ts
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.ts\shell\{#EnqueueVerb}"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: assocvideo\ts
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.ts\shell\{#EnqueueVerb}\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" --enqueue ""%1"""; Tasks: assocvideo\ts
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.m2ts\shell\{#EnqueueVerb}"; ValueType: string; ValueName: ""; ValueData: "{cm:EnqueueWithApp}"; Flags: uninsdeletekey; Tasks: assocvideo\m2ts
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.m2ts\shell\{#EnqueueVerb}"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: assocvideo\m2ts
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.m2ts\shell\{#EnqueueVerb}\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" --enqueue ""%1"""; Tasks: assocvideo\m2ts
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.mts\shell\{#EnqueueVerb}"; ValueType: string; ValueName: ""; ValueData: "{cm:EnqueueWithApp}"; Flags: uninsdeletekey; Tasks: assocvideo\mts
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.mts\shell\{#EnqueueVerb}"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: assocvideo\mts
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.mts\shell\{#EnqueueVerb}\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" --enqueue ""%1"""; Tasks: assocvideo\mts
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.ogv\shell\{#EnqueueVerb}"; ValueType: string; ValueName: ""; ValueData: "{cm:EnqueueWithApp}"; Flags: uninsdeletekey; Tasks: assocvideo\ogv
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.ogv\shell\{#EnqueueVerb}"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: assocvideo\ogv
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.ogv\shell\{#EnqueueVerb}\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" --enqueue ""%1"""; Tasks: assocvideo\ogv
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.mp3\shell\{#EnqueueVerb}"; ValueType: string; ValueName: ""; ValueData: "{cm:EnqueueWithApp}"; Flags: uninsdeletekey; Tasks: assocaudio\mp3
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.mp3\shell\{#EnqueueVerb}"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: assocaudio\mp3
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.mp3\shell\{#EnqueueVerb}\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" --enqueue ""%1"""; Tasks: assocaudio\mp3
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.wav\shell\{#EnqueueVerb}"; ValueType: string; ValueName: ""; ValueData: "{cm:EnqueueWithApp}"; Flags: uninsdeletekey; Tasks: assocaudio\wav
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.wav\shell\{#EnqueueVerb}"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: assocaudio\wav
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.wav\shell\{#EnqueueVerb}\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" --enqueue ""%1"""; Tasks: assocaudio\wav
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.flac\shell\{#EnqueueVerb}"; ValueType: string; ValueName: ""; ValueData: "{cm:EnqueueWithApp}"; Flags: uninsdeletekey; Tasks: assocaudio\flac
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.flac\shell\{#EnqueueVerb}"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: assocaudio\flac
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.flac\shell\{#EnqueueVerb}\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" --enqueue ""%1"""; Tasks: assocaudio\flac
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.aac\shell\{#EnqueueVerb}"; ValueType: string; ValueName: ""; ValueData: "{cm:EnqueueWithApp}"; Flags: uninsdeletekey; Tasks: assocaudio\aac
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.aac\shell\{#EnqueueVerb}"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: assocaudio\aac
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.aac\shell\{#EnqueueVerb}\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" --enqueue ""%1"""; Tasks: assocaudio\aac
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.ogg\shell\{#EnqueueVerb}"; ValueType: string; ValueName: ""; ValueData: "{cm:EnqueueWithApp}"; Flags: uninsdeletekey; Tasks: assocaudio\ogg
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.ogg\shell\{#EnqueueVerb}"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: assocaudio\ogg
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.ogg\shell\{#EnqueueVerb}\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" --enqueue ""%1"""; Tasks: assocaudio\ogg
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.oga\shell\{#EnqueueVerb}"; ValueType: string; ValueName: ""; ValueData: "{cm:EnqueueWithApp}"; Flags: uninsdeletekey; Tasks: assocaudio\oga
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.oga\shell\{#EnqueueVerb}"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: assocaudio\oga
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.oga\shell\{#EnqueueVerb}\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" --enqueue ""%1"""; Tasks: assocaudio\oga
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.m4a\shell\{#EnqueueVerb}"; ValueType: string; ValueName: ""; ValueData: "{cm:EnqueueWithApp}"; Flags: uninsdeletekey; Tasks: assocaudio\m4a
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.m4a\shell\{#EnqueueVerb}"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: assocaudio\m4a
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.m4a\shell\{#EnqueueVerb}\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" --enqueue ""%1"""; Tasks: assocaudio\m4a
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.opus\shell\{#EnqueueVerb}"; ValueType: string; ValueName: ""; ValueData: "{cm:EnqueueWithApp}"; Flags: uninsdeletekey; Tasks: assocaudio\opus
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.opus\shell\{#EnqueueVerb}"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: assocaudio\opus
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.opus\shell\{#EnqueueVerb}\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" --enqueue ""%1"""; Tasks: assocaudio\opus
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.wma\shell\{#EnqueueVerb}"; ValueType: string; ValueName: ""; ValueData: "{cm:EnqueueWithApp}"; Flags: uninsdeletekey; Tasks: assocaudio\wma
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.wma\shell\{#EnqueueVerb}"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: assocaudio\wma
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.wma\shell\{#EnqueueVerb}\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" --enqueue ""%1"""; Tasks: assocaudio\wma
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.aiff\shell\{#EnqueueVerb}"; ValueType: string; ValueName: ""; ValueData: "{cm:EnqueueWithApp}"; Flags: uninsdeletekey; Tasks: assocaudio\aiff
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.aiff\shell\{#EnqueueVerb}"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: assocaudio\aiff
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.aiff\shell\{#EnqueueVerb}\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" --enqueue ""%1"""; Tasks: assocaudio\aiff
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.aif\shell\{#EnqueueVerb}"; ValueType: string; ValueName: ""; ValueData: "{cm:EnqueueWithApp}"; Flags: uninsdeletekey; Tasks: assocaudio\aif
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.aif\shell\{#EnqueueVerb}"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: assocaudio\aif
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.aif\shell\{#EnqueueVerb}\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" --enqueue ""%1"""; Tasks: assocaudio\aif
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.ac3\shell\{#EnqueueVerb}"; ValueType: string; ValueName: ""; ValueData: "{cm:EnqueueWithApp}"; Flags: uninsdeletekey; Tasks: assocaudio\ac3
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.ac3\shell\{#EnqueueVerb}"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: assocaudio\ac3
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.ac3\shell\{#EnqueueVerb}\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" --enqueue ""%1"""; Tasks: assocaudio\ac3
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.mka\shell\{#EnqueueVerb}"; ValueType: string; ValueName: ""; ValueData: "{cm:EnqueueWithApp}"; Flags: uninsdeletekey; Tasks: assocaudio\mka
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.mka\shell\{#EnqueueVerb}"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: assocaudio\mka
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.mka\shell\{#EnqueueVerb}\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" --enqueue ""%1"""; Tasks: assocaudio\mka
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.wv\shell\{#EnqueueVerb}"; ValueType: string; ValueName: ""; ValueData: "{cm:EnqueueWithApp}"; Flags: uninsdeletekey; Tasks: assocaudio\wv
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.wv\shell\{#EnqueueVerb}"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: assocaudio\wv
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.wv\shell\{#EnqueueVerb}\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" --enqueue ""%1"""; Tasks: assocaudio\wv
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.ape\shell\{#EnqueueVerb}"; ValueType: string; ValueName: ""; ValueData: "{cm:EnqueueWithApp}"; Flags: uninsdeletekey; Tasks: assocaudio\ape
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.ape\shell\{#EnqueueVerb}"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: assocaudio\ape
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.ape\shell\{#EnqueueVerb}\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" --enqueue ""%1"""; Tasks: assocaudio\ape

Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mp4"; ValueData: "{#ProgId}"; Tasks: assocvideo\mp4
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".m4v"; ValueData: "{#ProgId}"; Tasks: assocvideo\m4v
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mkv"; ValueData: "{#ProgId}"; Tasks: assocvideo\mkv
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".avi"; ValueData: "{#ProgId}"; Tasks: assocvideo\avi
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mov"; ValueData: "{#ProgId}"; Tasks: assocvideo\mov
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".webm"; ValueData: "{#ProgId}"; Tasks: assocvideo\webm
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".flv"; ValueData: "{#ProgId}"; Tasks: assocvideo\flv
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".wmv"; ValueData: "{#ProgId}"; Tasks: assocvideo\wmv
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mpg"; ValueData: "{#ProgId}"; Tasks: assocvideo\mpg
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mpeg"; ValueData: "{#ProgId}"; Tasks: assocvideo\mpeg
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".3gp"; ValueData: "{#ProgId}"; Tasks: assocvideo\3gp
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".ts"; ValueData: "{#ProgId}"; Tasks: assocvideo\ts
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".m2ts"; ValueData: "{#ProgId}"; Tasks: assocvideo\m2ts
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mts"; ValueData: "{#ProgId}"; Tasks: assocvideo\mts
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".ogv"; ValueData: "{#ProgId}"; Tasks: assocvideo\ogv
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mp3"; ValueData: "{#ProgId}"; Tasks: assocaudio\mp3
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".wav"; ValueData: "{#ProgId}"; Tasks: assocaudio\wav
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".flac"; ValueData: "{#ProgId}"; Tasks: assocaudio\flac
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".aac"; ValueData: "{#ProgId}"; Tasks: assocaudio\aac
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".ogg"; ValueData: "{#ProgId}"; Tasks: assocaudio\ogg
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".oga"; ValueData: "{#ProgId}"; Tasks: assocaudio\oga
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".m4a"; ValueData: "{#ProgId}"; Tasks: assocaudio\m4a
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".opus"; ValueData: "{#ProgId}"; Tasks: assocaudio\opus
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".wma"; ValueData: "{#ProgId}"; Tasks: assocaudio\wma
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".aiff"; ValueData: "{#ProgId}"; Tasks: assocaudio\aiff
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".aif"; ValueData: "{#ProgId}"; Tasks: assocaudio\aif
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".ac3"; ValueData: "{#ProgId}"; Tasks: assocaudio\ac3
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mka"; ValueData: "{#ProgId}"; Tasks: assocaudio\mka
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".wv"; ValueData: "{#ProgId}"; Tasks: assocaudio\wv
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".ape"; ValueData: "{#ProgId}"; Tasks: assocaudio\ape
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".m3u"; ValueData: "{#ProgId}"; Tasks: assocplaylist\m3u
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".m3u8"; ValueData: "{#ProgId}"; Tasks: assocplaylist\m3u8

[Run]
; Finished-page checkboxes for normal (interactive) installs.
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent
Filename: "{code:GetManualPath}"; Description: "{cm:ReadManual}"; Flags: postinstall shellexec skipifsilent unchecked
; Silent in-app update path: relaunch with the original user token when Inno
; Setup has one, so user data is not first created by the elevated installer.
Filename: "{app}\{#AppExeName}"; Flags: nowait skipifnotsilent runasoriginaluser

[Code]
function GetInstallMode(Param: string): string;
begin
  if IsAdminInstallMode then
    Result := 'machine'
  else
    Result := 'user';
end;

function GetManualPath(Param: string): string;
begin
  if ActiveLanguage = 'english' then
    Result := ExpandConstant('{app}\docs\manual.en.html')
  else if ActiveLanguage = 'spanish' then
    Result := ExpandConstant('{app}\docs\manual.es.html')
  else
    Result := ExpandConstant('{app}\docs\manual.html');

  if not FileExists(Result) then
    Result := ExpandConstant('{app}\docs\manual.html');
end;
