from ...download.plan import download_source_url, safe_folder_name, unique_folder_name
from ...i18n import _, ngettext
import wx

from player.youtube_music.models import YOUTUBE_SEARCH_SOURCE_YOUTUBE, get_search_scope_option
from player.youtube_music.playlists import is_watch_playlist_id, looks_like_link

from .navigation import YouTubeResultsView

from ...playlists import PlaylistState


class SearchMixin:
    def _on_youtube_music_show_search_actions_menu(self, panel, anchor_window=None):
        selected_results = self._selected_youtube_music_search_results()
        can_go_back = self._youtube_music_can_go_back_in_results()
        if not selected_results and not can_go_back:
            self._announce(_("Selecione ao menos um item da lista para abrir o menu de ações."))
            return False

        single_result = selected_results[0] if len(selected_results) == 1 else None
        can_add_selection = bool(self._search_results_can_add_to_current_playlist(selected_results))

        menu = wx.Menu()

        def append(label, handler, enabled=True):
            menu_item = menu.Append(wx.ID_ANY, label)
            menu_item.Enable(bool(enabled))
            menu.Bind(wx.EVT_MENU, lambda _event: handler(), id=menu_item.GetId())

        append(
            _("Tocar (Enter)"),
            lambda: self._add_youtube_music_search_results_to_current_playlist(play=True),
            can_add_selection,
        )
        append(
            _("Adicionar sem tocar (Shift+Enter)"),
            lambda: self._add_youtube_music_search_results_to_current_playlist(play=False),
            can_add_selection,
        )
        append(
            _("Ver conteúdo (Seta para a direita)"),
            self.on_browse_youtube_music_search_result,
            single_result is not None and getattr(single_result, "can_browse", False),
        )
        append(_("Voltar à lista anterior (Backspace)"), self.on_youtube_music_results_back, can_go_back)
        menu.AppendSeparator()

        add_menu = wx.Menu()
        open_new_item = add_menu.Append(wx.ID_ANY, _("Abrir seleção em nova playlist"))

        add_targets = self._youtube_music_search_playlist_tab_targets()
        target_items = []
        if add_targets:
            add_menu.AppendSeparator()
        for target in add_targets:
            menu_item = add_menu.Append(wx.ID_ANY, target["label"])
            target_items.append((menu_item, target))

        open_new_item.Enable(can_add_selection)
        for menu_item, _target in target_items:
            menu_item.Enable(can_add_selection)

        menu.AppendSubMenu(add_menu, _("Adicionar seleção..."))

        download_item = menu.Append(wx.ID_ANY, _("Baixar seleção...\tCtrl+Shift+B"))
        download_item.Enable(self._youtube_music_search_results_can_download(selected_results))
        menu.Bind(
            wx.EVT_MENU,
            lambda _event: self.download_youtube_music_search_selection(),
            id=download_item.GetId(),
        )

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

        append(
            _("Salvar no YouTube Music"),
            self._save_youtube_music_search_result,
            any(getattr(result, "can_save", False) for result in selected_results),
        )
        if single_result is not None and getattr(single_result, "library_playlist", False):
            append(
                _("Excluir playlist do YouTube Music..."),
                self._delete_selected_youtube_music_library_playlist,
                not is_watch_playlist_id(single_result.playlist_id),
            )

        popup_parent = anchor_window or getattr(panel, "search_results_list", None) or self
        try:
            popup_parent.PopupMenu(menu)
        finally:
            menu.Destroy()
        return True

    def _youtube_music_search_download_entries(self, search_results=None):
        """``(endereço, título)`` dos resultados selecionados que podem ser baixados."""
        if search_results is None:
            search_results = self._selected_youtube_music_search_results()
        # Só faixas e vídeos têm um endereço direto; playlists e álbuns são abertos antes de baixar.
        return [
            (result.playback_url, result.title)
            for result in search_results
            if getattr(result, "playback_url", "")
        ]

    @staticmethod
    def _is_downloadable_youtube_music_list(search_result):
        """Playlist ou álbum, que é baixado inteiro: todas as faixas de dentro."""
        return bool(
            getattr(search_result, "result_type", "") in ("playlist", "album")
            and getattr(search_result, "playlist_id", "")
        )

    def _youtube_music_search_results_can_download(self, search_results):
        return any(
            self._is_downloadable_youtube_music_list(result) or download_source_url(getattr(result, "playback_url", ""))
            for result in search_results or []
        )

    def download_youtube_music_search_selection(self):
        """Baixa a seleção da lista; cada playlist ou álbum vai inteiro para uma subpasta com o nome dele."""
        search_results = self._selected_youtube_music_search_results()
        lists = [result for result in search_results if self._is_downloadable_youtube_music_list(result)]
        if not lists:
            self.download_media_entries(self._youtube_music_search_download_entries(search_results))
            return True

        if self._download_in_progress():
            self._offer_to_cancel_download()
            return False

        if len(lists) == 1:
            self._announce(_("Carregando as faixas de {title} para baixar.").format(title=lists[0].title))
        else:
            self._announce(_("Carregando as faixas das listas selecionadas para baixar."))

        def worker():
            return self._youtube_music_download_entries_with_folders(search_results)

        def on_error(exc):
            wx.MessageBox(
                _("Não foi possível carregar as faixas para baixar.") + "\n\n" + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc)),
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, self.download_media_entries, on_error=on_error)

    def _youtube_music_download_entries_with_folders(self, search_results):
        """``(endereço, título, subpasta)``: as faixas de cada playlist ou álbum na pasta dele, os avulsos sem pasta."""
        entries = []
        used_folders = set()
        for search_result in search_results:
            if not self._is_downloadable_youtube_music_list(search_result):
                playback_url = str(getattr(search_result, "playback_url", "") or "").strip()
                if playback_url:
                    entries.append((playback_url, search_result.title, ""))
                continue
            try:
                item_urls, item_labels, _expanded, _skipped = self._prepare_youtube_music_search_results_for_playlist(
                    [search_result]
                )
            except RuntimeError:
                # Lista vazia: as outras da seleção seguem.
                continue
            # Duas listas com o mesmo nome não se misturam: a segunda vira "nome (2)".
            folder = unique_folder_name(safe_folder_name(search_result.title), used_folders)
            entries.extend((url, label, folder) for url, label in zip(item_urls, item_labels))

        if not entries:
            raise RuntimeError(_("A seleção atual não tem faixas que possam ser baixadas."))
        return entries

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
                if getattr(search_result, "source", "") == YOUTUBE_SEARCH_SOURCE_YOUTUBE:
                    playlist_content = service.get_youtube_playlist_content(playlist_id, search_result.title)
                elif getattr(search_result, "library_playlist", False):
                    # Uma playlist da biblioteca pode ser privada: só a conta consegue abri-la.
                    playlist_content = service.get_playlist_content(
                        playlist_id, fallback_title=search_result.title, require_auth=True
                    )
                else:
                    playlist_content = service.get_playlist_content(playlist_id, fallback_title=_("Seleção do YouTube Music"))
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
        return _("Seleção do YouTube Music")

    def _announce_youtube_music_playlist_addition(self, added_count, target_title, playlist_result_count, skipped_count):
        normalized_message = ngettext(
            "{count} item adicionado à playlist: {title}.",
            "{count} itens adicionados à playlist: {title}.",
            added_count,
        ).format(count=added_count, title=target_title)
        if playlist_result_count:
            normalized_message = normalized_message + " " + ngettext(
                "{count} playlist da busca foi expandida.",
                "{count} playlists da busca foram expandidas.",
                playlist_result_count,
            ).format(count=playlist_result_count)
        if skipped_count:
            normalized_message = normalized_message + " " + ngettext(
                "{count} item da seleção foi ignorado.",
                "{count} itens da seleção foram ignorados.",
                skipped_count,
            ).format(count=skipped_count)
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
                announce_message = announce_message + " " + ngettext(
                    "{count} playlist da busca foi expandida.",
                    "{count} playlists da busca foram expandidas.",
                    playlist_result_count,
                ).format(count=playlist_result_count)
            if skipped_count:
                announce_message = announce_message + " " + ngettext(
                    "{count} item da seleção foi ignorado.",
                    "{count} itens da seleção foram ignorados.",
                    skipped_count,
                ).format(count=skipped_count)
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
            normalized_message = ngettext(
                "{count} resultado salvo no YouTube Music.",
                "{count} resultados salvos no YouTube Music.",
                success_count,
            ).format(count=success_count)
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

    def _add_youtube_music_search_results_to_current_playlist(self, play=False):
        """Põe a seleção da busca na playlist atual; com *play*, toca o primeiro item dela."""
        search_results = self._selected_youtube_music_search_results()
        if not search_results:
            self._announce(_("Selecione ao menos um resultado da busca para adicionar à playlist atual."))
            return False

        if play and len(search_results) == 1 and getattr(search_results[0], "library_playlist", False):
            # Uma playlist da sua biblioteca abre na aba dela, de onde dá para editá-la na conta.
            return self._load_youtube_music_playlist_by_id(
                search_results[0].playlist_id,
                fallback_title=search_results[0].title,
                require_auth=True,
            )

        target_state = self._resolve_youtube_music_player_playlist_target()
        if not isinstance(target_state, PlaylistState):
            self._announce(_("Não foi possível localizar uma playlist de destino no player."))
            return False

        service = self._get_youtube_music_service()

        def worker():
            return self._prepare_youtube_music_search_results_for_playlist(search_results)

        def on_success(result):
            prepared_items, prepared_labels, playlist_result_count, skipped_count = result
            added_count, play_item = self._append_prepared_items_to_playlist(
                prepared_items,
                target_state,
                browser_item_labels=prepared_labels,
            )

            if added_count == 0 and not play:
                self._announce(_("Os itens selecionados já estavam presentes na playlist atual."))
                return

            if added_count:
                self._add_recent_media_paths(prepared_items)
                self._announce_youtube_music_playlist_addition(
                    added_count,
                    target_state.title,
                    playlist_result_count,
                    skipped_count,
                )
            if play:
                self._play_youtube_music_search_item(target_state, play_item)
            self._refresh_playlist_browser()
            self._update_title()

        def on_error(exc):
            wx.MessageBox(
                _("Não foi possível adicionar a seleção à playlist atual.") + "\n\n" + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc)),
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def _play_youtube_music_search_item(self, target_state, media_path):
        """Toca *media_path* em *target_state* sem sair da aba do YouTube Music."""
        target_index = self._resolve_playlist_state_index(target_state)
        play_index = target_state.index_of_item(media_path) if media_path else None
        if target_index == wx.NOT_FOUND or play_index is None:
            return False

        target_state.select_index(play_index)
        self.active_playlist_index = target_index
        self._play_media(index=target_index)
        return True

    def on_search_youtube_music(self, _event=None):
        panel = self._get_youtube_music_panel()
        if panel is None:
            return False

        query = panel.get_search_query()
        if not query:
            self._announce(_("Digite algo para pesquisar no YouTube Music ou no YouTube."))
            return False
        if looks_like_link(query):
            return self._open_youtube_music_link(query)

        search_scope_id = panel.get_search_scope_id()
        scope_option = get_search_scope_option(search_scope_id)
        if scope_option.requires_auth and not self._ensure_youtube_music_authenticated():
            return False

        service = self._get_youtube_music_service()
        self._announce(_("Pesquisando {query}.").format(query=query))

        def fetch_page(start, count):
            return service.fetch_search_page(query, search_scope=search_scope_id, start=start, count=count)

        view = YouTubeResultsView(
            title=_("Busca por {query}").format(query=query),
            fetch_page=fetch_page,
        )
        return self._load_youtube_music_results_view(
            view,
            mode="reset",
            error_message=_("Não foi possível concluir a busca agora."),
        )
