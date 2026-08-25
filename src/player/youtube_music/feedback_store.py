import json
import os
import threading

from ..log import get_logger
from ..session import get_app_storage_dir


_logger = get_logger(__name__)

FEEDBACK_FILE_NAME = "youtube_music_feedback.json"
_DEFAULT_ACCOUNT_KEY = "__default__"


def _account_key(account_info):
    if not isinstance(account_info, dict):
        return ""

    handle = str(account_info.get("channelHandle") or "").strip().casefold()
    name = str(account_info.get("accountName") or "").strip().casefold()
    if handle:
        return f"handle:{handle}"
    if name:
        return f"name:{name}"
    return ""


class YouTubeMusicFeedbackStore:
    """Persistent, account-scoped cache of YouTube Music dislikes."""

    def __init__(self, path=None):
        self.path = str(path or os.path.join(get_app_storage_dir(), FEEDBACK_FILE_NAME))
        self._lock = threading.RLock()
        self._active_account = ""
        self._accounts = {}
        self._load()

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as feedback_file:
                payload = json.load(feedback_file)
        except FileNotFoundError:
            return
        except (OSError, json.JSONDecodeError) as exc:
            _logger.warning("Failed to load YouTube Music feedback cache from %s: %s", self.path, exc)
            return

        if not isinstance(payload, dict):
            return

        accounts = payload.get("accounts")
        if isinstance(accounts, dict):
            for account, values in accounts.items():
                if not isinstance(values, dict):
                    continue
                disliked = {
                    str(video_id or "").strip()
                    for video_id in values.get("disliked", [])
                    if str(video_id or "").strip()
                }
                self._accounts[str(account)] = disliked

        active_account = str(payload.get("active_account") or "").strip()
        if active_account:
            self._active_account = active_account

    def _save(self):
        parent_dir = os.path.dirname(self.path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        payload = {
            "version": 1,
            "active_account": self._active_account,
            "accounts": {
                account: {"disliked": sorted(video_ids)}
                for account, video_ids in sorted(self._accounts.items())
            },
        }
        temporary_path = self.path + ".tmp"
        try:
            with open(temporary_path, "w", encoding="utf-8") as feedback_file:
                json.dump(payload, feedback_file, ensure_ascii=False, indent=2)
            os.replace(temporary_path, self.path)
        except OSError as exc:
            _logger.warning("Failed to save YouTube Music feedback cache to %s: %s", self.path, exc)
            try:
                os.remove(temporary_path)
            except OSError:
                pass

    def set_active_account(self, account_info):
        account = _account_key(account_info)
        if not account:
            return False

        with self._lock:
            changed = account != self._active_account
            default_dislikes = self._accounts.pop(_DEFAULT_ACCOUNT_KEY, set())
            account_dislikes = self._accounts.setdefault(account, set())
            before_count = len(account_dislikes)
            account_dislikes.update(default_dislikes)
            changed = changed or len(account_dislikes) != before_count
            self._active_account = account
            if changed and any(self._accounts.values()):
                self._save()
        return True

    def clear_active_account(self):
        with self._lock:
            if not self._active_account:
                return
            self._active_account = ""
            self._save()

    def _current_account(self):
        return self._active_account or _DEFAULT_ACCOUNT_KEY

    def record(self, video_id, status):
        normalized_video_id = str(video_id or "").strip()
        normalized_status = str(status or "").strip().upper()
        if not normalized_video_id or normalized_status not in {"LIKE", "DISLIKE", "INDIFFERENT"}:
            return False

        with self._lock:
            disliked = self._accounts.setdefault(self._current_account(), set())
            was_disliked = normalized_video_id in disliked
            if normalized_status == "DISLIKE":
                disliked.add(normalized_video_id)
            else:
                disliked.discard(normalized_video_id)
            is_disliked = normalized_video_id in disliked
            if was_disliked != is_disliked and self._active_account:
                self._save()
        return True

    def ingest_items(self, items):
        changed = False
        with self._lock:
            disliked = self._accounts.setdefault(self._current_account(), set())
            for item in items or []:
                if isinstance(item, dict):
                    video_id = str(item.get("videoId") or "").strip()
                    status = str(item.get("likeStatus") or "").strip().upper()
                else:
                    video_id = str(getattr(item, "video_id", "") or "").strip()
                    status = str(getattr(item, "like_status", "") or "").strip().upper()
                if not video_id:
                    continue

                # Bulk responses have historically represented some dislikes
                # as INDIFFERENT. Only explicit LIKE/DISLIKE values are safe to
                # merge into the persistent account cache.
                if status == "DISLIKE" and video_id not in disliked:
                    disliked.add(video_id)
                    changed = True
                elif status == "LIKE" and video_id in disliked:
                    disliked.remove(video_id)
                    changed = True

            if changed and self._active_account:
                self._save()
        return changed

    def is_disliked(self, video_id):
        normalized_video_id = str(video_id or "").strip()
        if not normalized_video_id:
            return False
        with self._lock:
            return normalized_video_id in self._accounts.get(self._current_account(), set())

    def disliked_video_ids(self):
        with self._lock:
            return set(self._accounts.get(self._current_account(), set()))
