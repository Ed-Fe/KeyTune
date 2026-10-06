"""Atalhos personalizados da janela principal.

Os atalhos padrão continuam tratados onde sempre estiveram (``on_key_down``,
itens de menu e a tabela de aceleradores). Este mixin só entra quando o usuário
personaliza algo: o atalho novo dispara a ação, o padrão que ela deixou de usar
para de fazer qualquer coisa e os menus passam a mostrar o atalho em vigor.
"""

from __future__ import annotations

import re

import wx

from ..constants import LARGE_SEEK_STEP_MS
from ..i18n import _
from ..keyboard import KeyboardCustomizationDialog, Keymap, format_shortcut, is_bare_shortcut
from ..keyboard.shortcuts import SCOPE_LOCAL, actions, normalize_shortcut
from ..keyboard.wx_keys import accelerator_entry, shortcut_from_key_event

# "Em&baralhar (E)": a dica entre parênteses no fim do rótulo de um item de menu.
_MENU_HINT_PATTERN = re.compile(r"\s*\([^()]*\)\s*$")


class FrameKeyboardMixin:
    # ------------------------------------------------------------------
    # Aplicação das personalizações
    # ------------------------------------------------------------------
    def _apply_keyboard_customization(self):
        """Recarrega os atalhos personalizados nos menus, aceleradores e teclado."""
        self._keymap = Keymap(getattr(self.settings, "custom_shortcuts", {}) or {})
        self._refresh_accelerator_table()
        self._refresh_shortcut_menu_labels()

    def _refresh_accelerator_table(self):
        entries = []
        for action in actions(SCOPE_LOCAL):
            if not action.accelerator or not action.menu:
                continue
            shortcut = self._keymap.shortcut_for(action.action_id)
            command_id = getattr(self, action.menu, None)
            if not shortcut or command_id is None or is_bare_shortcut(shortcut):
                continue
            entry = accelerator_entry(shortcut, command_id)
            if entry is not None:
                entries.append(entry)
        self.SetAcceleratorTable(wx.AcceleratorTable(entries))

    def _shortcut_menu_item_id(self, action):
        if action.menu:
            command_id = getattr(self, action.menu, None)
            return int(command_id) if command_id is not None else None
        if action.action_id.startswith("rate_"):
            rating = int(action.action_id.split("_", 1)[1])
            for item_id, item_rating in getattr(self, "_rating_menu_actions", {}).items():
                if item_rating == rating:
                    return int(item_id)
        return None

    def _refresh_shortcut_menu_labels(self):
        menu_bar = self.GetMenuBar()
        if menu_bar is None:
            return
        # O texto de cada item sem o atalho, e se o atalho ia depois de um \t
        # (acelerador de verdade) ou entre parênteses (só uma dica).
        bases = getattr(self, "_shortcut_menu_bases", None)
        if bases is None:
            bases = self._shortcut_menu_bases = {}
        for action in actions(SCOPE_LOCAL):
            item_id = self._shortcut_menu_item_id(action)
            item = menu_bar.FindItemById(item_id) if item_id is not None else None
            if item is None:
                continue
            if action.action_id not in bases:
                label = item.GetItemLabel()
                if "\t" in label:
                    bases[action.action_id] = (label.split("\t", 1)[0], True)
                elif action.default and _MENU_HINT_PATTERN.search(label):
                    bases[action.action_id] = (_MENU_HINT_PATTERN.sub("", label), False)
                else:
                    bases[action.action_id] = (label, True)
            base, uses_accelerator = bases[action.action_id]
            shortcut = self._keymap.shortcut_for(action.action_id)
            if not shortcut:
                label = base
            elif uses_accelerator and not is_bare_shortcut(shortcut):
                label = f"{base}\t{shortcut}"
            else:
                # Tecla sem Ctrl/Alt nunca vira acelerador: ela deixaria de
                # chegar aos campos de texto.
                label = f"{base} ({format_shortcut(shortcut)})"
            if label != item.GetItemLabel():
                item.SetItemLabel(label)

    # ------------------------------------------------------------------
    # Teclado
    # ------------------------------------------------------------------
    def _handle_custom_shortcut(self, event):
        """Trata o atalho personalizado do evento; ``True`` se ele foi consumido."""
        keymap = getattr(self, "_keymap", None)
        if keymap is None or not keymap.has_overrides:
            return False
        shortcut = shortcut_from_key_event(event)
        if not shortcut:
            return False
        action, consumed = keymap.resolve(shortcut)
        if not consumed:
            return False
        if is_bare_shortcut(shortcut):
            # Como o Espaço e as setas: só na superfície do player. Na lista de
            # itens e nos demais controles a tecla pertence ao controle.
            if not self._focused_window_drives_playback():
                return False
            browser = self._get_browser_panel()
            if browser and browser.is_item_navigation_active():
                return False
        if action is not None:
            self._run_key_action(action)
        return True

    def _run_key_action(self, action):
        handler = getattr(self, action.handler, None)
        if not callable(handler):
            return False
        if action.handler.startswith("on_"):
            handler(None)
        else:
            handler()
        return True

    def _shortcut_volume_up(self):
        self._change_volume(self.settings.volume_step)

    def _shortcut_volume_down(self):
        self._change_volume(-self.settings.volume_step)

    # Os atalhos globais agem com a janela escondida: o volume novo é falado.
    def _shortcut_volume_up_announced(self):
        self._shortcut_volume_up()
        self._announce_current_volume()

    def _shortcut_volume_down_announced(self):
        self._shortcut_volume_down()
        self._announce_current_volume()

    def _shortcut_seek_forward(self):
        self._seek_relative(self.settings.seek_step_ms)

    def _shortcut_seek_backward(self):
        self._seek_relative(-self.settings.seek_step_ms)

    def _shortcut_seek_forward_large(self):
        self._seek_relative(LARGE_SEEK_STEP_MS)

    def _shortcut_seek_backward_large(self):
        self._seek_relative(-LARGE_SEEK_STEP_MS)

    def _shortcut_find_next(self):
        self._repeat_item_search(1)

    def _shortcut_find_previous(self):
        self._repeat_item_search(-1)

    def _rate_current_youtube_music_media_safely(self, rating):
        rate = getattr(self, "_rate_current_youtube_music_media", None)
        if callable(rate):
            rate(rating)

    def _shortcut_like_media(self):
        self._rate_current_youtube_music_media_safely("LIKE")

    def _shortcut_dislike_media(self):
        self._rate_current_youtube_music_media_safely("DISLIKE")

    def _shortcut_rate_0(self):
        self._rate_selection(0)

    def _shortcut_rate_1(self):
        self._rate_selection(1)

    def _shortcut_rate_2(self):
        self._rate_selection(2)

    def _shortcut_rate_3(self):
        self._rate_selection(3)

    def _shortcut_rate_4(self):
        self._rate_selection(4)

    def _shortcut_rate_5(self):
        self._rate_selection(5)

    # ------------------------------------------------------------------
    # Tela de personalização
    # ------------------------------------------------------------------
    def on_customize_keyboard(self, _event):
        self._open_keyboard_customization()

    def _open_keyboard_customization(self):
        dialog = KeyboardCustomizationDialog(
            self,
            local_overrides=self.settings.custom_shortcuts,
            global_overrides=self.settings.global_hotkeys,
            global_enabled=self.settings.global_hotkeys_enabled,
            global_available=self._global_hotkeys_supported(),
        )
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            self.settings.custom_shortcuts = dialog.get_local_overrides()
            self.settings.global_hotkeys = dialog.get_global_overrides()
            self.settings.global_hotkeys_enabled = dialog.get_global_enabled()
        finally:
            dialog.Destroy()

        self._save_settings()
        self._apply_keyboard_customization()
        failed = self._apply_global_hotkeys()
        if failed:
            self._announce(
                _("Atalhos salvos. Não foi possível registrar {shortcuts}: já estão em uso por outro programa.").format(
                    shortcuts=", ".join(format_shortcut(shortcut) for shortcut in failed)
                )
            )
        else:
            self._announce(_("Atalhos salvos."))

    def _custom_shortcuts_help_text(self):
        """Linhas da ajuda rápida com os atalhos que o usuário mudou."""
        overrides = getattr(self.settings, "custom_shortcuts", {}) or {}
        if not overrides:
            return ""
        lines = [_("Atalhos personalizados (substituem os acima):")]
        for action in actions(SCOPE_LOCAL):
            if action.action_id not in overrides:
                continue
            shortcut = overrides[action.action_id]
            lines.append(
                _("{shortcut}: {action}").format(shortcut=format_shortcut(shortcut), action=action.label)
                if shortcut
                else _("{action}: sem atalho (padrão era {default})").format(
                    action=action.label, default=format_shortcut(normalize_shortcut(action.default))
                )
            )
        return "\n".join(lines)
