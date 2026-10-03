from ..constants import PLAYLIST_WILDCARD, SUPPORTED_MEDIA_EXTENSIONS
from ..i18n import _


def build_supported_media_wildcard(include_playlists=False):
    media_pattern = ";".join(f"*{extension}" for extension in sorted(SUPPORTED_MEDIA_EXTENSIONS))
    if not include_playlists:
        return _("Mídia suportada") + "|" + media_pattern + "|" + _("Todos os arquivos") + "|*.*"

    return (
        _("Playlists e mídias suportadas")
        + "|*.m3u;*.m3u8;"
        + media_pattern
        + "|"
        + PLAYLIST_WILDCARD
        + "|"
        + _("Mídia suportada")
        + "|"
        + media_pattern
        + "|"
        + _("Todos os arquivos")
        + "|*.*"
    )
