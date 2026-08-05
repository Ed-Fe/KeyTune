import os

from ..i18n import _


def default_playlist_title(number):
    return _("Playlist {number}").format(number=number)


def build_playlist_title(items, explicit_title=None):
    if explicit_title:
        title_str = str(explicit_title).strip()
        if title_str.casefold().startswith("watch?v=") or "music.youtube.com/watch" in title_str.casefold() or "youtube.com/watch" in title_str.casefold():
            return _("Seleção do YouTube Music")
        return explicit_title

    normalized_items = list(items)
    if not normalized_items:
        return default_playlist_title(1)

    if len(normalized_items) == 1:
        item = str(normalized_items[0]).strip()
        if "watch?v=" in item.casefold() or "music.youtube.com" in item.casefold() or "youtube.com" in item.casefold():
            return _("Seleção do YouTube Music")
        basename = os.path.basename(item)
        if basename.casefold().startswith("watch?v="):
            return _("Seleção do YouTube Music")
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
