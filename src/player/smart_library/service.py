"""Fachada da biblioteca inteligente usada pelo frame.

Leituras (busca, favoritos, histórico, posição de retomada) são síncronas: são
consultas indexadas e curtas o bastante para a thread da interface. Gravações e
varreduras de pasta vão para uma thread de trabalho, para que indexar uma pasta
grande nunca trave a reprodução nem a navegação por teclado.

Quando o banco não pode ser aberto (disco cheio, permissão negada), o serviço
fica indisponível e todos os métodos viram operações inócuas — o player segue
funcionando sem a biblioteca.
"""

import os
import queue
import threading

from ..log import get_logger
from .database import SmartLibraryDatabase
from .history import (
    DEFAULT_HISTORY_LIMIT,
    HISTORY_VIEW_ALL,
    HISTORY_VIEW_GROUPED,
    HISTORY_VIEW_MOST_PLAYED,
    HistoryStore,
)
from .metadata_cache import DEFAULT_CACHE_LIMIT, MetadataCache, file_fingerprint
from .models import (
    SEARCH_SCOPE_ALL,
    IndexSummary,
    clamp_rating,
    default_media_label,
    is_remote_media,
)
from .ratings import RatingStore
from .records import MediaRecordStore
from .resume import ResumeStore
from .search import DEFAULT_SEARCH_LIMIT, MediaSearchStore
from .smart_playlists import SmartPlaylistStore


_logger = get_logger(__name__)

# Profundidade máxima da varredura recursiva, para que uma pasta raiz escolhida
# por engano (C:\, por exemplo) não vire uma indexação infinita.
MAX_INDEX_DEPTH = 12


