## [Unreleased]

### Fixed

- **Connecting the YouTube account right after opening KeyTune**: connecting with a `cookies.txt` or with pasted cookies failed with "does not contain a compatible YouTube Music authentication cookie", even with a correct export. It happened to anyone who connected the account before using anything from YouTube, such as right after installing. The account now connects in that situation too.
- **Cookies without `LOGIN_INFO`**: anyone who copied the cookies from the browser console, or used an exporter that leaves out protected cookies, was told they had expired. The message now says `LOGIN_INFO` is missing and asks you to export all youtube.com cookies to a `cookies.txt`. If the account connects even without it, KeyTune warns that tracks that require the account may not play.
