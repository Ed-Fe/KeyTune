from ...i18n import _
import wx

from player.youtube_music.models import get_search_scope_option

from ...playlists import PlaylistState


class SearchMixin:
    def _on_youtube_music_show_search_actions_menu(self, panel, anchor_window=None):
        selected_results = self._selected_youtube_music_search_results()
        if not selected_results:
            self._announce(_("Selecione ao menos um resultado da busca para abrir o menu de ações."))
            return False

        menu = wx.Menu()
        add_menu = wx.Menu()
        open_new_item = add_menu.Append(wx.ID_ANY, "Abrir seleção em nova playlist")

        add_targets = self._youtube_music_search_playlist_tab_targets()
        target_items = []
        if add_targets:
            add_menu.AppendSeparator()
        for target in add_targets:
            menu_item = add_menu.Append(wx.ID_ANY, target["label"])
            target_items.append((menu_item, target))

        can_add_selection = bool(self._search_results_can_add_to_current_playlist(selected_results))
        open_new_item.Enable(can_add_selection)
        for menu_item, _target in target_items:
            menu_item.Enable(can_add_selection)

        menu.AppendSubMenu(add_menu, "Adicionar seleção...")

        add_menu.Bind(
            wx.EVT_MENU,
            lambda _event: self._open_youtube_music_search_results_in_new_playlist(),
            id=open_new_item.GetId(),
        )
        for menu_item, target in target_items:
            add_menu.Bind(
                wx.EVT_MENU,
                lambda _event, target_index=target["index"]: self._add_youtube_music_search_results_to_playlist_tab(target_index),
                id=menu_item.GetId(),
            )

        popup_parent = anchor_window or getattr(panel, "search_results_list", None) or self
        try:
            popup_parent.PopupMenu(menu)
        finally:
            menu.Destroy()
        return True

    def _selected_youtube_music_search_result(self):
        selected_results = self._selected_youtube_music_search_results()
        if not selected_results:
            return None
        return selected_results[0]

    def _selected_youtube_music_search_results(self):
        panel = self._get_youtube_music_panel()
        if panel is None:
            return []
        return list(panel.get_selected_search_results())

    def _search_results_can_add_to_current_playlist(self, search_results):
        for search_result in search_results or []:
            if getattr(search_result, "playlist_id", "") or getattr(search_result, "playback_url", ""):
                return True
        return False

    def _youtube_music_search_playlist_tab_targets(self):
        current_index = self._get_current_tab_index()
        active_index = self._get_active_playlist_index()
        targets = []
        for index, state in enumerate(getattr(self, "playlists", [])):
            if not isinstance(state, PlaylistState) or state.is_folder_tab or state.is_loading:
                continue

            label = str(state.title or f"Playlist {index + 1}").strip()
            if index == current_index:
                label = f"{label} (aba atual)"
            elif index == active_index:
                label = f"{label} (playlist ativa)"

            targets.append({
                "index": index,
                "state": state,
                "label": label,
            })
        return targets

    def _prepare_youtube_music_search_results_for_playlist(self, search_results):
        service = self._get_youtube_music_service()
        prepared_items = []
        prepared_labels = []
        playlist_result_count = 0
        skipped_count = 0
        for search_result in search_results:
            playlist_id = str(getattr(search_result, "playlist_id", "") or "").strip()
            if playlist_id:
                playlist_content = service.get_playlist_content(playlist_id, fallback_title=search_result.title)
                if not playlist_content.item_urls:
                    skipped_count += 1
                    continue
                prepared_items.extend(playlist_content.item_urls)
                prepared_labels.extend(playlist_content.item_labels)
                playlist_result_count += 1
                continue

            playback_url = str(getattr(search_result, "playback_url", "") or "").strip()
            if not playback_url:
                skipped_count += 1
                continue
            prepared_items.append(playback_url)
            prepared_labels.append(search_result.choice_label)

        if not prepared_items:
            raise RuntimeError(_("A seleção atual não tem resultados reproduzíveis para adicionar à playlist escolhida."))

        return prepared_items, prepared_labels, playlist_result_count, skipped_count

    def _youtube_music_search_results_playlist_title(self, search_results):
        if len(search_results) == 1:
            title = str(getattr(search_results[0], "title", "") or "").strip()
            if title:
                return title
        return _("Seleção do YouTube Music")

    def _announce_youtube_music_playlist_addition(self, added_count, target_title, playlist_result_count, skipped_count):
        normalized_message = _("{count} item(ns) adicionado(s) à playlist: {title}.").format(count=added_count, title=target_title)
        if playlist_result_count:
            normalized_message = normalized_message + " " + _("{count} playlist(s) da busca foram expandidas.").format(count=playlist_result_count)
        if skipped_count:
            normalized_message = normalized_message + " " + _("{count} item(ns) da seleção foram ignorados.").format(count=skipped_count)
        self._announce(normalized_message)
        if hasattr(self, "_set_status_message"):
            self._set_status_message(normalized_message)

    def _open_youtube_music_search_results_in_new_playlist(self):
        search_results = self._selected_youtube_music_search_results()
        if not search_results:
            self._announce(_("Selecione ao menos um resultado da busca para abrir em uma nova playlist."))
            return False

        def worker():
            return self._prepare_youtube_music_search_results_for_playlist(search_results)

        def on_success(result):
            prepared_items, prepared_labels, playlist_result_count, skipped_count = result
            target_index = self._create_empty_playlist_tab(select=False)
            target_state = self._get_playlist_state(target_index)
            if not isinstance(target_state, PlaylistState):
                self._announce(_("Não foi possível criar uma nova playlist para a seleção atual."))
                return

            target_state.finish_library_load()
            target_state.clear_folder_location()
            target_state.title = self._youtube_music_search_results_playlist_title(search_results)
            target_state.set_items_prepared(
                prepared_items,
                {item: index for index, item in enumerate(prepared_items)},
                prepared_labels,
                start_index=0,
            )
            self.notebook.SetPageText(target_index, target_state.title)
            self._add_recent_media_paths(prepared_items)
            self.active_playlist_index = target_index
            self._select_tab(target_index, announce=False)
            self._refresh_playlist_browser()
            self._update_title()

            announce_message = _("Seleção aberta em nova playlist: {title}.").format(title=target_state.title)
            if playlist_result_count:
                announce_message = announce_message + " " + _("{count} playlist(s) da busca foram expandidas.").format(count=playlist_result_count)
            if skipped_count:
                announce_message = announce_message + " " + _("{count} item(ns) da seleção foram ignorados.").format(count=skipped_count)
            self._play_media(index=target_index, announce_message=announce_message)
            if hasattr(self, "_set_status_message"):
                self._set_status_message(announce_message)

        def on_error(exc):
            wx.MessageBox(
                _("Não foi possível abrir a seleção em uma nova playlist.") + "\n\n" + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc)),
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def _add_youtube_music_search_results_to_playlist_tab(self, target_index):
        search_results = self._selected_youtube_music_search_results()
        if not search_results:
            self._announce(_("Selecione ao menos um resultado da busca para adicionar à playlist escolhida."))
            return False

        target_state = self._get_playlist_state(target_index)
        if not isinstance(target_state, PlaylistState) or target_state.is_folder_tab or target_state.is_loading:
            self._announce(_("A playlist escolhida não está disponível para receber a seleção atual."))
            return False

        def worker():
            return self._prepare_youtube_music_search_results_for_playlist(search_results)

        def on_success(result):
            prepared_items, prepared_labels, playlist_result_count, skipped_count = result
            added_count, _play_item = self._append_prepared_items_to_playlist(
                prepared_items,
                target_state,
                browser_item_labels=prepared_labels,
            )

            if added_count == 0:
                self._announce(_("Os itens selecionados já estavam presentes na playlist: {title}.").format(title=target_state.title))
                return

            self._add_recent_media_paths(prepared_items)
            self.active_playlist_index = target_index
            self._select_tab(target_index, announce=False)
            self._refresh_playlist_browser()
            self._update_title()
            self._announce_youtube_music_playlist_addition(
                added_count,
                target_state.title,
                playlist_result_count,
                skipped_count,
            )

        def on_error(exc):
            wx.MessageBox(
                _("Não foi possível adicionar a seleção à playlist escolhida.") + "\n\n" + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc)),
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def _resolve_youtube_music_player_playlist_target(self):
        candidates = [
            self._get_playlist_state(self._get_current_tab_index()),
            self._get_active_playlist_state(),
        ]
        for candidate in candidates:
            if isinstance(candidate, PlaylistState) and not candidate.is_folder_tab and not candidate.is_loading:
                return candidate

        tab_index = self._create_empty_playlist_tab(select=False)
        return self._get_playlist_state(tab_index)

    def _save_youtube_music_search_result(self):
        search_results = self._selected_youtube_music_search_results()
        if not search_results:
            self._announce(_("Selecione ao menos um resultado da busca para salvar."))
            return False

        service = self._get_youtube_music_service()
        if not service.has_saved_browser_auth() and not self._ensure_youtube_music_authenticated():
            return False

        def worker():
            success_count = 0
            playlist_saved = False
            for search_result in search_results:
                if not getattr(search_result, "can_save", False):
                    continue
                service.save_search_result(search_result)
                success_count += 1
                if getattr(search_result, "result_type", "") == "playlist":
                    playlist_saved = True
            if success_count == 0:
                raise RuntimeError(_("A seleção atual não tem resultados compatíveis para salvar na biblioteca."))
            return success_count, playlist_saved

        def on_success(result):
            success_count, playlist_saved = result
            normalized_message = (
                "Resultado salvo no YouTube Music."
                if success_count == 1
                else f"{success_count} resultado(s) salvo(s) no YouTube Music."
            )
            self._youtube_music_library_status_message = normalized_message
            self._refresh_youtube_music_screen_later()
            self._announce(normalized_message)
            if playlist_saved:
                self.on_refresh_youtube_music_library(None, announce=False)

        def on_error(exc):
            wx.MessageBox(
                _("Não foi possível salvar o resultado no YouTube Music.") + "\n\n" + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc)),
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def _add_youtube_music_search_results_to_current_playlist(self):
        search_results = self._selected_youtube_music_search_results()
        if not search_results:
            self._announce(_("Selecione ao menos um resultado da busca para adicionar à playlist atual."))
            return False

        target_state = self._resolve_youtube_music_player_playlist_target()
        if not isinstance(target_state, PlaylistState):
            self._announce(_("Não foi possível localizar uma playlist de destino no player."))
            return False

        service = self._get_youtube_music_service()

        def worker():
            return self._prepare_youtube_music_search_results_for_playlist(search_results)

        def on_success(result):
            prepared_items, prepared_labels, playlist_result_count, skipped_count = result
            added_count, _play_item = self._append_prepared_items_to_playlist(
                prepared_items,
                target_state,
                browser_item_labels=prepared_labels,
            )

            if added_count == 0:
                self._announce(_("Os itens selecionados já estavam presentes na playlist atual."))
                return

            self._add_recent_media_paths(prepared_items)
            self._refresh_playlist_browser()
            self._update_title()
            self._announce_youtube_music_playlist_addition(
                added_count,
                target_state.title,
                playlist_result_count,
                skipped_count,
            )

        def on_error(exc):
            wx.MessageBox(
                _("Não foi possível adicionar a seleção à playlist atual.") + "\n\n" + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc)),
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def on_search_youtube_music(self, _event=None):
        panel = self._get_youtube_music_panel()
        if panel is None:
            return False

        query = panel.get_search_query()
        if not query:
            self._announce(_("Digite algo para pesquisar no YouTube Music ou no YouTube."))
            return False

        search_scope_id = panel.get_search_scope_id()
        scope_option = get_search_scope_option(search_scope_id)
        if scope_option.requires_auth and not self._ensure_youtube_music_authenticated():
            return False

        service = self._get_youtube_music_service()
        self._announce(_("Pesquisando em {scope}: {query}.").format(scope=scope_option.label, query=query))

        def worker():
            return service.search(query, search_scope=search_scope_id)

        def on_success(search_results):
            result_count = len(search_results)
            if result_count == 0:
                search_summary = f"Busca em {scope_option.label}: nenhum resultado para {query}."
            else:
                search_summary = (
                    f"Busca em {scope_option.label}: {result_count} resultado(s) para {query}."
                )
            self._set_youtube_music_search_results(
                search_results,
                search_summary=search_summary,
                status_message=search_summary,
            )
            self._announce(search_summary)

        def on_error(exc):
            wx.MessageBox(
                _("Não foi possível concluir a busca agora.") + "\n\n" + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc)),
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)
