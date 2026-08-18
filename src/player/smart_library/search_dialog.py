"""Caixa de busca global da biblioteca (Ctrl+G).

Diferente do Ctrl+F, que percorre a lista aberta, esta busca varre tudo que já
foi indexado — playlists locais, pastas e o que já tocou. Os resultados ficam
em uma lista de relatório com colunas nomeadas, então o leitor de tela lê
título, avaliação e pasta ao percorrer com as setas.
"""

import wx

from ..accessibility import attach_named_accessible
from ..i18n import _, ngettext
from .models import (
    SEARCH_SCOPE_ALL,
    SEARCH_SCOPE_FAVORITES,
    SEARCH_SCOPE_HISTORY,
    SEARCH_SCOPE_RATED,
)


GLOBAL_SEARCH_DIALOG_TITLE = _("Buscar na biblioteca")

# Ação escolhida pelo usuário ao fechar a caixa.
SEARCH_RESULT_ACTION_PLAY = "play"
SEARCH_RESULT_ACTION_ENQUEUE = "enqueue"


def format_rating(rating):
    try:
        normalized_rating = int(rating or 0)
    except (TypeError, ValueError):
        normalized_rating = 0

    if normalized_rating <= 0:
        return _("sem avaliação")

    return ngettext("{count} estrela", "{count} estrelas", normalized_rating).format(count=normalized_rating)


def format_favorite(favorite):
    return _("favorito") if favorite else ""


