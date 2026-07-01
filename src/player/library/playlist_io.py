import os
from urllib import error, parse, request

from ..constants import UPDATE_HTTP_TIMEOUT_SECONDS
from ..i18n import _


REMOTE_PREFIXES = (
    "http://",
    "https://",
    "rtsp://",
    "mms://",
    "ftp://",
    "file://",
)
REMOTE_PLAYLIST_PREFIXES = (
    "http://",
    "https://",
    "ftp://",
    "file://",
)
PLAYLIST_EXTENSIONS = (".m3u", ".m3u8")


def is_remote_media_path(path):
    normalized = str(path).strip().lower()
    return normalized.startswith(REMOTE_PREFIXES)


def is_playlist_source(source):
    normalized_source = str(source or "").strip()
    if not normalized_source:
        return False

    if normalized_source.lower().startswith(REMOTE_PLAYLIST_PREFIXES):
        source_path = parse.urlparse(normalized_source).path
    else:
        source_path = normalized_source

    return os.path.splitext(source_path)[1].lower() in PLAYLIST_EXTENSIONS


def playlist_display_name(file_path):
    normalized_source = str(file_path or "").strip()
    if not normalized_source:
        return "Playlist"

    if normalized_source.lower().startswith(REMOTE_PLAYLIST_PREFIXES):
        source_path = parse.unquote(parse.urlparse(normalized_source).path)
        display_name = os.path.splitext(os.path.basename(source_path.rstrip("/")))[0]
        if display_name:
            return display_name

        parsed_url = parse.urlparse(normalized_source)
        if parsed_url.netloc:
            return parsed_url.netloc

    return os.path.splitext(os.path.basename(normalized_source))[0]


def _resolve_playlist_entry(base_dir, entry, base_url=None):
    if is_remote_media_path(entry):
        return entry

    if base_url:
        return parse.urljoin(base_url, entry)

    normalized_entry = os.path.expandvars(entry)
    if not os.path.isabs(normalized_entry):
        normalized_entry = os.path.normpath(os.path.join(base_dir, normalized_entry))
    else:
        normalized_entry = os.path.normpath(normalized_entry)

    if os.path.exists(normalized_entry):
        return normalized_entry
    return None


def load_playlist(file_path):
    normalized_source = str(file_path or "").strip()
    if normalized_source.lower().startswith(REMOTE_PLAYLIST_PREFIXES):
        base_dir = ""
        base_url = normalized_source
        candidates = _download_playlist_lines(normalized_source)
    else:
        base_path = os.path.abspath(os.path.normpath(normalized_source))
        base_dir = os.path.dirname(base_path)
        base_url = None
        candidates = _read_local_playlist_lines(base_path)

    items = []
    for raw_line in candidates:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        resolved = _resolve_playlist_entry(base_dir, line, base_url=base_url)
        if resolved:
            items.append(resolved)

    return items


def _read_local_playlist_lines(file_path):
    candidates = []
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            with open(file_path, "r", encoding=encoding) as playlist_file:
                candidates = playlist_file.readlines()
            return candidates
        except UnicodeDecodeError:
            continue

    return candidates


def _download_playlist_lines(url):
    request_headers = {
        "Accept": "audio/x-mpegurl, application/vnd.apple.mpegurl, text/plain, */*",
    }
    playlist_request = request.Request(url, headers=request_headers)
    try:
        with request.urlopen(playlist_request, timeout=UPDATE_HTTP_TIMEOUT_SECONDS) as response:
            payload = response.read()
    except (OSError, ValueError, error.URLError) as exc:
        raise OSError(_("Não foi possível abrir a playlist remota: {error}.").format(error=exc)) from exc

    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return payload.decode(encoding).splitlines()
        except UnicodeDecodeError:
            continue

    return payload.decode("latin-1").splitlines()


def save_playlist(file_path, items):
    base_dir = os.path.dirname(file_path)
    lines = ["#EXTM3U"]

    for item in items:
        if is_remote_media_path(item):
            lines.append(item)
            continue

        normalized_item = os.path.abspath(item)
        try:
            stored_entry = os.path.relpath(normalized_item, base_dir)
        except ValueError:
            stored_entry = normalized_item

        lines.append(stored_entry)

    with open(file_path, "w", encoding="utf-8") as playlist_file:
        playlist_file.write("\n".join(lines) + "\n")
