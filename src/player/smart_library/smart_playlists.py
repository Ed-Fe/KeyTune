"""Playlists inteligentes: regras salvas que viram uma lista ao serem abertas.

Uma regra combina filtros sobre o que a biblioteca já sabe — favorito,
avaliação, pasta, quando tocou pela última vez, quantas vezes tocou — com uma
ordenação e um limite. Nada é copiado: a lista é montada na hora em que você
abre, então ela acompanha as mudanças de avaliação e de histórico.

As regras moram nas preferências (são configuração durável do usuário); este
módulo só cuida de validá-las e de traduzi-las em consulta.
"""

import os
import time
from dataclasses import dataclass, field

from .models import MediaRecord, clamp_rating, media_path_key


# Ordenações oferecidas ao usuário.
SORT_RECENTLY_PLAYED = "recently_played"
SORT_LEAST_RECENTLY_PLAYED = "least_recently_played"
SORT_MOST_PLAYED = "most_played"
SORT_HIGHEST_RATED = "highest_rated"
SORT_TITLE = "title"
SORT_RANDOM = "random"
SORT_ORDERS = (
    SORT_RECENTLY_PLAYED,
    SORT_LEAST_RECENTLY_PLAYED,
    SORT_MOST_PLAYED,
    SORT_HIGHEST_RATED,
    SORT_TITLE,
    SORT_RANDOM,
)

DEFAULT_SMART_PLAYLIST_LIMIT = 100
MIN_SMART_PLAYLIST_LIMIT = 1
MAX_SMART_PLAYLIST_LIMIT = 5000

MAX_NOT_PLAYED_DAYS = 3650

_SORT_CLAUSES = {
    SORT_RECENTLY_PLAYED: "last_played_epoch DESC, label COLLATE NOCASE",
    SORT_LEAST_RECENTLY_PLAYED: "last_played_epoch ASC, label COLLATE NOCASE",
    SORT_MOST_PLAYED: "play_count DESC, last_played_epoch DESC, label COLLATE NOCASE",
    SORT_HIGHEST_RATED: "rating DESC, favorite DESC, label COLLATE NOCASE",
    SORT_TITLE: "label COLLATE NOCASE",
    SORT_RANDOM: "RANDOM()",
}

_MEDIA_COLUMNS = (
    "id, media_path, label, folder_path, is_remote, duration_ms, favorite, rating, "
    "play_count, last_played_epoch, resume_position_ms, resume_updated_epoch"
)


def _clamp(value, minimum, maximum, fallback):
    try:
        numeric_value = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(maximum, numeric_value))


@dataclass
class SmartPlaylistRule:
    """Os critérios de uma playlist inteligente."""

    name: str = ""
    favorites_only: bool = False
    minimum_rating: int = 0
    folder_path: str = ""
    not_played_for_days: int = 0
    minimum_play_count: int = 0
    include_never_played: bool = True
    exclude_remote: bool = True
    sort_order: str = SORT_RECENTLY_PLAYED
    limit: int = DEFAULT_SMART_PLAYLIST_LIMIT

    def to_dict(self):
        return {
            "name": self.name,
            "favorites_only": self.favorites_only,
            "minimum_rating": self.minimum_rating,
            "folder_path": self.folder_path,
            "not_played_for_days": self.not_played_for_days,
            "minimum_play_count": self.minimum_play_count,
            "include_never_played": self.include_never_played,
            "exclude_remote": self.exclude_remote,
            "sort_order": self.sort_order,
            "limit": self.limit,
        }

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            return cls()

        rule = cls()
        rule.name = str(data.get("name") or "").strip()
        rule.favorites_only = bool(data.get("favorites_only", rule.favorites_only))
        rule.minimum_rating = clamp_rating(data.get("minimum_rating", rule.minimum_rating))
        rule.folder_path = str(data.get("folder_path") or "").strip()
        rule.not_played_for_days = _clamp(
            data.get("not_played_for_days", rule.not_played_for_days),
            minimum=0,
            maximum=MAX_NOT_PLAYED_DAYS,
            fallback=rule.not_played_for_days,
        )
        rule.minimum_play_count = _clamp(
            data.get("minimum_play_count", rule.minimum_play_count),
            minimum=0,
            maximum=100000,
            fallback=rule.minimum_play_count,
        )
        rule.include_never_played = bool(data.get("include_never_played", rule.include_never_played))
        rule.exclude_remote = bool(data.get("exclude_remote", rule.exclude_remote))
        sort_order = str(data.get("sort_order") or "")
        rule.sort_order = sort_order if sort_order in SORT_ORDERS else SORT_RECENTLY_PLAYED
        rule.limit = _clamp(
            data.get("limit", rule.limit),
            minimum=MIN_SMART_PLAYLIST_LIMIT,
            maximum=MAX_SMART_PLAYLIST_LIMIT,
            fallback=DEFAULT_SMART_PLAYLIST_LIMIT,
        )
        return rule


