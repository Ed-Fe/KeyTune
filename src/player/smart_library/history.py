"""Histórico local de reprodução.

Cada entrada registra uma reprodução: qual mídia, quando, em que ponto parou e
de onde veio (playlist local, pasta, YouTube Music). O histórico é aparado a um
limite configurável para não crescer sem fim.
"""

import time

from .models import HistoryEntry, HistorySummary, media_path_key


DEFAULT_HISTORY_LIMIT = 500

# Modos de visualização oferecidos pela caixa do histórico.
HISTORY_VIEW_ALL = "all"
HISTORY_VIEW_GROUPED = "grouped"
HISTORY_VIEW_MOST_PLAYED = "most_played"
HISTORY_VIEWS = (HISTORY_VIEW_ALL, HISTORY_VIEW_GROUPED, HISTORY_VIEW_MOST_PLAYED)

SOURCE_LOCAL = "local"
SOURCE_FOLDER = "folder"
SOURCE_REMOTE = "remote"
SOURCE_YOUTUBE_MUSIC = "youtube_music"


_HISTORY_COLUMNS = (
    "history.id AS id, media.media_path AS media_path, media.label AS label, "
    "history.played_epoch AS played_epoch, history.position_ms AS position_ms, "
    "history.duration_ms AS duration_ms, history.source AS source, "
    "media.favorite AS favorite, media.rating AS rating"
)


class HistoryStore:
    def __init__(self, database, record_store):
        self._database = database
        self._records = record_store

    def record(self, media_path, *, label="", position_ms=0, duration_ms=0, source="", limit=DEFAULT_HISTORY_LIMIT):
        """Registra uma reprodução e devolve True se a entrada foi criada."""
        media_id = self._records.register(media_path, label=label, duration_ms=duration_ms)
        if media_id is None:
            return False

        played_epoch = int(time.time())
        try:
            normalized_position_ms = max(0, int(position_ms or 0))
            normalized_duration_ms = max(0, int(duration_ms or 0))
        except (TypeError, ValueError):
            normalized_position_ms = 0
            normalized_duration_ms = 0

        normalized_limit = self._normalize_limit(limit)
        return self._database.execute_transaction(
            (
                (
                    """
                    INSERT INTO history (media_id, played_epoch, position_ms, duration_ms, source)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (media_id, played_epoch, normalized_position_ms, normalized_duration_ms, str(source or "")),
                ),
                (
                    """
                    UPDATE media
                    SET play_count = play_count + 1,
                        last_played_epoch = ?
                    WHERE id = ?
                    """,
                    (played_epoch, media_id),
                ),
                (
                    """
                    DELETE FROM history
                    WHERE id NOT IN (
                        SELECT id FROM history ORDER BY played_epoch DESC, id DESC LIMIT ?
                    )
                    """,
                    (normalized_limit,),
                ),
            )
        )

    @staticmethod
    def _normalize_limit(limit):
        try:
            return max(1, int(limit))
        except (TypeError, ValueError):
            return DEFAULT_HISTORY_LIMIT

    def recent(self, limit=DEFAULT_HISTORY_LIMIT, query=""):
        normalized_limit = self._normalize_limit(limit)

        conditions, parameters = self._filter_conditions(query)
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = self._database.query(
            f"SELECT {_HISTORY_COLUMNS} FROM history "
            f"JOIN media ON media.id = history.media_id {where_clause} "
            "ORDER BY history.played_epoch DESC, history.id DESC LIMIT ?",
            tuple(parameters) + (normalized_limit,),
        )
        return [HistoryEntry.from_row(row) for row in rows]

    def _filter_conditions(self, query):
        """Condições LIKE para o filtro de texto, uma por termo digitado."""
        from .search import escape_like, search_terms

        conditions = []
        parameters = []
        # Mesma tokenização e escape da busca global, para que o filtro do
        # histórico se comporte exatamente como o Ctrl+G.
        for term in search_terms(query):
            conditions.append("media.search_text LIKE ? ESCAPE '\\'")
            parameters.append(f"%{escape_like(term)}%")
        return conditions, parameters

    def grouped(self, limit=DEFAULT_HISTORY_LIMIT, query="", most_played_first=False):
        """Uma linha por mídia, com quantas vezes tocou e quando foi a última.

        Ouvir a mesma faixa quarenta vezes gera quarenta entradas na lista
        completa e empurra o resto para fora; agrupado, o histórico rende muito
        mais dentro do mesmo limite.
        """
        normalized_limit = self._normalize_limit(limit)

        conditions, parameters = self._filter_conditions(query)
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        order_by = (
            "play_count DESC, last_played_epoch DESC"
            if most_played_first
            else "last_played_epoch DESC"
        )

        rows = self._database.query(
            "SELECT media.media_path AS media_path, media.label AS label, "
            "COUNT(history.id) AS play_count, MAX(history.played_epoch) AS last_played_epoch, "
            "media.resume_position_ms AS position_ms, media.duration_ms AS duration_ms, "
            "'' AS source, media.favorite AS favorite, media.rating AS rating "
            "FROM history JOIN media ON media.id = history.media_id "
            f"{where_clause} GROUP BY media.id "
            f"ORDER BY {order_by}, media.label COLLATE NOCASE LIMIT ?",
            tuple(parameters) + (normalized_limit,),
        )
        return [HistorySummary.from_row(row) for row in rows]

    def most_played(self, limit=DEFAULT_HISTORY_LIMIT, query=""):
        return self.grouped(limit=limit, query=query, most_played_first=True)

    def count(self):
        row = self._database.query_one("SELECT COUNT(*) AS total FROM history")
        return int(row["total"]) if row is not None else 0

    def media_count(self):
        row = self._database.query_one(
            "SELECT COUNT(DISTINCT media_id) AS total FROM history"
        )
        return int(row["total"]) if row is not None else 0

    def remove_media_entries(self, media_path):
        """Apaga todas as reproduções de uma mídia (usado nos modos agrupados)."""
        key = media_path_key(media_path)
        if not key:
            return False

        return (
            self._database.execute(
                "DELETE FROM history WHERE media_id IN (SELECT id FROM media WHERE path_key = ?)",
                (key,),
            )
            is not None
        )

    def last_played_epoch(self, media_path):
        row = self._database.query_one(
            "SELECT last_played_epoch FROM media WHERE path_key = ?",
            (media_path_key(media_path),),
        )
        return int(row["last_played_epoch"] or 0) if row is not None else 0

    def trim(self, limit=DEFAULT_HISTORY_LIMIT):
        """Mantém apenas as `limit` reproduções mais recentes."""
        normalized_limit = self._normalize_limit(limit)

        self._database.execute(
            """
            DELETE FROM history
            WHERE id NOT IN (
                SELECT id FROM history ORDER BY played_epoch DESC, id DESC LIMIT ?
            )
            """,
            (normalized_limit,),
        )

    def remove(self, entry_id):
        try:
            normalized_entry_id = int(entry_id)
        except (TypeError, ValueError):
            return False

        return self._database.execute("DELETE FROM history WHERE id = ?", (normalized_entry_id,)) is not None

    def clear(self):
        return self._database.execute_transaction(
            (
                ("DELETE FROM history", ()),
                ("UPDATE media SET play_count = 0, last_played_epoch = 0", ()),
            )
        )
