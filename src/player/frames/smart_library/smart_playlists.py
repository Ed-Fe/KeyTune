"""Playlists inteligentes na janela: menu, gerenciador e abertura.

As regras ficam nas preferências, então sobrevivem entre sessões. O submenu
**Biblioteca > Playlists inteligentes** lista as regras salvas para abrir com um
comando só; o gerenciador cria, edita e remove.
"""

import wx

from ...i18n import _, ngettext
from ...smart_library import (
    SmartPlaylistCollection,
    SmartPlaylistManagerDialog,
    SmartPlaylistRule,
    describe_smart_playlist_rule,
)


class SmartLibraryPlaylistsMixin:
    def _initialize_smart_playlist_state(self):
        self._smart_playlist_menu_actions = {}
        self._smart_playlist_menu_ids = []

    # ------------------------------------------------------------------
    # Persistência
    # ------------------------------------------------------------------
    def _smart_playlist_rules(self):
        collection = SmartPlaylistCollection.from_list(
            getattr(self.settings, "smart_library_smart_playlists", [])
        )
        return collection.rules

    def _store_smart_playlist_rules(self, rules):
        self.settings.smart_library_smart_playlists = SmartPlaylistCollection(
            rules=list(rules or [])
        ).to_list()
        self._save_settings()
        self._refresh_smart_playlist_menu()

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------
    def _refresh_smart_playlist_menu(self):
        menu = getattr(self, "smart_playlist_menu", None)
        if menu is None:
            return

        while menu.GetMenuItemCount():
            menu.Delete(menu.FindItemByPosition(0))

        # Mesmo cuidado dos menus de recentes: soltar os handlers dos ids
        # anteriores, senão cada reconstrução vaza uma ligação no frame.
        for previous_item_id in getattr(self, "_smart_playlist_menu_ids", []):
            self.Unbind(wx.EVT_MENU, id=int(previous_item_id))
        self._smart_playlist_menu_actions = {}
        self._smart_playlist_menu_ids = []

        rules = self._smart_playlist_rules()
        if not rules:
            placeholder = menu.Append(wx.ID_ANY, _("Nenhuma playlist inteligente ainda."))
            placeholder.Enable(False)
        else:
            for rule in rules:
                item_id_ref = wx.NewIdRef()
                item_id = int(item_id_ref)
                self._smart_playlist_menu_ids.append(item_id_ref)
                menu.Append(item_id_ref, rule.name.replace("&", "&&"))
                self.Bind(wx.EVT_MENU, self.on_open_smart_playlist, id=item_id)
                self._smart_playlist_menu_actions[item_id] = rule

        menu.AppendSeparator()
        menu.Append(self.menu_manage_smart_playlists_id, _("&Gerenciar playlists inteligentes..."))

    # ------------------------------------------------------------------
    # Abertura
    # ------------------------------------------------------------------
    def _open_smart_playlist(self, rule):
        service = self._smart_library()
        if service is None:
            self._announce_smart_library_unavailable()
            return False

        if rule is None:
            return False

        records = service.smart_playlist_media(rule)
        if not records:
            self._announce(
                _("A playlist inteligente {name} não encontrou nenhuma mídia agora.").format(
                    name=rule.name
                )
            )
            if hasattr(self, "_set_status_message"):
                self._set_status_message(
                    _("{name}: {summary}").format(
                        name=rule.name, summary=describe_smart_playlist_rule(rule)
                    )
                )
            return False

        self._open_prepared_media_playlist(
            [record.media_path for record in records],
            rule.name,
            browser_item_labels=[record.display_label for record in records],
            announce_message=ngettext(
                "{name}: {count} item.",
                "{name}: {count} itens.",
                len(records),
            ).format(name=rule.name, count=len(records)),
        )
        return True

    def _open_smart_playlist_manager(self):
        if self._smart_library() is None:
            self._announce_smart_library_unavailable()
            return

        dialog = SmartPlaylistManagerDialog(
            self,
            rules=self._smart_playlist_rules(),
            announce=self._announce,
        )
        try:
            dialog.ShowModal()
            # As regras são salvas mesmo quando a caixa é fechada com Esc: criar
            # ou editar já é uma ação concluída, e perdê-la ao fechar seria uma
            # surpresa desagradável.
            updated_rules = dialog.get_rules()
            selected_rule = dialog.get_selected_rule() if dialog.wants_to_open() else None
        finally:
            dialog.Destroy()

        self._store_smart_playlist_rules(updated_rules)

        if selected_rule is not None:
            self._open_smart_playlist(selected_rule)

    # ------------------------------------------------------------------
    def on_open_smart_playlist(self, event):
        rule = getattr(self, "_smart_playlist_menu_actions", {}).get(event.GetId())
        if rule is None:
            event.Skip()
            return
        self._open_smart_playlist(rule)

    def on_manage_smart_playlists(self, _event):
        self._open_smart_playlist_manager()
