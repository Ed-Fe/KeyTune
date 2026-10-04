"""Cliente do Radio Browser (https://www.radio-browser.info), o diretório comunitário de rádios.

A API é pública e sem chave. O projeto pede só duas coisas a quem a usa: um
User-Agent que identifique o aplicativo e que os servidores sejam descobertos em
tempo de execução, porque os espelhos mudam.
"""

import json
import random
import threading
import urllib.error
import urllib.parse
import urllib.request

from ..constants import APP_TITLE, APP_VERSION
from ..log import get_logger

_logger = get_logger(__name__)

SERVER_DISCOVERY_URL = "https://all.api.radio-browser.info/json/servers"
# Usados quando a descoberta falha; o primeiro atende pelo nome que reúne todos os espelhos.
FALLBACK_SERVERS = (
    "all.api.radio-browser.info",
    "de1.api.radio-browser.info",
    "fi1.api.radio-browser.info",
    "de2.api.radio-browser.info",
)
_REQUEST_TIMEOUT_SECONDS = 12
_USER_AGENT = f"{APP_TITLE}/{APP_VERSION} (https://github.com/Ed-Fe)"


class RadioBrowserError(Exception):
    """O diretório não respondeu ou respondeu algo que não dá para ler."""


def _fetch_json(url):
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=_REQUEST_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


class RadioBrowserClient:
    def __init__(self, fetch_json=_fetch_json):
        self._fetch_json = fetch_json
        self._servers = []
        self._lock = threading.Lock()

    def _discover_servers(self):
        names = []
        try:
            payload = self._fetch_json(SERVER_DISCOVERY_URL)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            _logger.debug("Radio Browser server discovery failed: %s", exc)
            payload = None
        for entry in payload if isinstance(payload, list) else ():
            name = str(entry.get("name") or "").strip() if isinstance(entry, dict) else ""
            if name and name not in names:
                names.append(name)
        # O projeto pede que cada cliente sorteie o espelho, para dividir a carga.
        random.shuffle(names)
        return names + [name for name in FALLBACK_SERVERS if name not in names]

    def _server_candidates(self):
        with self._lock:
            if not self._servers:
                self._servers = self._discover_servers()
            return list(self._servers)

    def _demote_server(self, server):
        with self._lock:
            if server in self._servers and len(self._servers) > 1:
                self._servers.remove(server)
                self._servers.append(server)

    def _get(self, path, params=None):
        query = urllib.parse.urlencode({key: value for key, value in (params or {}).items() if value not in (None, "")})
        last_error = None
        for server in self._server_candidates():
            url = f"https://{server}/json/{path}"
            if query:
                url = f"{url}?{query}"
            try:
                return self._fetch_json(url)
            except (urllib.error.URLError, OSError, ValueError) as exc:
                _logger.debug("Radio Browser request to %s failed: %s", server, exc)
                last_error = exc
                self._demote_server(server)
        raise RadioBrowserError(str(last_error or "")) from last_error

    def _get_list(self, path, params=None):
        payload = self._get(path, params)
        return [entry for entry in payload if isinstance(entry, dict)] if isinstance(payload, list) else []

    def search_stations(
        self,
        *,
        name="",
        country_code="",
        state="",
        tag="",
        language="",
        order="clickcount",
        reverse=True,
        offset=0,
        limit=50,
    ):
        return self._get_list(
            "stations/search",
            {
                "name": name,
                "countrycode": country_code,
                "state": state,
                "tag": tag,
                "tagExact": "true" if tag else "",
                "language": language,
                "languageExact": "true" if language else "",
                "order": order,
                "reverse": "true" if reverse else "false",
                "offset": max(0, int(offset)),
                "limit": max(1, int(limit)),
                "hidebroken": "true",
            },
        )

    def _list_groups(self, path, *, order, reverse, offset, limit):
        return self._get_list(
            path,
            {
                "order": order,
                "reverse": "true" if reverse else "false",
                "offset": max(0, int(offset)),
                "limit": max(1, int(limit)),
                "hidebroken": "true",
            },
        )

    def countries(self, *, offset=0, limit=500):
        return self._list_groups("countries", order="name", reverse=False, offset=offset, limit=limit)

    def states(self, country_name, *, offset=0, limit=500):
        path = f"states/{urllib.parse.quote(str(country_name or '').strip(), safe='')}/"
        return self._list_groups(path, order="name", reverse=False, offset=offset, limit=limit)

    def tags(self, *, offset=0, limit=50):
        return self._list_groups("tags", order="stationcount", reverse=True, offset=offset, limit=limit)

    def languages(self, *, offset=0, limit=50):
        return self._list_groups("languages", order="stationcount", reverse=True, offset=offset, limit=limit)

    def count_click(self, station_uuid):
        """Avisa o diretório de que a estação foi ouvida; é o que ordena as mais ouvidas."""
        return self._get(f"url/{urllib.parse.quote(str(station_uuid or '').strip(), safe='')}")

    def vote(self, station_uuid):
        payload = self._get(f"vote/{urllib.parse.quote(str(station_uuid or '').strip(), safe='')}")
        if not isinstance(payload, dict):
            return False, ""
        return str(payload.get("ok")).strip().lower() == "true", str(payload.get("message") or "").strip()
