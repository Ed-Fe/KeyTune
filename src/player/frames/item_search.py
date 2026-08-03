import wx

from ..i18n import _
from ..library import ItemSearchDialog, normalize_search_text


class FrameItemSearchMixin:
    """Busca dentro da playlist ou pasta ativa (Ctrl+F, F3, Shift+F3).

    A busca opera sobre os rótulos que o navegador de itens já exibe, então
    funciona igual em playlists locais, pastas e listas do YouTube Music. O
    texto procurado fica guardado na sessão para que F3/Shift+F3 repitam a
    busca sem reabrir a caixa.
    """

    def _item_search_browser(self):
        browser = self._get_browser_panel()
        if browser is None or not browser.has_searchable_items():
            return None
        return browser

    def _item_search_context_label(self):
        state = self._get_playlist_state()
        if state is None:
            return _("Localiza itens da lista ativa.")

        if getattr(state, "is_folder_tab", False):
            return _("Localiza itens da pasta aberta em {title}.").format(title=state.title)

        return _("Localiza itens da playlist {title}.").format(title=state.title)

    def _current_item_search_query(self):
        return str(getattr(self, "_item_search_query", "") or "")

    def _announce_no_item_search_target(self):
        self._announce(_("Não há itens para localizar nesta aba."))

    def _open_item_search_dialog(self):
        browser = self._item_search_browser()
        if browser is None:
            self._announce_no_item_search_target()
            return

        dialog = ItemSearchDialog(
            self,
            initial_query=self._current_item_search_query(),
            context_label=self._item_search_context_label(),
        )
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            query = dialog.get_query()
        finally:
            dialog.Destroy()

        if not query:
            self._announce(_("Digite um texto para localizar."))
            return

        self._item_search_query = query
        self._run_item_search(1, include_current=True)

    def _repeat_item_search(self, direction):
        if not self._current_item_search_query():
            self._open_item_search_dialog()
            return

        if self._item_search_browser() is None:
            self._announce_no_item_search_target()
            return

        self._run_item_search(direction)

    def _item_search_matches(self, browser):
        needle = normalize_search_text(self._current_item_search_query())
        if not needle:
            return []
        return [
            index
            for index, label in enumerate(browser.search_labels())
            if needle in normalize_search_text(label)
        ]

    def _run_item_search(self, direction, include_current=False):
        browser = self._item_search_browser()
        if browser is None:
            self._announce_no_item_search_target()
            return False

        query = self._current_item_search_query()
        matches = self._item_search_matches(browser)
        if not matches:
            message = _('Nenhum item corresponde a "{query}".').format(query=query)
            self._announce(message)
            if hasattr(self, "_set_status_message"):
                self._set_status_message(message)
            return False

        labels = browser.search_labels()
        item_count = len(labels)
        start_index = browser.get_selected_index()
        if start_index == wx.NOT_FOUND or not 0 <= start_index < item_count:
            start_index = 0 if direction > 0 else item_count - 1
            include_current = True

        match_set = set(matches)
        first_offset = 0 if include_current else 1
        target_index = None
        for offset in range(first_offset, item_count + first_offset):
            candidate_index = (start_index + direction * offset) % item_count
            if candidate_index in match_set:
                target_index = candidate_index
                break

        if target_index is None:
            return False

        wrapped = (direction > 0 and target_index < start_index) or (
            direction < 0 and target_index > start_index
        )

        if not browser.focus_search_result(target_index):
            return False

        # O resultado em si não é anunciado: mover a seleção já faz o leitor de
        # tela ler o item, e um anúncio nosso atropelaria essa leitura. A
        # posição na busca fica na barra de status.
        position = matches.index(target_index) + 1
        if hasattr(self, "_set_status_message"):
            if wrapped and direction > 0:
                template = _('Busca "{query}": resultado {position} de {total}, voltando ao início da lista.')
            elif wrapped:
                template = _('Busca "{query}": resultado {position} de {total}, voltando ao fim da lista.')
            else:
                template = _('Busca "{query}": resultado {position} de {total}.')
            self._set_status_message(
                template.format(query=query, position=position, total=len(matches))
            )
        return True

    def on_find_item(self, _event):
        self._open_item_search_dialog()

    def on_find_next_item(self, _event):
        self._repeat_item_search(1)

    def on_find_previous_item(self, _event):
        self._repeat_item_search(-1)
