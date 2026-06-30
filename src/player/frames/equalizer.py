import wx

from ..i18n import _
from ..equalizer.backend import (
    build_mpv_equalizer_filter,
    load_equalizer_catalog,
)
from ..equalizer.models import (
    DEFAULT_EQUALIZER_PRESET_ID,
    DEFAULT_EQUALIZER_PRESET_KEY,
    EqualizerPreset,
    EQUALIZER_SCREEN_ID,
    build_builtin_preset_id,
    create_custom_preset,
    normalize_equalizer_preset_id,
    normalize_band_gains,
    normalize_custom_presets,
)
from ..playlists import PlaylistState, ScreenTabState


def _equalizer_preset_dialog_class():
    from ..equalizer.dialog import EqualizerPresetDialog

    return EqualizerPresetDialog


def _equalizer_tab_panel_class():
    from ..equalizer.panel import EqualizerTabPanel

    return EqualizerTabPanel


class FrameEqualizerMixin:
    def _initialize_equalizer_support(self):
        self.equalizer_catalog = load_equalizer_catalog()
        expected_band_count = len(self._equalizer_band_frequencies())
        self.settings.equalizer_custom_presets = normalize_custom_presets(
            getattr(self.settings, "equalizer_custom_presets", []),
            expected_band_count=expected_band_count,
        )

    def _equalizer_band_frequencies(self):
        if not hasattr(self, "equalizer_catalog"):
            return []
        return list(self.equalizer_catalog.band_frequencies_hz)

    def _equalizer_supported(self):
        return bool(getattr(self, "equalizer_catalog", None) and self.equalizer_catalog.supported)

    def _available_equalizer_presets(self):
        if not hasattr(self, "settings"):
            return []
        builtin_presets = list(getattr(self.equalizer_catalog, "builtin_presets", []))
        custom_presets = list(getattr(self.settings, "equalizer_custom_presets", []))
        return builtin_presets + custom_presets

    def _default_equalizer_preset(self):
        default_preset_id = build_builtin_preset_id(DEFAULT_EQUALIZER_PRESET_KEY)
        for preset in self._available_equalizer_presets():
            if preset.preset_id == default_preset_id:
                return preset

        presets = self._available_equalizer_presets()
        return presets[0] if presets else None

    def _get_equalizer_preset(self, preset_id=None):
        available_presets = self._available_equalizer_presets()
        if not available_presets:
            return None

        target_preset_id = normalize_equalizer_preset_id(preset_id)
        for preset in available_presets:
            if preset.preset_id == target_preset_id:
                return preset

        return self._default_equalizer_preset()

    def _get_equalizer_target_state(self):
        state = self._get_active_playlist_state()
        if state:
            return state
        return self._get_playlist_state()

    def _apply_equalizer_state_to_player(self, player, state=None):
        if not self._equalizer_supported() or player is None:
            return False

        state = state or self._get_equalizer_target_state()
        if not state:
            return False

        try:
            if not state.equalizer_enabled:
                player.set_audio_filters("")
                return True
        except Exception:
            return False

        preset = self._get_equalizer_preset(state.equalizer_preset_id)
        if preset is None:
            return False

        filter_chain = build_mpv_equalizer_filter(
            preset,
            band_frequencies_hz=self._equalizer_band_frequencies(),
        )
        if not filter_chain:
            return False

        try:
            player.set_audio_filters(filter_chain)
            return True
        except Exception:
            return False

    def _apply_equalizer_state(self, state=None):
        if not hasattr(self, "player"):
            return False

        return self._apply_equalizer_state_to_player(self.player, state)

    def _apply_equalizer_state_to_current_playback(self, state=None):
        applied = self._apply_equalizer_state(state)

        crossfade_state = getattr(self, "_crossfade_state", None)
        managed_player = getattr(self, "_managed_player", None)
        if not crossfade_state or not callable(managed_player):
            return applied

        for player_key in (crossfade_state.get("incoming_key"), crossfade_state.get("outgoing_key")):
            player = managed_player(player_key)
            if player is None or player is getattr(self, "player", None):
                continue
            applied = self._apply_equalizer_state_to_player(player, state) or applied

        return applied

    def _equalizer_media_tab_count(self):
        return sum(1 for state in getattr(self, "playlists", []) if isinstance(state, PlaylistState))

    def _set_equalizer_for_target_tab(self, *, enabled=None, preset_id=None, announce=True):
        state = self._get_equalizer_target_state()
        if not state:
            if announce:
                self._announce(_("Nenhuma aba de mídia ativa para configurar o equalizador."))
            return False

        preset = self._get_equalizer_preset(preset_id or state.equalizer_preset_id)
        if preset is None:
            if announce:
                self._announce(_("Nenhum preset de equalizador está disponível."))
            return False

        state.equalizer_preset_id = preset.preset_id
        if enabled is not None:
            state.equalizer_enabled = bool(enabled)
        elif preset_id is not None:
            state.equalizer_enabled = True

        applied = self._apply_equalizer_state_to_current_playback(state)
        self._refresh_equalizer_screen()
        if not announce:
            return applied

        if state.equalizer_enabled:
            self._announce(self._equalizer_enabled_message(state, preset, include_description=bool(preset_id is not None)))
            if hasattr(self, "_set_status_message"):
                self._set_status_message(_("Equalizador: {name}.").format(name=preset.name))
        else:
            self._announce(_("Equalizador desativado na aba {tab}.").format(tab=state.title))
            if hasattr(self, "_set_status_message"):
                self._set_status_message(_("Equalizador desativado."))
        return applied

    def _equalizer_enabled_message(self, state, preset, *, include_description=False):
        message = _("Equalizador na aba {tab}: {name}.").format(tab=state.title, name=preset.name)
        if not include_description:
            return message

        description = str(getattr(preset, "description", "") or "").strip()
        if description:
            return f"{message} {description}"

        if preset.is_builtin:
            return f"{message} " + _("Preset embutido do equalizador.")

        return f"{message} " + _("Preset personalizado.")

    def _create_equalizer_page(self, parent):
        panel_class = _equalizer_tab_panel_class()
        cached_page = getattr(self, "_equalizer_tab_page_cache", None)
        if isinstance(cached_page, panel_class) and cached_page.GetParent() == parent:
            self._equalizer_tab_page_cache = None
            return cached_page

        return panel_class(
            parent,
            on_toggle_enabled=self.on_toggle_equalizer_enabled,
            on_select_preset=self.on_select_equalizer_preset,
            on_apply_to_all_tabs=self.on_apply_equalizer_to_all_tabs,
            on_create_preset=self.on_create_equalizer_preset,
            on_edit_preset=self.on_edit_equalizer_preset,
            on_duplicate_preset=self.on_duplicate_equalizer_preset,
            on_delete_preset=self.on_delete_equalizer_preset,
        )

    def _prime_equalizer_ui(self):
        if getattr(self, "_equalizer_ui_primed", False):
            return

        self._equalizer_ui_primed = True
        if not self._equalizer_supported():
            return

        self._refresh_equalizer_screen_later()

    def _dispose_equalizer_ui_cache(self):
        dialog_class = _equalizer_preset_dialog_class()
        dialog = getattr(self, "_equalizer_preset_dialog", None)
        self._equalizer_preset_dialog = None
        if isinstance(dialog, dialog_class):
            try:
                dialog.Destroy()
            except Exception:
                pass

        panel_class = _equalizer_tab_panel_class()
        cached_page = getattr(self, "_equalizer_tab_page_cache", None)
        self._equalizer_tab_page_cache = None
        if isinstance(cached_page, panel_class):
            try:
                cached_page.Destroy()
            except Exception:
                pass

    def _refresh_equalizer_screen_later(self):
        wx.CallAfter(self._refresh_equalizer_screen)

    def _get_equalizer_panel(self):
        if not hasattr(self, "playlists") or not hasattr(self, "notebook"):
            return None

        panel_class = _equalizer_tab_panel_class()

        for index, state in enumerate(self.playlists):
            if isinstance(state, ScreenTabState) and state.screen_id == EQUALIZER_SCREEN_ID:
                page = self.notebook.GetPage(index)
                if isinstance(page, panel_class):
                    return page

        return None

    def _refresh_equalizer_screen(self):
        panel = self._get_equalizer_panel()
        if panel is None:
            return

        state = self._get_equalizer_target_state()
        selected_preset = self._get_equalizer_preset(state.equalizer_preset_id if state else None)
        if state and selected_preset:
            state.equalizer_preset_id = selected_preset.preset_id

        panel.update_view(
            target_tab_title=state.title if state else _("nenhuma aba de mídia"),
            equalizer_enabled=state.equalizer_enabled if state else False,
            presets=self._available_equalizer_presets(),
            selected_preset_id=state.equalizer_preset_id if state else DEFAULT_EQUALIZER_PRESET_ID,
            selected_preset=selected_preset,
            band_frequencies_hz=self._equalizer_band_frequencies(),
            can_apply_to_all=bool(state and self._equalizer_media_tab_count() > 1),
        )

    def _ensure_equalizer_available(self):
        if self._equalizer_supported():
            return True

        self._announce(_("O equalizador não está disponível nesta instalação."))
        return False

    def on_open_equalizer(self, _event):
        if not self._ensure_equalizer_available():
            return

        self._open_screen_tab(
            EQUALIZER_SCREEN_ID,
            _("Equalizador"),
            self._create_equalizer_page,
            select=True,
            activation_message=_("Aba Equalizador. Ajustes do som disponíveis para a aba de mídia ativa."),
            on_activate=self._refresh_equalizer_screen_later,
        )

    def on_toggle_equalizer_enabled(self, enabled):
        self._set_equalizer_for_target_tab(enabled=enabled, announce=True)

    def on_select_equalizer_preset(self, preset_id):
        self._set_equalizer_for_target_tab(preset_id=preset_id, announce=True)

    def on_apply_equalizer_to_all_tabs(self):
        if not self._ensure_equalizer_available():
            return

        state = self._get_equalizer_target_state()
        if not state:
            self._announce(_("Nenhuma aba de mídia ativa para copiar o equalizador."))
            return

        media_tab_count = self._equalizer_media_tab_count()
        if media_tab_count <= 1:
            self._announce(_("Abra pelo menos duas abas de mídia para aplicar o equalizador em lote."))
            return

        preset = self._get_equalizer_preset(state.equalizer_preset_id)
        if preset is None:
            self._announce(_("Nenhum preset de equalizador está disponível."))
            return

        for candidate_state in self.playlists:
            if not isinstance(candidate_state, PlaylistState):
                continue
            candidate_state.equalizer_enabled = bool(state.equalizer_enabled)
            candidate_state.equalizer_preset_id = preset.preset_id

        self._apply_equalizer_state_to_current_playback(state)
        self._refresh_equalizer_screen()

        if state.equalizer_enabled:
            self._announce(
                _("Equalizador {name} aplicado em {count} abas de mídia.").format(
                    name=preset.name, count=media_tab_count
                )
            )
            return

        self._announce(_("Equalizador desativado em {count} abas de mídia.").format(count=media_tab_count))

    def _validate_equalizer_preset_name(self, name, *, excluding_preset_id=None):
        normalized_name = str(name or "").strip().casefold()
        if not normalized_name:
            return _("Digite um nome para o preset.")

        for preset in self._available_equalizer_presets():
            if preset.preset_id == excluding_preset_id:
                continue
            if preset.name.strip().casefold() == normalized_name:
                return _("Já existe um preset com esse nome. Escolha outro nome.")

        return None

    def _suggest_equalizer_preset_name(self, base_name):
        base_label = str(base_name or _("Preset personalizado")).strip() or _("Preset personalizado")
        candidate = base_label
        sequence = 2
        while self._validate_equalizer_preset_name(candidate) is not None:
            candidate = f"{base_label} {sequence}"
            sequence += 1
        return candidate

    def _ensure_equalizer_preset_dialog(self):
        dialog_class = _equalizer_preset_dialog_class()
        dialog = getattr(self, "_equalizer_preset_dialog", None)
        if isinstance(dialog, dialog_class):
            return dialog

        seed_preset = self._default_equalizer_preset()
        if seed_preset is None:
            return None

        band_frequencies_hz = self._equalizer_band_frequencies()
        dialog = dialog_class(
            self,
            title=_("Novo preset do equalizador"),
            intro_text=_(
                "Crie um preset personalizado. Os ajustes ficam salvos nas preferências e podem ser aplicados a qualquer aba de mídia."
            ),
            band_frequencies_hz=band_frequencies_hz,
            preset_name=self._suggest_equalizer_preset_name(_("Preset personalizado")),
            preamp_db=seed_preset.preamp_db,
            band_gains_db=normalize_band_gains(
                seed_preset.band_gains_db,
                expected_count=len(band_frequencies_hz),
            ),
            validate_name=lambda name: self._validate_equalizer_preset_name(name),
        )
        self._equalizer_preset_dialog = dialog
        return dialog

    def _show_equalizer_preset_dialog(
        self,
        *,
        title,
        intro_text,
        seed_preset,
        preset_name,
        excluding_preset_id=None,
    ):
        band_frequencies_hz = self._equalizer_band_frequencies()
        dialog = self._ensure_equalizer_preset_dialog()
        if dialog is None:
            return None

        expected_band_count = len(band_frequencies_hz)

        dialog.configure_dialog(
            title=title,
            intro_text=intro_text,
            preset_name=preset_name,
            preamp_db=seed_preset.preamp_db,
            band_gains_db=normalize_band_gains(
                seed_preset.band_gains_db,
                expected_count=expected_band_count,
            ),
            validate_name=lambda name: self._validate_equalizer_preset_name(
                name,
                excluding_preset_id=excluding_preset_id,
            ),
            band_frequencies_hz=band_frequencies_hz,
        )
        if dialog.ShowModal() != wx.ID_OK:
            return None
        return dialog.get_preset_payload()

    def _append_custom_equalizer_preset(self, preset, *, refresh=True):
        self.settings.equalizer_custom_presets.append(preset)
        self._save_settings()
        if refresh:
            self._refresh_equalizer_screen()

    def on_create_equalizer_preset(self):
        if not self._ensure_equalizer_available():
            return

        seed_preset = self._default_equalizer_preset()
        if seed_preset is None:
            self._announce(_("Nenhum preset base está disponível para criar um preset novo."))
            return

        payload = self._show_equalizer_preset_dialog(
            title=_("Novo preset do equalizador"),
            intro_text=_(
                "Crie um preset personalizado. Os ajustes ficam salvos nas preferências e podem ser aplicados a qualquer aba de mídia."
            ),
            seed_preset=seed_preset,
            preset_name=self._suggest_equalizer_preset_name(_("Preset personalizado")),
        )
        if payload is None:
            return

        new_preset = create_custom_preset(
            payload["name"],
            payload["preamp_db"],
            normalize_band_gains(
                payload["band_gains_db"],
                expected_count=len(self._equalizer_band_frequencies()),
            ),
        )
        self._append_custom_equalizer_preset(new_preset, refresh=False)
        self._set_equalizer_for_target_tab(preset_id=new_preset.preset_id, enabled=True, announce=False)
        self._announce(_("Preset criado e aplicado: {name}.").format(name=new_preset.name))

    def _current_equalizer_preset(self):
        state = self._get_equalizer_target_state()
        return self._get_equalizer_preset(state.equalizer_preset_id if state else None)

    def _replace_custom_equalizer_preset(self, updated_preset, *, refresh=True):
        replaced = False
        updated_presets = []
        for preset in self.settings.equalizer_custom_presets:
            if preset.preset_id == updated_preset.preset_id:
                updated_presets.append(updated_preset)
                replaced = True
            else:
                updated_presets.append(preset)

        if not replaced:
            updated_presets.append(updated_preset)

        self.settings.equalizer_custom_presets = updated_presets
        self._save_settings()
        if refresh:
            self._refresh_equalizer_screen()

    def on_edit_equalizer_preset(self):
        if not self._ensure_equalizer_available():
            return

        preset = self._current_equalizer_preset()
        if preset is None:
            self._announce(_("Nenhum preset selecionado para editar."))
            return

        if preset.is_builtin:
            self._duplicate_equalizer_preset(
                preset,
                title=_("Salvar cópia do preset embutido"),
                intro_text=_(
                    "Presets embutidos são somente leitura. Ajuste os valores abaixo e salve uma cópia personalizada."
                ),
            )
            return

        payload = self._show_equalizer_preset_dialog(
            title=_("Editar preset: {name}").format(name=preset.name),
            intro_text=_("Altere o nome, a pré-amplificação e as bandas do preset personalizado."),
            seed_preset=preset,
            preset_name=preset.name,
            excluding_preset_id=preset.preset_id,
        )
        if payload is None:
            return

        updated_preset = create_custom_preset(
            payload["name"],
            payload["preamp_db"],
            normalize_band_gains(
                payload["band_gains_db"],
                expected_count=len(self._equalizer_band_frequencies()),
            ),
            preset_id=preset.preset_id,
        )
        self._replace_custom_equalizer_preset(updated_preset, refresh=False)
        self._apply_equalizer_state_to_current_playback(self._get_equalizer_target_state())
        self._refresh_equalizer_screen()
        self._announce(_("Preset atualizado: {name}.").format(name=updated_preset.name))

    def _duplicate_equalizer_preset(self, preset, *, title, intro_text):
        payload = self._show_equalizer_preset_dialog(
            title=title,
            intro_text=intro_text,
            seed_preset=preset,
            preset_name=self._suggest_equalizer_preset_name(_("{name} personalizado").format(name=preset.name)),
        )
        if payload is None:
            return False

        duplicated_preset = create_custom_preset(
            payload["name"],
            payload["preamp_db"],
            normalize_band_gains(
                payload["band_gains_db"],
                expected_count=len(self._equalizer_band_frequencies()),
            ),
        )
        self._append_custom_equalizer_preset(duplicated_preset, refresh=False)
        self._set_equalizer_for_target_tab(preset_id=duplicated_preset.preset_id, enabled=True, announce=False)
        self._announce(_("Preset criado e aplicado: {name}.").format(name=duplicated_preset.name))
        return True

    def on_duplicate_equalizer_preset(self):
        if not self._ensure_equalizer_available():
            return

        preset = self._current_equalizer_preset()
        if preset is None:
            self._announce(_("Nenhum preset selecionado para duplicar."))
            return

        self._duplicate_equalizer_preset(
            preset,
            title=_("Duplicar preset: {name}").format(name=preset.name),
            intro_text=_("Crie uma cópia editável do preset selecionado."),
        )

    def on_delete_equalizer_preset(self):
        if not self._ensure_equalizer_available():
            return

        preset = self._current_equalizer_preset()
        if preset is None:
            self._announce(_("Nenhum preset selecionado para excluir."))
            return

        if preset.is_builtin:
            self._announce(_("Presets embutidos não podem ser excluídos."))
            return

        with wx.MessageDialog(
            self,
            _("Deseja realmente excluir o preset {name}?").format(name=preset.name),
            _("Excluir preset do equalizador"),
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_YES:
                return

        self.settings.equalizer_custom_presets = [
            existing_preset
            for existing_preset in self.settings.equalizer_custom_presets
            if existing_preset.preset_id != preset.preset_id
        ]

        fallback_preset = self._default_equalizer_preset()
        fallback_preset_id = fallback_preset.preset_id if fallback_preset else DEFAULT_EQUALIZER_PRESET_ID
        for state in self.playlists:
            if isinstance(state, PlaylistState) and state.equalizer_preset_id == preset.preset_id:
                state.equalizer_preset_id = fallback_preset_id

        self._save_settings()
        self._apply_equalizer_state_to_current_playback(self._get_equalizer_target_state())
        self._refresh_equalizer_screen()
        self._announce(_("Preset excluído: {name}.").format(name=preset.name))
