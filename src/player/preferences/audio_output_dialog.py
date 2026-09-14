import wx

from ..audio_output import is_selectable_audio_output_device_id, normalize_audio_output_device_id
from ..i18n import _


class AudioOutputDialog(wx.Dialog):
    """Choose the audio output without opening the full preferences dialog."""

    def __init__(self, parent, devices, selected_device_id):
        super().__init__(
            parent,
            title=_("Selecionar dispositivo de áudio"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self._device_ids = [""]
        labels = [_("Padrão do sistema")]
        seen_ids = {""}
        for device in devices:
            device_id = normalize_audio_output_device_id(getattr(device, "device_id", ""))
            if not is_selectable_audio_output_device_id(device_id) or device_id in seen_ids:
                continue
            self._device_ids.append(device_id)
            labels.append(getattr(device, "menu_label", device_id))
            seen_ids.add(device_id)

        panel = wx.Panel(self)
        root_sizer = wx.BoxSizer(wx.VERTICAL)
        description = wx.StaticText(panel, label=_("Escolha a saída de áudio usada na reprodução."))
        description.Wrap(420)
        choice_label = wx.StaticText(panel, label=_("Dispositivo de áudio:"))
        self.device_choice = wx.Choice(panel, choices=labels, name=_("Selecione o dispositivo de áudio"))
        self.device_choice.SetToolTip(_("Use as setas para escolher a saída de áudio."))

        normalized_selected_id = normalize_audio_output_device_id(selected_device_id)
        try:
            selection = self._device_ids.index(normalized_selected_id)
        except ValueError:
            selection = 0
        self.device_choice.SetSelection(selection)

        button_sizer = wx.StdDialogButtonSizer()
        self.apply_button = wx.Button(panel, wx.ID_OK, _("&Aplicar"))
        self.cancel_button = wx.Button(panel, wx.ID_CANCEL, _("&Cancelar"))
        self.apply_button.SetName(_("Aplicar dispositivo de áudio"))
        self.apply_button.SetToolTip(_("Aplica o dispositivo de áudio selecionado."))
        self.apply_button.SetDefault()
        self.cancel_button.SetName(_("Cancelar seleção de dispositivo de áudio"))
        self.cancel_button.SetToolTip(_("Fecha a janela sem alterar o dispositivo de áudio."))
        button_sizer.AddButton(self.apply_button)
        button_sizer.AddButton(self.cancel_button)
        button_sizer.Realize()
        self.apply_button.Bind(wx.EVT_BUTTON, self._on_apply)
        self.cancel_button.Bind(wx.EVT_BUTTON, self._on_cancel)

        root_sizer.Add(description, 0, wx.ALL | wx.EXPAND, 12)
        root_sizer.Add(choice_label, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 12)
        root_sizer.Add(self.device_choice, 0, wx.ALL | wx.EXPAND, 12)
        root_sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 12)
        panel.SetSizer(root_sizer)

        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizerAndFit(frame_sizer)
        self.SetMinSize((460, -1))
        self.SetEscapeId(wx.ID_CANCEL)
        self.CentreOnParent()
        wx.CallAfter(self._focus_device_choice)

    def _focus_device_choice(self):
        try:
            self.device_choice.SetFocus()
        except RuntimeError:
            pass

    def _on_apply(self, _event):
        if self.IsModal():
            self.EndModal(wx.ID_OK)

    def _on_cancel(self, _event):
        if self.IsModal():
            self.EndModal(wx.ID_CANCEL)

    def selected_device_id(self):
        selection = self.device_choice.GetSelection()
        if 0 <= selection < len(self._device_ids):
            return self._device_ids[selection]
        return ""
