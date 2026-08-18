"""Cache reutilizável de metadados e análises de áudio.

Guarda qualquer payload JSON associado a uma mídia, em espaços de nome
separados (`namespace`), junto de uma impressão digital do arquivo. Se o
arquivo mudar (tamanho ou data de modificação), a entrada é considerada velha e
o chamador recalcula.

O AutoDJ da v1.5 usará o mesmo cache para BPM e posições de batida — por isso o
payload é livre e o namespace é parte da chave.
"""

import json
import os
import time

from ..log import get_logger
from .models import is_remote_media, media_path_key


_logger = get_logger(__name__)

NAMESPACE_MEDIA_METADATA = "media_metadata"
NAMESPACE_AUDIO_ANALYSIS = "audio_analysis"

DEFAULT_CACHE_LIMIT = 5000


def file_fingerprint(media_path):
    """Impressão digital barata do arquivo: tamanho + data de modificação.

    Mídias remotas não têm arquivo local, então usam o próprio caminho — o
    chamador decide quando invalidá-las.
    """
    normalized_path = str(media_path or "").strip()
    if not normalized_path:
        return ""

    if is_remote_media(normalized_path):
        return "remote"

    try:
        stat_result = os.stat(normalized_path)
    except OSError:
        return ""

    return f"{stat_result.st_size}:{int(stat_result.st_mtime)}"


class MetadataCache:
    def __init__(self, database):
        self._database = database

    def _cache_key(self, namespace, media_path):
        return f"{namespace}|{media_path_key(media_path)}"

    def get(self, namespace, media_path, fingerprint=None):
        """Devolve o payload guardado, ou None se ausente ou desatualizado."""
        path_key = media_path_key(media_path)
        if not path_key:
            return None

        row = self._database.query_one(
            "SELECT payload, fingerprint FROM metadata_cache WHERE cache_key = ?",
            (self._cache_key(namespace, media_path),),
        )
        if row is None:
            return None

        expected_fingerprint = fingerprint if fingerprint is not None else file_fingerprint(media_path)
        if expected_fingerprint and str(row["fingerprint"] or "") != expected_fingerprint:
            return None

        try:
            return json.loads(str(row["payload"] or ""))
        except (TypeError, ValueError) as exc:
            _logger.debug("Discarding malformed smart library cache payload: %s", exc)
            return None

    def store(self, namespace, media_path, payload, fingerprint=None, limit=DEFAULT_CACHE_LIMIT):
        path_key = media_path_key(media_path)
        if not path_key:
            return False

        try:
            serialized_payload = json.dumps(payload, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            _logger.debug("Refusing to cache a non-serializable payload: %s", exc)
            return False

        effective_fingerprint = fingerprint if fingerprint is not None else file_fingerprint(media_path)
        cursor = self._database.execute(
            """
            INSERT INTO metadata_cache (cache_key, namespace, media_key, fingerprint, payload, updated_epoch)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                fingerprint = excluded.fingerprint,
                payload = excluded.payload,
                updated_epoch = excluded.updated_epoch
            """,
            (
                self._cache_key(namespace, media_path),
                str(namespace or ""),
                path_key,
                str(effective_fingerprint or ""),
                serialized_payload,
                int(time.time()),
            ),
        )
        if cursor is None:
            return False

        self.trim(limit)
        return True

    def invalidate(self, namespace, media_path):
        self._database.execute(
            "DELETE FROM metadata_cache WHERE cache_key = ?",
            (self._cache_key(namespace, media_path),),
        )

    def count(self, namespace=None):
        if namespace is None:
            row = self._database.query_one("SELECT COUNT(*) AS total FROM metadata_cache")
        else:
            row = self._database.query_one(
                "SELECT COUNT(*) AS total FROM metadata_cache WHERE namespace = ?",
                (str(namespace),),
            )
        return int(row["total"]) if row is not None else 0

    def trim(self, limit=DEFAULT_CACHE_LIMIT):
        """Descarta as entradas mais antigas acima do limite configurado."""
        try:
            normalized_limit = max(1, int(limit))
        except (TypeError, ValueError):
            normalized_limit = DEFAULT_CACHE_LIMIT

        self._database.execute(
            """
            DELETE FROM metadata_cache
            WHERE cache_key NOT IN (
                SELECT cache_key FROM metadata_cache ORDER BY updated_epoch DESC LIMIT ?
            )
            """,
            (normalized_limit,),
        )

    def clear(self, namespace=None):
        if namespace is None:
            self._database.execute("DELETE FROM metadata_cache")
            return
        self._database.execute("DELETE FROM metadata_cache WHERE namespace = ?", (str(namespace),))
