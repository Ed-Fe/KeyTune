"""SQLite analysis cache keyed by path, size, mtime and analyzer version."""

import json
from contextlib import closing
from pathlib import Path
import sqlite3
import time

from .analyzer import AudioAnalysis


class AnalysisCache:
    def __init__(self, path):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS analysis (path TEXT PRIMARY KEY, size INTEGER, mtime_ns INTEGER, version INTEGER, payload TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS remote_analysis (media_key TEXT, version INTEGER, saved_at REAL, payload TEXT, PRIMARY KEY(media_key, version))")

    def get(self, media_path, version=1):
        path = Path(media_path); stat = path.stat()
        with closing(sqlite3.connect(self.path)) as db, db:
            row = db.execute("SELECT payload FROM analysis WHERE path=? AND size=? AND mtime_ns=? AND version=?", (str(path.resolve()), stat.st_size, stat.st_mtime_ns, version)).fetchone()
        if not row: return None
        value = self._decode_payload(row[0])
        return AudioAnalysis(**value)

    def put(self, media_path, analysis, version=1):
        path = Path(media_path); stat = path.stat()
        payload = json.dumps({**analysis.__dict__, "beats_ms": list(analysis.beats_ms)})
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT OR REPLACE INTO analysis VALUES (?, ?, ?, ?, ?)", (str(path.resolve()), stat.st_size, stat.st_mtime_ns, version, payload))

    def get_remote(self, media_key, version=1, max_age_seconds=7 * 24 * 60 * 60):
        with closing(sqlite3.connect(self.path)) as db, db:
            row = db.execute(
                "SELECT saved_at, payload FROM remote_analysis WHERE media_key=? AND version=?",
                (str(media_key), version),
            ).fetchone()
        if not row or time.time() - row[0] > max_age_seconds:
            return None
        value = self._decode_payload(row[1])
        return AudioAnalysis(**value)

    def put_remote(self, media_key, analysis, version=1):
        payload = json.dumps({**analysis.__dict__, "beats_ms": list(analysis.beats_ms)})
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "INSERT OR REPLACE INTO remote_analysis VALUES (?, ?, ?, ?)",
                (str(media_key), version, time.time(), payload),
            )

    @staticmethod
    def _decode_payload(payload):
        value = json.loads(payload)
        value["beats_ms"] = tuple(value.get("beats_ms") or ())
        value["phrase_boundaries_ms"] = tuple(value.get("phrase_boundaries_ms") or ())
        value["section_boundaries_ms"] = tuple(value.get("section_boundaries_ms") or ())
        return value
