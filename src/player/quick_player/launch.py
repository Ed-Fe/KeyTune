"""Decide o que o player rápido toca e com que volume; sem wxPython."""

import os

from ..constants import AUDIO_ONLY_EXTENSIONS, DEFAULT_VOLUME, VIDEO_EXTENSIONS


def quick_player_paths(paths, settings):
    """Devolve os arquivos que o player rápido toca, ou ``[]`` se o pedido é do KeyTune completo.

    Só arquivos soltos entram: playlists, pastas, links e, com a saída de vídeo
    ligada, os vídeos precisam da janela principal.
    """
    if not getattr(settings, "quick_player_enabled", True):
        return []

    playable_extensions = set(AUDIO_ONLY_EXTENSIONS)
    if getattr(settings, "disable_video_output", True):
        playable_extensions |= VIDEO_EXTENSIONS

    media_paths = []
    for path in paths or ():
        normalized_path = str(path or "").strip().strip('"')
        if not normalized_path:
            continue
        normalized_path = os.path.abspath(normalized_path)
        if os.path.splitext(normalized_path)[1].lower() not in playable_extensions:
            return []
        if not os.path.isfile(normalized_path):
            return []
        media_paths.append(normalized_path)
    return media_paths


def initial_volume(settings, session_payload):
    """Volume ao abrir: o da última sessão quando ela é restaurada, senão o padrão."""
    default_volume = getattr(settings, "default_volume", DEFAULT_VOLUME)
    if not getattr(settings, "restore_session_on_startup", False) or not isinstance(session_payload, dict):
        return default_volume
    try:
        saved_volume = int(session_payload.get("volume", default_volume))
    except (TypeError, ValueError):
        return default_volume
    return max(0, min(100, saved_volume))


def format_time_ms(milliseconds):
    total_seconds = max(0, int(milliseconds or 0)) // 1000
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02}:{seconds:02}"
    return f"{minutes}:{seconds:02}"