@dataclass
class SmartPlaylistCollection:
    """As playlists inteligentes salvas, na ordem em que aparecem no menu."""

    rules: list = field(default_factory=list)

    @classmethod
    def from_list(cls, payload):
        if not isinstance(payload, list):
            return cls()

        rules = []
        for item in payload:
            rule = SmartPlaylistRule.from_dict(item)
            if rule.name:
                rules.append(rule)
        return cls(rules=rules)

    def to_list(self):
        return [rule.to_dict() for rule in self.rules if rule.name]


class SmartPlaylistStore:
    def __init__(self, database):
        self._database = database

    def query(self, rule, now_epoch=None):
        """Devolve as mídias que atendem à regra, já ordenadas."""
        if rule is None:
            return []

        conditions = []
        parameters = []

        if rule.favorites_only:
            conditions.append("favorite = 1")

        if rule.minimum_rating > 0:
            conditions.append("rating >= ?")
            parameters.append(clamp_rating(rule.minimum_rating))

        if rule.folder_path:
            # Casa a pasta e tudo abaixo dela, comparando a chave normalizada
            # para que maiúsculas e barras não atrapalhem.
            folder_key = media_path_key(rule.folder_path)
            if folder_key:
                conditions.append("(folder_key = ? OR folder_key LIKE ? ESCAPE '\\')")
                parameters.append(folder_key)
                escaped_key = folder_key.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                escaped_separator = os.sep.replace("\\", "\\\\")
                parameters.append(f"{escaped_key}{escaped_separator}%")

        if rule.exclude_remote:
            conditions.append("is_remote = 0")

        if rule.minimum_play_count > 0:
            conditions.append("play_count >= ?")
            parameters.append(int(rule.minimum_play_count))

        if rule.not_played_for_days > 0:
            cutoff_epoch = int(now_epoch if now_epoch is not None else time.time())
            cutoff_epoch -= int(rule.not_played_for_days) * 86400
            if rule.include_never_played:
                conditions.append("(last_played_epoch = 0 OR last_played_epoch <= ?)")
            else:
                conditions.append("(last_played_epoch > 0 AND last_played_epoch <= ?)")
            parameters.append(cutoff_epoch)
        elif not rule.include_never_played:
            conditions.append("last_played_epoch > 0")

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        order_by = _SORT_CLAUSES.get(rule.sort_order, _SORT_CLAUSES[SORT_RECENTLY_PLAYED])
        limit = _clamp(
            rule.limit,
            minimum=MIN_SMART_PLAYLIST_LIMIT,
            maximum=MAX_SMART_PLAYLIST_LIMIT,
            fallback=DEFAULT_SMART_PLAYLIST_LIMIT,
        )

        rows = self._database.query(
            f"SELECT {_MEDIA_COLUMNS} FROM media {where_clause} ORDER BY {order_by} LIMIT ?",
            tuple(parameters) + (limit,),
        )
        return [MediaRecord.from_row(row) for row in rows]
