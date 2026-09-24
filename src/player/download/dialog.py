"""Diálogo mostrado ao baixar a mídia atual (Ctrl+Shift+B)."""

from __future__ import annotations

import wx

from ..i18n import _
from .panel import DownloadOptionsPanel


class DownloadDialog(wx.Dialog):
    def __init__(self, parent, settings, *, media_title="", item_count=1):
        super().__init__(
            parent,
            title=_("Baixar mídia"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        panel = wx.Panel(self)
        root_sizer = wx.BoxSizer(wx.VERTICAL)

        if item_count > 1:
            intro = _("Baixar {count} itens. Escolha o formato e a qualidade.").format(count=item_count)
        elif media_title:
            intro = _("Baixar “{title}”. Escolha o formato e a qualidade.").format(title=media_title)
        else:
            intro = _("Escolha o formato e a qualidade do download.")
        intro_label = wx.StaticText(panel, label=intro)
        intro_label.Wrap(520)
        root_sizer.Add(intro_label, 0, wx.ALL | wx.EXPAND, 10)

        self.options_panel = DownloadOptionsPanel(panel, kind_label=_("Baixar"))
        self.options_panel.set_values(
            kind=settings.download_kind,
            audio_quality=settings.download_audio_quality,
            video_quality=settings.download_video_quality,
            sample_rate=settings.download_sample_rate,
            directory=settings.download_directory,
        )
        root_sizer.Add(self.options_panel, 1, wx.LEFT | wx.RIGHT | wx.EXPAND, 4)

        self.always_ask_checkbox = wx.CheckBox(panel, label=_("Sempre &mostrar este diálogo ao baixar"))
        self.always_ask_checkbox.SetName(_("Sempre mostrar este diálogo ao baixar"))
        self.always_ask_checkbox.SetToolTip(
            _(
                "Desmarcado, o download começa direto com as opções da guia Download das Preferências, "
                "sem perguntar."
            )
        )
        self.always_ask_checkbox.SetValue(settings.download_always_ask)
        root_sizer.Add(self.always_ask_checkbox, 0, wx.ALL | wx.EXPAND, 10)

        button_sizer = wx.StdDialogButtonSizer()
        self.download_button = wx.Button(panel, wx.ID_OK, _("&Baixar"))
        self.cancel_button = wx.Button(panel, wx.ID_CANCEL, _("&Cancelar"))
        self.download_button.SetDefault()
        self.download_button.Bind(wx.EVT_BUTTON, self._on_confirm)
        button_sizer.AddButton(self.download_button)
        button_sizer.AddButton(self.cancel_button)
        button_sizer.Realize()
        root_sizer.Add(button_sizer, 0, wx.ALL | wx.EXPAND, 10)

        panel.SetSizer(root_sizer)
        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizerAndFit(frame_sizer)
        self.SetMinSize((560, 0))
        self.SetEscapeId(wx.ID_CANCEL)
        self.CentreOnParent()

    def get_choice(self):
        return self.options_panel.get_choice()

    def get_directory_setting(self):
        return self.options_panel.get_directory_setting()

    def always_ask(self):
        return self.always_ask_checkbox.GetValue()

    def _on_confirm(self, _event):
        if not self.options_panel.get_choice().directory:
            wx.MessageBox(
                _("Escolha uma pasta de destino para o download."),
                _("Baixar mídia"),
                wx.OK | wx.ICON_WARNING,
                self,
            )
            self.options_panel.directory_ctrl.SetFocus()
            return
        self.EndModal(wx.ID_OK)
