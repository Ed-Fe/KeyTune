import wx

from ..accessibility import attach_named_accessible
from ..i18n import _
from ..library.browser import VirtualItemsListCtrl


class RadioTabPanel(wx.Panel):
    """A aba de rádios online: a busca em cima e uma lista só para todo o resto.

    A lista começa no início (favoritas, recentes, países, gêneros) e mostra
    também a busca e o que há dentro de cada item aberto. O painel só tem os
    controles: teclas e cliques saem pelos callbacks e ele nunca fala com o serviço.
    """

    def __init__(
        self,
        parent,
        *,
        search_scope_labels,
        on_search,
        on_activate,
        on_browse,
        on_back,
        on_load_more,
        on_toggle_favorite,
        on_copy_stream_url,
        on_show_actions_menu,
    ):
        super().__init__(parent, style=wx.TAB_TRAVERSAL)

        self._results = []
        self._favorite_keys = set()
        self._has_more = False
        self._can_go_back = False
        self._loading = False
        self._on_search = on_search
        self._on_activate = on_activate
        self._on_browse = on_browse
        self._on_back = on_back
        self._on_load_more = on_load_more
        self._on_toggle_favorite = on_toggle_favorite
        self._on_copy_stream_url = on_copy_stream_url
        self._on_show_actions_menu = on_show_actions_menu

        root_sizer = wx.BoxSizer(wx.VERTICAL)

        search_row = wx.BoxSizer(wx.HORIZONTAL)
        search_label = wx.StaticText(self, label=_("Buscar rádio ou colar endereço:"))
        self.search_query_ctrl = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.search_query_ctrl.SetName(_("Buscar rádio pelo nome, ou colar o endereço de um stream"))
        self.search_query_ctrl.SetToolTip(
            _("Digite o nome da rádio e pressione Enter. O endereço de um stream colado aqui toca direto.")
        )
        search_scope_label = wx.StaticText(self, label=_("Em:"))
        self.search_scope_choice = wx.Choice(self, choices=list(search_scope_labels))
        self.search_scope_choice.SetSelection(0)
        self.search_scope_choice.SetName(_("Onde buscar"))
        search_row.Add(search_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        search_row.Add(self.search_query_ctrl, 1, wx.RIGHT, 12)
        search_row.Add(search_scope_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        search_row.Add(self.search_scope_choice, 0)

        self.results_label = wx.StaticText(self, label="")
        self.results_label.SetName(_("Lista atual das rádios online"))
        attach_named_accessible(
            self.results_label,
            name=_("Lista atual das rádios online"),
            value_provider=lambda: self.results_label.GetLabel(),
        )

        self.results_list = VirtualItemsListCtrl(self, self._get_result_label)
        self.results_list.SetName(_("Rádios online"))
        self.results_list.SetMinSize((-1, 180))

        self.actions_button = wx.Button(self, label=_("&Ações..."))
        self.actions_button.SetName(_("Ações do item selecionado"))
        self.actions_button.SetToolTip(
            _("Abre o menu com as ações do item selecionado: tocar, adicionar, favoritar, ver detalhes e outras.")
        )

        help_label = wx.StaticText(
            self,
            label=_(
                "Enter entra no item ou toca a rádio; Shift+Enter adiciona sem tocar. "
                "Ctrl+D favorita. Seta para a direita mostra o que há dentro e Backspace volta. "
                "Descer além do último item carrega mais. Shift+F10 abre as ações."
            ),
        )
        help_label.Wrap(620)

        root_sizer.Add(search_row, 0, wx.ALL | wx.EXPAND, 10)
        root_sizer.Add(self.results_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
        root_sizer.Add(self.results_list, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
        root_sizer.Add(self.actions_button, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        root_sizer.Add(help_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
        self.SetSizer(root_sizer)

        self.search_query_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_search_query_enter)
        self.actions_button.Bind(wx.EVT_BUTTON, self._on_actions_button)
        self.results_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_selection_changed)
        self.results_list.Bind(wx.EVT_LIST_ITEM_DESELECTED, self._on_selection_changed)
        self.results_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_item_activated)
        self.results_list.Bind(wx.EVT_CONTEXT_MENU, self._on_list_context_menu)
        self.results_list.Bind(wx.EVT_CHAR_HOOK, self._on_list_key_down)

        self._update_actions()

    def update_view(
        self,
        *,
        results,
        summary,
        favorite_keys,
        has_more=False,
        can_go_back=False,
        loading=False,
        selected_id="",
    ):
        self.Freeze()
        try:
            selected_ids = [selected_id] if selected_id else self.get_selected_result_ids()
            self._results = list(results or [])
            self._favorite_keys = set(favorite_keys or ())
            self._has_more = bool(has_more)
            self._can_go_back = bool(can_go_back)
            self._loading = bool(loading)
            self.results_label.SetLabel(str(summary or "").strip())
            self._refresh_results_list(selected_ids)
            self.Layout()
        finally:
            self.Thaw()

    def _refresh_results_list(self, selected_ids):
        visible_ids = [result.stable_id for result in self._results]
        old_count = self.results_list.GetItemCount()
        new_count = len(self._results)

        self.results_list.SetItemCount(new_count)
        self.results_list.Refresh()

        selected_indices = [visible_ids.index(result_id) for result_id in selected_ids if result_id in visible_ids]
        if not selected_indices and new_count > 0:
            selected_indices = [0]

        if old_count != new_count:
            self._clear_selection()

        if selected_indices != self._get_selections():
            self._clear_selection()
            for selection_index in selected_indices:
                self.results_list.Select(selection_index, on=True)
            if selected_indices:
                self.results_list.Focus(selected_indices[0])

        self._update_actions()

    def _update_actions(self):
        self.actions_button.Enable(bool(self.get_selected_results() or self._can_go_back))

    def _get_result_label(self, index):
        if not 0 <= index < len(self._results):
            return ""
        result = self._results[index]
        label = result.choice_label
        if getattr(result, "result_type", "") == "station" and result.key in self._favorite_keys:
            label = label + " — " + _("favorita")
        return label

    def _get_selections(self):
        selections = []
        selection = self.results_list.GetFirstSelected()
        while selection != -1:
            selections.append(selection)
            selection = self.results_list.GetNextSelected(selection)
        return selections

    def _clear_selection(self):
        for selection in self._get_selections():
            self.results_list.Select(selection, on=False)

    def get_selected_results(self):
        return [self._results[index] for index in self._get_selections() if 0 <= index < len(self._results)]

    def get_selected_result_ids(self):
        return [result.stable_id for result in self.get_selected_results()]

    def get_search_query(self):
        return str(self.search_query_ctrl.GetValue() or "").strip()

    def get_search_scope_index(self):
        return max(self.search_scope_choice.GetSelection(), 0)

    def set_search_scope_labels(self, labels):
        selection = self.get_search_scope_index()
        self.search_scope_choice.Set(list(labels))
        self.search_scope_choice.SetSelection(min(selection, len(labels) - 1))

    def focus_results(self):
        """Leva o foco à lista, se houver algo nela."""
        if self.results_list.GetItemCount() > 0:
            self.results_list.SetFocus()

    def _selected_folder(self):
        selected_results = self.get_selected_results()
        if len(selected_results) == 1 and getattr(selected_results[0], "can_browse", False):
            return selected_results[0]
        return None

    def _on_search_query_enter(self, _event):
        if self.get_search_query():
            self._on_search()

    def _on_selection_changed(self, _event):
        self._update_actions()

    def _on_actions_button(self, event):
        self._on_show_actions_menu(event.GetEventObject())

    def _on_list_context_menu(self, _event):
        self._on_show_actions_menu(self.results_list)

    def _on_item_activated(self, _event):
        # O duplo clique faz o mesmo que Enter: entra na pasta, toca a rádio.
        if self._selected_folder() is not None:
            self._on_browse()
        elif self.get_selected_results():
            self._on_activate(play=True)

    def _maybe_load_more(self):
        if not self._has_more or self._loading:
            return False
        last_index = self.results_list.GetItemCount() - 1
        if last_index < 0 or self.results_list.GetFocusedItem() < last_index:
            return False
        self._on_load_more()
        return True

    def _on_list_key_down(self, event):
        key_code = event.GetKeyCode()
        if key_code == wx.WXK_TAB:
            event.Skip()
            return

        if key_code == wx.WXK_F10 and event.ShiftDown():
            self._on_show_actions_menu(self.results_list)
            return

        only_control = event.ControlDown() and not event.AltDown() and not event.ShiftDown()
        if only_control and key_code in (ord("D"), ord("d")):
            self._on_toggle_favorite()
            return
        if only_control and key_code in (ord("C"), ord("c")):
            self._on_copy_stream_url()
            return

        has_modifiers = event.ControlDown() or event.AltDown() or event.ShiftDown()

        if key_code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and not event.ControlDown() and not event.AltDown():
            if self._selected_folder() is not None and not event.ShiftDown():
                self._on_browse()
                return
            if self.get_selected_results():
                # Como no explorador de pastas: Enter toca, Shift+Enter adiciona sem tocar.
                self._on_activate(play=not event.ShiftDown())
                return

        if key_code in (wx.WXK_RIGHT, wx.WXK_NUMPAD_RIGHT) and not has_modifiers:
            if self._selected_folder() is not None:
                self._on_browse()
                return

        is_back_key = (
            (key_code == wx.WXK_BACK and not has_modifiers)
            or (key_code in (wx.WXK_LEFT, wx.WXK_NUMPAD_LEFT) and event.AltDown() and not event.ControlDown())
            or (key_code in (wx.WXK_LEFT, wx.WXK_NUMPAD_LEFT) and not has_modifiers and self._can_go_back)
        )
        if is_back_key:
            self._on_back()
            return

        if key_code in (wx.WXK_DOWN, wx.WXK_NUMPAD_DOWN, wx.WXK_PAGEDOWN, wx.WXK_NUMPAD_PAGEDOWN) and not has_modifiers:
            if self._maybe_load_more():
                return

        event.Skip()
