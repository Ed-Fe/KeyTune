"""Histórico local de reprodução: registro e caixa de consulta.

Uma faixa entra no histórico depois de tocar o suficiente para contar como
ouvida — não basta abrir e pular. O critério é o mesmo usado para o histórico
do YouTube Music: um mínimo absoluto ou uma fração da duração, o que vier antes.
"""

import wx

from ...constants import (
    SMART_LIBRARY_HISTORY_MINIMUM_MS,
    SMART_LIBRARY_HISTORY_PROGRESS_FRACTION,
)
from ...i18n import _
from ...smart_library import HISTORY_ACTION_ENQUEUE, PlaybackHistoryDialog


class SmartLibraryHistoryMixin:
    def _library_history_threshold_ms(self, total_time_ms):
        try:
            normalized_total_time_ms = int(total_time_ms or 0)
        except (TypeError, ValueError):
            normalized_total_time_ms = 0

        if normalized_total_time_ms <= 0:
            return SMART_LIBRARY_HISTORY_MINIMUM_MS

        fraction_threshold_ms = int(round(normalized_total_time_ms * SMART_LIBRARY_HISTORY_PROGRESS_FRACTION))
        return min(SMART_LIBRARY_HISTORY_MINIMUM_MS, max(1, fraction_threshold_ms))

    def _maybe_record_library_history(self, media_path, position_ms, duration_ms):
        """Registra a reprodução atual quando ela cruza o limiar. Uma vez só."""
        if not getattr(self.settings, "smart_library_history_enabled", True):
            return False

        service = self._smart_library()
        if service is None:
            return False

        tracking_state = getattr(self, "_smart_library_playback_tracking", None)
        if not tracking_state or tracking_state.get("history_recorded"):
            return False

        if position_ms < self._library_history_threshold_ms(duration_ms):
            return False

        tracking_state["history_recorded"] = True
        service.record_playback(
            media_path,
            label=self._smart_library_label_for(media_path),
            position_ms=position_ms,
            duration_ms=duration_ms,
            source=self._smart_library_media_source(media_path),
            limit=getattr(self.settings, "smart_library_history_limit", 500),
        )
        return True

    def _remove_history_entry(self, entry, grouped):
        """Remove uma reprodução, ou todas as da mídia nos modos agrupados."""
        service = self._smart_library()
        if service is None:
            return False

        if grouped:
            return service.remove_history_for_media(entry.media_path)

        return service.remove_history_entry(entry.entry_id)

    def _open_playback_history_dialog(self):
        service = self._smart_library()
        if service is None:
            self._announce_smart_library_unavailable()
            return

        history_limit = getattr(self.settings, "smart_library_history_limit", 500)
        dialog = PlaybackHistoryDialog(
            self,
            history_provider=lambda view, query: service.history_for_view(
                view, limit=history_limit, query=query
            ),
            on_remove=self._remove_history_entry,
            on_clear=service.clear_history,
            announce=self._announce,
        )
        try:
            confirmed = dialog.ShowModal() == wx.ID_OK
            selected_entry = dialog.get_selected_entry() if confirmed else None
            action = dialog.get_chosen_action()
        finally:
            dialog.Destroy()

        if selected_entry is None:
            return

        if action == HISTORY_ACTION_ENQUEUE:
            self._enqueue_library_media(selected_entry.media_path, selected_entry.display_label)
            return

        self._open_prepared_media_playlist(
            [selected_entry.media_path],
            selected_entry.display_label,
            browser_item_labels=[selected_entry.display_label],
        )

    def _clear_playback_history(self):
        service = self._smart_library()
        if service is None:
            self._announce_smart_library_unavailable()
            return

        with wx.MessageDialog(
            self,
            _("Deseja apagar todo o histórico de reprodução?"),
            _("Limpar histórico"),
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
        ) as confirmation:
            if confirmation.ShowModal() != wx.ID_YES:
                return

        if service.clear_history():
            self._announce(_("Histórico de reprodução apagado."))
        else:
            self._announce(_("Não foi possível limpar o histórico."))

    def on_open_playback_history(self, _event):
        self._open_playback_history_dialog()

    def on_clear_playback_history(self, _event):
        self._clear_playback_history()
