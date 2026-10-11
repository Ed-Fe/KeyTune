"""O menu de ações da lista da aba do KeyTube (botão Ações..., Shift+F10).

O menu traz só o que vale para o item selecionado, em blocos: o que Enter e as
setas fazem com ele, o que mais dá para fazer com ele, para onde levar a
seleção e, por último, o que vale para a lista inteira.
"""

import wx

from player.youtube_music.folders import ACTION_SEND_CHAT_MESSAGE, ACTION_WRITE_COMMENT
from player.youtube_music.playlists import is_watch_playlist_id

from ...i18n import _


class ActionsMenuMixin:
    def _youtube_music_actions_menu_sections(self, selected_results):
        """Os blocos do menu para *selected_results*: listas de ``(rótulo, ação)``.

        A ação é o que roda ao escolher o item, ou uma lista de ``(rótulo, ação)``
        quando ele abre um submenu (``None`` nela vira um separador).
        """
        single = selected_results[0] if len(selected_results) == 1 else None
        sections = [
            self._youtube_music_primary_menu_entries(selected_results, single),
            self._youtube_music_item_menu_entries(single),
            self._youtube_music_selection_menu_entries(selected_results, single),
            self._youtube_music_list_menu_entries(single),
        ]
        return [section for section in sections if section]

    def _youtube_music_primary_menu_entries(self, selected_results, single):
        """O que Enter e as setas fazem com a seleção."""
        kind = getattr(single, "result_type", "")
        if kind == "action":
            return [(single.title, lambda: self.on_browse_youtube_music_search_result(single))]

        entries = []
        if self._search_results_can_add_to_current_playlist(selected_results):
            entries.append(
                (_("Tocar (Enter)"), lambda: self._add_youtube_music_search_results_to_current_playlist(play=True))
            )
            entries.append(
                (
                    _("Adicionar sem tocar (Shift+Enter)"),
                    lambda: self._add_youtube_music_search_results_to_current_playlist(play=False),
                )
            )
        if kind == "comment":
            entries.append((_("Ler o comentário inteiro (Enter)"), lambda: self._read_youtube_music_comment(single)))
        elif kind == "post":
            entries.append((_("Ler o post inteiro (Enter)"), lambda: self._read_youtube_music_post(single)))
        elif kind == "chat":
            entries.append(
                (_("Ler a mensagem inteira (Enter)"), lambda: self._read_youtube_live_chat_message(single))
            )
        if single is not None and getattr(single, "can_browse", False):
            if kind == "comment":
                label = _("Ver respostas (Seta para a direita)")
            elif kind == "post":
                label = _("Ver comentários (Seta para a direita)")
            elif kind == "notification":
                label = _("Ver a conversa (Seta para a direita)")
            elif getattr(single, "opens_on_enter", False):
                label = _("Abrir (Enter)")
            else:
                label = _("Ver conteúdo (Seta para a direita)")
            entries.append((label, self.on_browse_youtube_music_search_result))
        return entries

    def _youtube_music_item_menu_entries(self, single):
        """O que mais dá para fazer com o item selecionado, conforme o que ele é."""
        if single is None:
            return []
        entries = []
        if self._youtube_music_comments_url(single):
            entries.append((_("Ver comentários"), self.show_youtube_music_comments))
            entries.append((_("Ver detalhes"), self.show_youtube_music_details))
        owner = single.owner_result() if hasattr(single, "owner_result") else None
        if owner is not None:
            owner_label = _("Ir para o canal {name}") if owner.result_type == "channel" else _("Ir para o artista {name}")
            entries.append(
                (
                    owner_label.format(name=owner.title).replace("&", "&&"),
                    lambda: self.on_browse_youtube_music_search_result(owner, focus_results=True),
                )
            )
        entries.extend(self._youtube_music_live_chat_menu_entries(single))
        entries.extend(self._youtube_music_comment_menu_entries(single))
        entries.extend(self._youtube_music_post_menu_entries(single))
        entries.extend(self._youtube_music_channel_menu_entries(single))
        entries.extend(self._youtube_notification_menu_entries(single))
        return entries

    def _youtube_music_selection_menu_entries(self, selected_results, single):
        """Para onde a seleção pode ir: outra playlist, o computador, a biblioteca da conta."""
        entries = []
        if self._search_results_can_add_to_current_playlist(selected_results):
            targets = [(_("Abrir seleção em nova playlist"), self._open_youtube_music_search_results_in_new_playlist)]
            tab_targets = self._youtube_music_search_playlist_tab_targets()
            if tab_targets:
                targets.append(None)
            for target in tab_targets:
                targets.append(
                    (
                        target["label"],
                        lambda index=target["index"]: self._add_youtube_music_search_results_to_playlist_tab(index),
                    )
                )
            entries.append((_("Adicionar seleção..."), targets))
        if self._youtube_music_search_results_can_download(selected_results):
            entries.append((_("Baixar seleção...\tCtrl+Shift+B"), self.download_youtube_music_search_selection))
        if any(getattr(result, "can_save", False) for result in selected_results):
            entries.append((_("Salvar no YouTube Music"), self._save_youtube_music_search_result))
        if (
            single is not None
            and getattr(single, "library_playlist", False)
            and not is_watch_playlist_id(single.playlist_id)
        ):
            entries.append(
                (_("Excluir playlist do YouTube Music..."), self._delete_selected_youtube_music_library_playlist)
            )
        return entries

    def _youtube_music_list_menu_entries(self, single):
        """O que vale para a lista na tela, e não para o item."""
        view = self._youtube_music_current_results_view()
        entries = []
        # Escrever na lista (um comentário, uma mensagem do chat) é a primeira linha dela;
        # o menu repete o comando para quem já desceu.
        write_row = next(
            (
                result
                for result in view.results
                if getattr(result, "kind", "") in (ACTION_WRITE_COMMENT, ACTION_SEND_CHAT_MESSAGE)
            ),
            None,
        )
        if write_row is not None and write_row is not single:
            entries.append((write_row.title, lambda: self.on_browse_youtube_music_search_result(write_row)))
        entries.extend(self._youtube_music_comments_list_menu_entries())
        entries.extend(self._youtube_music_live_chat_list_menu_entries())
        if view.has_more:
            entries.append((_("Carregar a lista inteira"), self.on_load_all_youtube_music_results))
        if self._youtube_music_can_go_back_in_results():
            entries.append((_("Voltar à lista anterior (Backspace)"), self.on_youtube_music_results_back))
        return entries

    def _on_youtube_music_show_search_actions_menu(self, panel, anchor_window=None):
        sections = self._youtube_music_actions_menu_sections(self._selected_youtube_music_search_results())
        if not sections:
            self._announce(_("Não há ações para este item."))
            return False

        menu = wx.Menu()
        for index, section in enumerate(sections):
            if index:
                menu.AppendSeparator()
            self._fill_youtube_music_actions_menu(menu, section)

        popup_parent = anchor_window or getattr(panel, "search_results_list", None) or self
        try:
            popup_parent.PopupMenu(menu)
        finally:
            menu.Destroy()
        return True

    def _fill_youtube_music_actions_menu(self, menu, entries):
        for entry in entries:
            if entry is None:
                menu.AppendSeparator()
                continue
            label, action = entry
            if isinstance(action, list):
                submenu = wx.Menu()
                self._fill_youtube_music_actions_menu(submenu, action)
                menu.AppendSubMenu(submenu, label)
                continue
            menu_item = menu.Append(wx.ID_ANY, label)
            menu.Bind(wx.EVT_MENU, lambda _event, action=action: action(), id=menu_item.GetId())
