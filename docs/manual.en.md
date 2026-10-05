# KeyTune Manual

KeyTune is a media player built to be used from the keyboard, with accessibility first. It works well with playlists, with folder browsing, and with picking up where you left off last time.

This project was developed with AI assistance, including GitHub Copilot, OpenAI Codex and Anthropic's Claude Code.

Here you will find the app's features and step-by-step instructions for the most common tasks. If you just want to start listening, read [Getting started](#getting-started) and [How to open media](#how-to-open-media). The rest is for reference.

## What KeyTune offers

- Audio and video playback controlled from the keyboard
- Playlists in tabs, with an independent playback queue
- Folder explorer next to the tabs
- Search in the current playlist or folder, with navigation between results
- Smart library: global search, favorites, ratings, history and per-file resume
- Sleep timer with preset durations or a pause at the end of the track
- Per-tab equalizer, with presets and your own presets
- Lyrics panel with automatic search
- KeyTube tab, with YouTube Music and YouTube (`Ctrl+Shift+Y`)
- YouTube live broadcasts, with audio and optional video
- Online radio from all over the world (`Ctrl+Shift+N`)
- Download of YouTube songs and videos (`Ctrl+Shift+B`)
- Audio and video conversion between formats (`Ctrl+Shift+K`)
- AutoDJ, which mixes the tracks of the playlist
- Plugins and marketplace
- Restoring what was open in the last session
- Announcements for screen readers

## Getting started

