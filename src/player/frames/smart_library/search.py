"""Busca global na biblioteca (Ctrl+G) e atalhos para favoritos.

O resultado escolhido abre em uma playlist com todos os itens encontrados, com
a faixa selecionada tocando primeiro — assim uma busca vira uma lista utilizável
em vez de uma faixa solta.
"""

import wx

from ...i18n import _, ngettext
from ...smart_library import (
    SEARCH_RESULT_ACTION_ENQUEUE,
    SEARCH_SCOPE_ALL,
    GlobalSearchDialog,
)


class SmartLibrarySearchMixin:
    def _open_global_search_dialog(self):
        service = self._smart_library()
        if service is None:
            self._announce_smart_library_unavailable()
            return

        dialog = GlobalSearchDialog(
            self,
            search_provider=lambda query, scope: service.search(query, scope=scope),
            initial_query=getattr(self, "_smart_library_search_query", ""),
            library_summary=self._smart_library_summary_text(),
        )
        try:
            confirmed = dialog.ShowModal() == wx.ID_OK
            self._smart_library_search_query = str(dialog.query_text.GetValue() or "").strip()
            selected_record = dialog.get_selected_record() if confirmed else None
            results = dialog.get_results() if confirmed else []
            action = dialog.get_chosen_action()
        finally:
            dialog.Destroy()

        if selected_record is None:
            return

        if action == SEARCH_RESULT_ACTION_ENQUEUE:
            self._enqueue_library_media(selected_record.media_path, selected_record.display_label)
            return

        self._open_library_results_as_playlist(results, selected_record)

    def _open_library_results_as_playlist(self, records, selected_record):
        normalized_records = [record for record in (records or []) if record is not None]
        if not normalized_records:
            normalized_records = [selected_record]

        media_paths = [record.media_path for record in normalized_records]
        labels = [record.display_label for record in normalized_records]

        title = _("Busca: {query}").format(query=getattr(self, "_smart_library_search_query", "")).strip()
        if not getattr(self, "_smart_library_search_query", ""):
            title = _("Resultados da biblioteca")

        # A lista mantém a ordem dos resultados, mas quem começa a tocar é a
        # faixa que o usuário escolheu na caixa, não a primeira.
        try:
            start_index = media_paths.index(selected_record.media_path)
        except ValueError:
            start_index = 0

        self._open_prepared_media_playlist(
            media_paths,
            title,
            browser_item_labels=labels,
            start_index=start_index,
            announce_message=_("{count} resultados abertos em uma nova lista.").format(
                count=len(media_paths)
            ),
        )

    def _enqueue_library_media(self, media_path, label=""):
        state = self._get_active_playlist_state()
        if state is None:
            self._announce(_("Nenhuma playlist ativa para receber o item."))
            return False

        if not state.enqueue_item(media_path, label):
            self._announce(_("Este item já está na fila de reprodução."))
            return False

        self._refresh_playlist_browser()
        self._announce(_("{item} adicionado à fila de reprodução.").format(item=label or media_path))
        return True

    def _open_favorites_playlist(self):
        service = self._smart_library()
        if service is None:
            self._announce_smart_library_unavailable()
            return

        favorites = service.favorites()
        if not favorites:
            self._announce(_("Nenhum favorito ainda. Use Ctrl+D para marcar o item atual."))
            return

        self._open_prepared_media_playlist(
            [record.media_path for record in favorites],
            _("Favoritos"),
            browser_item_labels=[record.display_label for record in favorites],
            announce_message=ngettext(
                "{count} favorito aberto.",
                "{count} favoritos abertos.",
                len(favorites),
            ).format(count=len(favorites)),
        )

    def on_search_library(self, _event):
        self._open_global_search_dialog()

    def on_open_favorites(self, _event):
        self._open_favorites_playlist()
