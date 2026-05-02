import json
import os
import re
import stat
import tempfile
import time
from dataclasses import dataclass
from http.cookies import SimpleCookie

from player.session import APP_STORAGE_DIR


YTMUSIC_BROWSER_AUTH_FILE_NAME = "ytmusic_browser.json"
YTMUSIC_BROWSER_AUTH_COOKIE_FILE_NAME = "ytmusic_cookies.txt"
_REDACTED_VALUE = "[oculto]"


@dataclass(slots=True)
class YouTubeMusicPlaybackAuth:
    cookie_header: str = ""
    user_agent: str = ""
    cookie_file_path: str = ""

    @property
    def yt_dlp_http_headers(self):
        headers = {}
        if self.user_agent:
            headers["User-Agent"] = self.user_agent
        return headers

    @property
    def playback_http_headers(self):
        headers = {}
        if self.cookie_header:
            headers["Cookie"] = self.cookie_header
        if self.user_agent:
            headers["User-Agent"] = self.user_agent
        return headers


def sanitize_sensitive_text(raw_text, *, max_length=400):
    message = str(raw_text or "").strip()
    if not message:
        return ""

    sanitized_message = re.sub(r"(?i)(cookie\s*:)\s*[^\r\n]+", rf"\1 {_REDACTED_VALUE}", message)
    sanitized_message = re.sub(
        r"(?i)(set-cookie\s*:)\s*[^\r\n]+",
        rf"\1 {_REDACTED_VALUE}",
        sanitized_message,
    )
    sanitized_message = re.sub(
        r"(?i)(authorization\s*:)\s*[^\r\n]+",
        rf"\1 {_REDACTED_VALUE}",
        sanitized_message,
    )
    sanitized_message = re.sub(
        r"(?i)(\b(?:Bearer|SAPISIDHASH)\s+)[A-Za-z0-9._\-:+/=]+",
        rf"\1{_REDACTED_VALUE}",
        sanitized_message,
    )
    sanitized_message = re.sub(
        r"(?i)(\b(?:__Secure-3PAPISID|__Secure-1PAPISID|SAPISID|APISID|SID|HSID|SSID|LOGIN_INFO)\s*=)\s*[^;\s,]+",
        rf"\1{_REDACTED_VALUE}",
        sanitized_message,
    )
    sanitized_message = re.sub(
        r"(?i)([?&](?:token|po_token|sig|signature|lsig|spc|x-goog-visitor-id)=)[^&\s]+",
        rf"\1{_REDACTED_VALUE}",
        sanitized_message,
    )

    if len(sanitized_message) > max_length:
        return sanitized_message[:max_length].rstrip() + "..."
    return sanitized_message


