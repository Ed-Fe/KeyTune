## [Unreleased]

### Added

- **Load the whole list**: in the **Actions...** menu of the YouTube tab, brings what is missing from the list all at once, without going down to the end several times. In a playlist, every track comes. In a search or a channel, which have no known end, up to 1000 items come at a time.

### Changed

- **Items loaded at a time**: the **Playlists loaded at a time** option, in **Preferences > KeyTube**, was renamed and now applies to every list of the tab: library playlists, search results, playlist tracks and comments. Before, those other lists always came 20 at a time.
- **Long playlists load faster**: when going down a YouTube Music playlist, KeyTune reuses the tracks it had already fetched. Before, each new part asked for the whole playlist again.
- **YouTube playlist without a limit**: opening or downloading a regular YouTube playlist brings every video. Before, it stopped at 200.

### Fixed

- **Complete liked songs**: the **Liked songs** list on the YouTube Music home shows every track the account has liked. Before, it stopped at the first few hundred, while the same playlist opened from **Your playlists and mixes** came in full. It now loads a part at a time: go down to the end of the list to bring more.
