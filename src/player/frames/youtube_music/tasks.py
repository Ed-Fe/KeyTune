from ...i18n import _
import sys
import threading

import wx

from player.youtube_music.auth import sanitize_sensitive_text


class BackgroundTaskMixin:
    _YOUTUBE_MUSIC_BACKGROUND_TASK_TIMEOUT_MS = 45000

    def _format_youtube_music_error_detail(self, error):
        normalized_error_detail = sanitize_sensitive_text(error, max_length=2000)
        if normalized_error_detail:
            return normalized_error_detail
        return "Falha desconhecida."

    def _is_youtube_music_operation_in_progress(self):
        return bool(getattr(self, "_youtube_music_operation_in_progress", False))

    def _is_track_navigation_blocked_by_youtube_music(self):
        return self._is_youtube_music_operation_in_progress()

    def _announce_track_navigation_blocked_by_youtube_music(self):
        self._announce(
            "Aguarde o término da operação do YouTube Music antes de ir para a faixa anterior ou próxima."
        )

    def _play_windows_youtube_music_blocked_sound(self):
        if not sys.platform.startswith("win"):
            return

        try:
            import winsound

            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass

    def _block_sensitive_action_during_youtube_music(self, action_kind):
        if not self._is_youtube_music_operation_in_progress():
            return False

        messages = {
            "track-navigation": _(
                "Aguarde o término da operação do YouTube Music antes de ir para a faixa anterior ou próxima."
            ),
            "track-selection": _(
                "Aguarde o término da operação do YouTube Music antes de trocar a faixa atual."
            ),
            "playback-order": _(
                "Aguarde o término da operação do YouTube Music antes de alterar repetição, embaralhamento ou a ordem da playlist."
            ),
            "close-media": _(
                "Aguarde o término da operação do YouTube Music antes de fechar ou remover a mídia atual."
            ),
        }

        if action_kind == "track-navigation":
            self._play_windows_youtube_music_blocked_sound()

        self._announce(messages.get(action_kind, _("Aguarde o término da operação do YouTube Music.")))
        return True

    def _set_youtube_music_operation_state(self, in_progress):
        self._youtube_music_operation_in_progress = bool(in_progress)
        self._refresh_youtube_music_menu_state()

    def _on_youtube_music_screen_closed(self):
        # When the user closes the YouTube Music tab while a background task
        # is still in flight (e.g. library refresh, search, save), detach it:
        # the worker thread will run to completion but its result is ignored
        # because the active task id no longer matches. This prevents the
        # busy cursor and the global "operation in progress" lock (which
        # blocks track navigation, shuffle/repeat and Stop) from staying
        # active until the watchdog timeout fires.
        if not getattr(self, "_youtube_music_operation_in_progress", False):
            return
        self._youtube_music_active_task_id = None
        self._cancel_youtube_music_task_watchdog()
        self._end_youtube_music_busy_state()

    def _cancel_youtube_music_task_watchdog(self):
        watchdog = getattr(self, "_youtube_music_task_watchdog", None)
        self._youtube_music_task_watchdog = None
        if watchdog is not None:
            try:
                watchdog.Stop()
            except Exception:
                pass

    def _begin_youtube_music_busy_state(self):
        started = False
        if not wx.IsBusy():
            wx.BeginBusyCursor()
            started = True
        self._youtube_music_busy_cursor_started = started
        self._set_youtube_music_operation_state(True)

    def _end_youtube_music_busy_state(self):
        started = bool(getattr(self, "_youtube_music_busy_cursor_started", False))
        self._youtube_music_busy_cursor_started = False
        if started and wx.IsBusy():
            wx.EndBusyCursor()
        self._set_youtube_music_operation_state(False)

    def _run_youtube_music_background_task(self, worker, on_success, *, on_error=None):
        if getattr(self, "_youtube_music_operation_in_progress", False):
            self._announce(_("O YouTube Music já está processando uma solicitação. Aguarde um momento."))
            return False

        self._begin_youtube_music_busy_state()
        task_id = int(getattr(self, "_youtube_music_task_sequence", 0)) + 1
        self._youtube_music_task_sequence = task_id
        self._youtube_music_active_task_id = task_id
        self._cancel_youtube_music_task_watchdog()
        self._youtube_music_task_watchdog = wx.CallLater(
            self._YOUTUBE_MUSIC_BACKGROUND_TASK_TIMEOUT_MS,
            self._handle_youtube_music_background_task_timeout,
            task_id,
        )

        def runner():
            try:
                result = worker()
            except Exception as exc:
                wx.CallAfter(self._finish_youtube_music_background_task, task_id, on_success, on_error, None, exc)
                return

            wx.CallAfter(self._finish_youtube_music_background_task, task_id, on_success, on_error, result, None)

        threading.Thread(target=runner, daemon=True).start()
        return True

    def _handle_youtube_music_background_task_timeout(self, task_id):
        if task_id != getattr(self, "_youtube_music_active_task_id", None):
            return

        self._youtube_music_active_task_id = None
        self._cancel_youtube_music_task_watchdog()
        self._end_youtube_music_busy_state()
        self._announce(
            "A operação do YouTube Music demorou mais do que o esperado e foi cancelada para evitar travamento."
        )
        self._drain_youtube_music_pending_callbacks()

    def _finish_youtube_music_background_task(self, task_id, on_success, on_error, result, error):
        if task_id != getattr(self, "_youtube_music_active_task_id", None):
            return

        self._youtube_music_active_task_id = None
        self._cancel_youtube_music_task_watchdog()
        self._end_youtube_music_busy_state()
        try:
            if error is not None:
                if callable(on_error):
                    on_error(error)
                return

            if callable(on_success):
                on_success(result)
        finally:
            self._drain_youtube_music_pending_callbacks()

    def _queue_youtube_music_post_operation_callback(self, callback):
        if not callable(callback):
            return
        pending = getattr(self, "_youtube_music_pending_post_operation_callbacks", None)
        if pending is None:
            pending = []
            self._youtube_music_pending_post_operation_callbacks = pending
        # Avoid stacking duplicates of the same bound method.
        for existing in pending:
            if existing == callback:
                return
        pending.append(callback)

    def _drain_youtube_music_pending_callbacks(self):
        pending = getattr(self, "_youtube_music_pending_post_operation_callbacks", None)
        if not pending:
            return
        # Snapshot and clear before invoking so callbacks that re-enqueue
        # themselves (e.g. because another task started in the meantime)
        # don't get dropped.
        callbacks = list(pending)
        self._youtube_music_pending_post_operation_callbacks = []
        for callback in callbacks:
            try:
                callback()
            except Exception:
                continue
