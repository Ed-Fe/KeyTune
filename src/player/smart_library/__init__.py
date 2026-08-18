"""Biblioteca inteligente do KeyTune (busca global, favoritos, histórico, retomada).

O pacote separa o armazenamento (SQLite, sem wxPython) das caixas de diálogo,
para que os serviços possam ser testados sem interface e reaproveitados pelas
funcionalidades futuras — o AutoDJ da v1.5 usa o mesmo cache de análise.
"""

from .database import DATABASE_FILE_NAME, SmartLibraryDatabase, default_database_path
from .history import (
    DEFAULT_HISTORY_LIMIT,
    HISTORY_VIEW_ALL,
    HISTORY_VIEW_GROUPED,
    HISTORY_VIEW_MOST_PLAYED,
    HISTORY_VIEWS,
    SOURCE_FOLDER,
    SOURCE_LOCAL,
    SOURCE_REMOTE,
    SOURCE_YOUTUBE_MUSIC,
    HistoryStore,
)
from .history_dialog import (
    HISTORY_ACTION_ENQUEUE,
    HISTORY_ACTION_PLAY,
    PLAYBACK_HISTORY_DIALOG_TITLE,
    PlaybackHistoryDialog,
)
from .metadata_cache import (
    DEFAULT_CACHE_LIMIT,
    NAMESPACE_AUDIO_ANALYSIS,
    NAMESPACE_MEDIA_METADATA,
    MetadataCache,
    file_fingerprint,
)
from .models import (
    MAX_RATING,
    MIN_RATING,
    SEARCH_SCOPE_ALL,
    SEARCH_SCOPE_FAVORITES,
    SEARCH_SCOPE_HISTORY,
    SEARCH_SCOPE_RATED,
    SEARCH_SCOPES,
    HistoryEntry,
    HistorySummary,
    IndexSummary,
    MediaRecord,
    clamp_rating,
    default_media_label,
    media_path_key,
)
from .ratings import RatingStore
from .records import MediaRecordStore
from .resume import ResumeStore
from .search import DEFAULT_SEARCH_LIMIT, MediaSearchStore
from .search_dialog import (
    GLOBAL_SEARCH_DIALOG_TITLE,
    SEARCH_RESULT_ACTION_ENQUEUE,
    SEARCH_RESULT_ACTION_PLAY,
    GlobalSearchDialog,
    format_rating,
)
from .service import SmartLibraryService
from .smart_playlist_dialog import (
    SMART_PLAYLIST_EDITOR_TITLE,
    SMART_PLAYLIST_MANAGER_TITLE,
    SmartPlaylistEditorDialog,
    SmartPlaylistManagerDialog,
)
from .smart_playlist_dialog import describe_rule as describe_smart_playlist_rule
from .smart_playlists import (
    DEFAULT_SMART_PLAYLIST_LIMIT,
    MAX_SMART_PLAYLIST_LIMIT,
    MIN_SMART_PLAYLIST_LIMIT,
    SORT_ORDERS,
    SmartPlaylistCollection,
    SmartPlaylistRule,
    SmartPlaylistStore,
)

__all__ = [
    "DEFAULT_SMART_PLAYLIST_LIMIT",
    "HISTORY_VIEWS",
    "HISTORY_VIEW_ALL",
    "HISTORY_VIEW_GROUPED",
    "HISTORY_VIEW_MOST_PLAYED",
    "HistorySummary",
    "MAX_SMART_PLAYLIST_LIMIT",
    "MIN_SMART_PLAYLIST_LIMIT",
    "SMART_PLAYLIST_EDITOR_TITLE",
    "SMART_PLAYLIST_MANAGER_TITLE",
    "SORT_ORDERS",
    "SmartPlaylistCollection",
    "SmartPlaylistEditorDialog",
    "SmartPlaylistManagerDialog",
    "SmartPlaylistRule",
    "SmartPlaylistStore",
    "describe_smart_playlist_rule",
    "DATABASE_FILE_NAME",
    "DEFAULT_CACHE_LIMIT",
    "DEFAULT_HISTORY_LIMIT",
    "DEFAULT_SEARCH_LIMIT",
    "GLOBAL_SEARCH_DIALOG_TITLE",
    "HISTORY_ACTION_ENQUEUE",
    "HISTORY_ACTION_PLAY",
    "MAX_RATING",
    "MIN_RATING",
    "NAMESPACE_AUDIO_ANALYSIS",
    "NAMESPACE_MEDIA_METADATA",
    "PLAYBACK_HISTORY_DIALOG_TITLE",
    "SEARCH_RESULT_ACTION_ENQUEUE",
    "SEARCH_RESULT_ACTION_PLAY",
    "SEARCH_SCOPES",
    "SEARCH_SCOPE_ALL",
    "SEARCH_SCOPE_FAVORITES",
    "SEARCH_SCOPE_HISTORY",
    "SEARCH_SCOPE_RATED",
    "SOURCE_FOLDER",
    "SOURCE_LOCAL",
    "SOURCE_REMOTE",
    "SOURCE_YOUTUBE_MUSIC",
    "GlobalSearchDialog",
    "HistoryEntry",
    "HistoryStore",
    "IndexSummary",
    "MediaRecord",
    "MediaRecordStore",
    "MediaSearchStore",
    "MetadataCache",
    "PlaybackHistoryDialog",
    "RatingStore",
    "ResumeStore",
    "SmartLibraryDatabase",
    "SmartLibraryService",
    "clamp_rating",
    "default_database_path",
    "default_media_label",
    "file_fingerprint",
    "format_rating",
    "media_path_key",
]