class GlobalSearchDialog(wx.Dialog):
    def __init__(self, parent, search_provider, initial_query="", library_summary=""):
        super().__init__(
            parent,
            title=GLOBAL_SEARCH_DIALOG_TITLE,
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self._search_provider = search_provider
        self._results = []
        self._chosen_action = SEARCH_RESULT_ACTION_PLAY

        self._scope_values = (
            SEARCH_SCOPE_ALL,
            SEARCH_SCOPE_FAVORITES,
            SEARCH_SCOPE_RATED,
            SEARCH_SCOPE_HISTORY,
        )
        scope_labels = [
            _("Tudo na biblioteca"),
            _("Somente favoritos"),
            _("Somente avaliados"),
            _("Somente já reproduzidos"),
        ]

        root_sizer = wx.BoxSizer(wx.VERTICAL)

        description = wx.StaticText(
            self,
            label=library_summary or _("Procura em tudo que já foi indexado na biblioteca."),
        )
        description.Wrap(520)

        query_label = wx.StaticText(self, label=_("&Procurar por"))
        self.query_text = wx.TextCtrl(self, value=str(initial_query or ""), style=wx.TE_PROCESS_ENTER)
        self.query_text.SetName(_("Texto a procurar"))

        scope_label = wx.StaticText(self, label=_("&Filtrar"))
        self.scope_choice = wx.Choice(self, choices=scope_labels)
        self.scope_choice.SetSelection(0)
        self.scope_choice.SetName(_("Filtro da busca"))

        self.results_list = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.results_list.InsertColumn(0, _("Item"), width=260)
        self.results_list.InsertColumn(1, _("Avaliação"), width=110)
        self.results_list.InsertColumn(2, _("Pasta"), width=240)
        self.results_list.SetName(_("Resultados da busca"))
        attach_named_accessible(
            self.results_list,
            name=_("Resultados da busca"),
            description=_("Use as setas para percorrer os resultados e Enter para reproduzir."),
        )

        self.status_label = wx.StaticText(self, label=_("Digite um texto e pressione Enter para procurar."))
        self.status_label.SetName(_("Situação da busca"))
        attach_named_accessible(
            self.status_label,
            name=_("Situação da busca"),
            description=_("Informa quantos resultados a busca encontrou."),
            value_provider=lambda: self.status_label.GetLabel(),
        )

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.search_button = wx.Button(self, wx.ID_FIND, _("&Procurar"))
        self.play_button = wx.Button(self, wx.ID_OK, _("&Reproduzir"))
        self.enqueue_button = wx.Button(self, wx.ID_ANY, _("Adicionar à &fila"))
        self.close_button = wx.Button(self, wx.ID_CANCEL, _("&Fechar"))
        button_sizer.Add(self.search_button, 0, wx.RIGHT, 8)
        button_sizer.Add(self.play_button, 0, wx.RIGHT, 8)
        button_sizer.Add(self.enqueue_button, 0, wx.RIGHT, 8)
        button_sizer.Add(self.close_button, 0)

        root_sizer.Add(description, 0, wx.ALL | wx.EXPAND, 12)
        root_sizer.Add(query_label, 0, wx.LEFT | wx.RIGHT, 12)
        root_sizer.Add(self.query_text, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 12)
        root_sizer.Add(scope_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        root_sizer.Add(self.scope_choice, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        root_sizer.Add(self.results_list, 1, wx.ALL | wx.EXPAND, 12)
        root_sizer.Add(self.status_label, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 12)
        root_sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 12)

        self.SetSizer(root_sizer)
        self.SetMinSize((640, 480))
        self.SetSize((720, 540))
        self.SetEscapeId(wx.ID_CANCEL)
        self.SetAffirmativeId(wx.ID_OK)
        self.CentreOnParent()

        self.query_text.Bind(wx.EVT_TEXT_ENTER, self._on_search)
        self.search_button.Bind(wx.EVT_BUTTON, self._on_search)
        self.play_button.Bind(wx.EVT_BUTTON, self._on_play)
        self.enqueue_button.Bind(wx.EVT_BUTTON, self._on_enqueue)
        self.scope_choice.Bind(wx.EVT_CHOICE, self._on_search)
        self.results_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_play)
        self.results_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_selection_changed)
        self.results_list.Bind(wx.EVT_LIST_ITEM_DESELECTED, self._on_selection_changed)

        self._refresh_action_buttons()
        self.query_text.SetFocus()
        self.query_text.SelectAll()

        if initial_query:
            self._run_search()

    # ------------------------------------------------------------------
    def get_selected_record(self):
        selection = self.results_list.GetFirstSelected()
        if not 0 <= selection < len(self._results):
            return None
        return self._results[selection]

    def get_chosen_action(self):
        return self._chosen_action

    def get_results(self):
        return list(self._results)

    # ------------------------------------------------------------------
    def _selected_scope(self):
        selection = self.scope_choice.GetSelection()
        if not 0 <= selection < len(self._scope_values):
            return SEARCH_SCOPE_ALL
        return self._scope_values[selection]

    def _refresh_action_buttons(self):
        has_selection = self.get_selected_record() is not None
        self.play_button.Enable(has_selection)
        self.enqueue_button.Enable(has_selection)

    def _on_selection_changed(self, event):
        self._refresh_action_buttons()
        event.Skip()

    def _on_search(self, event):
        self._run_search()
        if event is not None:
            event.Skip(False)

    def _run_search(self):
        query = str(self.query_text.GetValue() or "").strip()
        scope = self._selected_scope()

        if not query and scope == SEARCH_SCOPE_ALL:
            self._results = []
            self._populate_results()
            self.status_label.SetLabel(_("Digite um texto para procurar na biblioteca."))
            return

        try:
            self._results = list(self._search_provider(query, scope) or [])
        except Exception:
            self._results = []

        self._populate_results()

        if not self._results:
            self.status_label.SetLabel(_("Nenhum item encontrado na biblioteca."))
            return

        self.status_label.SetLabel(
            ngettext(
                "{count} item encontrado. Use as setas na lista de resultados.",
                "{count} itens encontrados. Use as setas na lista de resultados.",
                len(self._results),
            ).format(count=len(self._results))
        )
        # Foco na lista para que o leitor de tela leia o primeiro resultado
        # imediatamente, sem o usuário precisar tabular até lá.
        self.results_list.SetFocus()

    def _populate_results(self):
        self.results_list.DeleteAllItems()
        for row_index, record in enumerate(self._results):
            label = record.display_label
            favorite_label = format_favorite(record.favorite)
            rating_label = format_rating(record.rating)
            if favorite_label:
                rating_label = f"{favorite_label}, {rating_label}"

            self.results_list.InsertItem(row_index, label)
            self.results_list.SetItem(row_index, 1, rating_label)
            self.results_list.SetItem(row_index, 2, record.folder_path or _("mídia remota"))

        if self._results:
            self.results_list.Select(0)
            self.results_list.Focus(0)

        self._refresh_action_buttons()

    def _finish(self, action):
        if self.get_selected_record() is None:
            return

        self._chosen_action = action
        if self.IsModal():
            self.EndModal(wx.ID_OK)
            return
        self.SetReturnCode(wx.ID_OK)
        self.Show(False)

    def _on_play(self, _event):
        self._finish(SEARCH_RESULT_ACTION_PLAY)

    def _on_enqueue(self, _event):
        self._finish(SEARCH_RESULT_ACTION_ENQUEUE)