def harden_sensitive_file_permissions(file_path):
    normalized_file_path = os.path.abspath(os.path.normpath(str(file_path or "").strip()))
    if not normalized_file_path or not os.path.isfile(normalized_file_path):
        return False

    try:
        if os.name == "nt":
            os.chmod(normalized_file_path, stat.S_IREAD | stat.S_IWRITE)
        else:
            os.chmod(normalized_file_path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        return False

    return True


def get_browser_auth_file_path():
    return os.path.join(_get_storage_dir(), YTMUSIC_BROWSER_AUTH_FILE_NAME)


def get_browser_auth_cookie_file_path():
    return os.path.join(_get_storage_dir(), YTMUSIC_BROWSER_AUTH_COOKIE_FILE_NAME)


def _get_storage_dir():
    if os.name == "nt":
        base_dir = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base_dir = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")

    storage_dir = os.path.join(base_dir, APP_STORAGE_DIR)
    os.makedirs(storage_dir, exist_ok=True)
    return storage_dir


def read_auth_file_text(file_path):
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            with open(file_path, "r", encoding=encoding) as auth_file:
                return auth_file.read()
        except UnicodeDecodeError:
            continue

    raise RuntimeError("Não foi possível ler o arquivo de autenticação selecionado.")


def prepare_browser_auth_input(raw_input, *, source_name="entrada"):
    normalized_input = str(raw_input or "").strip()
    if not normalized_input:
        return ""

    json_payload = _try_parse_json(normalized_input)
    if json_payload is not None:
        browser_headers = _extract_browser_auth_headers(json_payload)
        if browser_headers:
            return _headers_dict_to_raw(browser_headers)

        cookie_header = _cookie_header_from_json_payload(json_payload)
        if cookie_header:
            return _build_headers_raw_from_cookie(cookie_header)

        raise RuntimeError(
            f"O {source_name} não contém um browser.json válido nem um export JSON de cookies compatível."
        )

    cookie_header = _cookie_header_from_netscape_text(normalized_input)
    if cookie_header:
        return _build_headers_raw_from_cookie(cookie_header)

    return normalized_input


def write_browser_auth_cookie_file(raw_input, file_path, *, source_name="entrada", fallback_headers_raw=""):
    cookie_file_content = build_browser_auth_cookie_file_content(raw_input, source_name=source_name)
    if not cookie_file_content and fallback_headers_raw:
        cookie_file_content = build_browser_auth_cookie_file_content(fallback_headers_raw, source_name=source_name)

    normalized_file_path = os.path.abspath(os.path.normpath(str(file_path or "").strip()))
    if not normalized_file_path:
        return ""

    if not cookie_file_content:
        try:
            os.remove(normalized_file_path)
        except FileNotFoundError:
            pass
        return ""

    os.makedirs(os.path.dirname(normalized_file_path), exist_ok=True)
    newline = "\r\n" if os.name == "nt" else "\n"
    normalized_content = cookie_file_content.replace("\r\n", "\n").replace("\r", "\n")
    normalized_content = normalized_content.replace("\n", newline)
    with open(normalized_file_path, "w", encoding="utf-8", newline="") as cookie_file:
        cookie_file.write(normalized_content)

    harden_sensitive_file_permissions(normalized_file_path)

    return normalized_file_path


def create_temporary_browser_auth_cookie_file(cookie_header):
    cookie_file_content = _netscape_cookie_file_from_cookie_header(cookie_header)
    if not cookie_file_content:
        return ""

    newline = "\r\n" if os.name == "nt" else "\n"
    normalized_content = cookie_file_content.replace("\r\n", "\n").replace("\r", "\n")
    normalized_content = normalized_content.replace("\n", newline)

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        prefix="ytmusic_cookies_",
        suffix=".txt",
        delete=False,
    ) as temp_cookie_file:
        temp_cookie_file.write(normalized_content)
        temp_cookie_file_path = temp_cookie_file.name

    harden_sensitive_file_permissions(temp_cookie_file_path)
    return temp_cookie_file_path


def build_browser_auth_cookie_file_content(raw_input, *, source_name="entrada"):
    normalized_input = str(raw_input or "").strip()
    if not normalized_input:
        return ""

    json_payload = _try_parse_json(normalized_input)
    if json_payload is not None:
        cookie_entries = _cookie_entries_from_json_payload(json_payload)
        if cookie_entries:
            return _netscape_cookie_file_from_entries(cookie_entries)

        browser_headers = _extract_browser_auth_headers(json_payload)
        if browser_headers:
            return _netscape_cookie_file_from_cookie_header(_get_header_value(browser_headers, "cookie"))

        return ""

    normalized_netscape_text = _normalize_netscape_cookie_text(normalized_input)
    if normalized_netscape_text:
        return normalized_netscape_text

    headers = _headers_from_raw_text(normalized_input)
    cookie_header = _get_header_value(headers, "cookie")
    if cookie_header:
        return _netscape_cookie_file_from_cookie_header(cookie_header)

    return ""


