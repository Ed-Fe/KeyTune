import wx

from ..i18n import _


class QueueManagerDialog(wx.Dialog):
    """Accessible manager for the custom playback queue.

    Edits the queue live through the callbacks supplied by the frame: every
    action re-reads the entries from the owning playlist state, so the list
    always reflects the real queue. Closing simply dismisses the window.
    """

    def __init__(
        self,
        parent,
        *,
        get_entries,
        on_remove,
        on_move,
        on_clear,
        announce=None,
    ):
        super().__init__(
            parent,
            title=_("Gerenciar fila de reprodução"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self._get_entries = get_entries
        self._on_remove = on_remove
        self._on_move = on_move
        self._on_clear = on_clear
        self._announce = announce
        self._entries = []

        panel = wx.Panel(self)
        root_sizer = wx.BoxSizer(wx.VERTICAL)

        intro_label = wx.StaticText(
            panel,
            label=_(
                "Itens abaixo tocam antes da ordem normal, de cima para baixo. "
                "Use Delete para remover e Alt+Seta para cima ou para baixo para reordenar."
            ),
        )
        intro_label.Wrap(520)
        root_sizer.Add(intro_label, 0, wx.ALL | wx.EXPAND, 10)

        list_label = wx.StaticText(panel, label=_("Itens na fila:"))
        root_sizer.Add(list_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self.queue_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.queue_list.SetName(_("Fila de reprodução"))
        self.queue_list.Bind(wx.EVT_KEY_DOWN, self.on_list_key_down)
        root_sizer.Add(self.queue_list, 1, wx.ALL | wx.EXPAND, 10)

        action_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.move_up_button = wx.Button(panel, label=_("&Subir"))
        self.move_down_button = wx.Button(panel, label=_("&Descer"))
        self.remove_button = wx.Button(panel, label=_("&Remover"))
        self.clear_button = wx.Button(panel, label=_("&Limpar tudo"))
        self.move_up_button.SetToolTip(_("Move o item selecionado uma posição para cima (Alt+Seta para cima)."))
        self.move_down_button.SetToolTip(_("Move o item selecionado uma posição para baixo (Alt+Seta para baixo)."))
        self.remove_button.SetToolTip(_("Remove o item selecionado da fila (Delete)."))
        self.clear_button.SetToolTip(_("Esvazia a fila de reprodução inteira."))
        for button in (self.move_up_button, self.move_down_button, self.remove_button, self.clear_button):
            action_sizer.Add(button, 0, wx.RIGHT, 6)
        root_sizer.Add(action_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        button_sizer = wx.StdDialogButtonSizer()
        self.close_button = wx.Button(panel, wx.ID_CLOSE, _("&Fechar"))
        self.close_button.SetDefault()
        button_sizer.AddButton(self.close_button)
        button_sizer.Realize()
        root_sizer.Add(button_sizer, 0, wx.ALL | wx.EXPAND, 10)

        panel.SetSizer(root_sizer)

        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizerAndFit(frame_sizer)
        self.SetMinSize((520, 460))
        self.SetEscapeId(wx.ID_CLOSE)
        self.CentreOnParent()

        self.move_up_button.Bind(wx.EVT_BUTTON, lambda _event: self._move_selected(-1))
        self.move_down_button.Bind(wx.EVT_BUTTON, lambda _event: self._move_selected(1))
        self.remove_button.Bind(wx.EVT_BUTTON, lambda _event: self._remove_selected())
        self.clear_button.Bind(wx.EVT_BUTTON, lambda _event: self._clear_all())
        self.close_button.Bind(wx.EVT_BUTTON, lambda _event: self.EndModal(wx.ID_CLOSE))

        self._reload_entries(select=0)

    def _announce_message(self, message):
        if message and callable(self._announce):
            self._announce(message)

    def _reload_entries(self, select=None):
        self._entries = list(self._get_entries() or [])
        labels = [label for _path, label in self._entries]
        self.queue_list.Set(labels)

        has_items = bool(self._entries)
        self.move_up_button.Enable(has_items)
        self.move_down_button.Enable(has_items)
        self.remove_button.Enable(has_items)
        self.clear_button.Enable(has_items)

        if has_items and select is not None:
            bounded = max(0, min(select, len(self._entries) - 1))
            self.queue_list.SetSelection(bounded)

    def _selected_position(self):
        selection = self.queue_list.GetSelection()
        return selection if selection != wx.NOT_FOUND else None

    def _remove_selected(self):
        position = self._selected_position()
        if position is None:
            return
        removed_label = self._entries[position][1]
        self._on_remove(position)
        self._reload_entries(select=position)
        if self._entries:
            self._announce_message(_("{item} removido da fila.").format(item=removed_label))
        else:
            self._announce_message(_("{item} removido. A fila está vazia.").format(item=removed_label))
            self.queue_list.SetFocus()

    def _move_selected(self, direction):
        position = self._selected_position()
        if position is None:
            return
        new_position = self._on_move(position, direction)
        if new_position is None:
            boundary = _("O item já está no topo da fila.") if direction < 0 else _("O item já está no fim da fila.")
            self._announce_message(boundary)
            return
        moved_label = self._entries[position][1]
        self._reload_entries(select=new_position)
        self.queue_list.SetFocus()
        self._announce_message(
            _("{item} movido para a posição {pos} de {total}.").format(
                item=moved_label, pos=new_position + 1, total=len(self._entries)
            )
        )

    def _clear_all(self):
        if not self._entries:
            return
        self._on_clear()
        self._reload_entries()
        self._announce_message(_("Fila de reprodução esvaziada."))
        self.queue_list.SetFocus()

    def on_list_key_down(self, event):
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_DELETE:
            self._remove_selected()
            return
        if event.AltDown() and keycode == wx.WXK_UP:
            self._move_selected(-1)
            return
        if event.AltDown() and keycode == wx.WXK_DOWN:
            self._move_selected(1)
            return
        event.Skip()
