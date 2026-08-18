"""Conexão e esquema do banco da biblioteca inteligente.

Um único arquivo SQLite (`smart_library.db`, na pasta de dados do KeyTune)
guarda o índice de mídias, o histórico, as posições de retomada e o cache de
metadados. Este módulo só cuida da conexão e das migrações de esquema; cada
tabela tem seu próprio módulo de acesso ao lado.
"""

import os
import sqlite3
import threading

from ..log import get_logger
from ..session import get_app_storage_dir


_logger = get_logger(__name__)

DATABASE_FILE_NAME = "smart_library.db"
SCHEMA_VERSION = 1


_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS media (
        id INTEGER PRIMARY KEY,
        path_key TEXT NOT NULL UNIQUE,
        media_path TEXT NOT NULL,
        folder_key TEXT NOT NULL DEFAULT '',
        folder_path TEXT NOT NULL DEFAULT '',
        label TEXT NOT NULL DEFAULT '',
        search_text TEXT NOT NULL DEFAULT '',
        is_remote INTEGER NOT NULL DEFAULT 0,
        duration_ms INTEGER NOT NULL DEFAULT 0,
        favorite INTEGER NOT NULL DEFAULT 0,
        rating INTEGER NOT NULL DEFAULT 0,
        play_count INTEGER NOT NULL DEFAULT 0,
        last_played_epoch INTEGER NOT NULL DEFAULT 0,
        resume_position_ms INTEGER NOT NULL DEFAULT 0,
        resume_updated_epoch INTEGER NOT NULL DEFAULT 0,
        indexed_epoch INTEGER NOT NULL DEFAULT 0
    )
    """,
    "CREATE INDEX IF NOT EXISTS media_folder_key ON media(folder_key)",
    "CREATE INDEX IF NOT EXISTS media_search_text ON media(search_text)",
    "CREATE INDEX IF NOT EXISTS media_favorite ON media(favorite)",
    "CREATE INDEX IF NOT EXISTS media_last_played ON media(last_played_epoch)",
    """
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        media_id INTEGER NOT NULL REFERENCES media(id) ON DELETE CASCADE,
        played_epoch INTEGER NOT NULL DEFAULT 0,
        position_ms INTEGER NOT NULL DEFAULT 0,
        duration_ms INTEGER NOT NULL DEFAULT 0,
        source TEXT NOT NULL DEFAULT ''
    )
    """,
    "CREATE INDEX IF NOT EXISTS history_played_epoch ON history(played_epoch)",
    "CREATE INDEX IF NOT EXISTS history_media_id ON history(media_id)",
    """
    CREATE TABLE IF NOT EXISTS metadata_cache (
        cache_key TEXT PRIMARY KEY,
        namespace TEXT NOT NULL DEFAULT '',
        media_key TEXT NOT NULL DEFAULT '',
        fingerprint TEXT NOT NULL DEFAULT '',
        payload TEXT NOT NULL DEFAULT '',
        updated_epoch INTEGER NOT NULL DEFAULT 0
    )
    """,
    "CREATE INDEX IF NOT EXISTS metadata_cache_namespace ON metadata_cache(namespace)",
    "CREATE INDEX IF NOT EXISTS metadata_cache_updated ON metadata_cache(updated_epoch)",
)


# Índice de texto completo sobre `media.search_text`. É opcional: o SQLite
# embarcado em alguns Pythons é compilado sem FTS5, e nesse caso a busca cai
# para a varredura com LIKE. Os gatilhos mantêm o índice em dia sem que os
# módulos de acesso precisem saber que ele existe.
_FTS_STATEMENTS = (
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS media_fts USING fts5(
        search_text,
        content='media',
        content_rowid='id',
        tokenize='unicode61 remove_diacritics 2'
    )
    """,
    """
    CREATE TRIGGER IF NOT EXISTS media_fts_insert AFTER INSERT ON media BEGIN
        INSERT INTO media_fts(rowid, search_text) VALUES (new.id, new.search_text);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS media_fts_delete AFTER DELETE ON media BEGIN
        INSERT INTO media_fts(media_fts, rowid, search_text)
        VALUES ('delete', old.id, old.search_text);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS media_fts_update AFTER UPDATE OF search_text ON media BEGIN
        INSERT INTO media_fts(media_fts, rowid, search_text)
        VALUES ('delete', old.id, old.search_text);
        INSERT INTO media_fts(rowid, search_text) VALUES (new.id, new.search_text);
    END
    """,
)