def load_saved_playback_auth(auth_file_path=None, *, cookie_file_path=None, persist_cookie_file=False):
    normalized_auth_file_path = os.path.abspath(
        os.path.normpath(str(auth_file_path or get_browser_auth_file_path()).strip())
    )
    if not normalized_auth_file_path or not os.path.isfile(normalized_auth_file_path):
        return YouTubeMusicPlaybackAuth()

    raw_auth_text = read_auth_file_text(normalized_auth_file_path)
    json_payload = _try_parse_json(raw_auth_text)
    if json_payload is not None:
        headers = _extract_browser_auth_headers(json_payload) or {}
    else:
        headers = _headers_from_raw_text(raw_auth_text)

    cookie_header = _get_header_value(headers, "cookie")
    user_agent = _get_header_value(headers, "user-agent")

    should_persist_cookie_file = cookie_file_path is not None or bool(persist_cookie_file)
    normalized_cookie_file_path = ""
    if should_persist_cookie_file:
        normalized_cookie_file_path = os.path.abspath(
            os.path.normpath(str(cookie_file_path or get_browser_auth_cookie_file_path()).strip())
        )

    saved_cookie_file_path = ""
    if cookie_header and normalized_cookie_file_path:
        if _is_valid_browser_auth_cookie_file(normalized_cookie_file_path):
            saved_cookie_file_path = normalized_cookie_file_path
        else:
            saved_cookie_file_path = write_browser_auth_cookie_file(
                raw_auth_text,
                normalized_cookie_file_path,
                source_name=os.path.basename(normalized_auth_file_path),
                fallback_headers_raw=_headers_dict_to_raw(headers),
            )

    return YouTubeMusicPlaybackAuth(
        cookie_header=cookie_header,
        user_agent=user_agent,
        cookie_file_path=saved_cookie_file_path,
    )


def _is_valid_browser_auth_cookie_file(file_path):
    normalized_file_path = os.path.abspath(os.path.normpath(str(file_path or "").strip()))
    if not normalized_file_path or not os.path.isfile(normalized_file_path):
        return False

    try:
        raw_cookie_text = read_auth_file_text(normalized_file_path)
    except Exception:
        return False

    return bool(_normalize_netscape_cookie_text(raw_cookie_text))


def _try_parse_json(raw_text):
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return None


def _headers_from_raw_text(raw_text):
    normalized_headers = {}
    remembered_key = ""
    for raw_line in str(raw_text or "").splitlines():
        line = str(raw_line or "")
        if not line.strip():
            continue

        header = line.split(": ", 1)
        if header[0].startswith(":"):
            continue
        if header[0].endswith(":"):
            remembered_key = header[0].rstrip(":")
            continue
        if len(header) == 1:
            if remembered_key:
                normalized_headers[remembered_key] = header[0].strip()
            continue

        normalized_headers[header[0].strip()] = str(header[1] or "").strip()

    return normalized_headers


def _get_header_value(headers, header_name):
    normalized_header_name = str(header_name or "").strip().lower()
    for key, value in (headers or {}).items():
        if str(key or "").strip().lower() != normalized_header_name:
            continue
        return str(value or "").strip()
    return ""


def _extract_browser_auth_headers(payload):
    candidate = payload
    if isinstance(payload, dict) and isinstance(payload.get("headers"), dict):
        candidate = payload.get("headers")

    if not isinstance(candidate, dict):
        return None

    normalized_headers = {}
    for key, value in candidate.items():
        if not isinstance(key, str) or isinstance(value, (dict, list)):
            continue

        normalized_value = str(value).strip()
        if not normalized_value:
            continue
        normalized_headers[key] = normalized_value

    lowered_keys = {str(key).lower() for key in normalized_headers.keys()}
    if "cookie" not in lowered_keys:
        return None

    if "x-goog-authuser" not in lowered_keys:
        normalized_headers["X-Goog-AuthUser"] = "0"
    if "x-origin" not in lowered_keys:
        normalized_headers["x-origin"] = "https://music.youtube.com"

    return normalized_headers


def _cookie_header_from_json_payload(payload):
    cookie_entries = _cookie_entries_from_json_payload(payload)
    if not cookie_entries:
        return ""

    cookie_pairs = []
    seen_names = set()
    for cookie in cookie_entries:
        name = str(cookie.get("name") or "").strip()
        value = str(cookie.get("value") or "").strip()
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        cookie_pairs.append(f"{name}={value}")

    return "; ".join(cookie_pairs)


