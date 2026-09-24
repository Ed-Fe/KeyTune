"""Live-stream helpers for YouTube: status detection and format selection.

Everything here is a pure function over the info JSON that yt-dlp returns, with
no network and no wxPython, so it can be unit-tested with fixtures.
``streams.py`` wires these helpers into the stream resolver.
"""

from __future__ import annotations

from ..i18n import _


# Live video is capped so a long broadcast does not eat the connection; audio
# mode picks the cheapest variant that still carries sound.
LIVE_VIDEO_MAX_HEIGHT = 720

LIVE_STATUS_LIVE = "is_live"
LIVE_STATUS_UPCOMING = "is_upcoming"

# yt-dlp reports a scheduled broadcast as an error when ``ignore_no_formats_error``
# is off; these are the English fragments it uses.
_UPCOMING_MESSAGE_MARKERS = (
    "live event will begin",
    "premieres in",
    "premiere will begin",
)


class LiveNotStartedError(RuntimeError):
    """The broadcast is scheduled but has not started yet."""

    def __init__(self, message=""):
        super().__init__(message or _("Esta transmissão ao vivo ainda não começou."))


def live_status_from_info(info) -> str:
    """Return yt-dlp's ``live_status`` for *info*, falling back to ``is_live``."""
    if not isinstance(info, dict):
        return ""
    status = str(info.get("live_status") or "").strip().lower()
    if status:
        return status
    return LIVE_STATUS_LIVE if info.get("is_live") else ""


def is_live_info(info) -> bool:
    return live_status_from_info(info) == LIVE_STATUS_LIVE


def is_upcoming_info(info) -> bool:
    return live_status_from_info(info) == LIVE_STATUS_UPCOMING


def is_live_not_started_message(message) -> bool:
    normalized_message = " ".join(str(message or "").split()).casefold()
    return any(marker in normalized_message for marker in _UPCOMING_MESSAGE_MARKERS)


def live_display_title_from_info(info) -> str:
    """Return the broadcast title without the timestamp yt-dlp may append."""
    if not isinstance(info, dict):
        return ""
    for key in ("fulltitle", "title", "alt_title"):
        normalized_title = str(info.get(key) or "").strip()
        if normalized_title:
            return normalized_title
    return ""


def select_live_format(formats, *, prefer_video, max_height=LIVE_VIDEO_MAX_HEIGHT):
    """Pick the format to play for a live broadcast.

    *formats* are candidates that already carry a ``_stream_url``. HLS is
    preferred because MPV handles it well for live. With *prefer_video* the best
    muxed format up to *max_height* wins; otherwise the lightest format that has
    audio does. Returns ``None`` when nothing playable is left.
    """
    playable = [fmt for fmt in formats if _is_playable(fmt)]
    pool = [fmt for fmt in playable if _is_hls(fmt)] or playable
    audible = [fmt for fmt in pool if _has_audio(fmt)]
    if not audible:
        return None

    if prefer_video:
        with_video = [fmt for fmt in audible if _has_video(fmt)]
        if with_video:
            within_limit = [fmt for fmt in with_video if 0 < _number(fmt.get("height")) <= max_height]
            if within_limit:
                return max(within_limit, key=_quality_key)
            return min(with_video, key=_quality_key)

    audio_only = [fmt for fmt in audible if not _has_video(fmt)]
    if audio_only:
        return max(audio_only, key=_audio_quality_key)
    return min(audible, key=_quality_key)


def _codec(fmt, key) -> str:
    return str(fmt.get(key) or "").strip().lower()


def _number(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _is_playable(fmt) -> bool:
    if str(fmt.get("protocol") or "").strip().lower() == "mhtml":
        return False
    return not (_codec(fmt, "vcodec") == "none" and _codec(fmt, "acodec") == "none")


def _is_hls(fmt) -> bool:
    return str(fmt.get("protocol") or "").strip().lower().startswith("m3u8")


def _has_audio(fmt) -> bool:
    return _codec(fmt, "acodec") != "none"


def _has_video(fmt) -> bool:
    return _codec(fmt, "vcodec") not in {"", "none"} or _number(fmt.get("height")) > 0


def _quality_key(fmt):
    return (_number(fmt.get("height")), _number(fmt.get("tbr")))


def _audio_quality_key(fmt):
    return (_number(fmt.get("abr")) or _number(fmt.get("tbr")),)