class SmartLibraryDatabase:
    """Conexão SQLite compartilhada, protegida por um lock de escrita.

    O serviço da biblioteca faz as gravações em uma thread de trabalho e as
    leituras na thread da interface, então a conexão é aberta com
    ``check_same_thread=False`` e todo acesso passa por ``self._lock``.
    """

    def __init__(self, database_path=None):
        self.database_path = database_path or default_database_path()
        self._lock = threading.RLock()
        self._connection = None
        self._full_text_search_available = False

    @property
    def is_open(self):
        return self._connection is not None

    @property
    def supports_full_text_search(self):
        return self._full_text_search_available

    def open(self):
        if self._connection is not None:
            return True

        directory = os.path.dirname(self.database_path)
        if directory:
            try:
                os.makedirs(directory, exist_ok=True)
            except OSError as exc:
                _logger.warning("Failed to create smart library directory %s: %s", directory, exc)
                return False

        try:
            connection = sqlite3.connect(
                self.database_path,
                check_same_thread=False,
                timeout=5.0,
            )
        except sqlite3.Error as exc:
            _logger.warning("Failed to open smart library database %s: %s", self.database_path, exc)
            return False

        connection.row_factory = sqlite3.Row
        self._connection = connection

        try:
            self._prepare_connection()
        except sqlite3.Error as exc:
            _logger.warning("Failed to prepare smart library database: %s", exc)
            self.close()
            return False

        return True

    def _prepare_connection(self):
        with self._lock:
            connection = self._connection
            # WAL keeps the UI-thread reads from blocking on the worker's
            # writes; the pragmas below are the usual desktop-app trade-off
            # (durability on power loss is not worth a stutter per track).
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute("PRAGMA foreign_keys=ON")
            for statement in _SCHEMA_STATEMENTS:
                connection.execute(statement)
            connection.execute("PRAGMA user_version=%d" % SCHEMA_VERSION)
            connection.commit()

        self._full_text_search_available = self._prepare_full_text_search()

    def _prepare_full_text_search(self):
        """Cria o índice FTS5 e o preenche. Devolve False se indisponível."""
        with self._lock:
            connection = self._connection
            if connection is None:
                return False

            try:
                for statement in _FTS_STATEMENTS:
                    connection.execute(statement)
                # Um banco criado antes do índice (ou por um Python sem FTS5)
                # já tem linhas em `media` que os gatilhos nunca viram.
                missing_row = connection.execute(
                    "SELECT COUNT(*) FROM media WHERE id NOT IN (SELECT rowid FROM media_fts)"
                ).fetchone()
                if missing_row is not None and int(missing_row[0]) > 0:
                    connection.execute("INSERT INTO media_fts(media_fts) VALUES ('rebuild')")
                connection.commit()
            except sqlite3.Error as exc:
                _logger.info("Smart library full-text search unavailable, falling back to scans: %s", exc)
                try:
                    connection.rollback()
                except sqlite3.Error:
                    pass
                return False

            return True

    def close(self):
        with self._lock:
            connection = self._connection
            self._connection = None

        if connection is None:
            return

        try:
            connection.close()
        except sqlite3.Error as exc:
            _logger.debug("Failed to close smart library database: %s", exc)

    def execute(self, statement, parameters=()):
        """Roda uma instrução de escrita e confirma a transação."""
        with self._lock:
            connection = self._connection
            if connection is None:
                return None
            try:
                cursor = connection.execute(statement, parameters)
                connection.commit()
                return cursor
            except sqlite3.Error as exc:
                _logger.warning("Smart library write failed: %s", exc)
                try:
                    connection.rollback()
                except sqlite3.Error:
                    pass
                return None

    def execute_many(self, statement, parameter_sets):
        with self._lock:
            connection = self._connection
            if connection is None:
                return False
            try:
                connection.executemany(statement, list(parameter_sets))
                connection.commit()
                return True
            except sqlite3.Error as exc:
                _logger.warning("Smart library bulk write failed: %s", exc)
                try:
                    connection.rollback()
                except sqlite3.Error:
                    pass
                return False

    def execute_transaction(self, statements):
        """Executa várias escritas como uma única transação."""
        with self._lock:
            connection = self._connection
            if connection is None:
                return False
            try:
                for statement, parameters in statements:
                    connection.execute(statement, parameters)
                connection.commit()
                return True
            except sqlite3.Error as exc:
                _logger.warning("Smart library transaction failed: %s", exc)
                try:
                    connection.rollback()
                except sqlite3.Error:
                    pass
                return False

    def query(self, statement, parameters=()):
        """Roda uma consulta e devolve todas as linhas (lista, nunca None)."""
        with self._lock:
            connection = self._connection
            if connection is None:
                return []
            try:
                return list(connection.execute(statement, parameters).fetchall())
            except sqlite3.Error as exc:
                _logger.warning("Smart library query failed: %s", exc)
                return []

    def query_one(self, statement, parameters=()):
        rows = self.query(statement, parameters)
        return rows[0] if rows else None


def default_database_path():
    return os.path.join(get_app_storage_dir(), DATABASE_FILE_NAME)
