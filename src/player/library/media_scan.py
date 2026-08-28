import os

from ..constants import AUDIO_ONLY_EXTENSIONS, SUPPORTED_MEDIA_EXTENSIONS
from ..folder_sort import (
    FOLDER_SORT_CREATED,
    FOLDER_SORT_MODIFIED,
    FOLDER_SORT_NAME,
    FOLDER_SORT_OPTIONS,
    FOLDER_SORT_SIZE,
    FOLDER_SORT_TYPE,
)
from .models import (
    FOLDER_ENTRY_DIRECTORY,
    FOLDER_ENTRY_FILE,
    FOLDER_ENTRY_PARENT,
    FolderBrowserEntry,
)


def is_youtube_music_media(filename):
    from ..youtube_music.playlists import is_youtube_music_media as classifier

    return classifier(filename)


def is_supported_media(filename):
    return os.path.splitext(filename)[1].lower() in SUPPORTED_MEDIA_EXTENSIONS


def is_audio_only_media(filename):
    return os.path.splitext(str(filename or ""))[1].lower() in AUDIO_ONLY_EXTENSIONS


def is_audio_playback_media(filename):
    return is_audio_only_media(filename) or is_youtube_music_media(filename)


def folder_display_name(folder_path):
    normalized_path = os.path.abspath(os.path.normpath(str(folder_path or "")))
    if not normalized_path:
        return "Pasta"

    folder_name = os.path.basename(normalized_path.rstrip("\\/"))
    return folder_name or normalized_path


def _folder_entry_sort_key(entry, sort_by):
    name_key = str(getattr(entry, "label", "") or "").lower()
    if sort_by == FOLDER_SORT_MODIFIED:
        return (getattr(entry, "modified_time", 0.0), name_key)
    if sort_by == FOLDER_SORT_CREATED:
        return (getattr(entry, "created_time", 0.0), name_key)
    if sort_by == FOLDER_SORT_TYPE:
        return (getattr(entry, "extension", ""), name_key)
    if sort_by == FOLDER_SORT_SIZE:
        return (getattr(entry, "size", 0), name_key)
    return (name_key,)


def sort_folder_entries(entries, sort_by=FOLDER_SORT_NAME, descending=False):
    """Sort folder entries while keeping the parent entry and type groups stable."""
    normalized_sort = sort_by if sort_by in FOLDER_SORT_OPTIONS else FOLDER_SORT_NAME
    parent_entries = [entry for entry in entries if getattr(entry, "is_parent", False)]
    directories = [
        entry
        for entry in entries
        if getattr(entry, "is_directory", False) and not getattr(entry, "is_parent", False)
    ]
    files = [entry for entry in entries if getattr(entry, "is_file", False)]
    key = lambda entry: _folder_entry_sort_key(entry, normalized_sort)
    return parent_entries + sorted(directories, key=key, reverse=bool(descending)) + sorted(
        files,
        key=key,
        reverse=bool(descending),
    )


def _entry_metadata(entry, *, is_file):
    try:
        stat_result = entry.stat(follow_symlinks=False)
    except OSError:
        return 0.0, 0.0, 0

    created_time = getattr(stat_result, "st_birthtime", stat_result.st_ctime)
    return stat_result.st_mtime, created_time, stat_result.st_size if is_file else 0


def scan_folder_contents(folder_path, *, sort_by=FOLDER_SORT_NAME, descending=False):
    normalized_folder_path = os.path.abspath(os.path.normpath(folder_path))
    entries = []

    parent_path = os.path.dirname(normalized_folder_path)
    if parent_path and parent_path != normalized_folder_path:
        entries.append(
            FolderBrowserEntry(
                path=parent_path,
                label="[..] Pasta acima",
                entry_type=FOLDER_ENTRY_PARENT,
            )
        )

    directories = []
    files = []
    media_files = []

    with os.scandir(normalized_folder_path) as folder_entries:
        scanned_entries = list(folder_entries)

    for entry in scanned_entries:
        if entry.is_dir(follow_symlinks=False):
            modified_time, created_time, size = _entry_metadata(entry, is_file=False)
            directories.append(
                FolderBrowserEntry(
                    path=entry.path,
                    label=entry.name,
                    entry_type=FOLDER_ENTRY_DIRECTORY,
                    modified_time=modified_time,
                    created_time=created_time,
                    size=size,
                )
            )
            continue

        if entry.is_file(follow_symlinks=False) and is_supported_media(entry.name):
            modified_time, created_time, size = _entry_metadata(entry, is_file=True)
            files.append(
                FolderBrowserEntry(
                    path=entry.path,
                    label=entry.name,
                    entry_type=FOLDER_ENTRY_FILE,
                    modified_time=modified_time,
                    created_time=created_time,
                    size=size,
                    extension=os.path.splitext(entry.name)[1].lstrip(".").casefold(),
                )
            )
            media_files.append(entry.path)

    entries.extend(directories)
    entries.extend(files)
    entries = sort_folder_entries(entries, sort_by=sort_by, descending=descending)
    media_files = [entry.path for entry in entries if entry.is_file]
    return entries, media_files


def discover_media_files(folder_path):
    _entries, media_files = scan_folder_contents(folder_path)
    return media_files


def discover_folder_entries(folder_path, *, sort_by=FOLDER_SORT_NAME, descending=False):
    entries, _media_files = scan_folder_contents(folder_path, sort_by=sort_by, descending=descending)
    return entries
