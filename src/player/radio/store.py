"""Rádios favoritas e ouvidas recentemente, guardadas na biblioteca do KeyTune.

A rádio é uma mídia da biblioteca como as outras: o favorito é o mesmo do
Ctrl+D da playlist e "ouvidas recentemente" sai do histórico de reprodução.
Aqui fica só a ponte entre as estações e o banco da biblioteca, que pode não
estar disponível (preferência desligada, banco que não abriu).
"""

from .models import RadioStation

RECENT_STATIONS_LIMIT = 30


class RadioLibraryStore:
    def __init__(self, library_provider):
        # Uma função, e não o serviço: a janela liga e desliga a biblioteca em uso.
        self._library_provider = library_provider

    def _library(self):
        return self._library_provider() if callable(self._library_provider) else None

    @staticmethod
    def _read_stations(raw_stations):
        stations = (RadioStation.from_dict(raw_station) for raw_station in raw_stations)
        return [station for station in stations if station is not None]

    def favorites(self):
        library = self._library()
        return self._read_stations(library.favorite_radio_stations()) if library is not None else []

    def recents(self):
        library = self._library()
        if library is None:
            return []
        return self._read_stations(library.recent_radio_stations(limit=RECENT_STATIONS_LIMIT))

    def favorite_keys(self):
        return {station.key for station in self.favorites()}

    def is_favorite(self, station):
        library = self._library()
        return bool(library is not None and library.is_favorite(station.media_path))

    def remember(self, station):
        """Guarda os dados da estação, para ela ser reconhecida nas listas e ao tocar."""
        library = self._library()
        if library is None:
            return False
        return bool(library.save_radio_station(station.media_path, station.name, station.to_dict()))

    def toggle_favorite(self, station):
        """Devolve o novo estado do favorito, ou ``None`` quando não deu para gravar."""
        library = self._library()
        if library is None or not self.remember(station):
            return None
        return library.toggle_favorite(station.media_path, label=station.name)

    def find(self, media_path):
        library = self._library()
        if library is None:
            return None
        return RadioStation.from_dict(library.radio_station(media_path))
