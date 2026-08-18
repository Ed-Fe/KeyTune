"""Estruturas de dados compartilhadas pela biblioteca inteligente."""

import os
from dataclasses import dataclass

from ..library.text import normalize_search_text


MAX_RATING = 5
MIN_RATING = 0

# Filtros da busca global.
SEARCH_SCOPE_ALL = "all"
SEARCH_SCOPE_FAVORITES = "favorites"
SEARCH_SCOPE_RATED = "rated"
SEARCH_SCOPE_HISTORY = "history"
SEARCH_SCOPES = (SEARCH_SCOPE_ALL, SEARCH_SCOPE_FAVORITES, SEARCH_SCOPE_RATED, SEARCH_SCOPE_HISTORY)


def is_remote_media(media_path):
    return "://" in str(media_path or "")


def media_path_key(media_path):
    """Chave estável de uma mídia, tolerante a maiúsculas e separadores.

    Caminhos locais são normalizados como o sistema de arquivos faz; URLs
    remotas (YouTube Music, rádios) só perdem espaços e caixa.
    """
    normalized_path = str(media_path or "").strip()
    if not normalized_path:
        return ""

    if is_remote_media(normalized_path):
        return normalized_path.casefold()

    return os.path.normcase(os.path.abspath(os.path.normpath(normalized_path)))


def media_folder_path(media_path):
    normalized_path = str(media_path or "").strip()
    if not normalized_path or is_remote_media(normalized_path):
        return ""

    return os.path.dirname(os.path.abspath(os.path.normpath(normalized_path)))


def default_media_label(media_path):
    normalized_path = str(media_path or "").strip().rstrip("\\/")
    if not normalized_path:
        return ""

    if is_remote_media(normalized_path):
        return normalized_path

    return os.path.basename(normalized_path) or normalized_path


def build_search_text(label, media_path):
    """Texto indexado da mídia: rótulo + pasta, sem acentos nem caixa."""
    folder_path = media_folder_path(media_path)
    parts = [str(label or ""), default_media_label(media_path), folder_path]
    return normalize_search_text(" ".join(part for part in parts if part))


def clamp_rating(value):
    try:
        numeric_value = int(value)
    except (TypeError, ValueError):
        return MIN_RATING

    return max(MIN_RATING, min(MAX_RATING, numeric_value))


@dataclass(frozen=True)
class MediaRecord:
    """Uma mídia conhecida pela biblioteca, com seus marcadores do usuário."""

    media_id: int
    media_path: str
    label: str
    folder_path: str = ""
    is_remote: bool = False
    duration_ms: int = 0
    favorite: bool = False
    rating: int = 0
    play_count: int = 0
    last_played_epoch: int = 0
    resume_position_ms: int = 0
    resume_updated_epoch: int = 0

    @property
    def display_label(self):
        return self.label or default_media_label(self.media_path)

    @classmethod
    def from_row(cls, row):
        if row is None:
            return None

        return cls(
            media_id=int(row["id"]),
            media_path=str(row["media_path"] or ""),
            label=str(row["label"] or ""),
            folder_path=str(row["folder_path"] or ""),
            is_remote=bool(row["is_remote"]),
            duration_ms=int(row["duration_ms"] or 0),
            favorite=bool(row["favorite"]),
            rating=clamp_rating(row["rating"]),
            play_count=int(row["play_count"] or 0),
            last_played_epoch=int(row["last_played_epoch"] or 0),
            resume_position_ms=int(row["resume_position_ms"] or 0),
            resume_updated_epoch=int(row["resume_updated_epoch"] or 0),
        )


@dataclass(frozen=True)
class HistoryEntry:
    """Uma reprodução registrada no histórico local."""

    entry_id: int
    media_path: str
    label: str
    played_epoch: int
    position_ms: int = 0
    duration_ms: int = 0
    source: str = ""
    favorite: bool = False
    rating: int = 0

    @property
    def display_label(self):
        return self.label or default_media_label(self.media_path)

    @classmethod
    def from_row(cls, row):
        if row is None:
            return None

        return cls(
            entry_id=int(row["id"]),
            media_path=str(row["media_path"] or ""),
            label=str(row["label"] or ""),
            played_epoch=int(row["played_epoch"] or 0),
            position_ms=int(row["position_ms"] or 0),
            duration_ms=int(row["duration_ms"] or 0),
            source=str(row["source"] or ""),
            favorite=bool(row["favorite"]),
            rating=clamp_rating(row["rating"]),
        )


@dataclass(frozen=True)
class HistorySummary:
    """Uma mídia no histórico agrupado: quantas vezes e quando pela última vez."""

    media_path: str
    label: str
    play_count: int = 0
    last_played_epoch: int = 0
    position_ms: int = 0
    duration_ms: int = 0
    source: str = ""
    favorite: bool = False
    rating: int = 0

    @property
    def display_label(self):
        return self.label or default_media_label(self.media_path)

    @classmethod
    def from_row(cls, row):
        if row is None:
            return None

        return cls(
            media_path=str(row["media_path"] or ""),
            label=str(row["label"] or ""),
            play_count=int(row["play_count"] or 0),
            last_played_epoch=int(row["last_played_epoch"] or 0),
            position_ms=int(row["position_ms"] or 0),
            duration_ms=int(row["duration_ms"] or 0),
            source=str(row["source"] or ""),
            favorite=bool(row["favorite"]),
            rating=clamp_rating(row["rating"]),
        )


@dataclass(frozen=True)
class IndexSummary:
    """Resultado de uma varredura de indexação."""

    folder_path: str = ""
    scanned_files: int = 0
    indexed_files: int = 0
    failed: bool = False
