import os
from urllib.parse import parse_qs, urlparse

from ..i18n import _


_YOUTUBE_HOSTS = {"music.youtube.com", "www.youtube.com", "youtube.com", "m.youtube.com"}


def is_youtube_watch_reference(value):
    normalized_value = str(value or "").strip()
    if not normalized_value:
        return False
    if normalized_value.casefold().startswith("watch?v="):
        return True

    parsed_value = urlparse(normalized_value)
    host = str(parsed_value.hostname or "").casefold().rstrip(".")
    return (
        host in _YOUTUBE_HOSTS
        and str(parsed_value.path or "").rstrip("/").casefold() == "/watch"
        and bool(parse_qs(parsed_value.query).get("v"))
    )


def default_playlist_title(number):
    return _("Playlist {number}").format(number=number)


def build_playlist_title(items, explicit_title=None):
    if explicit_title:
        if is_youtube_watch_reference(explicit_title):
            return _("Seleção do YouTube Music")
        return explicit_title

    normalized_items = list(items)
    if not normalized_items:
        return default_playlist_title(1)

    if len(normalized_items) == 1:
        item = str(normalized_items[0]).strip()
        if is_youtube_watch_reference(item):
            return _("Seleção do YouTube Music")
        basename = os.path.basename(item)
        return os.path.splitext(basename)[0]

    parent_directories = {os.path.dirname(path) for path in normalized_items}
    if len(parent_directories) == 1:
        folder_name = os.path.basename(parent_directories.pop())
        if folder_name:
            return f"{folder_name} ({len(normalized_items)})"

    return _("Seleção ({count})").format(count=len(normalized_items))


def build_folder_tab_title(folder_path):
    normalized_path = os.path.abspath(os.path.normpath(str(folder_path or "")))
    folder_name = os.path.basename(normalized_path.rstrip("\\/")) or normalized_path
    return f"Pasta: {folder_name}"