def _cookie_entries_from_json_payload(payload):
    cookie_entries = []
    _collect_cookie_entries(payload, cookie_entries)
    if not cookie_entries:
        return []

    filtered_cookie_entries = []
    seen_names = set()
    for cookie in cookie_entries:
        name = str(cookie.get("name") or "").strip()
        value = str(cookie.get("value") or "").strip()
        if not name or not value or name in seen_names:
            continue
        if not _cookie_entry_matches_music_youtube(cookie):
            continue
        if _cookie_entry_is_expired(cookie):
            continue
        seen_names.add(name)
        filtered_cookie_entries.append(cookie)

    return filtered_cookie_entries


def _collect_cookie_entries(node, cookie_entries):
    if isinstance(node, dict):
        if _looks_like_cookie_entry(node):
            cookie_entries.append(node)
            return
        for value in node.values():
            _collect_cookie_entries(value, cookie_entries)
        return

    if isinstance(node, list):
        for item in node:
            _collect_cookie_entries(item, cookie_entries)


def _looks_like_cookie_entry(value):
    return isinstance(value, dict) and "name" in value and "value" in value


def _cookie_entry_matches_music_youtube(cookie):
    domain = str(cookie.get("domain") or cookie.get("host") or "").strip().lstrip(".").lower()
    if not domain:
        return True
    return domain.endswith("youtube.com") or domain.endswith("music.youtube.com")


def _cookie_entry_is_expired(cookie):
    expiration_value = cookie.get("expirationDate")
    if expiration_value in (None, "", 0, "0"):
        return False

    try:
        return float(expiration_value) <= time.time()
    except (TypeError, ValueError):
        return False


