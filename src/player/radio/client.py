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


def _request_headers():
    return {"Accept": "application/json", "User-Agent": _USER_AGENT}


def _fetch_json(url):
    request = urllib.request.Request(url, headers=_request_headers())
    with urllib.request.urlopen(request, timeout=_REQUEST_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_form(url, fields):
    headers = _request_headers()
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(fields).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=_REQUEST_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def _directory_result(payload):
    """``(aceito, mensagem, uuid)``. ``ok`` ausente ou falso, em texto ou booleano, é recusa."""
    if not isinstance(payload, dict):
        return False, "", ""
    accepted = str(payload.get("ok")).strip().lower() == "true"
    message = str(payload.get("message") or "").strip()
    station_uuid = str(payload.get("uuid") or "").strip()
    return accepted, message, station_uuid


class RadioBrowserClient:
    def __init__(self, fetch_json=_fetch_json, post_form=None):
        self._fetch_json = fetch_json
        self._post_form = post_form or _post_form
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
        accepted, message, _station_uuid = _directory_result(payload)
        return accepted, message

    def stations_by_url(self, url):
        """Estações cujo endereço de stream é exatamente *url*.

        Uma resposta que não seja uma lista volta como veio. Tratar isso como
        lista vazia faria o cadastro seguir mesmo com a consulta ilegível.
        """
        return self._get("stations/byurl", {"url": str(url or "").strip()})

    def add_station(self, *, name, url, homepage="", favicon="", countrycode="", languagecodes="", tags=""):
        """Publica a estação com um único POST.

        O espelho é escolhido antes, pela descoberta que as buscas já usam. Se o
        envio falhar, não há segunda tentativa: um tempo esgotado pode ter gravado
        a estação, e repetir noutro espelho criaria uma duplicata.
        """
        fields = {
            "name": name,
            "url": url,
            "homepage": homepage,
            "favicon": favicon,
            "countrycode": countrycode,
            "languagecodes": languagecodes,
            "tags": tags,
        }
        payload = {key: str(value).strip() for key, value in fields.items() if str(value or "").strip()}
        servers = self._server_candidates()
        if not servers:
            raise RadioBrowserError("no radio browser server")
        server = servers[0]
        post_url = f"https://{server}/json/add"
        try:
            response = self._post_form(post_url, payload)
        except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:
            _logger.debug("Radio Browser add to %s failed: %s", server, exc)
            raise RadioBrowserError(str(exc)) from exc
        return _directory_result(response)
