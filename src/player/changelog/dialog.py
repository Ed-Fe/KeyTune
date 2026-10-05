"""Histórico de mudanças: escolha uma versão e leia o que mudou nela."""

from __future__ import annotations

import wx

from ..i18n import _
from ..reading_dialog import add_reading_field
from .service import ChangelogEntry, list_changelog_entries


class ChangelogDialog(wx.Dialog):
    def __init__(self, parent, entries: list[ChangelogEntry] | None = None):
        super().__init__(
            parent,
            title=_("Histórico de mudanças"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.entries = list(entries) if entries is not None else list_changelog_entries()
        root_sizer = wx.BoxSizer(wx.VERTICAL)

        versions_label = wx.StaticText(self, label=_("Versões:"))
        self.versions_list = wx.ListBox(self, choices=[self._entry_label(entry) for entry in self.entries])
        self.versions_list.SetName(_("Versões"))
        self.versions_list.SetMinSize(self.FromDIP(wx.Size(520, 110)))
        root_sizer.Add(versions_label, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 10)
        root_sizer.Add(self.versions_list, 0, wx.ALL | wx.EXPAND, 10)

        self.notes_ctrl = add_reading_field(self, root_sizer, _("Mudanças da versão"), self._empty_text())
        self.notes_ctrl.SetMinSize(self.FromDIP(wx.Size(520, 260)))

        close_button = wx.Button(self, wx.ID_CLOSE, _("&Fechar"))
        close_button.SetDefault()
        close_button.Bind(wx.EVT_BUTTON, lambda _event: self.EndModal(wx.ID_CLOSE))
        root_sizer.Add(close_button, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, 10)

        self.SetEscapeId(wx.ID_CLOSE)
        self.SetSizerAndFit(root_sizer)
        self.SetMinSize(self.GetSize())
        self.CentreOnParent()

        self.versions_list.Bind(wx.EVT_LISTBOX, self.on_select_version)
        if self.entries:
            self.versions_list.SetSelection(0)
            self._show_entry(self.entries[0])

    @staticmethod
    def _entry_label(entry: ChangelogEntry) -> str:
        if entry.is_unreleased:
            return _("Não lançado")
        if entry.date:
            return _("{version} ({date})").format(version=entry.version, date=entry.date)
        return entry.version

    @staticmethod
    def _empty_text() -> str:
        return _("Nenhum histórico de mudanças foi encontrado nesta instalação.")

    def _show_entry(self, entry: ChangelogEntry):
        try:
            text = entry.read_text()
        except OSError:
            text = self._empty_text()
        self.notes_ctrl.SetValue(text)
        self.notes_ctrl.SetInsertionPoint(0)

    def on_select_version(self, _event):
        index = self.versions_list.GetSelection()
        if 0 <= index < len(self.entries):
            self._show_entry(self.entries[index])
