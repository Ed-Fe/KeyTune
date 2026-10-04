"""Como uma rádio online aparece numa playlist.

O item é o endereço do stream com um fragmento que o marca como rádio e leva o
identificador da estação: ``https://servidor/stream#keytune-radio=<uuid>``. A
marca viaja junto com o item (sessão restaurada, playlist salva), então dá para
reconhecer a rádio sem guardar nada à parte. O fragmento nunca vai ao servidor:
ele é retirado antes de o endereço chegar ao player.
"""

RADIO_FRAGMENT_KEY = "keytune-radio"
_RADIO_FRAGMENT_PREFIX = f"#{RADIO_FRAGMENT_KEY}="
_STREAM_PREFIXES = ("http://", "https://", "mms://", "rtsp://", "rtmp://")


def is_stream_url(value):
    return str(value or "").strip().lower().startswith(_STREAM_PREFIXES)


def build_radio_media_path(stream_url, station_uuid=""):
    normalized_url = str(stream_url or "").strip().split("#", 1)[0]
    if not is_stream_url(normalized_url):
        return ""
    return f"{normalized_url}{_RADIO_FRAGMENT_PREFIX}{str(station_uuid or '').strip()}"


def is_radio_media(media_path):
    normalized_path = str(media_path or "").strip()
    return _RADIO_FRAGMENT_PREFIX in normalized_path.lower() and is_stream_url(normalized_path)


def radio_stream_url(media_path):
    """O endereço que o player abre: o item sem a marca de rádio."""
    return str(media_path or "").strip().split("#", 1)[0]


def radio_station_uuid(media_path):
    normalized_path = str(media_path or "").strip()
    marker_position = normalized_path.lower().find(_RADIO_FRAGMENT_PREFIX)
    if marker_position < 0:
        return ""
    return normalized_path[marker_position + len(_RADIO_FRAGMENT_PREFIX):].strip()
