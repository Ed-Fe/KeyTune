"""Acesso à tabela `media`: registro e consulta das mídias conhecidas.

Toda mídia que a biblioteca inteligente acompanha (favorito, avaliação,
histórico, retomada) tem uma linha aqui. Registrar é idempotente: chamar de
novo apenas atualiza rótulo, pasta e duração, preservando os marcadores que o
usuário criou.
"""

import time

from .models import (
    MediaRecord,
    build_search_text,
    default_media_label,
    is_remote_media,
    media_folder_path,
    media_path_key,
)


_MEDIA_COLUMNS = (
    "id, media_path, label, folder_path, is_remote, duration_ms, favorite, rating, "
    "play_count, last_played_epoch, resume_position_ms, resume_updated_epoch"
)


class MediaRecordStore:
    def __init__(self, database):
        self._database = database

    def register(self, media_path, label="", duration_ms=0):
        """Garante uma linha para a mídia e devolve seu id (ou None)."""
        path_key = media_path_key(media_path)
        if not path_key:
            return None

        normalized_path = str(media_path or "").strip()
        normalized_label = str(label or "").strip() or default_media_label(normalized_path)
        folder_path = media_folder_path(normalized_path)
        search_text = build_search_text(normalized_label, normalized_path)
        try:
            normalized_duration_ms = max(0, int(duration_ms or 0))
        except (TypeError, ValueError):
            normalized_duration_ms = 0

        cursor = self._database.execute(
            """
            INSERT INTO media (
                path_key, media_path, folder_key, folder_path, label, search_text,
                is_remote, duration_ms, indexed_epoch
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path_key) DO UPDATE SET
                media_path = excluded.media_path,
                folder_key = excluded.folder_key,
                folder_path = excluded.folder_path,
                label = excluded.label,
                search_text = excluded.search_text,
                is_remote = excluded.is_remote,
                -- Uma duração desconhecida (0) nunca apaga a que já foi medida.
                duration_ms = CASE
                    WHEN excluded.duration_ms > 0 THEN excluded.duration_ms
                    ELSE media.duration_ms
                END,
                indexed_epoch = excluded.indexed_epoch
            """,
            (
                path_key,
                normalized_path,
                media_path_key(folder_path) if folder_path else "",
                folder_path,
                normalized_label,
                search_text,
                1 if is_remote_media(normalized_path) else 0,
                normalized_duration_ms,
                int(time.time()),
            ),
        )

        if cursor is None:
            return None

        return self.media_id_for_path(normalized_path)

    def register_many(self, entries):
        """Registra várias mídias de uma vez. `entries` é (caminho, rótulo)."""
        prepared = []
        now = int(time.time())
        for entry in entries:
            media_path, label = entry if isinstance(entry, (tuple, list)) else (entry, "")
            path_key = media_path_key(media_path)
            if not path_key:
                continue

            normalized_path = str(media_path or "").strip()
            normalized_label = str(label or "").strip() or default_media_label(normalized_path)
            folder_path = media_folder_path(normalized_path)
            prepared.append(
                (
                    path_key,
                    normalized_path,
                    media_path_key(folder_path) if folder_path else "",
                    folder_path,
                    normalized_label,
                    build_search_text(normalized_label, normalized_path),
                    1 if is_remote_media(normalized_path) else 0,
                    now,
                )
            )

        if not prepared:
            return 0

        succeeded = self._database.execute_many(
            """
            INSERT INTO media (
                path_key, media_path, folder_key, folder_path, label, search_text,
                is_remote, indexed_epoch
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path_key) DO UPDATE SET
                media_path = excluded.media_path,
                folder_key = excluded.folder_key,
                folder_path = excluded.folder_path,
                label = excluded.label,
                search_text = excluded.search_text,
                is_remote = excluded.is_remote,
                indexed_epoch = excluded.indexed_epoch
            """,
            prepared,
        )

        return len(prepared) if succeeded else 0

    def media_id_for_path(self, media_path):
        path_key = media_path_key(media_path)
        if not path_key:
            return None

        row = self._database.query_one("SELECT id FROM media WHERE path_key = ?", (path_key,))
        return int(row["id"]) if row is not None else None

    def get(self, media_path):
        path_key = media_path_key(media_path)
        if not path_key:
            return None

        row = self._database.query_one(
            f"SELECT {_MEDIA_COLUMNS} FROM media WHERE path_key = ?",
            (path_key,),
        )
        return MediaRecord.from_row(row)

    def get_many(self, media_paths):
        """Devolve um dicionário caminho-normalizado -> MediaRecord."""
        path_keys = [media_path_key(path) for path in media_paths]
        path_keys = [key for key in path_keys if key]
        if not path_keys:
            return {}

        records = {}
        # SQLite limita o número de parâmetros por consulta, então varremos em
        # blocos em vez de montar um IN gigante para playlists longas.
        for start in range(0, len(path_keys), 400):
            chunk = path_keys[start : start + 400]
            placeholders = ", ".join("?" for _ in chunk)
            rows = self._database.query(
                f"SELECT {_MEDIA_COLUMNS}, path_key FROM media WHERE path_key IN ({placeholders})",
                tuple(chunk),
            )
            for row in rows:
                records[str(row["path_key"])] = MediaRecord.from_row(row)

        return records

    def count(self):
        row = self._database.query_one("SELECT COUNT(*) AS total FROM media")
        return int(row["total"]) if row is not None else 0

    def folder_count(self):
        row = self._database.query_one(
            "SELECT COUNT(DISTINCT folder_key) AS total FROM media WHERE folder_key <> ''"
        )
        return int(row["total"]) if row is not None else 0

    def forget_missing(self, path_exists):
        """Remove mídias locais que sumiram do disco. Devolve quantas saíram."""
        rows = self._database.query(
            "SELECT id, media_path FROM media WHERE is_remote = 0"
        )
        stale_ids = [
            (int(row["id"]),)
            for row in rows
            if not path_exists(str(row["media_path"] or ""))
        ]
        if not stale_ids:
            return 0

        if not self._database.execute_many("DELETE FROM media WHERE id = ?", stale_ids):
            return 0

        return len(stale_ids)

    def clear(self):
        self._database.execute("DELETE FROM media")
