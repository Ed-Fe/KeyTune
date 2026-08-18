"""Caixa do histórico local de reprodução (Ctrl+Shift+H).

Três modos de visualização, escolhidos no campo **Ver**:

- **Todas as reproduções**: uma linha por vez que a mídia tocou.
- **Agrupado por mídia**: uma linha por mídia, com a contagem e a última vez.
- **Mais tocadas**: o mesmo agrupamento, ordenado pela contagem.

As colunas mudam junto com o modo, para que o leitor de tela sempre anuncie o
que aquela coluna realmente contém.
"""

import time

import wx

from ..accessibility import attach_named_accessible
from ..i18n import _, ngettext
from .history import HISTORY_VIEW_ALL, HISTORY_VIEW_GROUPED, HISTORY_VIEW_MOST_PLAYED


PLAYBACK_HISTORY_DIALOG_TITLE = _("Histórico de reprodução")

HISTORY_ACTION_PLAY = "play"
HISTORY_ACTION_ENQUEUE = "enqueue"

_SOURCE_LABELS = {
    "local": _("playlist local"),
    "folder": _("pasta"),
    "remote": _("mídia remota"),
    "youtube_music": _("YouTube Music"),
}


def format_played_epoch(played_epoch):
    try:
        normalized_epoch = int(played_epoch or 0)
    except (TypeError, ValueError):
        normalized_epoch = 0

    if normalized_epoch <= 0:
        return _("data desconhecida")

    return time.strftime("%d/%m/%Y %H:%M", time.localtime(normalized_epoch))


