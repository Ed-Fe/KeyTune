# KeyTune Manual

KeyTune is a media player designed for keyboard use with a focus on accessibility. It was built to work well with playlists, folder navigation, and preserving what you were doing between sessions.

This project was developed with AI assistance, including GitHub Copilot, OpenAI Codex, and Anthropic Claude Code.

This manual presents the application's main features and the most common actions so you can start using the player quickly.

## What KeyTune offers

- Keyboard-controlled media playback
- Tabbed playlists
- A playback queue to organize what plays next
- Folder navigation with preview
- Per-tab equalizer with built-in profiles and custom presets
- A lyrics panel with automatic fetching and text copying
- Dedicated YouTube Music tab, opened with `Ctrl+Shift+Y`
- Loading and saving playlists
- Restoration of what was open in the last session
- List of recent files, folders, and playlists
- Accessibility announcements when screen readers are available

## Getting started

1. Download the latest `KeyTune-Setup.exe` installer from the [releases](https://github.com/ed-fe/KeyTune/releases) page.
2. Run the installer and follow the steps. On the additional tasks page, you can choose to create a desktop shortcut and select which audio, video, and playlist formats you want to associate with KeyTune - all optional and unchecked by default. Associating a format registers KeyTune as an option in the *Open with* menu; to make it open those files automatically, you still need to confirm it as the default in Windows settings.
3. At the end, the installer offers to start KeyTune and open this manual.
4. In future runs, when an update is available, the application itself shows a dialog with what's new and asks for confirmation before downloading and installing it (see [Updates](#updates)).

KeyTune depends on the MPV runtime to play media. The installer already includes this runtime; if the player opens but does not play anything, see the [Troubleshooting](#troubleshooting) section.

## Interface

When you open KeyTune for the first time, the main window shows a single empty playlist tab, with nothing to play yet. The window is divided into four areas:

- **Menu bar**, at the top: **File** (open media/folder/playlist, recent items, save), **Playback** (play/pause, previous/next track, shuffle, repeat, audio device, announcements), **View** (switch focus, equalizer, YouTube Music), **Tabs** (new tab, tab navigation, close), **Settings** (preferences), and **Help** (manual, shortcuts, check for updates).
- **Tab area**, taking up most of the window: each tab represents a playlist or an open folder (see [Playlist, folders, and tabs](#playlist-folders-and-tabs)). Inside each tab, the space is split into two side-by-side parts:
    - on the **left**, the item browser - the playlist list or the contents of the current folder;
    - on the **right**, the player area. When the current media is a video, this area shows the video frame; for audio, or when nothing is loaded, it shows supporting text with the most commonly used shortcuts to get started.
- **Time panel**, below the tab area: shows the elapsed time and duration of the current media, a visual progress bar, and a summary of the main shortcuts.
- **Status bar**, at the bottom edge of the window: displays short, temporary messages about the last action performed (for example, when opening a file or saving a playlist).

Use `Tab` or `Ctrl+B` to move focus between the item browser and the player within the active tab, and `F1` at any time to open the quick shortcut help.

## How to open media

You can open media files, a local playlist, a folder, or a compatible path and link using the shortcuts or the **File** menu:

- `Ctrl+Alt+O` - unified dialog that accepts any type: file, folder, playlist, link, or YouTube Music ID.
- `Ctrl+O` - opens media files or an `.m3u`/`.m3u8` playlist.
- `Ctrl+Shift+O` - opens a folder directly in the folder browser.
- `Ctrl+V` - pastes a path or link from the clipboard into the current playlist.
- `Ctrl+Shift+V` - pastes and opens in a new playlist.

Directly supported media formats:

- Audio: `.mp3`, `.wav`, `.flac`, `.aac`, `.ogg`, `.oga`, `.m4a`, `.opus`, `.wma`, `.aiff`, `.aif`, `.ac3`, `.mka`, `.wv`, `.ape`.
- Video: `.mp4`, `.m4v`, `.mkv`, `.avi`, `.mov`, `.webm`, `.flv`, `.wmv`, `.mpg`, `.mpeg`, `.3gp`, `.ts`, `.m2ts`, `.mts`, `.ogv`.

The **File > Recent** menu separately stores the latest **Recent files**, **Recent folders**, and **Recent playlists**, making it easier to reopen what you used before without navigating again.

## Playlist, folders, and tabs

Each playlist is kept in a separate tab. This helps separate contexts, such as a list of songs to listen to now, a folder with local files, or a collection you want to keep organized.

The active tab defines what is being played and what appears in the side browser. You can keep one tab for a saved playlist, another for an entire folder, and others for temporary lists, without mixing everything in the same context. Tabs can be opened, switched, and closed without affecting the others.

### Tab and item shortcuts

The shortcuts for opening media, folders, playlists, and links are in the [How to open media](#how-to-open-media) section above. The shortcuts below are specific to tabs and the current playlist:

- `Ctrl+T`: open a new playlist tab
- `Ctrl+W`: close the current tab or playlist
- `Ctrl+Shift+W`: close the current media
- `Ctrl+Tab` / `Ctrl+Shift+Tab`: move to the next or previous tab
- `Ctrl+Shift+E`: open the equalizer for the active tab
- `Ctrl+C`: copy the path or link of the selected item
- `Ctrl+Shift+S`: save the current playlist
- `Ctrl+B`: switch focus between the item browser and the player

### Playback queue

The playback queue organizes what should play after the current track, without depending on the order of the playlist you are browsing. It always belongs to the playlist that is currently playing.

Use `Ctrl+Shift+F` or the **Playback > Add to Playback Queue** menu to add or remove items from the queue. To view, remove, reorder, or clear the entire queue, use `Ctrl+Shift+Q` or the **Playback > Manage Playback Queue** menu.

If the queue is empty, the queue manager tells you so and asks you to add items first.

### Playback shortcuts

- `Space`: play or pause
- `Left Arrow` / `Right Arrow`: rewind or fast-forward in the current media
- `Shift+Left Arrow` / `Shift+Right Arrow`: rewind or fast-forward 1 minute in the current media
- `Home` / `End`: go to the beginning or end of the media
- `Up Arrow` / `Down Arrow`: increase or decrease the volume
- `Ctrl+.`: stop playback
- `Ctrl+PageUp` / `Ctrl+PageDown`: previous or next track in the playlist
- `Alt+Left Arrow` / `Alt+Right Arrow`: previous or next track in the playlist (alternative to `Ctrl+PageUp`/`Ctrl+PageDown`)
- `Alt+Up Arrow` / `Alt+Down Arrow`: move the current item up or down in the playlist
- `Alt+Home` / `Alt+End`: go to the first or last item in the playlist
- `E`: toggle shuffle mode
- `R`: toggle repeat mode
- `A`: toggle playback of related YouTube Music content (automatic radio at the end of the playlist)
- `]` / `[`: increase or decrease playback speed
- `Shift+]` / `Shift+[`: increase or decrease playback pitch by semitones
- `Shift+\`: restore the original pitch
- `Ctrl+Alt+L`: toggle the lyrics panel
- `Ctrl+Shift+F`: add the selected item to the playback queue
- `Ctrl+Shift+Q`: manage the playback queue
- `T`: announce the current media time
- `V`: announce the current volume
- `S`: announce the player status
- `Ctrl+L`: like the current media on YouTube Music
- `Ctrl+Shift+L`: mark the current media as disliked on YouTube Music

The `Ctrl+W` shortcut closes the active tab directly; the `Ctrl+Shift+W` shortcut closes or unloads the current media in the active tab.

### Item browser

The browser is on the left side of the window and operates in two distinct modes depending on what is in the active tab: **playlist mode** and **folder mode**. Use `Tab` or `Ctrl+B` to switch focus between the browser and the player.

#### Playlist mode

When the tab contains a playlist, the browser shows all items in the sequence. The item currently playing is marked with `▶` at the start of the line. The available shortcuts are:

- `Enter`: plays the selected item immediately.
- `Delete`: removes the selected item from the playlist.
- `Shift+F10`: opens the context menu with additional actions for the item or the whole selection (the list supports multiple selection). In addition to copy, paste, and remove, the menu shows YouTube Music actions when the selection contains tracks from that source: **Like**/**Dislike**, **Add to YouTube Music playlist...**, and, when the current tab is one of your YouTube Music playlists, **Remove from YouTube Music playlist**. See [Managing YouTube Music playlists](#managing-youtube-music-playlists).
- `Tab` / `Esc`: returns focus to the player.

#### Folder mode

When the tab came from a folder opened with `Ctrl+Shift+O`, the browser displays the contents of the current directory: subfolders and media files. As playback advances, the item corresponding to the current media is highlighted automatically. When you move the selection to a media file, the player immediately starts playing that file. The available shortcuts are:

- `Enter`: enters the selected subfolder or plays the media file.
- `Backspace`: goes back to the parent folder (equivalent to selecting `..`).
- `Shift+F10`: opens the context menu.
- `Tab` / `Esc`: returns focus to the player.

#### Quick location by typing

In both modes, typing letters or numbers moves the selection to the first item whose name starts with the typed characters. The search ignores accents and differences between uppercase and lowercase. After one second without typing, the character accumulator is reset and the next letter starts a new search.

For organization tasks, it is useful to think of tabs as independent workspaces: one tab to play something now, another to review the library, and another for tests or temporary collections.

## Settings

Preferences are under `Ctrl+,` and are divided into four tabs: **General**, **Playback**, **Accessibility**, and **Additional features**.

### General

The **General** tab brings together the options that control how KeyTune resumes on the next launch:

- **Restore session on startup**: reopens tabs and tries to restore the state from the previous run.
- **Remember window size**: saves and restores the main window size between runs.
- **Remember last used folder**: uses the last opened folder as the initial directory in open and save dialogs.
- **Confirm before exiting**: asks for confirmation before closing the player.

This same tab contains the **File associations** section (Windows). The **Register as default player** button adds KeyTune to the *Open with* menu for audio, video, and playlist formats. After registering, set the app as the default in Windows settings if you want those files to open directly in KeyTune. The **Unregister associations** button removes this registration.

The **General** tab also includes the **Log recording** section:

- **Record diagnostic logs**: when enabled, the player writes a rotating log file to disk. Useful for debugging problems and attaching to bug reports. Logs are written in English.
- **Detail level**: controls how much information is recorded. *Errors only* is the quietest; *Debug* is the most detailed and can generate large files. It is available only when logging is enabled.
- **Open logs folder**: opens the folder where log files are saved in the file explorer.

Logs are rotated automatically every 2 MB and up to 3 previous files are kept. Files from previous sessions are stored as `keytune.log.1`, `.2`, and `.3` in the same folder.

### Playback

The **Playback** tab controls audio behavior and the initial state of new playlists:

- **Default volume**: volume when starting the player (0-100).
- **Volume step**: how much each press of `Up Arrow`/`Down Arrow` increases or decreases the volume (1-25).
- **Crossfade (seconds)**: audio overlap between tracks during automatic transition (0-12 s). Use 0 to disable it. Crossfade is applied only between audio files.
- **Seek step (seconds)**: how much each press of `Left Arrow`/`Right Arrow` moves forward or backward in the media (1-120 s).
- **Default repeat**: repeat mode automatically applied to new playlists. The options are *Repeat off*, *Repeat current track*, and *Repeat playlist*.
- **Audio device**: sound output used for playback. *System default* follows the main Windows device.
- **Enable shuffle in new playlists**: automatically enables shuffle mode in playlists created after saving.
- **Apply crossfade when changing tracks manually**: when enabled, crossfade is also used when moving forward or backward manually; by default it applies only at the natural end of each track.
- **Disable video output (play audio only)**: keeps playback audio-only, including video files. Useful to avoid external video windows.

### Accessibility

The **Accessibility** tab has a single option: **Enable accessibility announcements**. When enabled, the player announces changes in time, volume, tab switching, and status to the screen reader. When disabled, those announcements are suppressed. On-demand announcement shortcuts (`T`, `V`, `S`) keep working regardless of this setting - see [Accessibility features](#accessibility-features) for details.

### Additional features

The **Additional features** tab contains optional integrations. Today it brings together the YouTube Music and YouTube controls in two sections.

#### YouTube Music and YouTube integration

- **Enable additional features for YouTube Music and YouTube (yt-dlp and ytmusicapi)**: downloads and maintains a `yt-dlp` executable and the required Python packages in a local folder. Without this, the YouTube Music tab does not work. On first run, the download can take a few minutes and requires internet access. When disabled, already downloaded files are not removed.
- **Automatically update YouTube Music dependencies**: checks for and applies updates at the interval defined below. It appears only when the option above is enabled.
- **Use nightly version of yt-dlp (recommended)**: downloads nightly builds of `yt-dlp`. Recommended because YouTube and YouTube Music frequently change their extraction mechanisms and nightly usually receives fixes before the stable channel. It appears only when the integration is enabled.
- **Update interval (hours)**: how often the player tries to update dependencies when the YouTube Music tab is opened (1-720 h). It is available only when automatic updates are enabled.

#### YouTube Music library

This section appears only when the integration is enabled.

- **Playlists loaded at a time**: how many library playlists are fetched in each load (5-200). Smaller values speed up opening; when the end of the list is reached, the player offers to load more.
- **Personalized mixes to discover**: maximum number of items scanned on the YouTube Music home page to find personalized mixes (5-200). Smaller values make synchronization faster.
- **Play related content at the end of the playlist (automatic radio)**: when the last YouTube Music track ends naturally - or when you request the next track while on the last one -, the player searches for related tracks (YouTube Music radio) and continues playing automatically. For a continuous transition, the search starts shortly before the last track ends and the next link is resolved in advance, avoiding a pause while content is discovered. It can also be turned on or off with the `A` key during playback.
- **Save listened songs to YouTube Music history**: enabled by default. When you listen to a YouTube Music track for enough time (about 30% of the duration, between 15 and 30 seconds), the player marks that track as watched in your YouTube Music account history. Disable it to play YouTube Music tracks without recording anything in history.

## Equalizer

The equalizer is opened per tab with `Ctrl+Shift+E`, so each playlist can have its own adjustment.

In practice, this lets you keep one playlist with enhanced bass and another with a more neutral adjustment without having to redo everything whenever you switch contexts.

### How to use

When you open the equalizer, the **Target tab** field shows which playlist will receive the adjustments. Use the **Enable equalizer on this tab** checkbox to turn the effect on or off only for that tab.

The **Preset** field lists all available presets. Built-in presets appear with the *(built-in)* suffix. When you select one, the **Description** field shows a note about the sound profile and the **Preset summary** section displays the preamp and each band value so you can review them before applying.

#### Preset management buttons

- **New...**: creates a custom preset from scratch. Opens the editor so you can define the name, preamp, and gain for each band. Use this button when you want a curve that does not exist among the built-in presets.
- **Edit...**: edits an existing custom preset. This button appears this way only when the selected preset is custom.
- **Save copy...**: when the selected preset is built-in, the button changes its name to **Save copy...** and creates an editable version based on it. Use this path to start from a built-in preset and adjust it.
- **Duplicate...**: creates a copy of a custom preset with a new name, keeping the original untouched. Not available for built-in presets.
- **Delete**: permanently removes the selected custom preset. Not available for built-in presets.
- **Apply to all tabs**: copies the preset and enabled state from the current tab to all open media tabs.

#### Preset editor

The editor shows the name field, the preamp control, and one control for each frequency band. Each band accepts values from -12.0 dB to +12.0 dB. Positive values boost the frequency; negative values attenuate it. The preamp adjusts the overall gain before all bands.

### Built-in presets

KeyTune includes 18 presets ready to use:

| Preset | Profile |
|---|---|
| Default | Neutral curve, keeps the original sound |
| Classical | Enhances definition and brightness without overdoing the bass |
| Club | More energetic bass and treble |
| Dance | More bass impact and top-end brightness |
| Deep bass | Prioritizes sub-bass and bass to add weight to the beat |
| Bass and treble | V-shaped curve with strong bass and bright treble |
| Enhanced treble | Highlights details, voices, and overall brightness |
| Headphones | Balance designed for headphones with a sense of clarity |
| Large hall | Creates a more open and spacious feel |
| Live | Stage presence and ambience |
| Party | Curve for casual volume and upbeat songs |
| Pop | Vocals, brightness, and clean bass |
| Reggae | More body in the bass with relaxed mids |
| Rock | Guitar attack, snare, and overall presence |
| Ska | Firm bass with lively mids and treble |
| Soft | Gentle listening, reduces harshness |
| Soft rock | Balance with light vocal presence and brightness |
| Techno | Beat, sub-bass, and electronic brightness |

### Tips

- Reduce the preamp if the sound starts to distort.
- Make small adjustments to the bands to avoid excess.
- Use **Save copy...** on a built-in preset to start from a ready-made curve and adjust only what you need.
- Use **Duplicate...** instead of editing directly when you want to experiment without losing the previous version.

## YouTube Music

KeyTune includes a dedicated YouTube Music tab. Use `Ctrl+Shift+Y` to open it. It works as a separate tab, so you can keep the local library in one tab and YouTube Music in another.

For the tab to work, you must enable the integration in `Ctrl+,` > **Additional features** and connect an account.

The YouTube Music integration depends on how the site changes and how `yt-dlp` interprets those pages. Because of that, errors, temporary failures, and even stops without an apparent explanation can occur; when this happens, you usually need to update the dependencies or try again later.

### Account and library

The **Account and library** section shows the connected account status, the loaded library summary, and the latest operation message. It has three buttons:

- **Connect account...**: opens the dialog to connect a YouTube Music account or renew the saved authentication.
- **Disconnect account**: removes the saved authentication from this installation.
- **Refresh library**: fetches the playlists and mixes available in the connected account again.

Below the account section is the **Playlists and mixes** list with all playlists and mixes in the library. Use the **Filter** field to find items by name. The counter above the list shows how many items are visible after filtering. Below the list are the actions:

- **Open selection**: opens the selected playlist or mix in a new tab (`Enter` in the list does the same).
- **New playlist...**: creates a new playlist in your account. The player asks for the name and privacy (Private, Unlisted, or Public). See [Managing YouTube Music playlists](#managing-youtube-music-playlists).
- **Delete playlist...**: deletes the selected playlist from your account, with confirmation. It only works for playlists you created - mixes, charts, and third-party playlists cannot be deleted.
- **Load more playlists**: fetches the next batch when there are more playlists to load. You can also press `Page Down` when at the end of the list.

### Search in the catalog and on YouTube

The **Search in the catalog and on YouTube** section is collapsed by default. Expand it to search. It has:

- **Search field**: type what you want to search for and press `Enter` or click **Search**.
- **Scope**: chooses where the search will be performed. The available options are:
    - *YouTube Music - songs*: tracks from the YouTube Music catalog.
    - *YouTube Music - videos*: music videos and video content from YouTube Music.
    - *YouTube Music - playlists*: playlists from the YouTube Music catalog.
    - *YouTube - videos*: YouTube videos in general, without requiring an account.
- **Explore**: four buttons bring more content into the same results list:
    - **Trending...**: opens a menu with *Global* at the top and the other countries grouped into submenus by continent. When you choose a country, the YouTube Music charts and trending highlights appear in the list as playlists you can open or save to the library. Does not require a connected account.
    - **Moods and genres...**: opens a menu with YouTube Music mood and genre categories (for example *Focus*, *Workout*, *Pop*, *Rock*). When you choose a category, its playlists appear in the list. Does not require a connected account.
    - **Liked songs**: loads liked tracks (the *Liked Music* playlist from your account). Requires a connected account.
    - **History**: loads your YouTube Music playback history, from the most recent track to the oldest. Requires a connected account.
- **Results list**: shows the items found (from search, trending charts, moods and genres, liked songs, or history). The list allows **multiple selection**: use `Ctrl+Arrows` to move focus without changing the selection, `Ctrl+Space` to check or uncheck the focused item, and `Shift+Arrows` to select a range. `Enter` adds the selection to the current playlist; `Ctrl+Enter` opens the selection in a new playlist; `Shift+F10` or the **Actions...** button opens the context menu with additional options.
- **Save to Music**: saves the selection to the YouTube Music library when the result is compatible (playlists or tracks).

### Open playlist or video

The **Open playlist or video** section is also collapsed by default. Expand it to paste a YouTube Music or YouTube playlist, mix, or video link. Click **Open link** or press `Enter` in the field to open it.

### Managing YouTube Music playlists

In addition to opening and saving playlists, KeyTune lets you edit your playlists directly in the connected account. All these actions require a connected account and change the playlist **in your YouTube Music account** - anything involving deletion is confirmed first and cannot be undone by the player.

**Adding tracks to a playlist.** Select one or more YouTube Music tracks (in the current playlist or in the search results list) and use **Add to YouTube Music playlist...** in the context menu (`Shift+F10`), or press `Ctrl+Shift+A` to add the track that is playing. A list of your editable playlists appears; personalized mixes and radios are not included in this list because they cannot be edited. At the top of the list is the **Create new playlist...** option, which creates a new playlist already containing the current selection (same behavior as the YouTube Music app).

**Removing tracks from a playlist.** With one of your YouTube Music playlists open in the current tab, select the tracks and use **Remove from YouTube Music playlist** in the context menu. The player asks for confirmation and, when finished, also removes the tracks from the open tab so the list continues to mirror the account. Removal is offered only for playlists you created or where you are a collaborator.

**Creating a playlist.** Use **New playlist...** in the *Playlists and mixes* section to create an empty playlist, or **Create new playlist...** in the add tracks dialog to create it already with the selection. In both cases, the player opens a dialog where you enter the **name** and choose the **privacy**: *Private* (only you can see it), *Unlisted* (visible to anyone with the link), or *Public* (appears on your profile and may appear in searches). The default is Private. After creating it, the library is refreshed so the new playlist appears in the list.

**Deleting a playlist.** Select the playlist in the *Playlists and mixes* list and use **Delete playlist...**. You can only delete playlists you created; the player confirms first and then refreshes the library.

### YouTube Music session

#### What cookies are

Cookies are small text files that browsers store to remember your preferences and login information on websites. When you log in to YouTube Music, the browser saves cookies that contain your authentication. By exporting these cookies, you are transferring that logged-in session information to KeyTune, allowing the application to access your account without asking for your password.

#### Why use an incognito window

Using an incognito window (also called private browsing) is important because Google constantly renews cookies in normal windows. If you exported cookies from a regular session, they would become invalid quickly as the browser renewed them. In the incognito window, because the session is no longer used after you close it, the cookies are not renewed and remain valid for much longer.

#### Step by step: export YouTube Music cookies

**Prerequisite:** install the [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) extension in your browser (works in Chrome, Edge, and Chromium-based browsers).

**1. Enable the extension in incognito tabs**

First, configure the extension to work in private tabs:

1. Press `Ctrl+L` to focus the address bar.
2. Press `Esc` to exit the address bar edit box.
3. Press `Alt+F` to open the browser menu.
4. Navigate with the arrows to **Extensions**, expand the submenu by pressing `Enter`, and choose **Manage extensions**.
5. Find **Get cookies.txt LOCALLY** and click **Details** (or "Learn more").
6. On the details page, find the **Allow in private tabs** or **Allow in incognito** option and enable it.
7. Close the page and return to your browser.

**2. Log in and export cookies**

1. Open a new incognito/private tab (usually `Ctrl+Shift+N` or `Ctrl+Shift+P`).
2. Navigate to [music.youtube.com](https://music.youtube.com/).
3. Log in with your Google account and choose your music account if there are multiple options.
4. After completing login, press `Ctrl+L` to focus the address bar.
5. Press `Esc` to exit the address bar edit box (may be necessary).
6. Navigate with `Tab` until you reach the **Extensions** section. Expand it by pressing `Enter`.
7. Continue navigating with `Tab` until you find the **Get cookies.txt LOCALLY** extension and click it (or press `Enter`).
8. A page will open with the cookies. Look for the **Export** or **Download** button (usually the first button on the page) and click it to download the `cookies.txt` file.
9. **Important**: close the incognito tab **without navigating to any other site**. This ensures the cookies are not renewed.

**3. Import into KeyTune**

1. In KeyTune, open the YouTube Music tab (`Ctrl+Shift+Y`).
2. In the **Account and library** section, click **Connect account...**.
3. A dialog will open offering the option to import a session. Choose the `cookies.txt` file you just downloaded.
4. The account will be connected and you can use YouTube Music normally.

#### Security information

The exported `cookies.txt` file contains authentication information for your account. For security:

- Use the file only on your own computer.
- Do not share the file with other people.
- Delete the file after importing it into KeyTune if you want (KeyTune keeps an internal, secure copy).
- If you disconnect the account in KeyTune, the stored cookies will be removed.

### Shortcuts

- `Ctrl+Shift+Y`: open the YouTube Music tab
- `Ctrl+Shift+A`: add the current media to a YouTube Music playlist
- `Enter` in the search field: run the search
- `Enter` in the results list: add the item to the current playlist
- `Ctrl+Enter` in the results list: open the item in a new playlist
- `Ctrl+Space` in the results list: check or uncheck the focused item (multiple selection)
- `Ctrl+Arrows` in the results list: move focus without changing the selection
- `Shift+Arrows` in the results list: select a range of items
- `Shift+F10` in the results list: open the actions menu
- `Enter` in the library playlist list: open the selection
- `Page Down` at the end of the playlist list: load more playlists
- `Esc`: close the tab when it has focus

## Accessibility features

The application was designed for screen readers and keyboard use. In general:

- focus avoids unnecessary jumps to the native video area;
- state and navigation announcements are made when accessibility support is available;
- fields, buttons, and lists have names and descriptions readable by screen readers.

If you use a screen reader, the on-demand announcement shortcuts `T`, `V`, and `S` (described in [Playback shortcuts](#playback-shortcuts)) and the `F1` quick help help you orient yourself without depending on automatic events.

Automatic announcements - such as track changes, tab switching, and volume changes - can be turned on or off in `Ctrl+,` > **Accessibility**.

The lyrics panel is also designed for this use: `Ctrl+Alt+L` or the **Lyrics** checkbox in the time area shows or hides the panel, and the text can be read, navigated with the arrow keys, and copied with the **Copy full lyrics** button. When the track changes, the player tries to fetch the lyrics automatically from LRCLIB first and then YouTube Music.

## Updates

On startup, KeyTune can check for updates automatically. To check manually at any time, use the **Help > Check for updates** menu.

When a new version is available, the application shows a dialog with the release notes, the file name, and the download size before asking for confirmation. If you accept, the application downloads the package, shows download progress, and asks for permission to install after the file is ready. If you cancel or close the dialog, nothing is installed and the player continues working normally.

## Troubleshooting

If the application does not open correctly, first check whether installation completed without errors (reinstalling with the latest installer solves most cases) and whether the system has permission to access the files or folders you tried to open.

If the player cannot find the MPV runtime, check whether it is in one of these paths: an `mpv/` folder next to the executable, `MPV_HOME`, `MPV_DLL_DIR`, the cache saved from the previous run, or a compatible Chocolatey installation.

If media does not open, test another local file to separate an invalid path, permission, or incompatible file type problem.

If file association does not work as expected, there are two separate steps to confirm: first, that KeyTune was registered as an option (during installation or later in **Settings > General > Register as default player**); second, that it was chosen as the default application for those formats in Windows default app settings - registration alone does not automatically make KeyTune the default.

If session restoration fails, open the app once without depending on the previous session and check whether window and folder settings are being saved normally.

If the YouTube Music tab does not load or shows dependency errors, open `Ctrl+,` > **Additional features** and confirm that **Enable additional features for YouTube Music and YouTube** is checked. The initial download can take a few minutes and requires internet access. If the dependencies are already installed but search or loading fails, use the nightly version of `yt-dlp` in the same preferences - it usually receives fixes before the stable channel.

If the YouTube Music session expires or the player asks for authentication again, export the browser cookies as described in the [YouTube Music session](#youtube-music-session) section and reconnect the account.

To investigate other problems, enable log recording in `Ctrl+,` > **General** > **Log recording**. With **Record diagnostic logs** enabled and the level set to *Debug*, the player writes detailed information to `keytune.log` in the data folder. Use **Open logs folder** to locate the file and, if you need to report a problem, attach it to the issue.

## For developers

KeyTune is an open source project. The repository, issues, pull requests, and releases are at [github.com/ed-fe/KeyTune](https://github.com/ed-fe/KeyTune). The source of this manual is at [docs/manual.md](https://github.com/ed-fe/KeyTune/blob/main/docs/manual.md).
