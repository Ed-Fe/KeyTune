"""Fachada das rádios online: o diretório, as favoritas e as recentes.

As consultas ao diretório bloqueiam e rodam fora da thread da interface; as
favoritas e as recentes moram na biblioteca do KeyTune e são lidas e gravadas
na thread da interface.
"""

import threading

from .client import RadioBrowserClient, RadioBrowserError
from .media import build_radio_media_path, is_radio_media, radio_station_uuid, radio_stream_url
from .models import RadioResultPage, RadioStation

_GROUP_LIST_LIMIT = 500


class RadioService:
    def __init__(self, store, client=None):
        self._client = client or RadioBrowserClient()
        self._store = store
        # Estações vistas nesta sessão, para reconhecer a que está tocando.
        self._known_stations = {}
        self._country_names = {}
        self._lock = threading.Lock()

    def _stations_page(self, count, **search):
        raw_stations = self._client.search_stations(limit=count, **search)
        stations = []
        seen_keys = set()
        for raw_station in raw_stations:
            station = RadioStation.from_api(raw_station)
            if station is None or station.key in seen_keys:
                continue
            seen_keys.add(station.key)
            stations.append(station)
        with self._lock:
            for station in stations:
                self._known_stations[station.key] = station
        return RadioResultPage(results=stations, has_more=len(raw_stations) >= count)

    def fetch_search_page(self, query, *, country_code="", start=0, count=50):
        return self._stations_page(count, name=str(query or "").strip(), country_code=country_code, offset=start)

    def fetch_top_page(self, *, country_code="", start=0, count=50):
        return self._stations_page(count, country_code=country_code, offset=start)

    def fetch_country_page(self, country_code, *, start=0, count=50):
        """Todas as rádios do país, em ordem alfabética."""
        return self._stations_page(count, country_code=country_code, order="name", reverse=False, offset=start)

    def fetch_state_page(self, country_code, state, *, start=0, count=50):
        return self._stations_page(count, country_code=country_code, state=state, offset=start)

    def fetch_tag_page(self, tag, *, start=0, count=50):
        return self._stations_page(count, tag=tag, offset=start)

    def fetch_language_page(self, language, *, start=0, count=50):
        return self._stations_page(count, language=language, offset=start)

    def list_countries(self):
        countries = self._client.countries(limit=_GROUP_LIST_LIMIT)
        with self._lock:
            for country in countries:
                country_code = str(country.get("iso_3166_1") or "").strip().upper()
                if country_code:
                    self._country_names[country_code] = str(country.get("name") or "").strip()
        return countries

    def _country_name(self, country_code):
        """Nome do país como o diretório o escreve; é por ele que os estados são pedidos."""
        normalized_code = str(country_code or "").strip().upper()
        with self._lock:
            known_name = self._country_names.get(normalized_code)
        if known_name is None:
            self.list_countries()
            with self._lock:
                known_name = self._country_names.get(normalized_code, "")
        return known_name

    def list_states(self, country_code):
        country_name = self._country_name(country_code)
        if not country_name:
            return []
        return self._client.states(country_name, limit=_GROUP_LIST_LIMIT)

    def list_tags(self, *, start=0, count=50):
        return self._client.tags(offset=start, limit=count)

    def list_languages(self, *, start=0, count=50):
        return self._client.languages(offset=start, limit=count)

    def favorites(self):
        return self._store.favorites()

    def recents(self):
        return self._store.recents()

    def favorite_keys(self):
        return self._store.favorite_keys()

    def is_favorite(self, station):
        return self._store.is_favorite(station)

    def toggle_favorite(self, station):
        """Devolve o novo estado do favorito, ou ``None`` sem a biblioteca disponível."""
        return self._store.toggle_favorite(station)

    def set_favorite(self, station, favorite):
        """Marca (ou desmarca) direto, sem alternar o estado atual. Devolve se deu certo."""
        return self._store.set_favorite(station, favorite)

    def remember(self, station):
        """Guarda os dados da estação na biblioteca, onde o favorito e o histórico a acham."""
        return self._store.remember(station)

    def station_for_media_path(self, media_path, fallback_name=""):
        """A estação de um item de playlist; sem registro dela, uma só com nome e stream."""
        if not is_radio_media(media_path):
            return None
        stream_url = radio_stream_url(media_path)
        station_uuid = radio_station_uuid(media_path)
        station_key = station_uuid or stream_url.casefold()
        with self._lock:
            station = self._known_stations.get(station_key)
        if station is None:
            station = self._store.find(media_path)
        if station is not None:
            return station
        return RadioStation(
            name=str(fallback_name or "").strip() or stream_url,
            stream_url=stream_url,
            station_uuid=station_uuid,
        )

    @staticmethod
    def custom_station(stream_url):
        """Uma rádio que não está no diretório: o endereço do stream colado pelo usuário."""
        normalized_url = radio_stream_url(stream_url)
        if not build_radio_media_path(normalized_url):
            return None
        return RadioStation(name=normalized_url, stream_url=normalized_url)

    @staticmethod
    def build_manual_station(name, stream_url):
        """Uma rádio digitada à mão (nome e endereço); ``None`` com o endereço inválido."""
        normalized_url = radio_stream_url(stream_url)
        if not build_radio_media_path(normalized_url):
            return None
        station_name = str(name or "").strip() or normalized_url
        return RadioStation(name=station_name, stream_url=normalized_url)

    def count_click(self, station):
        if not station.station_uuid:
            return
        try:
            self._client.count_click(station.station_uuid)
        except RadioBrowserError:
            pass

    def vote(self, station):
        """Devolve ``(aceito, mensagem do diretório)``."""
        if not station.station_uuid:
            return False, ""
        return self._client.vote(station.station_uuid)
