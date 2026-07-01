import wx

from ..accessibility import attach_named_accessible
from ..i18n import _
from .models import format_frequency_label


class EqualizerTabPanel(wx.Panel):
    def __init__(
        self,
        parent,
        *,
        on_toggle_enabled,
        on_select_preset,
        on_apply_to_all_tabs,
        on_create_preset,
        on_edit_preset,
        on_duplicate_preset,
        on_delete_preset,
    ):
        super().__init__(parent, style=wx.TAB_TRAVERSAL)

        self._choice_preset_ids = []
        self._updating_controls = False
        self._on_toggle_enabled = on_toggle_enabled
        self._on_select_preset = on_select_preset
        self._on_apply_to_all_tabs = on_apply_to_all_tabs
        self._on_create_preset = on_create_preset
        self._on_edit_preset = on_edit_preset
        self._on_duplicate_preset = on_duplicate_preset
        self._on_delete_preset = on_delete_preset
        self._band_value_labels = []

        root_sizer = wx.BoxSizer(wx.VERTICAL)

        intro_label = wx.StaticText(
            self,
            label=_(
                "Ajuste o equalizador da aba de mídia ativa. "
                "Use os botões para criar presets, editar ou duplicar presets personalizados "
                "e salvar uma cópia editável de presets embutidos. "
                "Quando quiser repetir a mesma configuração nas abas abertas, use Aplicar em todas as abas."
            ),
        )
        intro_label.Wrap(620)
        root_sizer.Add(intro_label, 0, wx.ALL | wx.EXPAND, 10)

        context_box = wx.StaticBoxSizer(wx.StaticBox(self, label=_("Contexto")), wx.VERTICAL)
        self.target_tab_label = wx.StaticText(self, label=_("Aba alvo: nenhuma"))
        self.target_tab_label.SetName(_("Aba de mídia alvo do equalizador"))
        context_box.Add(self.target_tab_label, 0, wx.ALL | wx.EXPAND, 6)
        root_sizer.Add(context_box, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

        attach_named_accessible(
            self.target_tab_label,
            name=_("Aba de mídia alvo do equalizador"),
            description=_("Informa qual aba de mídia receberá os ajustes do equalizador."),
            value_provider=lambda: self.target_tab_label.GetLabel(),
        )

        controls_box = wx.StaticBoxSizer(wx.StaticBox(self, label=_("Preset ativo")), wx.VERTICAL)
        self.enable_checkbox = wx.CheckBox(self, label=_("Ativar &equalizador nesta aba"))
        self.enable_checkbox.SetName(_("Ativar equalizador nesta aba"))
        self.enable_checkbox.SetToolTip(_("Liga ou desliga o equalizador apenas para a aba de mídia ativa."))

        preset_label = wx.StaticText(self, label=_("Preset:"))
        self.preset_choice = wx.Choice(self)
        self.preset_choice.SetName(_("Preset do equalizador"))
        self.preset_choice.SetToolTip(_("Escolha o preset que será usado na aba de mídia ativa."))

        preset_description_label = wx.StaticText(self, label=_("Descrição do preset:"))
        self.preset_description_ctrl = wx.TextCtrl(
            self,
            style=wx.TE_MULTILINE | wx.TE_READONLY,
        )
        self.preset_description_ctrl.SetMinSize((-1, 72))
        self.preset_description_ctrl.SetName(_("Descrição do preset atual"))
        self.preset_description_ctrl.SetToolTip(
            _("Mostra a descrição do preset atualmente selecionado. Campo somente leitura.")
        )

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.new_button = wx.Button(self, label=_("&Novo..."))
        self.edit_button = wx.Button(self, label=_("&Editar..."))
        self.duplicate_button = wx.Button(self, label=_("&Duplicar..."))
        self.delete_button = wx.Button(self, label=_("E&xcluir"))

        self._configure_action_button(
            self.new_button,
            name=_("Novo preset do equalizador"),
            description=_("Cria um preset personalizado com base nos ajustes atuais."),
        )
        self._configure_action_button(
            self.edit_button,
            name=_("Editar preset do equalizador"),
            description=_("Edita o preset selecionado ou salva uma cópia se o preset for embutido."),
        )
        self._configure_action_button(
            self.duplicate_button,
            name=_("Duplicar preset do equalizador"),
            description=_("Cria uma cópia editável do preset selecionado."),
        )
        self._configure_action_button(
            self.delete_button,
            name=_("Excluir preset do equalizador"),
            description=_("Exclui o preset personalizado selecionado."),
        )

        for button in (self.new_button, self.edit_button, self.duplicate_button, self.delete_button):
            button_sizer.Add(button, 0, wx.RIGHT, 8)

        self.apply_all_button = wx.Button(self, label=_("Aplicar em &todas as abas"))
        self._configure_action_button(
            self.apply_all_button,
            name=_("Aplicar equalizador em todas as abas de mídia"),
            description=_(
                "Copia o estado atual do equalizador, incluindo ativação e preset, "
                "para todas as abas de mídia abertas."
            ),
        )

        controls_box.Add(self.enable_checkbox, 0, wx.ALL | wx.EXPAND, 6)
        controls_box.Add(preset_label, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 6)
        controls_box.Add(self.preset_choice, 0, wx.ALL | wx.EXPAND, 6)
        controls_box.Add(preset_description_label, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 6)
        controls_box.Add(self.preset_description_ctrl, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
        controls_box.Add(button_sizer, 0, wx.ALL | wx.EXPAND, 6)
        controls_box.Add(self.apply_all_button, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
        root_sizer.Add(controls_box, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

        values_box = wx.StaticBoxSizer(wx.StaticBox(self, label=_("Resumo do preset")), wx.VERTICAL)
        values_help = wx.StaticText(
            self,
            label=_("Os valores abaixo mostram a curva do preset atualmente selecionado."),
        )
        values_help.Wrap(600)
        values_box.Add(values_help, 0, wx.ALL | wx.EXPAND, 6)

        values_grid = wx.FlexGridSizer(cols=2, hgap=10, vgap=8)
        values_grid.AddGrowableCol(1, 1)
        values_grid.Add(wx.StaticText(self, label=_("Pré-amplificação:")), 0, wx.ALIGN_CENTER_VERTICAL)
        self.preamp_value_label = wx.StaticText(self, label="0.0 dB")
        self.preamp_value_label.SetName(_("Pré-amplificação atual do preset"))
        values_grid.Add(self.preamp_value_label, 0, wx.ALIGN_CENTER_VERTICAL)
        values_box.Add(values_grid, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)

        attach_named_accessible(
            self.preamp_value_label,
            name=_("Pré-amplificação atual do preset"),
            description=_("Mostra o ganho geral do preset selecionado antes das bandas."),
            value_provider=lambda: self.preamp_value_label.GetLabel(),
        )

        self._values_grid = values_grid
        root_sizer.Add(values_box, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

        self.SetSizer(root_sizer)

        self.enable_checkbox.Bind(wx.EVT_CHECKBOX, self.on_toggle_enabled)
        self.preset_choice.Bind(wx.EVT_CHOICE, self.on_select_preset)
        self.new_button.Bind(wx.EVT_BUTTON, lambda _event: self._on_create_preset())
        self.edit_button.Bind(wx.EVT_BUTTON, lambda _event: self._on_edit_preset())
        self.duplicate_button.Bind(wx.EVT_BUTTON, lambda _event: self._on_duplicate_preset())
        self.delete_button.Bind(wx.EVT_BUTTON, lambda _event: self._on_delete_preset())
        self.apply_all_button.Bind(wx.EVT_BUTTON, lambda _event: self._on_apply_to_all_tabs())

    def _configure_action_button(self, button, *, name, description):
        button.SetName(name)
        button.SetToolTip(description)

    def _update_action_buttons(self, selected_preset):
        has_selection = selected_preset is not None
        is_builtin = bool(has_selection and selected_preset.is_builtin)

        if is_builtin:
            self.edit_button.SetLabel(_("&Salvar cópia..."))
            self._configure_action_button(
                self.edit_button,
                name=_("Salvar cópia do preset do equalizador"),
                description=_("Cria uma cópia editável do preset embutido selecionado."),
            )
        else:
            self.edit_button.SetLabel(_("&Editar..."))
            self._configure_action_button(
                self.edit_button,
                name=_("Editar preset do equalizador"),
                description=_("Edita o preset personalizado selecionado."),
            )

        self._configure_action_button(
            self.duplicate_button,
            name=_("Duplicar preset do equalizador"),
            description=_("Cria uma cópia editável do preset personalizado selecionado."),
        )

        self.edit_button.Enable(has_selection)
        self.duplicate_button.Enable(bool(has_selection and not is_builtin))
        self.delete_button.Enable(bool(has_selection and not is_builtin))

    def _preset_description_text(self, selected_preset):
        if selected_preset is None:
            return _("Nenhum preset selecionado.")

        description = str(getattr(selected_preset, "description", "") or "").strip()
        if description:
            return description

        if selected_preset.is_builtin:
            return _("Preset embutido sem descrição adicional.")

        return _("Preset personalizado sem descrição adicional.")

    def _preset_choice_help_text(self, selected_preset):
        description = self._preset_description_text(selected_preset)
        return _("Escolha o preset que será usado na aba de mídia ativa. Descrição do preset atual: {desc}").format(
            desc=description
        )

    def update_view(
        self,
        *,
        target_tab_title,
        equalizer_enabled,
        presets,
        selected_preset_id,
        selected_preset,
        band_frequencies_hz,
        can_apply_to_all,
    ):
        self.Freeze()
        self._updating_controls = True
        try:
            self.target_tab_label.SetLabel(_("Aba alvo: {title}").format(title=target_tab_title))
            self.enable_checkbox.SetValue(bool(equalizer_enabled))

            self.preset_choice.Clear()
            self._choice_preset_ids = []
            for preset in presets:
                suffix = _(" (embutido)") if preset.is_builtin else ""
                self.preset_choice.Append(f"{preset.name}{suffix}")
                self._choice_preset_ids.append(preset.preset_id)

            selection_index = 0
            if selected_preset_id in self._choice_preset_ids:
                selection_index = self._choice_preset_ids.index(selected_preset_id)
            elif selected_preset and selected_preset.preset_id in self._choice_preset_ids:
                selection_index = self._choice_preset_ids.index(selected_preset.preset_id)

            if self._choice_preset_ids:
                self.preset_choice.SetSelection(selection_index)

            rows_added = self._refresh_value_rows(band_frequencies_hz)
            preset_description = self._preset_description_text(selected_preset)
            self.preset_description_ctrl.ChangeValue(preset_description)
            self.preset_description_ctrl.SetInsertionPoint(0)
            preset_choice_help_text = self._preset_choice_help_text(selected_preset)
            self.preset_choice.SetToolTip(preset_choice_help_text)
            self.preamp_value_label.SetLabel(
                f"{selected_preset.preamp_db:+.1f} dB" if selected_preset else "0.0 dB"
            )

            selected_band_gains = list(selected_preset.band_gains_db) if selected_preset else []
            for label, gain_db in zip(self._band_value_labels, selected_band_gains):
                label.SetLabel(f"{gain_db:+.1f} dB")

            if len(selected_band_gains) < len(self._band_value_labels):
                for label in self._band_value_labels[len(selected_band_gains):]:
                    label.SetLabel("0.0 dB")

            self._update_action_buttons(selected_preset)
            self.apply_all_button.Enable(bool(can_apply_to_all and selected_preset is not None))
            if rows_added:
                self.Layout()
        finally:
            self._updating_controls = False
            self.Thaw()

    def _refresh_value_rows(self, band_frequencies_hz):
        rows_added = False
        while len(self._band_value_labels) < len(band_frequencies_hz):
            frequency_index = len(self._band_value_labels)
            frequency_label = wx.StaticText(self, label=f"{format_frequency_label(band_frequencies_hz[frequency_index])}:")
            value_label = wx.StaticText(self, label="0.0 dB")
            self._values_grid.Add(frequency_label, 0, wx.ALIGN_CENTER_VERTICAL)
            self._values_grid.Add(value_label, 0, wx.ALIGN_CENTER_VERTICAL)
            self._band_value_labels.append(value_label)
            rows_added = True

        return rows_added

    def on_toggle_enabled(self, event):
        if self._updating_controls:
            event.Skip()
            return

        self._on_toggle_enabled(self.enable_checkbox.GetValue())

    def on_select_preset(self, event):
        if self._updating_controls:
            event.Skip()
            return

        selection = self.preset_choice.GetSelection()
        if not 0 <= selection < len(self._choice_preset_ids):
            return

        self._on_select_preset(self._choice_preset_ids[selection])
