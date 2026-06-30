import os
import queue
import threading

import wx

from ..library import (
    discover_folder_entries,
    is_remote_media_path,
    load_playlist,
    scan_folder_contents,
)
from ..i18n import _
from ..log import get_logger
from ..playlists import PlaylistState, build_folder_tab_title


_logger = get_logger(__name__)


class FrameLibraryLoaderMixin:
    def _create_library_loader(self):
        self._library_request_serial = 0
        self._library_queue = queue.Queue()
        self._library_stop_event = threading.Event()
        self._library_worker = threading.Thread(target=self._library_worker_loop, daemon=True)
        self._library_worker.start()

    def _shutdown_library_loader(self):
        self._begin_library_loader_shutdown()
        self._finish_library_loader_shutdown()

    def _begin_library_loader_shutdown(self):
        stop_event = getattr(self, "_library_stop_event", None)
        if stop_event is not None:
            stop_event.set()

        if hasattr(self, "_library_queue"):
            self._library_queue.put({"kind": "shutdown"})

    def _finish_library_loader_shutdown(self):
        worker = getattr(self, "_library_worker", None)
        if worker is not None and worker.is_alive():
            worker.join(timeout=1.0)

    def _next_library_request_serial(self):
        self._library_request_serial += 1
        return self._library_request_serial

    def _queue_library_request(self, request):
        state = request.get("state")
        if not isinstance(state, PlaylistState):
            return None

        request_serial = self._next_library_request_serial()
        request["serial"] = request_serial
        state.library_request_serial = request_serial
        self._library_queue.put(request)
        return request_serial

    def _store_latest_library_request(self, pending_requests, request):
        state = request.get("state")
        request_key = id(state) if state is not None else (request.get("kind"), request.get("serial"))
        pending_requests[request_key] = request

    def _library_worker_loop(self):
        while True:
            request = self._library_queue.get()
            if request.get("kind") == "shutdown" or self._library_stop_event.is_set():
                return

            pending_requests = {}
            self._store_latest_library_request(pending_requests, request)
            while True:
                try:
                    newer_request = self._library_queue.get_nowait()
                except queue.Empty:
                    break

                if newer_request.get("kind") == "shutdown" or self._library_stop_event.is_set():
                    return

                self._store_latest_library_request(pending_requests, newer_request)

            for current_request in pending_requests.values():
                if self._library_stop_event.is_set():
                    return
                self._process_library_request(current_request)

    def _process_library_request(self, request):
        kind = request.get("kind")

        if kind == "folder":
            try:
                folder_entries, media_files = scan_folder_contents(request["folder_path"])
                media_item_index_map = {path: index for index, path in enumerate(media_files)}
                media_browser_labels = [os.path.basename(path) or path for path in media_files]
                folder_entry_index_map = {
                    os.path.normcase(os.path.normpath(getattr(entry, "path", ""))): index
                    for index, entry in enumerate(folder_entries)
                    if getattr(entry, "path", None)
                }
                error_message = ""
            except OSError as exc:
                folder_entries = []
                media_files = []
                media_item_index_map = {}
                media_browser_labels = []
                folder_entry_index_map = {}
                error_message = str(exc)
                _logger.warning("OS error loading folder %r: %s", request["folder_path"], exc)
            except Exception as exc:
                folder_entries = []
                media_files = []
                media_item_index_map = {}
                media_browser_labels = []
                folder_entry_index_map = {}
                error_message = f"Falha inesperada ao carregar a pasta: {exc}."
                _logger.error("Unexpected error loading folder %r: %s", request["folder_path"], exc, exc_info=True)

            if self._library_stop_event.is_set():
                return

            wx.CallAfter(
                self._finish_folder_load_request,
                request,
                folder_entries,
                folder_entry_index_map,
                media_files,
                media_item_index_map,
                media_browser_labels,
                error_message,
            )
            return

        if kind == "folder_playlist":
            try:
                _folder_entries, media_files = scan_folder_contents(request["folder_path"])
                item_index_map = {path: index for index, path in enumerate(media_files)}
                browser_item_labels = [os.path.basename(path) or path for path in media_files]
                error_message = ""
            except OSError as exc:
                media_files = []
                item_index_map = {}
                browser_item_labels = []
                error_message = str(exc)
                _logger.warning("OS error loading folder playlist %r: %s", request["folder_path"], exc)
            except Exception as exc:
                media_files = []
                item_index_map = {}
                browser_item_labels = []
                error_message = f"Falha inesperada ao carregar a pasta: {exc}."
                _logger.error("Unexpected error loading folder playlist %r: %s", request["folder_path"], exc, exc_info=True)

            if self._library_stop_event.is_set():
                return

            wx.CallAfter(
                self._finish_folder_playlist_load_request,
                request,
                media_files,
                item_index_map,
                browser_item_labels,
                error_message,
            )
            return

        if kind == "playlist":
            try:
                items = load_playlist(request["playlist_source"])
                item_index_map = {path: index for index, path in enumerate(items)}
                browser_item_labels = [os.path.basename(path) or path for path in items]
                error_message = ""
            except OSError as exc:
                items = []
                item_index_map = {}
                browser_item_labels = []
                error_message = str(exc)
            except Exception as exc:
                items = []
                item_index_map = {}
                browser_item_labels = []
                error_message = f"Falha inesperada ao carregar a playlist: {exc}."

            if self._library_stop_event.is_set():
                return

            wx.CallAfter(
                self._finish_playlist_load_request,
                request,
                items,
                item_index_map,
                browser_item_labels,
                error_message,
            )

    def _is_current_library_request(self, state, request_serial):
        if not isinstance(state, PlaylistState):
            return False

        if state.library_request_serial != request_serial:
            return False

        return self._resolve_playlist_state_index(state) != wx.NOT_FOUND

    def _begin_playlist_load(self, state, title):
        state.finish_library_load()
        state.clear_folder_location()
        state.title = title
        state.source_path = None
        state.set_items([], auto_select=False)
        state.begin_library_load("Carregando playlist...")

    def _begin_folder_load(self, state, folder_path, root_path=None, selected_path=None):
        normalized_root_path = self._normalize_path(root_path) if root_path else folder_path
        if not normalized_root_path:
            normalized_root_path = folder_path

        state.finish_library_load()
        state.set_folder_location(
            root_path=normalized_root_path,
            current_path=folder_path,
            selected_path=selected_path,
        )
        state.title = build_folder_tab_title(folder_path)
        state.source_path = None
        state.set_items([], auto_select=False)
        state.begin_library_load("Carregando itens da pasta...")

    def _finish_playlist_load_request(self, request, items, item_index_map, browser_item_labels, error_message):
        if self._library_stop_event.is_set():
            return

        state = request.get("state")
        request_serial = request.get("serial")
        if not self._is_current_library_request(state, request_serial):
            return

        state.finish_library_load()
        tab_index = self._resolve_playlist_state_index(state)
        if tab_index == wx.NOT_FOUND:
            return

        if error_message:
            state.title = request.get("previous_title") or state.title
            state.source_path = request.get("previous_source_path")
            state.set_items([], auto_select=False)
            self.notebook.SetPageText(tab_index, state.title)
            if self._is_current_playlist_state(state):
                self._update_title()
                self._refresh_playlist_browser()
            wx.MessageBox(error_message, _("Abrir playlist"), wx.OK | wx.ICON_ERROR, self)
            return

        if not items:
            state.title = request.get("previous_title") or state.title
            state.source_path = request.get("previous_source_path")
            state.set_items([], auto_select=False)
            self.notebook.SetPageText(tab_index, state.title)
            if self._is_current_playlist_state(state):
                self._update_title()
                self._refresh_playlist_browser()
            wx.MessageBox(
                _("Nenhum item válido foi encontrado na playlist selecionada."),
                _("Abrir playlist"),
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return

        state.title = request["title"]
        state.source_path = request["playlist_source"]
        state.set_items_prepared(items, item_index_map, browser_item_labels, start_index=0)
        self.notebook.SetPageText(tab_index, state.title)
        if not is_remote_media_path(request["playlist_source"]):
            self._add_recent_path("recent_playlists", request["playlist_source"])

        if self._is_current_playlist_state(state):
            self._play_media(
                index=tab_index,
                announce_message=_("Playlist carregada: {title}. {count} item(ns).").format(title=state.title, count=len(items)),
            )

    def _finish_folder_playlist_load_request(self, request, items, item_index_map, browser_item_labels, error_message):
        if self._library_stop_event.is_set():
            return

        state = request.get("state")
        request_serial = request.get("serial")
        if not self._is_current_library_request(state, request_serial):
            return

        state.finish_library_load()
        tab_index = self._resolve_playlist_state_index(state)
        if tab_index == wx.NOT_FOUND:
            return

        if error_message:
            state.title = request.get("previous_title") or state.title
            state.source_path = request.get("previous_source_path")
            state.set_items([], auto_select=False)
            self.notebook.SetPageText(tab_index, state.title)
            if self._is_current_playlist_state(state):
                self._update_title()
                self._refresh_playlist_browser()
            wx.MessageBox(error_message, _("Abrir pasta como playlist"), wx.OK | wx.ICON_ERROR, self)
            return

        if not items:
            state.title = request.get("previous_title") or state.title
            state.source_path = request.get("previous_source_path")
            state.set_items([], auto_select=False)
            self.notebook.SetPageText(tab_index, state.title)
            if self._is_current_playlist_state(state):
                self._update_title()
                self._refresh_playlist_browser()
            wx.MessageBox(
                _("Nenhuma mídia compatível foi encontrada na pasta selecionada."),
                _("Abrir pasta como playlist"),
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return

        state.title = request["title"]
        state.source_path = request["folder_path"]
        state.set_items_prepared(items, item_index_map, browser_item_labels, start_index=0)
        self.notebook.SetPageText(tab_index, state.title)

        if self._is_current_playlist_state(state):
            self._play_media(
                index=tab_index,
                announce_message=_("Pasta carregada como playlist: {title}. {count} item(ns).").format(title=state.title, count=len(items)),
            )

    def _finish_folder_load_request(
        self,
        request,
        folder_entries,
        folder_entry_index_map,
        media_files,
        media_item_index_map,
        media_browser_labels,
        error_message,
    ):
        if self._library_stop_event.is_set():
            return

        state = request.get("state")
        request_serial = request.get("serial")
        if not self._is_current_library_request(state, request_serial):
            return

        state.finish_library_load()
        state.set_folder_entries(folder_entries, entry_index_map=folder_entry_index_map)
        state.set_items_prepared(media_files, media_item_index_map, media_browser_labels, auto_select=False)

        tab_index = self._resolve_playlist_state_index(state)
        if tab_index == wx.NOT_FOUND:
            return

        self.notebook.SetPageText(tab_index, state.title)

        if error_message:
            if self._is_current_playlist_state(state):
                self._update_title()
                self._refresh_playlist_browser()
            self._announce(_("Não foi possível carregar a pasta selecionada: {error}.").format(error=error_message))
            return

        recent_path = request.get("recent_path")
        if recent_path:
            self._add_recent_path("recent_folders", recent_path)

        if self._is_current_playlist_state(state):
            self._update_title()
            self._refresh_playlist_browser()
            if request.get("focus_items"):
                browser = self._get_browser_panel(tab_index)
                if browser:
                    wx.CallAfter(browser.focus_current_item)

            completion_announcement = request.get("completion_announcement")
            if completion_announcement:
                wx.CallAfter(self._announce, completion_announcement)

    def _get_folder_entries(self, state=None):
        state = state or self._get_playlist_state()
        if not state or not state.is_folder_tab or not state.folder_current_path:
            return []

        if state.is_loading or state.folder_entries_loaded:
            return state.folder_entries

        try:
            entries = discover_folder_entries(state.folder_current_path)
        except OSError:
            entries = []

        state.set_folder_entries(entries)
        return state.folder_entries
