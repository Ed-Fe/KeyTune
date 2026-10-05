"""Acesso à tabela `radio_stations`: os dados das rádios online conhecidas.

A rádio em si é uma mídia como outra qualquer (favorito, avaliação e histórico
moram na linha dela em `media`); aqui fica só o que o diretório informa sobre a
estação — país, gêneros, site, qualidade —, guardado como veio, em JSON. A
linha some junto com a mídia.
"""

import json
import time

from .models import media_path_key


DEFAULT_RADIO_STATION_LIMIT = 500

_STATION_QUERY = (
    "SELECT radio_stations.details AS details "
    "FROM radio_stations JOIN media ON media.id = radio_stations.media_id "
)


def _read_details(rows):
    stations = []
    for row in rows:
        try:
            details = json.loads(row["details"])
        except (TypeError, ValueError):
            continue
        if isinstance(details, dict):
            stations.append(details)
    return stations


class RadioStationTable:
    def __init__(self, database, record_store):
        self._database = database
        self._records = record_store

    def save(self, media_path, label, details):
        """Guarda (ou atualiza) os dados da estação e devolve True se gravou."""
        media_id = self._records.media_id_for_path(media_path)
        if media_id is None:
            media_id = self._records.register(media_path, label=label)
        if media_id is None:
            return False

        cursor = self._database.execute(
            """
            INSERT INTO radio_stations (media_id, details, updated_epoch)
            VALUES (?, ?, ?)
            ON CONFLICT(media_id) DO UPDATE SET
                details = excluded.details,
                updated_epoch = excluded.updated_epoch
            """,
            (media_id, json.dumps(details, ensure_ascii=False), int(time.time())),
        )
        return cursor is not None

    def get(self, media_path):
        stations = _read_details(
            self._database.query(_STATION_QUERY + "WHERE media.path_key = ?", (media_path_key(media_path),))
        )
        return stations[0] if stations else None

    def favorites(self, limit=DEFAULT_RADIO_STATION_LIMIT):
        return _read_details(
            self._database.query(
                _STATION_QUERY + "WHERE media.favorite = 1 ORDER BY media.label COLLATE NOCASE LIMIT ?",
                (max(1, int(limit)),),
            )
        )

    def recently_played(self, limit=DEFAULT_RADIO_STATION_LIMIT):
        return _read_details(
            self._database.query(
                _STATION_QUERY
                + "WHERE media.last_played_epoch > 0 ORDER BY media.last_played_epoch DESC LIMIT ?",
                (max(1, int(limit)),),
            )
        )
