"""As notificações do YouTube que o KeyTune já avisou, guardadas entre uma execução e outra.

Sem isto, cada vez que o KeyTune abre ele avisaria de novo as mesmas notificações
não lidas, ou deixaria de avisar as que chegaram com ele fechado.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading

from ..log import get_logger
from ..session import get_app_storage_dir


_logger = get_logger(__name__)

NOTIFICATIONS_FILE_NAME = "youtube_notifications.json"
MAX_SEEN_NOTIFICATIONS = 500
# Quantas contas o arquivo guarda; a que ficou mais tempo sem uso sai.
MAX_ACCOUNTS = 5
# Os cookies que identificam a conta e não mudam enquanto ela está conectada; os outros
# (SIDCC, PSIDTS...) são renovados o tempo todo.
_STABLE_ACCOUNT_COOKIES = ("SAPISID", "__Secure-3PAPISID", "__Secure-1PAPISID")


class _AccountNotifications:
    """O que já foi avisado de uma conta; vê o arquivo pelo ``YouTubeNotificationStore``."""

    def __init__(self, store, scope):
        self._store = store
        self._scope = scope

    @property
    def has_baseline(self):
        return self._store.has_baseline_for(self._scope)

    def seen_ids(self):
        return self._store.seen_ids_for(self._scope)

    def remember(self, notification_ids):
        self._store.remember_for(self._scope, notification_ids)


class YouTubeNotificationStore:
    """Os ids já avisados, separados por conta: trocar de conta não mistura nem reavisa as do outro."""

    def __init__(self, path=None):
        self.path = str(path or os.path.join(get_app_storage_dir(), NOTIFICATIONS_FILE_NAME))
        self._lock = threading.RLock()
        # Por conta (``scope``); sem arquivo ainda, a primeira consulta só toma nota do que há.
        self._seen = {}
        self._load()

    def scoped(self, scope):
        """O que se sabe da conta *scope* (veja :func:`account_scope`)."""
        return _AccountNotifications(self, str(scope or ""))

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as notifications_file:
                payload = json.load(notifications_file)
        except FileNotFoundError:
            return
        except (OSError, json.JSONDecodeError) as exc:
            _logger.warning("Failed to load the seen YouTube notifications from %s: %s", self.path, exc)
            return
        if not isinstance(payload, dict):
            return
        accounts = payload.get("accounts")
        if not isinstance(accounts, dict) and isinstance(payload.get("seen"), list):
            # O formato de antes de haver contas: valeu para a conta única do escopo vazio.
            accounts = {"": payload["seen"]}
        for scope, ids in (accounts or {}).items():
            if isinstance(ids, list):
                self._seen[str(scope)] = [str(value) for value in ids if str(value or "").strip()]

    # O escopo vazio é o das chamadas sem conta: ``store.remember(...)`` vale para ele.
    @property
    def has_baseline(self):
        return self.has_baseline_for("")

    def seen_ids(self):
        return self.seen_ids_for("")

    def remember(self, notification_ids):
        self.remember_for("", notification_ids)

    def has_baseline_for(self, scope):
        with self._lock:
            return scope in self._seen

    def seen_ids_for(self, scope):
        with self._lock:
            return set(self._seen.get(scope, ()))

    def remember_for(self, scope, notification_ids):
        """Toma nota de *notification_ids* como já avisadas para a conta *scope*."""
        with self._lock:
            current = self._seen.get(scope)
            known = set(current or ())
            new_ids = [str(value) for value in notification_ids if str(value) not in known]
            if not new_ids and current is not None:
                return
            # A conta em uso vai para o fim; passando do limite, a mais antiga sai.
            self._seen.pop(scope, None)
            self._seen[scope] = ((current or []) + new_ids)[-MAX_SEEN_NOTIFICATIONS:]
            while len(self._seen) > MAX_ACCOUNTS:
                del self._seen[next(iter(self._seen))]
            self._save()

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as notifications_file:
                json.dump({"accounts": self._seen}, notifications_file)
        except OSError as exc:
            _logger.warning("Failed to save the seen YouTube notifications to %s: %s", self.path, exc)


def account_scope(cookie_header, account_index=0):
    """Um nome estável para a conta dos cookies, sem guardar o cookie."""
    cookie_header = str(cookie_header or "").strip()
    if not cookie_header:
        return ""
    identity = cookie_header
    cookies = dict(part.strip().split("=", 1) for part in cookie_header.split(";") if "=" in part)
    for name in _STABLE_ACCOUNT_COOKIES:
        if cookies.get(name):
            # Os cookies renovados não mudam o nome: a conta segue a mesma.
            identity = cookies[name]
            break
    digest = hashlib.sha256(f"{account_index}|{identity}".encode("utf-8")).hexdigest()
    return digest[:16]
