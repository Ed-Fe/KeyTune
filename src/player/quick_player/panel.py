"""Controles do player rápido; não conhece o backend de reprodução."""

import wx

from ..accessibility import attach_named_accessible
from ..constants import PROGRESS_GAUGE_RANGE
from ..i18n import _
from ..widgets import ROW_BORDER, describe_control


class QuickPlayerPanel(wx.Panel):
    def __init__(self, parent, *, on_toggle_play=None, on_continue=None):
        super().__init__(parent)

        self.title_label = wx.StaticText(self, label="", style=wx.ST_ELLIPSIZE_MIDDLE | wx.ST_NO_AUTORESIZE)
        self.time_label = wx.StaticText(self, label=_("Tempo: nenhuma mídia carregada."))
        self.progress_gauge = wx.Gauge(self, range=PROGRESS_GAUGE_RANGE, style=wx.GA_SMOOTH)
        # Os mesmos nomes da janela principal. A barra expõe o texto do tempo no
        # lugar da porcentagem nativa, como lá.
        attach_named_accessible(
            self.time_label, name=_("Tempo da mídia"), value_provider=lambda: self.time_label.GetLabel()
        )
        attach_named_accessible(
            self.progress_gauge, name=_("Barra de tempo"), value_provider=lambda: self.time_label.GetLabel()
        )

        self.play_button = wx.Button(self, label=_("&Pausar"))
        self.continue_button = wx.Button(self, label=_("&Continuar no KeyTune completo"))
        describe_control(
            self.continue_button,
            self.continue_button.GetLabelText(),
            _("Abre a janela principal com esta mídia numa playlist nova."),
        )
        self.hint_label = wx.StaticText(
            self,
            label=_("Espaço reproduzir/pausar · ←/→ buscar · ↑/↓ volume · Ctrl+Enter KeyTune completo · Esc fechar"),
        )

        if on_toggle_play is not None:
            self.play_button.Bind(wx.EVT_BUTTON, lambda _event: on_toggle_play())
        if on_continue is not None:
            self.continue_button.Bind(wx.EVT_BUTTON, lambda _event: on_continue())

        button_row = wx.BoxSizer(wx.HORIZONTAL)
        button_row.Add(self.play_button, 0, wx.RIGHT, self.FromDIP(6))
        button_row.Add(self.continue_button, 0)

        border = self.FromDIP(ROW_BORDER * 2)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.title_label, 0, wx.ALL | wx.EXPAND, border)
        sizer.Add(self.time_label, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, border)
        sizer.Add(self.progress_gauge, 0, wx.ALL | wx.EXPAND, border)
        sizer.Add(button_row, 0, wx.LEFT | wx.RIGHT, border)
        sizer.Add(self.hint_label, 0, wx.ALL | wx.EXPAND, border)
        self.SetSizer(sizer)
        self.hint_label.Wrap(self.FromDIP(440))

    def set_title(self, text):
        self.title_label.SetLabel(text)

    def set_time(self, text, gauge_value):
        if self.time_label.GetLabel() != text:
            self.time_label.SetLabel(text)
        gauge_value = max(0, min(PROGRESS_GAUGE_RANGE, int(gauge_value)))
        if self.progress_gauge.GetValue() != gauge_value:
            self.progress_gauge.SetValue(gauge_value)

    def set_playing(self, playing):
        label = _("&Pausar") if playing else _("&Reproduzir")
        if self.play_button.GetLabel() != label:
            self.play_button.SetLabel(label)
