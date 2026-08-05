import os
from urllib.parse import urlparse


def is_music_youtube_url(media_path):
    from ...youtube_music.playlists import is_music_youtube_url as classifier

    return classifier(media_path)


def is_youtube_music_media(media_path):
    from ...youtube_music.playlists import is_youtube_music_media as classifier

    return classifier(media_path)


_STREAM_ARTIFACT_TITLE_SUFFIXES = (
    ".m3u8",
    ".mpd",
    ".m4s",
    ".ts",
    ".mp4",
    ".m4a",
    ".webm",
    ".aac",
    ".mp3",
)


def _normalize_runtime_title_token(value):
    normalized_value = str(value or "").strip()
    if not normalized_value:
        return ""
    parsed_value = urlparse(normalized_value)
    if parsed_value.scheme and parsed_value.netloc:
        normalized_value = parsed_value.path or normalized_value
    normalized_value = normalized_value.rstrip("\\/")
    return os.path.basename(normalized_value) or normalized_value


def _looks_like_stream_artifact_title(title):
    normalized_title = _normalize_runtime_title_token(title).casefold()
    if not normalized_title:
        return False
    return normalized_title.endswith(_STREAM_ARTIFACT_TITLE_SUFFIXES)


def _default_remote_media_label(media_path):
    normalized_path = str(media_path or "").strip().rstrip("\\/")
    if not normalized_path:
        return ""
    media_name = os.path.basename(normalized_path)
    if media_name.casefold().startswith("watch?v="):
        return _("Mídia do YouTube Music")
    return media_name or normalized_path


def _should_apply_runtime_stream_title(media_path, current_label, runtime_title):
    normalized_runtime_title = str(runtime_title or "").strip()
    if not normalized_runtime_title:
        return False

    normalized_current_label = str(current_label or "").strip()
    default_label = _default_remote_media_label(media_path)
    if not normalized_current_label or normalized_current_label == default_label:
        return True

    if _looks_like_stream_artifact_title(normalized_runtime_title):
        return False

    return False