class SmartLibraryService:
    def __init__(self, database_path=None, dispatch=None):
        self._database = SmartLibraryDatabase(database_path)
        self._dispatch = dispatch
        self._available = self._database.open()
        self._records = MediaRecordStore(self._database)
        self._search = MediaSearchStore(self._database)
        self._ratings = RatingStore(self._database, self._records)
        self._resume = ResumeStore(self._database, self._records)
        self._history = HistoryStore(self._database, self._records)
        self._metadata_cache = MetadataCache(self._database)
        self._smart_playlists = SmartPlaylistStore(self._database)
        self._work_queue = queue.Queue()
        self._worker = None
        self._shutting_down = False

        if self._available:
            self._start_worker()

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------
    @property
    def is_available(self):
        return bool(self._available)

    def _start_worker(self):
        self._worker = threading.Thread(
            target=self._worker_loop,
            name="keytune-smart-library",
            daemon=True,
        )
        self._worker.start()

    def _worker_loop(self):
        while True:
            task = self._work_queue.get()
            if task is None:
                return

            try:
                task()
            except Exception:  # pragma: no cover - defensivo
                _logger.exception("Smart library background task failed")

    def _submit(self, task):
        if not self._available or self._shutting_down:
            return False
        self._work_queue.put(task)
        return True

    def _notify(self, callback, *args):
        if not callable(callback):
            return
        if callable(self._dispatch):
            self._dispatch(callback, *args)
            return
        callback(*args)

    def begin_shutdown(self):
        if not self._available or self._shutting_down:
            return
        self._shutting_down = True
        self._work_queue.put(None)

    def finish_shutdown(self, timeout=3.0):
        worker = self._worker
        if worker is not None and worker.is_alive():
            worker.join(timeout=timeout)
        self._worker = None
        self._database.close()
        self._available = False

    def close(self):
        self.begin_shutdown()
        self.finish_shutdown()

    # ------------------------------------------------------------------
    # Registro de mídias e indexação
    # ------------------------------------------------------------------
    def register_media(self, media_path, label="", duration_ms=0):
        """Registra uma mídia em segundo plano (não bloqueia a interface)."""
        return self._submit(
            lambda: self._records.register(media_path, label=label, duration_ms=duration_ms)
        )

    def register_media_batch(self, entries):
        prepared = list(entries or [])
        if not prepared:
            return False
        return self._submit(lambda: self._records.register_many(prepared))

    def index_folder(self, folder_path, *, recursive=True, on_finished=None):
        """Varre uma pasta e indexa as mídias suportadas encontradas."""
        normalized_folder_path = str(folder_path or "").strip()
        if not normalized_folder_path:
            return False

        def task():
            summary = self._scan_folder(normalized_folder_path, recursive=recursive)
            self._notify(on_finished, summary)

        return self._submit(task)

    def _scan_folder(self, folder_path, *, recursive=True):
        from ..library.media_scan import is_supported_media

        normalized_folder_path = os.path.abspath(os.path.normpath(folder_path))
        if not os.path.isdir(normalized_folder_path):
            return IndexSummary(folder_path=normalized_folder_path, failed=True)

        scanned_files = 0
        pending_entries = []
        indexed_files = 0
        root_depth = normalized_folder_path.rstrip("\\/").count(os.sep)

        for current_root, directories, file_names in os.walk(normalized_folder_path):
            if not recursive:
                directories[:] = []
            elif current_root.rstrip("\\/").count(os.sep) - root_depth >= MAX_INDEX_DEPTH:
                directories[:] = []

            for file_name in file_names:
                scanned_files += 1
                if not is_supported_media(file_name):
                    continue
                pending_entries.append((os.path.join(current_root, file_name), file_name))

                if len(pending_entries) >= 500:
                    indexed_files += self._records.register_many(pending_entries)
                    pending_entries = []

            if self._shutting_down:
                break

        if pending_entries:
            indexed_files += self._records.register_many(pending_entries)

        return IndexSummary(
            folder_path=normalized_folder_path,
            scanned_files=scanned_files,
            indexed_files=indexed_files,
        )

    def forget_missing_media(self, on_finished=None):
        def task():
            removed = self._records.forget_missing(os.path.isfile)
            self._notify(on_finished, removed)

        return self._submit(task)

    # ------------------------------------------------------------------
    # Busca
    # ------------------------------------------------------------------
    def search(self, query, scope=SEARCH_SCOPE_ALL, limit=DEFAULT_SEARCH_LIMIT):
        if not self._available:
            return []
        return self._search.search(query, scope=scope, limit=limit)

    def favorites(self, limit=DEFAULT_SEARCH_LIMIT):
        if not self._available:
            return []
        return self._search.favorites(limit=limit)

    def top_rated(self, minimum_rating=1, limit=DEFAULT_SEARCH_LIMIT):
        if not self._available:
            return []
        return self._search.top_rated(minimum_rating=minimum_rating, limit=limit)

    def smart_playlist_media(self, rule):
        """Monta a lista de uma playlist inteligente na hora da abertura."""
        if not self._available:
            return []
        return self._smart_playlists.query(rule)

    def get_record(self, media_path):
        if not self._available:
            return None
        return self._records.get(media_path)

    def get_records(self, media_paths):
        if not self._available:
            return {}
        return self._records.get_many(media_paths)

    # ------------------------------------------------------------------
    # Favoritos e avaliações
    # ------------------------------------------------------------------
    def toggle_favorite(self, media_path, label=""):
        """Alterna o favorito de forma síncrona e devolve o novo estado."""
        if not self._available:
            return None
        return self._ratings.toggle_favorite(media_path, label=label)

    def set_favorite(self, media_path, favorite, label=""):
        if not self._available:
            return False
        return self._ratings.set_favorite(media_path, favorite, label=label)

    def is_favorite(self, media_path):
        if not self._available:
            return False
        return self._ratings.is_favorite(media_path)

    def set_rating(self, media_path, rating, label=""):
        if not self._available:
            return False
        return self._ratings.set_rating(media_path, clamp_rating(rating), label=label)

    def get_rating(self, media_path):
        if not self._available:
            return 0
        return self._ratings.get_rating(media_path)

    # ------------------------------------------------------------------
    # Histórico
    # ------------------------------------------------------------------
    def record_playback(
        self,
        media_path,
        *,
        label="",
        position_ms=0,
        duration_ms=0,
        source="",
        limit=DEFAULT_HISTORY_LIMIT,
    ):
        normalized_label = str(label or "").strip() or default_media_label(media_path)
        return self._submit(
            lambda: self._history.record(
                media_path,
                label=normalized_label,
                position_ms=position_ms,
                duration_ms=duration_ms,
                source=source,
                limit=limit,
            )
        )

    def recent_history(self, limit=DEFAULT_HISTORY_LIMIT, query=""):
        if not self._available:
            return []
        return self._history.recent(limit=limit, query=query)

    def grouped_history(self, limit=DEFAULT_HISTORY_LIMIT, query="", most_played_first=False):
        if not self._available:
            return []
        return self._history.grouped(limit=limit, query=query, most_played_first=most_played_first)

    def history_for_view(self, view, limit=DEFAULT_HISTORY_LIMIT, query=""):
        """Entrega a lista do modo escolhido na caixa do histórico."""
        if view == HISTORY_VIEW_GROUPED:
            return self.grouped_history(limit=limit, query=query)
        if view == HISTORY_VIEW_MOST_PLAYED:
            return self.grouped_history(limit=limit, query=query, most_played_first=True)
        if view != HISTORY_VIEW_ALL:
            return []
        return self.recent_history(limit=limit, query=query)

    def remove_history_for_media(self, media_path):
        if not self._available:
            return False
        return self._history.remove_media_entries(media_path)

    def clear_history(self):
        if not self._available:
            return False
        return self._history.clear()

    def remove_history_entry(self, entry_id):
        if not self._available:
            return False
        return self._history.remove(entry_id)

    # ------------------------------------------------------------------
    # Retomada
    # ------------------------------------------------------------------
    def should_remember_position(self, position_ms, duration_ms, *, minimum_duration_ms, ignore_edges_ms):
        return self._resume.should_remember(
            position_ms,
            duration_ms,
            minimum_duration_ms=minimum_duration_ms,
            ignore_edges_ms=ignore_edges_ms,
        )

    def remember_position(self, media_path, position_ms, duration_ms=0, label=""):
        return self._submit(
            lambda: self._resume.remember(media_path, position_ms, duration_ms=duration_ms, label=label)
        )

    def resume_position_ms(self, media_path):
        if not self._available:
            return 0
        return self._resume.get_position_ms(media_path)

    def pending_resumes(self, limit=100):
        """O que está pela metade, para a lista "Continuar ouvindo"."""
        if not self._available:
            return []
        return self._resume.pending(limit=limit)

    def forget_position(self, media_path):
        return self._submit(lambda: self._resume.forget(media_path))

    def clear_resume_positions(self):
        if not self._available:
            return False
        self._resume.clear_all()
        return True

    # ------------------------------------------------------------------
    # Cache de metadados / análise de áudio
    # ------------------------------------------------------------------
    def cached_payload(self, namespace, media_path, fingerprint=None):
        if not self._available:
            return None
        return self._metadata_cache.get(namespace, media_path, fingerprint=fingerprint)

    def store_payload(self, namespace, media_path, payload, fingerprint=None, limit=DEFAULT_CACHE_LIMIT):
        if fingerprint is None and not is_remote_media(media_path):
            # Calcula a impressão digital agora, na thread do chamador: o
            # arquivo pode mudar antes de a gravação sair da fila.
            fingerprint = file_fingerprint(media_path)

        return self._submit(
            lambda: self._metadata_cache.store(
                namespace,
                media_path,
                payload,
                fingerprint=fingerprint,
                limit=limit,
            )
        )

    def clear_metadata_cache(self, namespace=None):
        if not self._available:
            return False
        self._metadata_cache.clear(namespace)
        return True

    # ------------------------------------------------------------------
    # Resumo para a interface
    # ------------------------------------------------------------------
    def statistics(self):
        """Números mostrados nas preferências e nos anúncios de status."""
        if not self._available:
            return {
                "media": 0,
                "folders": 0,
                "favorites": 0,
                "history": 0,
                "resume": 0,
                "cache": 0,
            }

        return {
            "media": self._records.count(),
            "folders": self._records.folder_count(),
            "favorites": self._ratings.favorite_count(),
            "history": self._history.count(),
            "resume": self._resume.pending_count(),
            "cache": self._metadata_cache.count(),
        }

    def clear_everything(self):
        if not self._available:
            return False
        return self._database.execute_transaction(
            (
                ("DELETE FROM metadata_cache", ()),
                # O histórico é removido por ON DELETE CASCADE.
                ("DELETE FROM media", ()),
            )
        )
