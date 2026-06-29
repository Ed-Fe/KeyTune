import wx

from .models import (
    DEFAULT_EQUALIZER_PREAMP_DB,
    EQUALIZER_GAIN_MAX_DB,
    EQUALIZER_GAIN_MIN_DB,
    format_frequency_label,
    normalize_band_gains,
)


class EqualizerPresetDialog(wx.Dialog):
    def __init__(
        self,
        parent,
        *,
        title,
        intro_text,
        band_frequencies_hz,
        preset_name="",
        preamp_db=DEFAULT_EQUALIZER_PREAMP_DB,
        band_gains_db=None,
        validate_name=None,
    ):
        super().__init__(
            parent,
            title=title,
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self._validate_name = validate_name
        self._band_frequencies_hz = list(band_frequencies_hz or [])
        self._band_controls = []
        self._gain_control_names = {}

        panel = wx.Panel(self)
        root_sizer = wx.BoxSizer(wx.VERTICAL)

        intro_label = wx.StaticText(panel, label=intro_text)
        intro_label.Wrap(560)
        self.intro_label = intro_label
        root_sizer.Add(intro_label, 0, wx.ALL | wx.EXPAND, 10)

        name_box = wx.StaticBoxSizer(wx.StaticBox(panel, label="Identificação do preset"), wx.VERTICAL)
        name_label = wx.StaticText(panel, label="Nome do preset:")
        self.name_ctrl = wx.TextCtrl(panel)
        self.name_ctrl.SetName("Nome do preset")
        self.name_ctrl.SetToolTip("Digite um nome único e fácil de reconhecer para o preset.")
        name_help = wx.StaticText(
            panel,
            label="Use um nome curto e claro. Exemplo: Graves profundos personalizados.",
        )
        name_help.Wrap(540)
        name_box.Add(name_label, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 6)
        name_box.Add(self.name_ctrl, 0, wx.ALL | wx.EXPAND, 6)
        name_box.Add(name_help, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
        root_sizer.Add(name_box, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

        preamp_box = wx.StaticBoxSizer(wx.StaticBox(panel, label="Pré-amplificação"), wx.VERTICAL)
        preamp_group, self.preamp_ctrl = self._build_gain_control_group(
            panel,
            label_text="Pré-amplificação",
            help_text="Ajusta o ganho geral antes das bandas. Se o som distorcer, reduza este valor.",
        )
        preamp_box.Add(preamp_group, 0, wx.ALL | wx.EXPAND, 6)
        root_sizer.Add(preamp_box, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

        bands_box = wx.StaticBoxSizer(wx.StaticBox(panel, label="Bandas do equalizador"), wx.VERTICAL)
        bands_help = wx.StaticText(
            panel,
            label="Valores positivos reforçam a frequência. Valores negativos atenuam. Faça ajustes sutis para evitar distorção.",
        )
        bands_help.Wrap(540)
        bands_box.Add(bands_help, 0, wx.ALL | wx.EXPAND, 6)

        bands_grid = wx.FlexGridSizer(cols=2, hgap=10, vgap=8)
        bands_grid.AddGrowableCol(1, 1)
        for frequency_hz in self._band_frequencies_hz:
            frequency_label = format_frequency_label(frequency_hz)
            group, control = self._build_gain_control_group(
                panel,
                label_text=f"Banda {frequency_label}",
                help_text=(
                    f"Ajusta o ganho da banda de {frequency_label}. "
                    "Aceita valores de -20,0 dB até 20,0 dB."
                ),
            )
            bands_grid.Add(group, 0, wx.EXPAND)
            self._band_controls.append(control)

        bands_box.Add(bands_grid, 0, wx.ALL | wx.EXPAND, 6)
        root_sizer.Add(bands_box, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

        button_sizer = wx.StdDialogButtonSizer()
        self.save_button = wx.Button(panel, wx.ID_OK, "&Salvar")
        self.cancel_button = wx.Button(panel, wx.ID_CANCEL, "&Cancelar")
        self.save_button.SetName("Salvar preset do equalizador")
        self.save_button.SetToolTip("Salva o preset com o nome e os ajustes informados.")
        self.cancel_button.SetName("Cancelar edição do preset do equalizador")
        self.cancel_button.SetToolTip("Fecha a janela sem salvar as alterações do preset.")
        self.save_button.SetDefault()
        button_sizer.AddButton(self.save_button)
        button_sizer.AddButton(self.cancel_button)
        button_sizer.Realize()
        root_sizer.Add(button_sizer, 0, wx.ALL | wx.EXPAND, 10)

        panel.SetSizer(root_sizer)

        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizerAndFit(frame_sizer)
        self.SetMinSize((640, 680))
        self.SetEscapeId(wx.ID_CANCEL)
        self.CentreOnParent()

        self._populate_controls(
            preset_name=preset_name,
            preamp_db=preamp_db,
            band_gains_db=band_gains_db,
        )

        self.Bind(wx.EVT_BUTTON, self.on_confirm, id=wx.ID_OK)
        # ESC handling is provided by SetEscapeId(wx.ID_CANCEL) above;
        # an extra EVT_CHAR_HOOK would duplicate that behavior.

    def configure_dialog(self, *, title, intro_text, preset_name, preamp_db, band_gains_db, validate_name, band_frequencies_hz):
        self.SetTitle(title)
        self._validate_name = validate_name
        self._band_frequencies_hz = list(band_frequencies_hz or self._band_frequencies_hz)

        self.Freeze()
        try:
            self.intro_label.SetLabel(intro_text)
            self.intro_label.Wrap(560)
            self._populate_controls(
                preset_name=preset_name,
                preamp_db=preamp_db,
                band_gains_db=band_gains_db,
            )
        finally:
            self.Thaw()

    def _build_gain_control(self, parent, *, name, help_text):
        control = wx.SpinCtrlDouble(
            parent,
            min=EQUALIZER_GAIN_MIN_DB,
            max=EQUALIZER_GAIN_MAX_DB,
            inc=0.5,
        )
        control.SetDigits(1)
        control.SetName(f"{name} (dB)")
        control.SetToolTip(help_text)
        # Unlike the Preferences wx.SpinCtrl, wx.SpinCtrlDouble wraps its edit
        # field and spin buttons in an extra ROLE_SYSTEM_CLIENT window. wx-dev
        # confirms NVDA/JAWS can read the value through that wrapper but never
        # the label, and that this cannot be fixed via wx.Accessible/SetName
        # (https://groups.google.com/g/wx-dev/c/nEaCaK6vHZU). So we bypass the
        # accessibility tree entirely and announce the labeled value directly
        # through the screen reader on focus and on change.
        self._gain_control_names[control.GetId()] = name
        control.Bind(wx.EVT_SET_FOCUS, self.on_gain_control_focus)
        control.Bind(wx.EVT_SPINCTRLDOUBLE, self.on_gain_control_changed)
        return control

    def _build_gain_control_group(self, parent, *, label_text, help_text):
        label = wx.StaticText(parent, label=f"{label_text}:")
        label.Wrap(250)
        control = self._build_gain_control(parent, name=label_text, help_text=help_text)
        help_label = wx.StaticText(parent, label=help_text)
        help_label.Wrap(250)

        # Plain vertical sizer instead of a per-control StaticBox: each gain
        # control already lives inside a section box ("Pré-amplificação" /
        # "Bandas do equalizador"), so an extra box per control just repeated the
        # caption as a third copy of the label. The visible label stays; the
        # accessible name is guaranteed by the focus/change announcement above.
        box_sizer = wx.BoxSizer(wx.VERTICAL)
        box_sizer.Add(label, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 6)
        box_sizer.Add(control, 0, wx.ALL | wx.EXPAND, 6)
        box_sizer.Add(help_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
        return box_sizer, control

    def _announce_from_parent(self, message):
        if not message:
            return

        parent = self.GetParent()
        announce = getattr(parent, "_announce", None)
        if callable(announce):
            announce(message)

    def _gain_control_message(self, control):
        control_name = self._gain_control_names.get(control.GetId(), control.GetName() or "Controle de ganho")
        try:
            value = float(control.GetValue())
        except (TypeError, ValueError):
            value = 0.0
        return f"{control_name}: {value:+.1f} dB."

    def _populate_controls(self, *, preset_name, preamp_db, band_gains_db):
        self.name_ctrl.SetValue(str(preset_name or "").strip())
        self.preamp_ctrl.SetValue(float(preamp_db or 0.0))

        normalized_bands = normalize_band_gains(
            list(band_gains_db or []),
            expected_count=len(self._band_controls),
        )
        for control, gain_db in zip(self._band_controls, normalized_bands):
            control.SetValue(gain_db)

    def get_preset_payload(self):
        return {
            "name": self.name_ctrl.GetValue().strip(),
            "preamp_db": float(self.preamp_ctrl.GetValue()),
            "band_gains_db": [float(control.GetValue()) for control in self._band_controls],
        }

    def on_confirm(self, event):
        payload = self.get_preset_payload()
        if not payload["name"]:
            wx.MessageBox(
                "Digite um nome para o preset antes de salvar.",
                "Preset do equalizador",
                wx.OK | wx.ICON_INFORMATION,
                parent=self,
            )
            self.name_ctrl.SetFocus()
            return

        if callable(self._validate_name):
            validation_error = self._validate_name(payload["name"])
            if validation_error:
                wx.MessageBox(
                    validation_error,
                    "Preset do equalizador",
                    wx.OK | wx.ICON_INFORMATION,
                    parent=self,
                )
                self.name_ctrl.SetFocus()
                return

        event.Skip()

    def on_gain_control_focus(self, event):
        control = event.GetEventObject()
        if isinstance(control, wx.SpinCtrlDouble):
            # CallAfter so our announcement is spoken after (and replaces) the
            # screen reader's own bare "edit selected 0.0" on focus.
            wx.CallAfter(self._announce_from_parent, self._gain_control_message(control))
        event.Skip()

    def on_gain_control_changed(self, event):
        control = event.GetEventObject()
        if isinstance(control, wx.SpinCtrlDouble):
            self._announce_from_parent(self._gain_control_message(control))
        event.Skip()
