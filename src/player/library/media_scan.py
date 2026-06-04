import os

from ..constants import AUDIO_ONLY_EXTENSIONS, SUPPORTED_MEDIA_EXTENSIONS
from .models import FOLDER_ENTRY_DIRECTORY, FOLDER_ENTRY_FILE, FOLDER_ENTRY_PARENT, FolderBrowserEntry


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


def scan_folder_contents(folder_path):
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
        sorted_entries = sorted(folder_entries, key=lambda entry: entry.name.lower())

    for entry in sorted_entries:
        if entry.is_dir(follow_symlinks=False):
            directories.append(
                FolderBrowserEntry(
                    path=entry.path,
                    label=entry.name,
                    entry_type=FOLDER_ENTRY_DIRECTORY,
                )
            )
            continue

        if entry.is_file(follow_symlinks=False) and is_supported_media(entry.name):
            files.append(
                FolderBrowserEntry(
                    path=entry.path,
                    label=entry.name,
                    entry_type=FOLDER_ENTRY_FILE,
                )
            )
            media_files.append(entry.path)

    entries.extend(directories)
    entries.extend(files)
    return entries, media_files


def discover_media_files(folder_path):
    _entries, media_files = scan_folder_contents(folder_path)
    return media_files


def discover_folder_entries(folder_path):
    entries, _media_files = scan_folder_contents(folder_path)
    return entries