1. Download the latest `KeyTune-Setup.exe` from the [releases](https://github.com/ed-fe/KeyTune/releases) page.
2. Run the installer and follow the steps. On the additional tasks page you can create a desktop shortcut and choose which audio, video and playlist formats to associate with KeyTune. All of this is optional and unchecked by default. Associating a format adds KeyTune to the *Open with* menu; for it to open those files on its own, you still need to set it as the default in the Windows settings.
3. From then on, when a new version is available, KeyTune shows what's new and asks for confirmation before downloading and installing (see [Updates](#updates)).

KeyTune plays media through the MPV runtime, and the installer already includes it. If the player opens but plays nothing, see [Troubleshooting](#troubleshooting).

## Interface

The first time you open it, the window shows an empty playlist tab. It has these areas:

- **Menu bar**, at the top: **File**, **Playback**, **View**, **Library**, **Tabs**, **Settings** and **Help**.
- **Tab area**, which takes up most of the window. Each tab is a playlist (see [Playlists, folders and tabs](#playlists-folders-and-tabs)) and is split into two parts side by side: on the left, the item browser, which is the playlist list; on the right, the player area. For a video, the player area shows the video frame. For audio, or with nothing loaded, it shows a help text with the most-used shortcuts.
- **Folder explorer**, to the left of the tabs when opened with `Ctrl+E`. It shows the folders and media files on the computer (see [Folder explorer](#folder-explorer)).
- **Time panel**, below the tabs: elapsed time, duration, progress bar and a summary of the main shortcuts.
- **Status bar**, along the bottom edge: the result of the last action.

`Tab` or `Ctrl+B` switch focus between the item browser and the player (with the explorer open, `Tab` goes through it too). `F1`, at any time, opens the quick shortcuts help.

## How to open media

There are three ways to put media into KeyTune: open, paste and use the folder explorer. All three work the same way: what comes in goes to the **current playlist** and starts playing. With `Shift`, it goes in **without playing**, at the end of the list, and whatever was playing keeps playing.

| To | Playing | Without playing |
| --- | --- | --- |
| Choose files | `Ctrl+O` (**File > Open...**) | `Ctrl+Shift+O` (**File > Open without playing...**) |
| Paste from the clipboard | `Ctrl+V` | `Ctrl+Shift+V` |
| Use the folder explorer | `Enter` | `Shift+Enter` |

- A `.m3u` or `.m3u8` file opened with `Ctrl+O` becomes a playlist.
- `Ctrl+V` accepts links, paths as text, and files or folders copied in Windows File Explorer. From a folder, all the media come in, including those in subfolders. YouTube Music playlist links are recognized by the `list=` parameter and opened as the complete playlist.

To start a separate list, create a new playlist with `Ctrl+T` and open or paste into it. To open a link, copy it and use `Ctrl+V`.

Formats supported directly:

- Audio: `.mp3`, `.wav`, `.flac`, `.aac`, `.ogg`, `.oga`, `.m4a`, `.opus`, `.wma`, `.aiff`, `.aif`, `.ac3`, `.mka`, `.wv`, `.ape`.
- Video: `.mp4`, `.m4v`, `.mkv`, `.avi`, `.mov`, `.webm`, `.flv`, `.wmv`, `.mpg`, `.mpeg`, `.3gp`, `.ts`, `.m2ts`, `.mts`, `.ogv`.

**File > Recent** keeps, in separate lists, the last files, folders and playlists you used.

### Listening to a file straight from Windows File Explorer

With KeyTune set as the default player, `Enter` on an audio file in File Explorer opens the **quick player**: a small window that plays the file right away, without loading tabs, playlists or the previous session.

1. In File Explorer, select the file and press `Enter`.
2. Listen. The screen reader announces the file name in the window title.
3. Press `Esc` or `Alt+F4` to close.

`Enter` on another file, with the quick player open, replaces what is playing with the new file, in the same window. Focus stays in File Explorer, and KeyTune announces nothing: you hear the new file start.

| Action | Shortcut |
| --- | --- |
| Play or pause | `Space` |
| Seek back or forward | `Left arrow` / `Right arrow` |
| Seek back or forward 1 minute | `Shift+Left arrow` / `Shift+Right arrow` |
| Volume | `Up arrow` / `Down arrow` |
| Go to the start or the end | `Home` / `End` |
| Speed | `]` faster, `[` slower, `\` back to normal |
| Hear the time, the volume or the status | `T` / `V` / `S` |
| Continue in the full KeyTune | `Ctrl+Enter` (or the **Continue in the full KeyTune** button) |
| Close | `Esc` or `Alt+F4` |

The keys and the announcements are the same as in the main window's player: changing the volume or seeking says nothing, and `V` and `T` tell you the volume and the time when you want them.

`Ctrl+Enter` opens the main window and takes the media to a new playlist. The sound is not interrupted: the media keeps playing from where it was, at the same volume and speed, while the tabs of the last session come back. Opening KeyTune from the Start menu while the quick player is open does the same.

The quick player saves nothing: the file does not enter the recent files, the history or the session, and a volume changed in it lasts only until you close it or continue in the full KeyTune, which keeps it. It starts with the volume of the last session, or with the default volume if the session is not restored.

These open straight in the main window, as before: `.m3u` and `.m3u8` playlists, videos when video output is on, and any file when the full KeyTune is already open (it goes to the current playlist). To always use the main window, uncheck **Use the quick player when opening files from Windows** in `Ctrl+,` > **General**.

## Playback

### Playback shortcuts

| Key | What it does |
| --- | --- |
| `Space` | Play or pause |
| `Left arrow` / `Right arrow` | Rewind or fast-forward the media (the step is in **Preferences > Playback**) |
| `Shift+Left arrow` / `Shift+Right arrow` | Rewind or fast-forward 1 minute |
| `Home` / `End` | Go to the start or the end of the media |
| `Up arrow` / `Down arrow` | Raise or lower the volume |
| `Ctrl+.` | Stop |
| `Ctrl+PageUp` / `Ctrl+PageDown` | Previous or next track |
| `Alt+Left arrow` / `Alt+Right arrow` | The same, as an alternative |
| `Alt+Up arrow` / `Alt+Down arrow` | Move the current item up or down in the playlist |
| `Alt+Home` / `Alt+End` | Go to the first or the last item of the playlist |
| `E` | Toggle shuffle |
| `R` | Toggle repeat mode |
| `]` / `[` | Raise or lower the speed |
| `\` | Back to normal speed |
| `Shift+]` / `Shift+[` | Raise or lower the pitch, in semitones |
| `Shift+\` | Back to the original pitch |
| `Alt+D` | Choose the audio output |
| `Ctrl+Alt+L` | Show or hide the lyrics panel |
| `Ctrl+Alt+V` | Toggle the video of live broadcasts |
| `Ctrl+Shift+F` | Put the selected item in the queue |
| `Ctrl+Shift+Q` | Manage the queue |
| `Ctrl+Shift+D` | Configure the sleep timer |
| `T`, `V`, `S` | Announce the time, the volume and the status |

The shortcuts for YouTube Music, download and convert are in [KeyTube](#keytube-youtube-and-youtube-music), [Download from YouTube](#download-from-youtube) and [Convert media](#convert-media).

`Ctrl+W` closes the active tab. `Ctrl+Shift+W` closes, or unloads, only the current media.

### Playback queue

The queue defines what plays after the current track, regardless of the order of the playlist you are looking at. It always belongs to the playlist that is playing.

`Ctrl+Shift+F` (or **Playback > Add to playback queue**) puts an item in the queue or takes it out. `Ctrl+Shift+Q` (or **Playback > Manage playback queue**) shows the queue and lets you remove, reorder or clear it.

### Sleep timer

The sleep timer pauses playback after an agreed time, good for listening to something before falling asleep. It **pauses** instead of stopping: the position is kept and `Space` continues from where it stopped.

Open it with `Ctrl+Shift+D` or **Playback > Sleep timer**. The options:

- **Preset durations**: 5, 10, 15, 30, 45, 60, 90 or 120 minutes, right in the submenu.
- **Custom time**: from 1 to 720 minutes, in the settings box.
- **At the end of the current track**: playback ends when the track finishes, without advancing, repeating or pulling in related content. Does not apply to live broadcasts.
- **Do not use a timer**: cancels the schedule.

The submenu also has **Time remaining** and **Cancel timer**. The player warns you when 5 minutes are left and when 1 minute is left.

### Lyrics

`Ctrl+Alt+L`, or the **Lyrics** box in the time panel, shows or hides the lyrics panel. When the track changes, KeyTune looks for the lyrics on its own, first on LRCLIB and then on YouTube Music. The **Copy full lyrics** button copies the text to the clipboard.

## Playlists, folders and tabs

Each playlist lives in a tab, which helps separate contexts: a list to listen to now, an organized collection, one for tests. The active tab decides what plays and what shows in the item browser.

### Tab and item shortcuts

- `Ctrl+T`: new playlist tab
- `Ctrl+W`: close the current tab
- `Ctrl+Tab` / `Ctrl+Shift+Tab`: next tab or previous tab
- `Ctrl+Shift+E`: equalizer of the active tab
- `Ctrl+C`: copy the selection as text and, for files on the computer, also as files. You can paste into another playlist, into a text field or into Windows Explorer
- `Ctrl+Shift+C`: copy the link or the path of the current media (in the folder explorer, the path of the selection)
- `Ctrl+Shift+S`: save the current playlist
- `Ctrl+B`: switch focus between the item browser and the player
- `Ctrl+F`: find an item in the current playlist or folder
- `Ctrl+G`: search the whole library
- `Ctrl+D`: favorite or unfavorite the selection
- `Ctrl+0` to `Ctrl+5`: rate the selection from zero to five stars
- `Ctrl+Shift+H`: playback history
- `Ctrl+Shift+R`: continue listening to what was left halfway
- `F3` / `Shift+F3`: next or previous search result

### Item browser

The browser sits on the left of each tab and lists the playlist items. What is playing has `▶` at the start of the line.

- `Enter`: plays the selected item.
- `Delete`: takes the item out of the playlist.
- `Shift+F10`: opens the context menu of the item or the selection. Besides copy, paste (playing or not) and remove, the menu brings the YouTube actions when the selection has items from that source: **Like**, **Dislike**, **View details**, **View comments** and **Add to YouTube Music playlist...**. When the tab is one of your YouTube Music playlists, **Remove from YouTube Music playlist** also appears. See [Manage YouTube Music playlists](#manage-youtube-music-playlists).
- `Tab` or `Esc`: gives focus back to the player.

### How lists work

The folder explorer, KeyTube and online radio navigate the same way: you go into items, see what is inside and go back. The keys are the same in all three.

- `Enter`: goes into the item when it holds other items (a folder, a channel, an artist, a country) and **plays** when it plays (a file, a track, a video, a radio station). Albums and playlists go whole into the current playlist.
- `Shift+Enter`: adds to the current playlist **without playing**.
- `Right arrow`: shows what is inside the item, in the same list, even when `Enter` would play.
- `Backspace`: goes back to the previous list, with the selection on the item you had opened. In KeyTube and online radio, `Left arrow` and `Alt+Left arrow` also go back.
- `Down arrow` or `Page Down` on the last item: loads more, in KeyTube and online radio.
- Letters: jump to the item that starts with them.
- `Shift+F10`, the Applications key or the right mouse button: open the item's actions menu.
- Multiple selection: `Shift+arrows` select a range and `Ctrl+arrows` move focus without changing the selection. `Ctrl+Space` selects or deselects the item in focus (in the explorer, `Ctrl+Space` opens sorting).

### Folder explorer

`Ctrl+E` (or **File > Folder Explorer**) opens, to the left of the tabs, the list of folders and media files on the computer. It does not take up a tab: it sits next to any playlist and is meant for building it little by little, without interrupting what is playing. With focus on it, `Ctrl+E` closes the list; with focus elsewhere, it moves focus to it.

It starts at **This PC**, with the Music, Videos, Downloads, Desktop and Documents folders and the disk drives. The folder where you stopped and the chosen sort order are kept for the next time you open it, and the folders from **File > Recent > Recent folders** also open here.

In addition to the keys in [How lists work](#how-lists-work):

- `Enter` goes into the folder or plays the file, adding it to the current playlist. With `Shift+Enter`, all the media in a folder come in, including those in subfolders.
- `Ctrl+Shift+F` adds the selection to the queue, and `Ctrl+Shift+K` converts the selected files (see [Convert media](#convert-media)).
- `Backspace` goes up to the parent folder.
- `Ctrl+C` copies the selected files or folders, to paste into a playlist or into Windows Explorer. `Ctrl+Shift+C` copies the paths as text.
- `Ctrl+Space` opens the sort menu: by name, date modified, date created, type or size, in ascending or descending order.
- `F5` refreshes the folder.
- `Shift+F10` opens the menu with all the actions: **Play now**, **Add to playlist without playing**, **Add to playback queue**, **Open in new playlist**, **Add the whole current folder to the playlist**, **Convert...**, **Index folder in the library**, **Copy**, **Copy path**, **Show in Windows File Explorer**, sorting, **Refresh** and **Close explorer**.
- `Esc` gives focus back to where it was before you opened the explorer.

### Finding items

**Quick typing.** In the playlist and in the explorer, typing letters or numbers moves the selection to the first item whose name starts with what you typed. The search ignores accents and letter case. After one second without typing, the next letter starts a new search.

**Full search.** For long lists, use `Ctrl+F` (or **View > Find item...**), which finds the text in **any part** of the name, not just at the start.

- `Ctrl+F` opens the **Find item** box. Type the text and confirm with `Enter` or with the **Find** button.
- `F3` goes to the next result and `Shift+F3` to the previous one. The **View** menu has the same commands.
- The search goes through the items of the active tab: playlists, folders and KeyTube lists.
- `F3` repeats the last search without opening the box. If there has been no search yet, it opens the box.

## Download and convert

### Download from YouTube

`Ctrl+Shift+B` downloads YouTube and YouTube Music songs and videos. It follows the same rule as `Ctrl+Shift+K` (convert): with focus on a list (the playlist or the KeyTube results), it downloads the **selection**; with focus on the player, it downloads the **current media**. The same commands are in **File > Download from YouTube**: **Download current media**, **Download selection** and **Download whole playlist**. The download uses `yt-dlp`, the same tool that already plays this media, and it happens in the background: playback continues normally.

1. Select what you want to download, or leave focus on the player to download the current media.
2. Press `Ctrl+Shift+B`.
3. In the dialog, choose **Audio** or **Video**, the quality, the sample rate (only for converted audio) and the folder. Your last choice becomes the default in Preferences.
4. Confirm.

Things worth knowing:

- **No dialog.** Uncheck **Always show this dialog when downloading** so the next downloads start right away, with the options from the **Download** tab in Preferences.
- **Quality not available.** If the chosen quality does not exist for that media, KeyTune downloads the original quality and tells you.
- **File name.** The file gets the same name KeyTune shows for the track (`Artist — Title.mp3`). A download never replaces a file that is already in the folder: if the name exists, the new one gets " (2)", " (3)" and so on.
- **Progress.** Press `Ctrl+Shift+B` again during a download to hear the progress or cancel.
- **FFmpeg.** Converting the audio (MP3, FLAC or another sample rate) and downloading high-resolution video require FFmpeg. If it isn't found, KeyTune asks whether it can download it (about 90 MB). If you refuse, the download continues in the original quality, without conversion. An FFmpeg already installed on the system is also used.

**Several items at once.** **Download selection** downloads the selected items, and **Download whole playlist** downloads all the items in the tab into a subfolder named after the playlist. Both are in **File > Download from YouTube** and in the list's context menu. KeyTune asks for confirmation before starting.

Items are downloaded one at a time, with the same options. At the end, the player summarizes how many succeeded and how many failed, and `Ctrl+Shift+B` tells you the position and lets you cancel. An item that fails does not interrupt the others, and KeyTune offers a list with each failure and its reason, with the **Copy list** button. A queue holds at most 200 items.

Only YouTube and YouTube Music media can be downloaded, one at a time.

### Convert media

KeyTune converts audio and video files from your computer without leaving the player. `Ctrl+Shift+K` follows the same rule as `Ctrl+Shift+B`: with focus on a list (the playlist or the folder explorer), it converts the **selection**; with focus on the player, it converts the **current media**. The same commands are in **File > Convert** (**Convert current media** and **Convert selection**) and in the lists' context menu.

KeyTune asks what to do and shows only the options that suit the file type:

- **Audio to video**: creates a video from the audio, with a still image. Choose MP4, MKV or WebM and the resolution (480p, 720p or 1080p). If the audio has embedded album art, it becomes the image; without art, the background is black.
- **Video to audio**: extracts the sound from the video to MP3, M4A (AAC), OGG (Vorbis), Opus, FLAC or WAV.
- **Audio to another audio format**: converts between MP3, M4A (AAC), OGG (Vorbis), Opus, FLAC and WAV. Cover art and track information come along when converting to MP3, M4A and FLAC.
- **Video to another video format**: changes only the format (MP4, MKV, WebM, AVI or MOV). Tracks that are compatible with the new format are copied without re-encoding, which is fast and loses no quality; incompatible ones are re-encoded. Subtitles are only kept in MKV.

In the dialog, besides the format, you set:

- the quality of lossy formats (128, 192, 256 or 320 kbps);
- the sample rate (original, 44100 or 48000 Hz; Opus always uses 48000 Hz);
- where to save: **Same folder as the original file** (the default) or **Another folder**, which enables the folder field and the **Choose folder** button.

The dialog remembers your last choices. The original file is never changed or overwritten: if a file with the same name already exists, the new one gets " (1)", " (2)" and so on.

**Several files.** Select them in the playlist or in the explorer and press `Ctrl+Shift+K`. KeyTune asks for the mode and shows how many files each one applies to. Only files of the right type are converted. The options apply to all of them. With **Same folder as the original file**, each file goes to its own original's folder; with **Another folder**, all go to the chosen folder. Files are converted one at a time, with a summary at the end. An error in one file does not interrupt the others, and the list of failures can be opened and copied, as with downloads.

Conversion runs in the background, and playback continues. Press `Ctrl+Shift+K` during a conversion to hear the progress or cancel; an incomplete file is never left behind.

Conversion uses FFmpeg, the same one as the download. If it isn't found, KeyTune asks whether it can download it, as described in [Download from YouTube](#download-from-youtube). Only files on the computer are converted; for YouTube media, use `Ctrl+Shift+B`.

## Smart library

While `Ctrl+F` searches the list that is open, the **smart library** remembers what you have opened and listened to and makes it all searchable at once. It also keeps favorites, ratings, the playback history and the point where each long media stopped.

Everything lives in a local database (`smart_library.db`), in the same data folder as the preferences. Nothing leaves your computer, and the whole feature can be turned off in `Ctrl+,` > **Library**. The **Library** menu gathers the commands.

### What goes into the index

- The media of any playlist or folder you open goes into the index, in the background.
- **Library > Index a folder into the library...** scans a folder and its subfolders.
- **Library > Refresh indexed folders** scans the already indexed folders again and drops files that no longer exist.
- **Library > Library summary** announces how many media items, folders, favorites and plays are stored.
- **Library > Clear the library...** erases everything (index, favorites, ratings, history and resume), with confirmation.

If you prefer that only the folders you choose go into the index, turn off **Automatically index folders opened in the browser** in the preferences. Browsing in the explorer does not index anything on its own: the folders opened from Recent and the ones you index from the explorer's context menu go into the index.

### Global search

`Ctrl+G` opens the **Search the library** box. Type the text and confirm with `Enter` or with the **Search** button.

- The search ignores accents and letter case, and each word you type must appear somewhere in the item's or folder's name.
- The **Filter** field limits the search to **Everything in the library**, **Favorites only**, **Rated only** or **Already played only**. The last three work even with the text empty.
- Results come in a list with item, rating and folder columns.
- The search is instant even with tens of thousands of files. It matches the start of each word ("estrad" finds "Estrada") and, if nothing turns up, it also looks in the middle of words ("onita" finds "Bonita").
- `Enter` (or the **Play** button) opens **all** the results in a new playlist and starts from the selected track, so a search becomes a usable list.
- **Add to queue** queues only the selected item, in the playlist that is playing.

### Favorites and ratings

The commands act on what is selected in the list; with no selection, they act on the media that is playing.

- `Ctrl+D`: favorites or unfavorites.
- `Ctrl+0` to `Ctrl+5`: gives from zero to five stars.
- **Library > Announce the selection's marks**: reads the item's favorite status, rating and play count.
- **Library > Open favorites in a new playlist**: builds a playlist with everything you favorited.

The same commands are in the list's context menu (`Shift+F10`).

Favorite status and rating appear next to the name, in the list itself, for example `Estrada — favorite, 5 stars`, both in playlists and in the folder explorer. That way the screen reader speaks the mark together with the item.

### Playback history

`Ctrl+Shift+H` opens the **Playback history**. The **View** field chooses between three views, and the columns change with it:

- **All plays**: one line for each time the media played, with when it played, where it stopped and the source (local playlist, folder, remote media or YouTube Music).
- **Grouped by media**: one line per media item, with how many times it played, the last time and the marks.
- **Most played**: the same grouping, from the most played to the least played.

**Filter by text** narrows the list. `Enter` (or **Play**) plays again, and **Add to queue** queues it. **Remove entry** takes one play out of the list without deleting the media from the index; in the grouped views the button becomes **Remove from history** and deletes all plays of that media. **Clear history** erases everything, with confirmation.

A track only enters the history after playing long enough to count as listened, and the oldest entries drop out when the history goes over the limit in the preferences.

This history is local and has no relation to **Save what I listened to in the YouTube Music history**, which records to your YouTube Music account.

### Resume where you stopped

Podcasts, audiobooks and long videos pick up from the point where they stopped. The rule is deliberately conservative:

- it only applies to local files, because streams don't have a stable timeline between sessions;
- it only applies to media longer than the configured **minimum duration** (10 minutes by default);
- stopping within the configured **margin** (30 seconds by default) of the start or the end does not create a resume point;
- reaching the end of the track erases the mark, and the next time it starts from the beginning.

**Library > Continue listening** (`Ctrl+Shift+R`) opens a playlist with everything left halfway, from the most recent to the oldest, and each item shows where it stopped. **Library > Clear resume positions** clears them all at once.

### Smart playlists

A smart playlist is a saved rule, not a fixed list. It is built every time you open it, so it follows changes in ratings and history: "five stars that I haven't played in 30 days" is still right a month later, on its own.

**Library > Smart playlists** lists the saved rules, to open with a single command, and **Manage smart playlists...** creates, edits and removes them. In the editor, everything is a keyboard field, with no visual builder:

- **Favorites only** and **Minimum rating** filter by your marks.
- **Not played for at least (days)** finds what has been forgotten, and **Include media never played** decides whether what never played comes along.
- **Minimum plays** goes the other way: only what you have listened to a lot.
- **Limit to folder** restricts to one folder and everything below it.
- **Include remote media** also brings YouTube Music links and radio stations, which are left out by default.
- **Sort by** and **Maximum number of items** define what comes out and in what order.

Each change updates the **Rule summary**, at the end of the box, in one sentence: the fastest way to check what the rule will gather before saving.

## KeyTube: YouTube and YouTube Music

KeyTube is KeyTune's hub for YouTube Music and regular YouTube. In versions up to 2.0.6 it was called YouTube Music and handled music only; today it also brings together YouTube videos, channels, subscriptions and comments. Open it with `Ctrl+Shift+Y` (or **View > KeyTube per tab**). It is a separate tab, so you can keep the local library in one and KeyTube in another.

For the tab to work, turn on the integration in `Ctrl+,` > **Additional resources** and connect a YouTube account. The same account serves YouTube and YouTube Music.

The integration depends on how the site changes and on how `yt-dlp` reads those pages. Because of that, errors, temporary failures and stops with no apparent explanation can happen. When that happens, updating the dependencies or trying again later is usually enough.

### Account and library

The tab has two parts. At the top, the **Account and library** section; below it, the search field and **a single list**, through which everything else passes: your library, the search and what is inside each item.

**Account and library** shows the connected account, the summary of the loaded library and the last operation message. The buttons:

- **Connect account...**: opens the dialog to connect an account or renew the saved authentication.
- **Disconnect account**: removes the saved authentication on this installation.
- **Refresh library**: searches again for the account's playlists and mixes and updates the ratings of songs visible in the account.
- **New playlist...**: creates a playlist in your account. The player asks for the name and the privacy (see [Manage YouTube Music playlists](#manage-youtube-music-playlists)).

**Like** and **Dislike** are sent to the connected account, so they also show up in YouTube Music on your phone and other devices. KeyTune removes tracks marked as disliked from the account's playlists and radios. A rating made outside KeyTune is only noticed when the track shows up again; **Refresh library** forces the check.

### The list

The list works like the folder explorer (see [How lists work](#how-lists-work)) and starts at **Home**, with seven items:

- **Your playlists and mixes**: those of the connected account. `Enter` opens the playlist in its own tab, where you can edit it in the account; `Right arrow` shows the tracks in the list itself. Requires a connected account.
- **Liked songs**: the tracks you liked (the *Liked Music* playlist of your account). Requires a connected account.
- **History**: your YouTube Music playback history. Requires a connected account.
- **Videos from subscriptions**: the new videos from the channels you are subscribed to, with duration, views and date. Requires a connected account and YouTube.js turned on.
- **Subscribed channels**: the channels you are subscribed to. Each one opens like any channel, so you can choose between videos, Shorts, live broadcasts and playlists. Requires a connected account and YouTube.js turned on. Both subscription lists are read-only: subscribing and unsubscribing are still done on YouTube.
- **Trending**: *Global* and the continents. Go into a continent, choose the country, and the charts and highlights that are trending appear as playlists you can play, open or save to the library. Does not require an account.
- **Moods and genres**: YouTube Music's mood and genre categories (*Focus*, *Workout*, *Pop*, *Rock*...). Go into a category to see its playlists. Does not require an account.

In KeyTube, also:

- `Backspace` goes back one level at a time, down to **Home**. You can chain: from an artist to an album, from a channel to one of its playlists.
- Each list brings 20 items at a time.
- The **Actions...** button opens the item's menu: **Play**, **Add without playing**, **View contents**, **Back to the previous list**, **View comments**, **View details**, **Go to the channel** (or **Go to the artist**, followed by the name), **Add selection...** (to a new playlist or to an open one), **Download selection...** and **Save to YouTube Music** (compatible playlists or tracks). On one of your playlists, the menu also has **Delete YouTube Music playlist...**, which deletes it from the account, with confirmation, and only works for playlists you created. On a comment, it has **Read the whole comment**.
- `Shift+Enter` on one of your playlists adds the tracks to the current playlist without playing.
- `Ctrl+Shift+B` (or **Download selection...**) downloads what is selected. With a **playlist or an album**, KeyTune fetches all the tracks inside and downloads everything. You choose the destination folder; each playlist or album becomes a **subfolder with its name**, and standalone tracks and videos stay in the folder itself, even in a mixed selection. Two lists with the same name get separate folders (*Mix* and *Mix (2)*), and a track that is in two playlists is downloaded in both, so each folder is complete.

Just above the list, a line tells you where you are and how many items there are (for example, *Trending — Europe: 24 items*).

### Search and open links

- **Search or paste a link**: type what you are looking for and press `Enter`. The results appear on top of **Home**, and `Backspace` goes back to it.
- **Paste a link**: a YouTube Music or YouTube playlist, mix or video link pasted into that field is opened with `Enter`, instead of being searched.
- **In** and **Type**: two boxes next to the field. **In** chooses where to search (*YouTube Music* or *YouTube*) and **Type**, what to search for there. In both, the first letter jumps to the option.
    - In *YouTube Music*: *Songs* (tracks from the catalog), *Videos* (music videos and YouTube Music videos), *Albums* (albums, singles and EPs), *Artists* and *Playlists* (from the YouTube Music catalog).
    - In *YouTube*: *Videos* (in general, no account required), *Channels* and *Playlists*.
- **Inside a channel or artist**: when you go in, the list shows what there is to see first. In a YouTube channel: *Videos*, *Shorts*, *Live* and *Playlists*. In a YouTube Music artist: *Songs*, *Albums*, *Singles and EPs*, *Videos* and *Similar artists*. Go into whichever you like; `Backspace` goes back to choose another.

### Video and song details

**View details**, in the **Actions...** menu (or in the playlist's context menu, for a YouTube item), opens a reading box with title, channel and subscribers, duration, views, likes, publication date and the whole description. For the media that is playing, use `Ctrl+Shift+I` (**Playback > View details of the current media**). The **Go to the channel** button, or **Go to the artist** on a YouTube Music track, opens the channel or the artist in KeyTube; the same command is in the **Actions...** menu.

### Comments

**View comments**, in the **Actions...** menu of a video or a song, opens the comments in the list itself, on top of what you were looking at; `Backspace` goes back. For the media that is playing, use `Ctrl+Shift+M` (**Playback > View comments on the current media**), which opens the tab already on the comments.

- Each line has the author, the text, the date, the likes and how many replies there are. The comment pinned by the channel is marked as *pinned*.
- `Enter` opens the whole comment in a reading box; `Esc` closes it.
- `Right arrow`, on a comment with replies, opens the replies.

With YouTube.js turned on (**Preferences > Additional resources**), comments arrive in under a second, in the content language, with pagination and replies. Without it, KeyTune uses yt-dlp, which is slower, brings only the first 20 comments, without replies, and with dates in English.

### Audio language

**Playback > Audio language of the current media...** lists the audio tracks of the YouTube video that is playing (the original and the dubs) and starts playing the chosen one from the same point. The choice holds for that media until you close KeyTune. To make it hold for all of them, use **Audio of dubbed videos** in the preferences.

### Live broadcasts

Paste the link of a YouTube live broadcast into the **Search or paste a link** field (or use `Ctrl+V`, as with any link). KeyTune recognizes the broadcast on its own.

- It plays at the current moment, without resuming from a saved position. The time bar shows a fixed label in place of the duration, and `T` tells you how long you have been watching.
- With **Show the video of live broadcasts** turned on (the default), the picture appears in the player area even with **Disable video output** checked. The video is limited to 720p. Turned off, the broadcast plays only the audio, in the lightest variant. `Ctrl+Alt+V` toggles the option and restarts the broadcast in the new mode.
- You can't rewind, fast-forward, or go to the start or the end. Pausing and resuming continues from where it stopped.
- If the connection drops, the player tries to reconnect up to three times and lets you know. If the broadcast has already ended, the player lets you know instead of playing the recording from the beginning.
- A scheduled broadcast that hasn't started yet lets you know; try again when it starts.
- Live broadcasts stay out of AutoDJ and crossfade, have no lyrics and don't create a resume point.

### Radio from the current track

With a YouTube Music song playing, press `Ctrl+R` (or use **Playback > Start radio from this track**). KeyTune opens a new tab, keeps the playback position and puts the current track as item 1, without continuing the previous radio's queue.

KeyTune avoids repeating tracks from the source playlist and from the last radios you opened. Since YouTube Music is the one that picks the candidates, there is no guarantee of different songs; if there is nothing new, the new tab stays with just the first track.

Don't confuse it with [online radio](#online-radio), which are real radio stations.

### Manage YouTube Music playlists

Besides opening and saving playlists, KeyTune edits your playlists directly in the connected account. All of this requires a connected account and changes the playlist **in your YouTube Music account**. Deleting can't be undone from the player.

**Add tracks.** Select one or more YouTube Music tracks (in the current playlist or in the search results) and use **Add to YouTube Music playlist...** in the context menu (`Shift+F10`). To add the track that is playing, press `Ctrl+Shift+A`. The list of your editable playlists appears; mixes and personalized radios are not included because they can't be edited. At the top there is **Create new playlist...**, which creates a playlist already containing the selection.

**Remove tracks.** With one of your playlists open in the current tab, select the tracks and use **Remove from YouTube Music playlist** in the context menu. The player asks for confirmation. Removal is only offered on playlists you created or where you are a collaborator.

**Create a playlist.** Use **New playlist...** (in the *Playlists and mixes* section) to create an empty one, or **Create new playlist...** in the add-tracks dialog to create it already with the selection. In both cases the player asks for the **name** and the **privacy**: *Private* (only you see it), *Unlisted* (visible to anyone with the link) or *Public* (appears on your profile and may show up in searches). The default is Private.

**Delete a playlist.** Select the playlist in *Playlists and mixes* and use **Delete playlist...**. You can only delete playlists you created.

### Connect your account

To use your library (saved playlists, history, likes and ratings), connect an account. The **Connect account** dialog offers two modes:

1. **Extract from the installed browser**: choose Firefox, Google Chrome, Microsoft Edge, Brave or Opera from the list and click **Connect**. KeyTune extracts the session from the browser profile through `yt-dlp`. Firefox is the most recommended, because it works best on Windows.
2. **Import a file or manual text**: for browsers that are not on the list, or custom setups, import a `cookies.txt` file or paste the session's HTTP headers.

On Windows, Chrome, Edge and Brave may require the browser to be fully closed and, in some versions, the browser's own protection prevents extraction. If that happens, use Firefox or the manual import.

#### What cookies are

Cookies are small text files that browsers keep to remember preferences and logins. When you sign in to YouTube Music, the browser saves cookies with your authentication. When you connect the account in KeyTune, the app uses that session to access your library without asking for your password.

#### Connect through the browser

1. Sign in to your account on [YouTube Music](https://music.youtube.com/) in the browser (Chrome, Edge, Firefox, Brave or Opera).
2. In KeyTune, open KeyTube (`Ctrl+Shift+Y`).
3. In the **Account and library** section, click **Connect account...**.
4. Choose **Extract from the installed browser**.
5. Choose the browser from the list and click **Connect**.

#### Alternative: export the cookies.txt

Use this path if you choose manual mode or have a browser that is not supported directly.

**Before you start**, install the [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) extension in the browser.

**1. Enable the extension in incognito tabs.** In an incognito tab, Google doesn't refresh the cookies all the time during normal browser use.

1. Press `Ctrl+L` to focus the address bar.
2. Press `Escape` to leave the address bar's edit box.
3. Press `Alt+F` to open the browser menu.
4. With the arrow keys, go to **Extensions**, open the submenu with `Enter` and choose **Manage extensions**.
5. Find **Get cookies.txt LOCALLY** and click **Details** (or "Learn more").
6. On the details page, turn on **Allow in private tabs** (or **Allow in incognito**).
7. Close the page and go back to the browser.

**2. Sign in and export the cookies.**

1. Open an incognito tab (`Ctrl+Shift+N` or `Ctrl+Shift+P`).
2. Go to [music.youtube.com](https://music.youtube.com/).
3. Sign in with your Google account.
4. Open the **Get cookies.txt LOCALLY** extension and click **Export** (or **Download**) to save the `cookies.txt`.
5. Close the incognito tab without visiting other sites.

**3. Import into KeyTune.**

1. In the **Connect account...** dialog, choose **Import a file or manual text**.
2. Select the downloaded `cookies.txt` (or paste the headers text) and click **Connect**.

#### Security

The `cookies.txt` holds your account's authentication. Because of that:

- use the file only on your own computer;
- don't share it with anyone;
- delete it after importing, if you like: KeyTune's internal copy has only the YouTube cookies needed for the connection;
- when you disconnect the account in KeyTune, the stored cookies are removed.

### KeyTube shortcuts

- `Ctrl+Shift+Y`: open KeyTube
- `Ctrl+R`: start a radio from the current track
- `Ctrl+Shift+A`: add the current media to a YouTube Music playlist
- `Ctrl+Shift+I`: view the details of the current media
- `Ctrl+Shift+M`: view the comments of the current media
- `Ctrl+L`: like the current media
- `Ctrl+Shift+L`: mark the current media as disliked (and skip to the next track)
- `A`: turn related content at the end of the playlist on or off
- `Enter` in the search field: search; with results, focus goes to the list
- `Esc`: close the tab, when it is focused

## Online radio

`Ctrl+Shift+N` (or **View > Online radio in a tab**) opens a tab to listen to radio stations from all over the world. The stations come from [Radio Browser](https://www.radio-browser.info/), an open directory maintained by the community. You don't need an account or to turn anything on in **Additional resources**: the stations play directly, without going through `yt-dlp`.

The tab has a search field and, below it, a single list that works like the folder explorer and like the KeyTube list: you go into items and come back.

### The home

The list starts at **Home**, with these items:

- **Favorite radio stations**: the ones you marked with `Ctrl+D`.
- **Recently listened**: the last stations you played.
- **Radio stations in your country**: those of the country KeyTune treats as yours. By default it is the Windows one; you can choose another in **Preferences > Online radio**, under **My country**, or in the country's actions menu, inside the tab (**Set ... as my country**).
- **Most listened worldwide**.
- **Countries**: choose a country and see the **Most listened**, **All, in alphabetical order** or **By state or region**.
- **Genres**: choose a genre to see its stations.
- **Languages**: choose a language to see its stations.

### Keys and actions

In addition to the keys in [How lists work](#how-lists-work):

- `Ctrl+D`: adds the station to favorites or takes it out. It is the same favorite as the playlists', and the list marks the station as "favorite".
- `Ctrl+C`: copies the stream address of the selected station.
- The **Actions...** button opens the menu with **Play**, **Add without playing**, **View contents**, **Back to the previous list**, **Add to favorites** (or **Remove from favorites**), **View radio station details**, **Open the radio station's website in the browser**, **Copy the stream address** and **Vote for this radio station in the directory**. With a station playing, the menu also lets you favorite it even if it isn't selected.

**View radio station details** opens a reading box with name, country, state or region, language, genres, quality (codec and bitrate), votes, listeners in the last 24 hours, website and stream address, with a button to open the website. **Vote for this radio station in the directory** records your vote on Radio Browser.

### Search and paste addresses

Type the name of a radio station in the search field and press `Enter`. The **In** box chooses where to search: **Worldwide** or only your country. If you paste a stream address into the field, it plays right away, with no search.

### How the radio plays

The station goes into the current playlist under the station's name. It plays as an audio-only live broadcast: you can't rewind or fast-forward, and it stays out of AutoDJ and crossfade.

The song the station announces appears in the status bar, in the format *Station: title*, and goes into the status announcement (`S`). Recent stations come from the playback history.

## Equalizer

`Ctrl+Shift+E` (or **View > Per-tab equalizer**) opens the active tab's equalizer, so each playlist can have its own setting. That lets you, for example, keep one playlist with boosted bass and another with a neutral setting, without redoing everything each time you switch.

### How to use it

The **Target tab** field shows which playlist receives the adjustments. The **Enable equalizer on this tab** box turns the effect on or off for that tab only.

The **Preset** field lists all the presets. The built-in ones carry the suffix *(built-in)*. When you choose one, **Description** shows a note about the sound profile and **Preset summary** brings the preamp and the value of each band, so you can check before applying.

#### Management buttons

- **New...**: creates a custom preset from scratch. The editor asks for the name, the preamp and the gain of each band. Use it when you want a curve that doesn't exist among the built-in ones.
- **Edit...**: edits a custom preset. It only appears like this when the selected one is custom.
- **Save copy...**: when the selected one is built-in, this is the button that appears. It creates an editable version based on it, the right way to start from a ready-made preset and adjust.
- **Duplicate...**: copies a custom preset under another name, without touching the original. Doesn't apply to built-in ones.
- **Delete**: permanently removes the selected custom preset. Doesn't apply to built-in ones.
- **Apply to all tabs**: copies the current tab's preset and enabled state to all open media tabs.

#### Preset editor

The editor has the name field, the preamp and one control per frequency band. Each band goes from -12.0 dB to +12.0 dB: positive values boost the frequency and negative ones cut it. The preamp adjusts the overall gain before all the bands.

### Built-in presets

KeyTune comes with 18 presets:

| Preset | Profile |
|---|---|
| Default | Neutral curve, keeps the original sound |
| Classical | Brings out definition and brightness without overdoing the bass |
| Club | Livelier bass and treble |
| Dance | More impact in the bass and sparkle at the top |
| Deep bass | Prioritizes sub-bass and bass, to give weight to the beat |
| Bass and treble | V-shaped curve, with strong bass and bright treble |
| Boosted treble | Highlights detail, vocals and overall brightness |
| Headphones | Balance designed for headphones, with a sense of clarity |
| Large room | Creates a more open, spacious feel |
| Live | Stage presence and ambience |
| Party | Curve for casual volumes and upbeat music |
| Pop | Clean vocals, brightness and bass |
| Reggae | More body in the bass, with relaxed mids |
| Rock | Guitar attack, snare and overall presence |
| Ska | Firm bass, with lively mids and highs |
| Soft | Calm listening, reduces harshness |
| Soft rock | Balance with a slight presence of voice and brightness |
| Techno | Beat, sub-bass and electronic sparkle |

### Tips

- Lower the preamp if the sound starts to distort.
- To adjust a ready-made curve, use **Save copy...** on the built-in preset. To experiment without losing the current version, use **Duplicate...**.

## AutoDJ

AutoDJ mixes the playlist's tracks the way a DJ would, instead of cutting from one to the next. It is not part of the installer: KeyTune downloads the analysis libraries (`librosa`, NumPy, SciPy, Numba and PyAV) after you confirm, in **Preferences > Additional resources**. Once installed, **Playback > Enable AutoDJ** turns it on and off.

It analyzes the current track and the next options in the background and picks the following one by energy, key, volume and tempo, avoiding repeating recent artists. When the rhythm is reliable, it aligns the beats of the two tracks during the overlap. The manual queue always takes priority. If the analysis is late, fails or isn't confident, the player uses the regular crossfade or moves on to the next track normally.

**Play playlist with AutoDJ** creates a separate tab, without touching the original playlist. The current track starts right away, and KeyTune keeps up to five songs prepared ahead. The tab has a reading field with the source, how many tracks are prepared, the analysis activity and the next transition: BPM, tempo adjustment and, when a regular transition is needed, the reason. Each item appears as played, playing, next or prepared.

The session controls swap the next track, recalculate the sequence, add files, pause or resume the preparation and end the session keeping the part already prepared. The same actions are in `Shift+F10`, on the list. The session is restored along with the player.

AutoDJ options are in **Preferences > Playback** and **Additional resources**; see [Settings](#settings).

## Settings

Preferences open with `Ctrl+,` and are divided into eight tabs: **General**, **Playback**, **Accessibility**, **Library**, **Download**, **KeyTube**, **Online radio** and **Additional resources**.

### General

**Restore session on startup**, **Remember window size**, **Remember last used folder** and **Confirm on exit** do what the name says. **Use the quick player when opening files from Windows** comes checked and decides whether an audio file opened from File Explorer plays in the small window or in the main window (see [Listening to a file straight from Windows File Explorer](#listening-to-a-file-straight-from-windows-file-explorer)).

The **File association** section (Windows) has the **Register as default player** button, which adds KeyTune to the *Open with* menu for audio, video and playlist formats. After registering, set the app as the default in the Windows settings if you want those files to open directly in it. **Unregister associations** undoes the registration.

The **Log recording** section helps investigate problems. **Record diagnostic logs** writes a log file, in English, to the data folder, useful to attach to a bug report. **Detail level** goes from *Errors only*, the quietest, to *Debug*, which produces large files. **Open log folder** takes you to them.

### Playback

- **Crossfade (seconds)**: the audio overlap between tracks on the automatic change (0 to 12 s). Use 0 to turn it off. Only applies between audio files.
- **Apply crossfade when changing track manually**: with the option on, the crossfade also applies when you skip forward or back with the controls; by default, only at the natural end of the track. When an AutoDJ transition is ready, skipping forward uses that plan even with the option off.
- **Audio device**: the sound output. *System default* follows the main Windows device.
- **Disable video output (play audio only)**: plays only the audio, including from video files. Avoids external video windows.
- **Show the video of live broadcasts**: shows the picture of YouTube broadcasts in the player area even with video output disabled for the rest of the app. Unchecked, the broadcast plays only the audio. `Ctrl+Alt+V` toggles it during a broadcast.

The **default volume**, the **volume** and **seek** steps (how much each arrow changes), the **default repeat** and **shuffle** for new playlists complete the tab and also do what the name says.

With AutoDJ installed, there are two more options: **AutoDJ profile** (*Smooth* makes a long, balanced mix; *Party* concentrates the bass swap in the middle and raises the energy gradually; *Electronic* uses sharper cuts and a faster swap, designed for strong beats) and **AutoDJ transition length** (8, 16 or 32 beats, independent of the regular crossfade).

### Accessibility

It has a single option: **Enable accessibility announcements**. When on, the player announces changes of time, volume, tab switching and status to the screen reader. When off, those announcements stop. The on-demand announcement shortcuts (`T`, `V` and `S`) work either way. See [Accessibility features](#accessibility-features).

### Library

Controls the [smart library](#smart-library). Turning off **Enable the smart library** deactivates the whole feature and disables the other options.

- **Automatically index folders opened in the browser**: when you open a folder, its media goes into the index in the background.
- **Keep a local playback history** and **Plays kept in the history** (50 to 20000): over the limit, the oldest drop out.
- **Remember the position of long media**, **Minimum duration to remember the position** (1 to 240 minutes) and **Margin ignored at the start and at the end** (5 to 300 seconds): see [Resume where you stopped](#resume-where-you-stopped).
- **Entries kept in the cache** (100 to 100000): how many metadata items and audio analyses are kept.

### Download

Sets the defaults for `Ctrl+Shift+B`:

- **Default download type**: **Audio** or **Video**.
- **Audio quality**: **Original (no conversion)** keeps the audio as YouTube delivers it; **MP3** (128, 192, 256 or 320 kbps) and **FLAC (lossless)** convert the audio and require FFmpeg.
- **Audio sample rate**: **Original**, 44100 Hz or 48000 Hz. Only applies when the audio is converted. YouTube delivers 44.1 or 48 kHz, so higher rates would bring no quality gain.
- **Video quality**: **Best available** or a maximum height from 2160p to 144p. If the chosen height doesn't exist, the video is downloaded in the best quality available.
- **Download folder**: where the files are saved. The default is **Downloads\KeyTune**, in your user folder.
- **Always show the dialog when downloading**: on (the default), each download opens the confirmation dialog; off, the download starts right away with the options from this tab.

### KeyTube

Gathers the YouTube and YouTube Music options. They only take effect with the integration turned on in **Additional resources**.

**Library**

- **Playlists loaded at a time**: how many playlists from the library come with each load (5 to 200). Smaller values open faster; at the end of the list, the player offers to load more.
- **Custom mixes to discover**: the maximum number of items scanned on the YouTube Music home to find personalized mixes (5 to 200). Smaller values make syncing faster.

**Playback**

- **Play related tracks at the end of the playlist**: when the last YouTube Music track ends, or when you ask for the next one while on the last, the player fetches related tracks (the YouTube Music radio) and keeps playing, with no pause between one and the next. The `A` key turns it on and off during playback. Tracks that are already in the playlist don't come in again.
- **Save what I listened to in the YouTube Music history**: on by default. When you listen to a track long enough (about 30% of the duration, between 15 and 30 seconds), the player marks it as watched in your account's history. Turn it off to play without recording anything.

**Language and region**

- **Content language**: the language requested from YouTube in searches and in the texts it returns (counts, dates). The default is **Same as KeyTune**. It applies to YouTube searches with YouTube.js turned on; YouTube Music searches use only the region.
- **Content region**: the country used in YouTube and YouTube Music searches. With **Automatic**, YouTube decides from your connection.
- **Audio of dubbed videos**: some videos come with the original audio and dubs. Here you choose what plays: **Whatever YouTube delivers** (the default), **The video's original** or the dub in a language. Videos without the requested track play normally. A track that isn't the default goes through yt-dlp and takes a few seconds longer to start.

### Online radio

- **My country**: the country that opens the home of the **Online radio** tab and that appears as a search option. With **Automatic (follow the system)**, the country set in Windows applies. A country that isn't on the list can be set in the tab itself, in the country's actions menu.

### Additional resources

Gathers the optional YouTube and AutoDJ integrations and libraries. Before the first download, KeyTune shows a dialog with all the components that will be installed.

**YouTube components**

- **Enable the YouTube and YouTube Music integration**: downloads and keeps the `yt-dlp` executable, the necessary Python packages and, if there isn't a compatible one, a portable Node.js for the EJS resolver. Without this, KeyTube doesn't work. The first time, the download may take a few minutes and requires internet. When you turn it off, the files already downloaded stay in place.
- **Update the components automatically**: checks for and applies updates at the interval set below. Only available with the integration turned on.
- **Use the nightly version of yt-dlp (recommended)**: downloads `yt-dlp` nightly builds. YouTube changes its extraction mechanisms often, and the nightly usually gets fixes before the stable channel.
- **Use YouTube.js (recommended)**: improves resolution and playback. Installs YouTube.js and uses the same Node.js 24 or higher prepared for `yt-dlp`, which stays as a fallback. The package is part of the periodic update check.
- **Update interval (hours)**: how often the player tries to update the dependencies when KeyTube is opened (1 to 720 h). Only available with automatic update turned on.

**AutoDJ**

- **Download resources and enable AutoDJ**: downloads `librosa`, NumPy, SciPy, Numba and PyAV separately; they don't come in the installer. When you turn it off, the downloaded files stay in place.
- **Play DJ effects during transitions**, **AutoDJ profile** and **AutoDJ transition length** become available with AutoDJ turned on.

## Accessibility features

KeyTune was designed for screen readers and for keyboard-only use:

- focus avoids unnecessary jumps to the native video area;
- states and navigation are announced when accessibility support is available;
- fields, buttons, lists and groups have names and descriptions readable by screen readers.

If you use a screen reader, `T`, `V` and `S` (see [Playback shortcuts](#playback-shortcuts)) and the quick help `F1` help you find your bearings without depending on the automatic announcements. Those announcements, such as track change, tab change and volume change, can be turned on or off in `Ctrl+,` > **Accessibility**.

Favorites and ratings are spoken together with the item, and details, comments and plugin permissions appear in reading fields with a label. The screen reader also announces the name of the group when focus enters it.

## Updates

On startup, KeyTune can check for updates on its own. To check at any time, use **Help > Check for updates**.

When there is a new version, the app shows the release notes, the file name and the download size before asking for confirmation. If you accept, it downloads the package, shows the progress and asks for permission to install when the file is ready.

## Troubleshooting

**The app doesn't open properly.** Check that the installation finished without errors (reinstalling with the latest installer fixes most cases) and that the system has permission to access the files or folders you tried to open.

**The player can't find the MPV runtime.** Check that it is in one of these places: an `mpv/` folder next to the executable, `MPV_HOME`, `MPV_DLL_DIR`, the cache saved from the previous run or a compatible Chocolatey installation.

**File association doesn't work as expected.** There are two separate steps. First, KeyTune must be registered as an option (during installation, or later in **Settings > Preferences > General > Register as default player**). Second, it must be chosen as the default app for those formats in the Windows default apps settings. Registering alone doesn't make KeyTune the default.

**KeyTube doesn't load or shows dependency errors.** Open `Ctrl+,` > **Additional resources** and confirm that **Enable the YouTube and YouTube Music integration** is checked. The initial download may take a few minutes and requires internet. If the dependencies are already installed but the search or loading fails, use the nightly version of `yt-dlp`, in the same preferences: it usually gets fixes before the stable channel.

**A conversion failed.** Confirm that the file opens normally in the player and that the destination folder accepts writing. FFmpeg's message is shown and announced; corrupted files or files in unusual formats may not be converted.

**A download or a live broadcast doesn't work.** Confirm that **Additional resources** are turned on and up to date (`yt-dlp` changes often to keep up with YouTube). For a download, also confirm that the folder exists and accepts writing. Error 429 indicates a temporary YouTube block for too many requests: wait a few minutes and try again.

**An online radio station doesn't play or the list doesn't open.** The Radio Browser directory and the stations themselves are sometimes offline. Try another station from the list, or go back to the list and open it again.

**The YouTube session expired, or the player asks for authentication again.** Export the browser's cookies as described in [Connect your account](#connect-your-account) and reconnect.

**Other problems.** Turn on log recording in `Ctrl+,` > **General** > **Log recording**. With **Record diagnostic logs** on and the level set to *Debug*, the player writes detailed information to `keytune.log`, in the data folder. **Open log folder** takes you to the file. If you report the problem, attach the log to the issue.

## Plugins and marketplace

Open **Settings > Manage plugins...** to install a `.ktplugin` file or choose **Open marketplace**. Select a plugin, check the author, version, source, permissions and isolation and confirm with **Install and enable**. The manager also enables, disables and uninstalls plugins.

The actions plugins add are in **Settings > Plugin actions**. Plugins can also offer tabs and screens. Install only code from authors you trust: running in a separate process is not a security sandbox. The verification badge indicates a provenance review, not a security guarantee.

The [development and API 2.0 guide](plugins.en.md) covers the manifest, permissions, methods, events and publishing. It ships with the player and can be read offline; external links require internet.

## For developers

KeyTune is an open-source project. The repository, issues, pull requests and releases are at [github.com/ed-fe/KeyTune](https://github.com/ed-fe/KeyTune). The source of this manual is at [docs/manual.en.md](https://github.com/ed-fe/KeyTune/blob/main/docs/manual.en.md).

To run the project from source, install the dependencies with `uv sync` and open the player with `uv run keytune`. The writing rules for the manual, changelog and commits are in `.github/instructions/writing.instructions.md`.
