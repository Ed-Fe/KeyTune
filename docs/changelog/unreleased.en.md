## [Unreleased]

### Added

- **Full-screen video**: `Alt+Enter`, or **View > Full-screen video**, leaves only the video, filling the screen. `Alt+Enter` or `Esc` go back. The video-output-off notice and the player area's help text now show in large print and wrap instead of being cut off.
- **SponsorBlock**: KeyTune skips the segments the SponsorBlock community marked in YouTube videos, such as sponsorships, subscribe requests and non-music parts of music videos, and says what it skipped. Segments marked to be muted are only silenced while they last. It is off by default. To turn it on, use **Preferences > KeyTube > SponsorBlock**, where you also pick the categories and whether KeyTube skips on its own or only tells you. **Playback > SponsorBlock** lets you skip the announced segment (`Ctrl+J`) and go back to the last skipped one (`Ctrl+Shift+J`).
- **Help SponsorBlock** (optional): with the option on, you mark the start (`Ctrl+[`) and end (`Ctrl+]`) of a segment and submit it, vote on whether the last segment is right (`Ctrl+U`) or wrong (`Ctrl+Shift+U`), and skips are counted for the authors. Lookups don't reveal to SponsorBlock which video is playing.

### Changed

- **Video**: the **Show the video of live broadcasts** option is gone. Live broadcasts now follow **Disable video output**, like the rest of the app, and `Ctrl+Alt+V` turns video output on or off for everything.
