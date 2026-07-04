import os
import random
from collections.abc import Callable
from dataclasses import dataclass, field

from ..constants import REPEAT_MODES, REPEAT_OFF
from ..equalizer.models import DEFAULT_EQUALIZER_PRESET_ID
from .titles import build_playlist_title


TAB_TYPE_PLAYLIST = "playlist"
TAB_TYPE_FOLDER = "folder"
TAB_TYPE_SCREEN = "screen"


@dataclass
class ScreenTabState:
    title: str
    screen_id: str
    activation_message: str | None = None
    on_activate: Callable[[], None] | None = None
    on_close: Callable[[], None] | None = None
    persist_session: bool = False
    return_to_tab_index: int | None = None
    return_focus_mode: str | None = None
    tab_type: str = TAB_TYPE_SCREEN

    @property
    def is_empty(self):
        return False

    @property
    def is_folder_tab(self):
        return False

    @property
    def is_screen_tab(self):
        return True


@dataclass
class PlaylistState:
    title: str
    items: list[str] = field(default_factory=list)
    item_index_map: dict[str, int] = field(default_factory=dict)
    custom_queue: list[str] = field(default_factory=list)
    is_loading: bool = False
    loading_message: str | None = None
    library_request_serial: int = 0
    current_index: int = -1
    current_media_path: str | None = None
    last_position_ms: int = 0
    was_playing: bool = False
    source_path: str | None = None
    shuffle_enabled: bool = False
    repeat_mode: str = REPEAT_OFF
    playback_order: list[int] = field(default_factory=list)
    playback_order_position: int = 0
    tab_type: str = TAB_TYPE_PLAYLIST
    folder_root_path: str | None = None
    folder_current_path: str | None = None
    folder_selected_path: str | None = None
    folder_entries: list = field(default_factory=list)
    folder_entry_index_map: dict[str, int] = field(default_factory=dict)
    folder_entries_loaded: bool = False
    folder_entries_revision: int = 0
    browser_item_labels: list[str] = field(default_factory=list)
    items_revision: int = 0
    equalizer_enabled: bool = False
    equalizer_preset_id: str = DEFAULT_EQUALIZER_PRESET_ID

    @property
    def is_empty(self):
        return not self.is_folder_tab and not self.items and not self.current_media_path

    @property
    def is_folder_tab(self):
        return self.tab_type == TAB_TYPE_FOLDER

    @property
    def is_screen_tab(self):
        return False

    @property
    def item_count(self):
        return len(self.items)

    def clear(self):
        self.is_loading = False
        self.loading_message = None
        self.items = []
        self.item_index_map = {}
        self.custom_queue = []
        self.browser_item_labels = []
        self.items_revision += 1
        self.current_index = -1
        self.current_media_path = None
        self.last_position_ms = 0
        self.was_playing = False
        self.playback_order = []
        self.playback_order_position = 0

    def _fallback_browser_item_label(self, item):
        normalized_item = str(item or "")
        return os.path.basename(normalized_item) or normalized_item

    def _normalize_browser_item_labels(self, labels):
        labels_by_item = {}
        for item, label in zip(self.items, labels or []):
            normalized_label = str(label or "").strip()
            if normalized_label:
                labels_by_item.setdefault(item, []).append(normalized_label)

        normalized_labels = []
        for item in self.items:
            existing_labels = labels_by_item.get(item)
            if existing_labels:
                normalized_labels.append(existing_labels.pop(0))
            else:
                normalized_labels.append(self._fallback_browser_item_label(item))

        return normalized_labels

    def _apply_prepared_items(self, items, item_index_map, browser_item_labels):
        self.items = items if isinstance(items, list) else list(items)
        self.item_index_map = dict(item_index_map or {})
        self.browser_item_labels = self._normalize_browser_item_labels(browser_item_labels)
        self.items_revision += 1

    def refresh_browser_item_labels(self):
        self.item_index_map = {item: index for index, item in enumerate(self.items)}
        self.browser_item_labels = self._normalize_browser_item_labels(self.browser_item_labels)
        self.items_revision += 1

    def contains_item(self, media_path):
        return media_path in self.item_index_map

    def index_of_item(self, media_path):
        return self.item_index_map.get(media_path)

    def begin_library_load(self, message):
        self.is_loading = True
        self.loading_message = str(message or "").strip() or None

    def finish_library_load(self):
        self.is_loading = False
        self.loading_message = None

    def set_items(self, items, start_index=0, auto_select=True):
        normalized_items = list(items)
        self._apply_prepared_items(
            normalized_items,
            {item: index for index, item in enumerate(normalized_items)},
            [os.path.basename(item) or item for item in normalized_items],
        )
        if not self.items:
            self.current_index = -1
            self.current_media_path = None
            self.last_position_ms = 0
            self.was_playing = False
            self.playback_order = []
            self.playback_order_position = 0
            self.custom_queue = []
            return

        if auto_select:
            self.select_index(start_index)
        else:
            self.current_index = -1
            self.current_media_path = None
            self.last_position_ms = 0
            self.was_playing = False
            self.reset_playback_order(preferred_index=0)

    def append_items(self, new_items, new_labels=None):
        normalized_new_items = [str(item) for item in new_items if item]
        if not normalized_new_items:
            return

        combined_items = self.items + normalized_new_items
        combined_labels = list(self.browser_item_labels) + [
            str(label or "").strip() or self._fallback_browser_item_label(item)
            for item, label in zip(normalized_new_items, list(new_labels or []) + [None] * len(normalized_new_items))
        ]
        self._apply_prepared_items(
            combined_items,
            {item: index for index, item in enumerate(combined_items)},
            combined_labels,
        )
        self.sync_playback_order()

    def enqueue_item(self, media_path, label=None):
        if not media_path:
            return False

        normalized_path = str(media_path)
        if normalized_path not in self.item_index_map:
            # Preserve the current shuffle order so appending a brand-new item
            # for the queue doesn't reshuffle everything still to play.
            preserved_order = list(self.playback_order) if self.shuffle_enabled else None
            self.append_items([normalized_path], [label])
            if preserved_order is not None:
                new_index = self.item_index_map.get(normalized_path)
                if new_index is not None and new_index not in preserved_order:
                    preserved_order.append(new_index)
                if len(preserved_order) == len(self.items):
                    self.playback_order = preserved_order
                    if self.current_index in preserved_order:
                        self.playback_order_position = preserved_order.index(self.current_index)

        if normalized_path not in self.item_index_map:
            return False
        if normalized_path in self.custom_queue:
            return False

        self.custom_queue.append(normalized_path)
        return True

    def dequeue_item(self, media_path):
        normalized_path = str(media_path)
        if normalized_path not in self.custom_queue:
            return False
        self.custom_queue = [path for path in self.custom_queue if path != normalized_path]
        return True

    def is_queued(self, media_path):
        return str(media_path) in self.custom_queue

    def clear_queue(self):
        had_entries = bool(self.custom_queue)
        self.custom_queue = []
        return had_entries

    def queue_paths(self):
        # Only surface entries that still resolve to a playlist item; stale
        # paths (removed meanwhile) are dropped so the manager never lists them.
        resolved = [path for path in self.custom_queue if path in self.item_index_map]
        if len(resolved) != len(self.custom_queue):
            self.custom_queue = resolved
        return list(resolved)

    def remove_queue_entry(self, position):
        self.queue_paths()
        if not 0 <= position < len(self.custom_queue):
            return None
        return self.custom_queue.pop(position)

    def move_queue_entry(self, position, direction):
        self.queue_paths()
        if not 0 <= position < len(self.custom_queue):
            return None
        target = position + (1 if direction > 0 else -1)
        if not 0 <= target < len(self.custom_queue):
            return None
        self.custom_queue[position], self.custom_queue[target] = (
            self.custom_queue[target],
            self.custom_queue[position],
        )
        return target

    def set_items_prepared(self, items, item_index_map, browser_item_labels, start_index=0, auto_select=True):
        self._apply_prepared_items(items, item_index_map, browser_item_labels)
        if not self.items:
            self.current_index = -1
            self.current_media_path = None
            self.last_position_ms = 0
            self.was_playing = False
            self.playback_order = []
            self.playback_order_position = 0
            self.custom_queue = []
            return

        if auto_select:
            self.select_index(start_index)
        else:
            self.current_index = -1
            self.current_media_path = None
            self.last_position_ms = 0
            self.was_playing = False
            self.reset_playback_order(preferred_index=0)

    def set_folder_location(self, root_path, current_path=None, selected_path=None):
        normalized_root_path = os.path.abspath(os.path.normpath(str(root_path or "")))
        normalized_current_path = current_path or normalized_root_path
        normalized_current_path = os.path.abspath(os.path.normpath(str(normalized_current_path or normalized_root_path)))

        self.tab_type = TAB_TYPE_FOLDER
        self.folder_root_path = normalized_root_path
        self.folder_current_path = normalized_current_path
        self.folder_selected_path = str(selected_path or "").strip() or None
        self.folder_entries = []
        self.folder_entry_index_map = {}
        self.folder_entries_loaded = False
        self.folder_entries_revision += 1

    def clear_folder_location(self):
        self.tab_type = TAB_TYPE_PLAYLIST
        self.folder_root_path = None
        self.folder_current_path = None
        self.folder_selected_path = None
        self.folder_entries = []
        self.folder_entry_index_map = {}
        self.folder_entries_loaded = False
        self.folder_entries_revision += 1

    def set_folder_entries(self, entries, entry_index_map=None):
        self.folder_entries = entries if isinstance(entries, list) else list(entries)
        self.folder_entry_index_map = dict(entry_index_map or {})
        self.folder_entries_loaded = True
        self.folder_entries_revision += 1

    def set_current_media_path(self, media_path):
        media_index = self.index_of_item(media_path)
        if not self.items or media_index is None:
            self.current_index = -1
            self.current_media_path = None
            self.last_position_ms = 0
            self.was_playing = False
            self.sync_playback_order()
            return None

        return self.select_index(media_index)

    def select_index(self, index, reset_playback_order=True):
        if not self.items:
            self.clear()
            return None

        bounded_index = max(0, min(index, len(self.items) - 1))
        self.current_index = bounded_index
        self.current_media_path = self.items[bounded_index]
        self.last_position_ms = 0

        if reset_playback_order:
            self.reset_playback_order(preferred_index=bounded_index)
        else:
            self.sync_playback_order()

        return self.current_media_path

    def current_item_name(self):
        if not self.current_media_path:
            return None
        return os.path.basename(self.current_media_path)

    def has_next(self):
        return self.current_index + 1 < len(self.items)

    def has_previous(self):
        return self.current_index > 0

    def move_next(self):
        return self.move_in_playback_order(1)

    def move_previous(self):
        return self.move_in_playback_order(-1)

    def peek_in_playback_order(self, direction, wrap=False):
        if not self.items:
            return None

        self.sync_playback_order()

        if direction > 0:
            for queued_path in self.custom_queue:
                if queued_path in self.item_index_map:
                    return queued_path

        if not self.shuffle_enabled:
            target_index = self.current_index + direction
            if 0 <= target_index < len(self.items):
                return self.items[target_index]

            if not wrap:
                return None

            if direction < 0:
                return self.items[-1]
            return self.items[0]

        target_position = self.playback_order_position + direction
        if 0 <= target_position < len(self.playback_order):
            return self.items[self.playback_order[target_position]]

        if not wrap or not self.playback_order:
            return None

        if direction < 0:
            return self.items[self.playback_order[-1]]

        return None

    def reset_playback_order(self, preferred_index=None, anchor_current=True):
        if not self.items:
            self.playback_order = []
            self.playback_order_position = 0
            return

        if preferred_index is None or not 0 <= preferred_index < len(self.items):
            preferred_index = self.current_index if 0 <= self.current_index < len(self.items) else 0

        if not self.shuffle_enabled:
            self.playback_order = list(range(len(self.items)))
            self.playback_order_position = preferred_index
            return

        ordered_indices = list(range(len(self.items)))
        if anchor_current and preferred_index in ordered_indices:
            ordered_indices.remove(preferred_index)
            random.shuffle(ordered_indices)
            ordered_indices.insert(0, preferred_index)
            self.playback_order = ordered_indices
            self.playback_order_position = 0
            return

        random.shuffle(ordered_indices)
        self.playback_order = ordered_indices
        self.playback_order_position = (
            ordered_indices.index(preferred_index) if preferred_index in ordered_indices else 0
        )

    def sync_playback_order(self):
        if not self.items:
            self.playback_order = []
            self.playback_order_position = 0
            return

        expected_indices = set(range(len(self.items)))
        current_indices = set(self.playback_order)

        if len(self.playback_order) != len(self.items) or current_indices != expected_indices:
            self.reset_playback_order(preferred_index=self.current_index)
            return

        if self.current_index in self.playback_order:
            self.playback_order_position = self.playback_order.index(self.current_index)

    def move_in_playback_order(self, direction, wrap=False):
        if not self.items:
            return None

        self.sync_playback_order()

        if direction > 0:
            while self.custom_queue:
                queued_path = self.custom_queue.pop(0)
                target_index = self.item_index_map.get(queued_path)
                if target_index is not None and 0 <= target_index < len(self.items):
                    return self.select_index(target_index, reset_playback_order=False)

        if not self.shuffle_enabled:
            target_index = self.current_index + direction
            if wrap:
                target_index %= len(self.items)
            elif not 0 <= target_index < len(self.items):
                return None

            return self.select_index(target_index, reset_playback_order=False)

        target_position = self.playback_order_position + direction
        if 0 <= target_position < len(self.playback_order):
            self.playback_order_position = target_position
            return self.select_index(self.playback_order[target_position], reset_playback_order=False)

        if not wrap:
            return None

        if direction < 0:
            self.playback_order_position = len(self.playback_order) - 1
            return self.select_index(self.playback_order[self.playback_order_position], reset_playback_order=False)

        self.reset_playback_order(preferred_index=self.current_index, anchor_current=False)
        if not self.playback_order:
            return None

        self.playback_order_position = 0
        return self.select_index(self.playback_order[0], reset_playback_order=False)

    def to_dict(self):
        return {
            "title": self.title,
            "items": list(self.items),
            "custom_queue": list(self.custom_queue),
            "browser_item_labels": list(self.browser_item_labels),
            "current_index": self.current_index,
            "current_media_path": self.current_media_path,
            "last_position_ms": self.last_position_ms,
            "was_playing": self.was_playing,
            "source_path": self.source_path,
            "shuffle_enabled": self.shuffle_enabled,
            "repeat_mode": self.repeat_mode,
            "tab_type": self.tab_type,
            "folder_root_path": self.folder_root_path,
            "folder_current_path": self.folder_current_path,
            "folder_selected_path": self.folder_selected_path,
            "equalizer_enabled": self.equalizer_enabled,
            "equalizer_preset_id": self.equalizer_preset_id,
        }

    @classmethod
    def from_dict(cls, data):
        items = [str(item) for item in data.get("items", []) if item]
        title = str(data.get("title") or build_playlist_title(items))
        state = cls(title=title)
        state.items = items
        
        raw_queue = data.get("custom_queue", [])
        item_set = set(items)
        state.custom_queue = [str(path) for path in raw_queue if path and str(path) in item_set]

        raw_browser_item_labels = data.get("browser_item_labels")
        if isinstance(raw_browser_item_labels, list):
            state.browser_item_labels = [str(label or "") for label in raw_browser_item_labels]
        state.refresh_browser_item_labels()
        state.source_path = data.get("source_path")
        state.shuffle_enabled = bool(data.get("shuffle_enabled", False))
        tab_type = data.get("tab_type", TAB_TYPE_PLAYLIST)
        state.tab_type = tab_type if tab_type in {TAB_TYPE_PLAYLIST, TAB_TYPE_FOLDER} else TAB_TYPE_PLAYLIST
        state.folder_root_path = data.get("folder_root_path") or None
        state.folder_current_path = data.get("folder_current_path") or None
        state.folder_selected_path = data.get("folder_selected_path") or None
        state.equalizer_enabled = bool(data.get("equalizer_enabled", False))
        state.equalizer_preset_id = str(data.get("equalizer_preset_id") or DEFAULT_EQUALIZER_PRESET_ID)

        repeat_mode = data.get("repeat_mode", REPEAT_OFF)
        state.repeat_mode = repeat_mode if repeat_mode in REPEAT_MODES else REPEAT_OFF

        current_media_path = data.get("current_media_path")
        current_index = data.get("current_index", -1)

        if items:
            if current_media_path in items:
                state.current_index = items.index(current_media_path)
                state.current_media_path = current_media_path
            elif isinstance(current_index, int) and 0 <= current_index < len(items):
                state.current_index = current_index
                state.current_media_path = items[current_index]
            else:
                state.current_index = 0
                state.current_media_path = items[0]
        else:
            state.current_index = -1
            state.current_media_path = None

        try:
            state.last_position_ms = max(0, int(data.get("last_position_ms", 0)))
        except (TypeError, ValueError):
            state.last_position_ms = 0

        state.was_playing = bool(data.get("was_playing", False))
        state.reset_playback_order(preferred_index=state.current_index if state.current_index >= 0 else 0)
        return state