def format_position(position_ms, duration_ms):
    def as_clock(milliseconds):
        total_seconds = max(0, int(milliseconds or 0) // 1000)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02}:{seconds:02}"
        return f"{minutes}:{seconds:02}"

    if not position_ms:
        return ""

    if duration_ms and duration_ms > 0:
        return f"{as_clock(position_ms)} / {as_clock(duration_ms)}"

    return as_clock(position_ms)


def format_source(source):
    return _SOURCE_LABELS.get(str(source or ""), "")


def format_play_count(play_count):
    try:
        normalized_count = int(play_count or 0)
    except (TypeError, ValueError):
        normalized_count = 0

    return ngettext("{count} vez", "{count} vezes", normalized_count).format(count=normalized_count)


class PlaybackHistoryDialog(wx.Dialog):
    def __init__(self, parent, history_provider, on_remove=None, on_clear=None, announce=None):
        super().__init__(
            parent,
            title=PLAYBACK_HISTORY_DIALOG_TITLE,
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self._history_provider = history_provider
        self._on_remove = on_remove
        self._on_clear = on_clear
        self._announce = announce
        self._entries = []
        self._chosen_action = HISTORY_ACTION_PLAY
        self._rendered_view = None

        self._view_values = (HISTORY_VIEW_ALL, HISTORY_VIEW_GROUPED, HISTORY_VIEW_MOST_PLAYED)
        view_labels = [
            _("Todas as reproduções"),
            _("Agrupado por mídia"),
            _("Mais tocadas"),
        ]

        root_sizer = wx.BoxSizer(wx.VERTICAL)

        self.description_label = wx.StaticText(self, label=self._description_for_view(HISTORY_VIEW_ALL))
        self.description_label.Wrap(520)

        view_label = wx.StaticText(self, label=_("&Ver"))
        self.view_choice = wx.Choice(self, choices=view_labels)
        self.view_choice.SetSelection(0)
        self.view_choice.SetName(_("Modo de visualização do histórico"))

        filter_label = wx.StaticText(self, label=_("&Filtrar por texto"))
        self.filter_text = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.filter_text.SetName(_("Filtro do histórico"))

        self.history_list = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.history_list.SetName(_("Histórico de reprodução"))
        attach_named_accessible(
            self.history_list,
            name=_("Histórico de reprodução"),
            description=_("Use as setas para percorrer o histórico e Enter para reproduzir de novo."),
        )

        self.status_label = wx.StaticText(self, label="")
        self.status_label.SetName(_("Situação do histórico"))
        attach_named_accessible(
            self.status_label,
            name=_("Situação do histórico"),
            description=_("Informa quantas reproduções o histórico guarda."),
            value_provider=lambda: self.status_label.GetLabel(),
        )

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.play_button = wx.Button(self, wx.ID_OK, _("&Reproduzir"))
        self.enqueue_button = wx.Button(self, wx.ID_ANY, _("Adicionar à &fila"))
        self.remove_button = wx.Button(self, wx.ID_ANY, _("&Remover entrada"))
        self.clear_button = wx.Button(self, wx.ID_ANY, _("&Limpar histórico"))
        self.close_button = wx.Button(self, wx.ID_CANCEL, _("F&echar"))
        button_sizer.Add(self.play_button, 0, wx.RIGHT, 8)
        button_sizer.Add(self.enqueue_button, 0, wx.RIGHT, 8)
        button_sizer.Add(self.remove_button, 0, wx.RIGHT, 8)
        button_sizer.Add(self.clear_button, 0, wx.RIGHT, 8)
        button_sizer.Add(self.close_button, 0)

        root_sizer.Add(self.description_label, 0, wx.ALL | wx.EXPAND, 12)
        root_sizer.Add(view_label, 0, wx.LEFT | wx.RIGHT, 12)
        root_sizer.Add(self.view_choice, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        root_sizer.Add(filter_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        root_sizer.Add(self.filter_text, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 12)
        root_sizer.Add(self.history_list, 1, wx.ALL | wx.EXPAND, 12)
        root_sizer.Add(self.status_label, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 12)
        root_sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 12)

        self.SetSizer(root_sizer)
        self.SetMinSize((700, 500))
        self.SetSize((780, 560))
        self.SetEscapeId(wx.ID_CANCEL)
        self.SetAffirmativeId(wx.ID_OK)
        self.CentreOnParent()

        self.filter_text.Bind(wx.EVT_TEXT_ENTER, lambda _event: self.refresh())
        self.view_choice.Bind(wx.EVT_CHOICE, self._on_view_changed)
        self.play_button.Bind(wx.EVT_BUTTON, self._on_play)
        self.enqueue_button.Bind(wx.EVT_BUTTON, self._on_enqueue)
        self.remove_button.Bind(wx.EVT_BUTTON, self._on_remove_entry)
        self.clear_button.Bind(wx.EVT_BUTTON, self._on_clear_history)
        self.history_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_play)
        self.history_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_selection_changed)
        self.history_list.Bind(wx.EVT_LIST_ITEM_DESELECTED, self._on_selection_changed)

        self.refresh()
        self.history_list.SetFocus()

    # ------------------------------------------------------------------
    def selected_view(self):
        selection = self.view_choice.GetSelection()
        if not 0 <= selection < len(self._view_values):
            return HISTORY_VIEW_ALL
        return self._view_values[selection]

    def get_selected_entry(self):
        selection = self.history_list.GetFirstSelected()
        if not 0 <= selection < len(self._entries):
            return None
        return self._entries[selection]

    def get_chosen_action(self):
        return self._chosen_action

    def _is_grouped_view(self):
        return self.selected_view() in (HISTORY_VIEW_GROUPED, HISTORY_VIEW_MOST_PLAYED)

    def _description_for_view(self, view):
        if view == HISTORY_VIEW_GROUPED:
            return _("Uma linha por mídia, da que tocou mais recentemente para a mais antiga.")
        if view == HISTORY_VIEW_MOST_PLAYED:
            return _("Uma linha por mídia, da mais tocada para a menos tocada.")
        return _("Reproduções recentes, da mais nova para a mais antiga.")

    # ------------------------------------------------------------------
    def _rebuild_columns(self, view):
        if self._rendered_view == view:
            return

        self._rendered_view = view
        self.history_list.ClearAll()
        if view == HISTORY_VIEW_ALL:
            self.history_list.InsertColumn(0, _("Item"), width=250)
            self.history_list.InsertColumn(1, _("Quando"), width=140)
            self.history_list.InsertColumn(2, _("Parou em"), width=110)
            self.history_list.InsertColumn(3, _("Origem"), width=120)
            return

        self.history_list.InsertColumn(0, _("Item"), width=250)
        self.history_list.InsertColumn(1, _("Reproduções"), width=110)
        self.history_list.InsertColumn(2, _("Última vez"), width=140)
        self.history_list.InsertColumn(3, _("Marcadores"), width=140)

    def _entry_marks(self, entry):
        parts = []
        if entry.favorite:
            parts.append(_("favorito"))
        if entry.rating > 0:
            parts.append(
                ngettext("{count} estrela", "{count} estrelas", entry.rating).format(count=entry.rating)
            )
        return ", ".join(parts)

    def _on_view_changed(self, _event):
        self.description_label.SetLabel(self._description_for_view(self.selected_view()))
        self.description_label.Wrap(520)
        self.Layout()
        self.refresh()
        self.history_list.SetFocus()

    def refresh(self, preserve_position=None):
        view = self.selected_view()
        query = str(self.filter_text.GetValue() or "").strip()
        try:
            self._entries = list(self._history_provider(view, query) or [])
        except Exception:
            self._entries = []

        self._rebuild_columns(view)
        self.history_list.DeleteAllItems()

        for row_index, entry in enumerate(self._entries):
            self.history_list.InsertItem(row_index, entry.display_label)
            if view == HISTORY_VIEW_ALL:
                self.history_list.SetItem(row_index, 1, format_played_epoch(entry.played_epoch))
                self.history_list.SetItem(row_index, 2, format_position(entry.position_ms, entry.duration_ms))
                self.history_list.SetItem(row_index, 3, format_source(entry.source))
                continue

            self.history_list.SetItem(row_index, 1, format_play_count(entry.play_count))
            self.history_list.SetItem(row_index, 2, format_played_epoch(entry.last_played_epoch))
            self.history_list.SetItem(row_index, 3, self._entry_marks(entry))

        if self._entries:
            target_row = 0
            if preserve_position is not None:
                target_row = max(0, min(int(preserve_position), len(self._entries) - 1))
            self.history_list.Select(target_row)
            self.history_list.Focus(target_row)
            if view == HISTORY_VIEW_ALL:
                self.status_label.SetLabel(
                    ngettext(
                        "{count} reprodução no histórico.",
                        "{count} reproduções no histórico.",
                        len(self._entries),
                    ).format(count=len(self._entries))
                )
            else:
                self.status_label.SetLabel(
                    ngettext(
                        "{count} mídia no histórico.",
                        "{count} mídias no histórico.",
                        len(self._entries),
                    ).format(count=len(self._entries))
                )
        else:
            self.status_label.SetLabel(_("O histórico está vazio."))

        self._refresh_action_buttons()

    def _refresh_action_buttons(self):
        has_selection = self.get_selected_entry() is not None
        self.play_button.Enable(has_selection)
        self.enqueue_button.Enable(has_selection)
        self.remove_button.Enable(has_selection and callable(self._on_remove))
        self.remove_button.SetLabel(
            _("&Remover do histórico") if self._is_grouped_view() else _("&Remover entrada")
        )
        self.clear_button.Enable(bool(self._entries) and callable(self._on_clear))

    def _on_selection_changed(self, event):
        self._refresh_action_buttons()
        event.Skip()

    def _speak(self, message):
        if callable(self._announce) and message:
            self._announce(message)

    def _finish(self, action):
        if self.get_selected_entry() is None:
            return

        self._chosen_action = action
        if self.IsModal():
            self.EndModal(wx.ID_OK)
            return
        self.SetReturnCode(wx.ID_OK)
        self.Show(False)

    def _on_play(self, _event):
        self._finish(HISTORY_ACTION_PLAY)

    def _on_enqueue(self, _event):
        self._finish(HISTORY_ACTION_ENQUEUE)

    def _on_remove_entry(self, _event):
        entry = self.get_selected_entry()
        if entry is None or not callable(self._on_remove):
            return

        selected_row = self.history_list.GetFirstSelected()
        grouped = self._is_grouped_view()
        # Agrupado, cada linha representa todas as reproduções daquela mídia, e
        # é isso que sai; na lista completa, sai só a reprodução selecionada.
        if not self._on_remove(entry, grouped):
            self._speak(_("Não foi possível remover esta entrada do histórico."))
            return

        self._speak(_("{item} removido do histórico.").format(item=entry.display_label))
        self.refresh(preserve_position=selected_row)
        self.history_list.SetFocus()

    def _on_clear_history(self, _event):
        if not callable(self._on_clear) or not self._entries:
            return

        with wx.MessageDialog(
            self,
            _("Deseja apagar todo o histórico de reprodução?"),
            _("Limpar histórico"),
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
        ) as confirmation:
            if confirmation.ShowModal() != wx.ID_YES:
                return

        if not self._on_clear():
            self._speak(_("Não foi possível limpar o histórico."))
            return

        self._speak(_("Histórico de reprodução apagado."))
        self.refresh()
        self.history_list.SetFocus()
