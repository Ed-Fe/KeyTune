"""As notificações do YouTube que o KeyTune já avisou, guardadas entre uma execução e outra.

Sem isto, cada vez que o KeyTune abre ele avisaria de novo as mesmas notificações
não lidas, ou deixaria de avisar as que chegaram com ele fechado.
"""

from __future__ import annotations

import json
import os
import threading

from ..log import get_logger
from ..session import get_app_storage_dir


_logger = get_logger(__name__)

NOTIFICATIONS_FILE_NAME = "youtube_notifications.json"
MAX_SEEN_NOTIFICATIONS = 500


class YouTubeNotificationStore:
    def __init__(self, path=None):
        self.path = str(path or os.path.join(get_app_storage_dir(), NOTIFICATIONS_FILE_NAME))
        self._lock = threading.RLock()
        self._seen_ids = []
        # Sem arquivo ainda: a primeira consulta só toma nota do que há, sem avisar nada.
        self.has_baseline = False
        self._load()

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as notifications_file:
                payload = json.load(notifications_file)
        except FileNotFoundError:
            return
        except (OSError, json.JSONDecodeError) as exc:
            _logger.warning("Failed to load the seen YouTube notifications from %s: %s", self.path, exc)
            return
        if not isinstance(payload, dict) or not isinstance(payload.get("seen"), list):
            return
        self._seen_ids = [str(value) for value in payload["seen"] if str(value or "").strip()]
        self.has_baseline = True

    def seen_ids(self):
        with self._lock:
            return set(self._seen_ids)

    def remember(self, notification_ids):
        """Toma nota de *notification_ids* como já avisadas."""
        with self._lock:
            known = set(self._seen_ids)
            new_ids = [str(value) for value in notification_ids if str(value) not in known]
            if not new_ids and self.has_baseline:
                return
            self._seen_ids = (self._seen_ids + new_ids)[-MAX_SEEN_NOTIFICATIONS:]
            self.has_baseline = True
            self._save()

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as notifications_file:
                json.dump({"seen": self._seen_ids}, notifications_file)
        except OSError as exc:
            _logger.warning("Failed to save the seen YouTube notifications to %s: %s", self.path, exc)
