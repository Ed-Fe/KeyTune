## [Unreleased]

### Added

- **Diagnostics** (**Help > Diagnostics**): tests what KeyTune needs to play and shows, in a reading box, what is wrong and what to do in each case.
  - It checks the MPV library and its Windows dependencies, starting the player, the audio devices, `yt-dlp`, Node.js, YouTube.js, FFmpeg, the YouTube account and, by resolving a real public video, whether YouTube answers YouTube.js and `yt-dlp`.
  - If the player does not start when KeyTune opens, the diagnostics run by themselves and show the reason before the app closes. Before, the window stayed open without working.
  - It only reads and tests; it does not install or change anything on the computer.
  - The video test uses the internet and does not send the account cookies.

### Fixed

- **KeyTune could not start MPV on computers with an old video driver**: the window showed "ctypes.CDLL could not load it" and nothing played. The Vulkan loader that ships with drivers from 2016 or older lacks functions the current MPV needs, and Windows refused to load the library.
  - KeyTune now carries its own `vulkan-1.dll` in the `mpv` folder and uses the installed video drivers as before.
  - If MPV fails to load for another reason, the diagnostics name the missing DLL or function, or says that Windows or the antivirus blocked the file.
- **Good YouTube Music cookies were refused when connecting**: on some accounts the connection failed with "does not contain a compatible YouTube Music authentication cookie" or with an error about `__Secure-3PAPISID`, even with a correct export.
  - A cookie with a space, an accented letter or another non-standard character hid every cookie after it, including the authentication one. It is now set aside and the rest is read.
  - You can paste only the value of the `Cookie` header, a `cookies.txt` whose tabs became spaces when copied, or the headers without `X-Goog-AuthUser`.
  - If YouTube confirms the session is signed in but the account menu comes in a format KeyTune does not recognise, the account is accepted anyway, without the name.
  - When the browser has already replaced the cookies, the message says so and explains how to export again.
- **With the YouTube account connected, MPV could not create a new player**: after KeyTune talked to the account, any player created afterwards failed with "access violation". This affected switching to a video after another media and recreating the player. The account library changed a regional setting of the process that MPV requires; KeyTune now restores it before creating each player.