def _cookie_header_from_netscape_text(raw_text):
    cookie_pairs = []
    seen_names = set()

    for raw_line in str(raw_text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = raw_line.split("\t")
        if len(parts) < 7:
            continue

        domain, _include_subdomains, _path, _secure, expiry, name, value = parts[:7]
        normalized_domain = str(domain or "").strip().lstrip(".").lower()
        normalized_name = str(name or "").strip()
        normalized_value = str(value or "").strip()
        if not normalized_name or not normalized_value:
            continue
        if normalized_name in seen_names:
            continue
        if normalized_domain and not (
            normalized_domain.endswith("youtube.com") or normalized_domain.endswith("music.youtube.com")
        ):
            continue

        try:
            if expiry and expiry != "0" and float(expiry) <= time.time():
                continue
        except ValueError:
            pass

        seen_names.add(normalized_name)
        cookie_pairs.append(f"{normalized_name}={normalized_value}")

    return "; ".join(cookie_pairs)


def _looks_like_netscape_cookie_text(raw_text):
    normalized_text = str(raw_text or "")
    if normalized_text.lstrip().startswith("# HTTP Cookie File"):
        return True
    if normalized_text.lstrip().startswith("# Netscape HTTP Cookie File"):
        return True

    for raw_line in normalized_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if len(raw_line.split("\t")) >= 7:
            return True

    return False


def _normalize_netscape_cookie_text(raw_text):
    if not _looks_like_netscape_cookie_text(raw_text):
        return ""

    normalized_lines = ["# Netscape HTTP Cookie File"]
    for raw_line in str(raw_text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = raw_line.split("\t")
        if len(parts) < 7:
            continue

        domain, include_subdomains, path, secure, expiry, name, value = parts[:7]
        normalized_domain = str(domain or "").strip()
        if normalized_domain and not _cookie_entry_matches_music_youtube({"domain": normalized_domain}):
            continue
        if _cookie_entry_is_expired({"expirationDate": expiry}):
            continue

        normalized_name = str(name or "").strip()
        normalized_value = str(value or "").strip()
        if not normalized_name or not normalized_value:
            continue

        normalized_lines.append(
            "\t".join(
                [
                    normalized_domain or ".youtube.com",
                    "TRUE" if str(include_subdomains or "").strip().upper() == "TRUE" or normalized_domain.startswith(".") else "FALSE",
                    str(path or "/").strip() or "/",
                    "TRUE" if str(secure or "").strip().upper() == "TRUE" else "FALSE",
                    _normalize_cookie_expiry(expiry),
                    normalized_name,
                    normalized_value,
                ]
            )
        )

    if len(normalized_lines) == 1:
        return ""
    return "\n".join(normalized_lines) + "\n"


def _netscape_cookie_file_from_cookie_header(cookie_header):
    cookie = SimpleCookie()
    try:
        cookie.load(str(cookie_header or "").replace('"', ""))
    except Exception:
        return ""

    normalized_lines = ["# Netscape HTTP Cookie File"]
    for morsel in cookie.values():
        normalized_name = str(morsel.key or "").strip()
        normalized_value = str(morsel.value or "").strip()
        if not normalized_name or not normalized_value:
            continue
        normalized_lines.append(
            "\t".join([
                ".youtube.com",
                "TRUE",
                "/",
                "TRUE",
                "0",
                normalized_name,
                normalized_value,
            ])
        )

    if len(normalized_lines) == 1:
        return ""
    return "\n".join(normalized_lines) + "\n"


def _netscape_cookie_file_from_entries(cookie_entries):
    normalized_lines = ["# Netscape HTTP Cookie File"]
    for cookie in cookie_entries or []:
        normalized_name = str(cookie.get("name") or "").strip()
        normalized_value = str(cookie.get("value") or "").strip()
        if not normalized_name or not normalized_value:
            continue

        normalized_domain = str(cookie.get("domain") or cookie.get("host") or ".youtube.com").strip()
        normalized_path = str(cookie.get("path") or "/").strip() or "/"
        secure = cookie.get("secure")
        host_only = cookie.get("hostOnly")
        include_subdomains = not bool(host_only) if host_only is not None else normalized_domain.startswith(".")

        normalized_lines.append(
            "\t".join(
                [
                    normalized_domain or ".youtube.com",
                    "TRUE" if include_subdomains else "FALSE",
                    normalized_path,
                    "TRUE" if bool(secure) else "FALSE",
                    _normalize_cookie_expiry(cookie.get("expirationDate")),
                    normalized_name,
                    normalized_value,
                ]
            )
        )

    if len(normalized_lines) == 1:
        return ""
    return "\n".join(normalized_lines) + "\n"


def _normalize_cookie_expiry(expiry_value):
    if expiry_value in (None, "", 0, "0"):
        return "0"

    try:
        return str(int(float(expiry_value)))
    except (TypeError, ValueError):
        return "0"


def _build_headers_raw_from_cookie(cookie_header):
    normalized_cookie_header = str(cookie_header or "").strip()
    if not normalized_cookie_header:
        return ""

    origin = "https://music.youtube.com"
    authorization = _authorization_from_cookie(normalized_cookie_header, origin)
    if not authorization:
        raise RuntimeError(
            "O export de cookies não contém um cookie de autenticação compatível do YouTube Music. "
            "Faça login em music.youtube.com e exporte novamente os cookies da sessão ativa."
        )

    return "\n".join(
        [
            "Accept: */*",
            f"Authorization: {authorization}",
            "Content-Type: application/json",
            f"Cookie: {normalized_cookie_header}",
            "X-Goog-AuthUser: 0",
            f"x-origin: {origin}",
        ]
    )


def _headers_dict_to_raw(headers):
    header_lines = []
    for key, value in headers.items():
        normalized_key = str(key or "").strip()
        normalized_value = str(value or "").strip()
        if not normalized_key or not normalized_value:
            continue
        header_lines.append(f"{normalized_key}: {normalized_value}")

    return "\n".join(header_lines)


def _authorization_from_cookie(cookie_header, origin):
    cookie = SimpleCookie()
    try:
        cookie.load(str(cookie_header or "").replace('"', ""))
    except Exception:
        return ""

    sapisid = ""
    for cookie_name in ("__Secure-3PAPISID", "SAPISID", "__Secure-1PAPISID"):
        morsel = cookie.get(cookie_name)
        if morsel is not None:
            sapisid = str(morsel.value or "").strip()
            if sapisid:
                break

    if not sapisid:
        return ""

    try:
        from ytmusicapi.helpers import get_authorization
    except ImportError:
        return ""

    return get_authorization(f"{sapisid} {origin}")
