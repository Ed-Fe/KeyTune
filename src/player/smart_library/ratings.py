"""Favoritos e avaliações das mídias locais.

Os dois marcadores moram na própria linha da mídia; este módulo só cuida de
lê-los e escrevê-los, registrando a mídia antes quando ela ainda não é
conhecida pela biblioteca.
"""

from .models import clamp_rating, media_path_key


class RatingStore:
    def __init__(self, database, record_store):
        self._database = database
        self._records = record_store

    def _ensure_media(self, media_path, label=""):
        media_id = self._records.media_id_for_path(media_path)
        if media_id is not None:
            return media_id
        return self._records.register(media_path, label=label)

    def set_favorite(self, media_path, favorite, label=""):
        if self._ensure_media(media_path, label) is None:
            return False

        cursor = self._database.execute(
            "UPDATE media SET favorite = ? WHERE path_key = ?",
            (1 if favorite else 0, media_path_key(media_path)),
        )
        return cursor is not None

    def toggle_favorite(self, media_path, label=""):
        """Inverte o favorito e devolve o novo estado (None em caso de falha)."""
        if self._ensure_media(media_path, label) is None:
            return None

        row = self._database.query_one(
            "SELECT favorite FROM media WHERE path_key = ?",
            (media_path_key(media_path),),
        )
        if row is None:
            return None

        new_value = not bool(row["favorite"])
        if not self.set_favorite(media_path, new_value, label=label):
            return None
        return new_value

    def is_favorite(self, media_path):
        row = self._database.query_one(
            "SELECT favorite FROM media WHERE path_key = ?",
            (media_path_key(media_path),),
        )
        return bool(row["favorite"]) if row is not None else False

    def set_rating(self, media_path, rating, label=""):
        if self._ensure_media(media_path, label) is None:
            return False

        cursor = self._database.execute(
            "UPDATE media SET rating = ? WHERE path_key = ?",
            (clamp_rating(rating), media_path_key(media_path)),
        )
        return cursor is not None

    def get_rating(self, media_path):
        row = self._database.query_one(
            "SELECT rating FROM media WHERE path_key = ?",
            (media_path_key(media_path),),
        )
        return clamp_rating(row["rating"]) if row is not None else 0

    def favorite_count(self):
        row = self._database.query_one("SELECT COUNT(*) AS total FROM media WHERE favorite = 1")
        return int(row["total"]) if row is not None else 0

    def clear_all(self):
        self._database.execute("UPDATE media SET favorite = 0, rating = 0")
