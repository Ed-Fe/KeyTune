"""Posições de retomada por arquivo (podcasts, audiolivros, vídeos longos).

A regra é conservadora de propósito: só guardamos a posição de mídias longas o
bastante, ignoramos os primeiros segundos (quem parou logo no início quer
recomeçar) e apagamos a marca quando a faixa chega perto do fim.
"""

import time

from .models import MediaRecord, media_path_key


_MEDIA_COLUMNS = (
    "id, media_path, label, folder_path, is_remote, duration_ms, favorite, rating, "
    "play_count, last_played_epoch, resume_position_ms, resume_updated_epoch"
)


class ResumeStore:
    def __init__(self, database, record_store):
        self._database = database
        self._records = record_store

    def should_remember(self, position_ms, duration_ms, *, minimum_duration_ms, ignore_edges_ms):
        """Se vale guardar a posição atual como ponto de retomada."""
        try:
            normalized_position_ms = int(position_ms or 0)
            normalized_duration_ms = int(duration_ms or 0)
            normalized_minimum_duration_ms = max(0, int(minimum_duration_ms or 0))
            normalized_edges_ms = max(0, int(ignore_edges_ms or 0))
        except (TypeError, ValueError):
            return False

        if normalized_position_ms <= 0 or normalized_duration_ms <= 0:
            return False

        if normalized_duration_ms < normalized_minimum_duration_ms:
            return False

        if normalized_position_ms < normalized_edges_ms:
            return False

        return normalized_position_ms <= normalized_duration_ms - normalized_edges_ms

    def remember(self, media_path, position_ms, duration_ms=0, label=""):
        if self._records.media_id_for_path(media_path) is None:
            if self._records.register(media_path, label=label, duration_ms=duration_ms) is None:
                return False

        try:
            normalized_position_ms = max(0, int(position_ms or 0))
            normalized_duration_ms = max(0, int(duration_ms or 0))
        except (TypeError, ValueError):
            return False

        cursor = self._database.execute(
            """
            UPDATE media
            SET resume_position_ms = ?,
                resume_updated_epoch = ?,
                duration_ms = CASE WHEN ? > 0 THEN ? ELSE duration_ms END
            WHERE path_key = ?
            """,
            (
                normalized_position_ms,
                int(time.time()),
                normalized_duration_ms,
                normalized_duration_ms,
                media_path_key(media_path),
            ),
        )
        return cursor is not None

    def get_position_ms(self, media_path):
        row = self._database.query_one(
            "SELECT resume_position_ms FROM media WHERE path_key = ?",
            (media_path_key(media_path),),
        )
        return max(0, int(row["resume_position_ms"] or 0)) if row is not None else 0

    def forget(self, media_path):
        self._database.execute(
            "UPDATE media SET resume_position_ms = 0, resume_updated_epoch = 0 WHERE path_key = ?",
            (media_path_key(media_path),),
        )

    def pending(self, limit=100):
        """Mídias com retomada pendente, da mais recente para a mais antiga."""
        try:
            normalized_limit = max(1, int(limit))
        except (TypeError, ValueError):
            normalized_limit = 100

        rows = self._database.query(
            f"SELECT {_MEDIA_COLUMNS} FROM media WHERE resume_position_ms > 0 "
            "ORDER BY resume_updated_epoch DESC, label COLLATE NOCASE LIMIT ?",
            (normalized_limit,),
        )
        return [MediaRecord.from_row(row) for row in rows]

    def pending_count(self):
        row = self._database.query_one(
            "SELECT COUNT(*) AS total FROM media WHERE resume_position_ms > 0"
        )
        return int(row["total"]) if row is not None else 0

    def clear_all(self):
        self._database.execute("UPDATE media SET resume_position_ms = 0, resume_updated_epoch = 0")
