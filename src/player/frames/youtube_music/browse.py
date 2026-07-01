from ...i18n import _
import threading

import wx

from player.youtube_music.models import get_chart_country_groups, get_chart_country_label


class BrowseMixin:
    _YOUTUBE_MUSIC_LIKED_SONGS_LIMIT = 200

    def on_show_youtube_music_charts(self, panel=None, anchor_window=None):
        panel = panel or self._get_youtube_music_panel()
        if panel is None:
            return False

        self._announce(_("Escolha um país no menu para carregar o que está em alta."))
        self._show_youtube_music_charts_menu(panel, anchor_window, get_chart_country_groups())
        return True

    def _show_youtube_music_charts_menu(self, panel, anchor_window, sections):
        menu = wx.Menu()
        for section_title, countries in sections:
            if not section_title:
                # Global (and any other top-level shortcut) goes straight onto
                # the root menu, followed by a separator before the continents.
                for code, label in countries:
                    menu_item = menu.Append(wx.ID_ANY, label)
                    menu.Bind(
                        wx.EVT_MENU,
                        lambda _event, chosen_code=code, chosen_label=label: self._load_youtube_music_charts(
                            chosen_code, chosen_label
                        ),
                        id=menu_item.GetId(),
                    )
                menu.AppendSeparator()
                continue
            submenu = wx.Menu()
            for code, label in countries:
                menu_item = submenu.Append(wx.ID_ANY, label)
                submenu.Bind(
                    wx.EVT_MENU,
                    lambda _event, chosen_code=code, chosen_label=label: self._load_youtube_music_charts(
                        chosen_code, chosen_label
                    ),
                    id=menu_item.GetId(),
                )
            menu.AppendSubMenu(submenu, section_title)

        anchor = anchor_window or getattr(panel, "charts_button", None) or self
        try:
            anchor.PopupMenu(menu)
        finally:
            menu.Destroy()

    def _load_youtube_music_charts(self, country_code, country_label=""):
        country_label = str(country_label or "").strip() or get_chart_country_label(country_code)
        service = self._get_youtube_music_service()
        self._announce(_("Carregando o que está em alta em {country}.").format(country=country_label))

        def worker():
            return service.get_charts(country_code)

        def on_success(chart_results):
            result_count = len(chart_results)
            if result_count == 0:
                search_summary = _("Em alta em {country}: nenhum destaque disponível.").format(country=country_label)
            else:
                search_summary = (
                    _("Em alta em {country}: {count} lista(s) de destaque.").format(country=country_label, count=result_count)
                )
            self._set_youtube_music_search_results(
                chart_results,
                search_summary=search_summary,
                status_message=search_summary,
            )
            self._announce(search_summary)

        def on_error(exc):
            wx.MessageBox(
                _("Não foi possível carregar as paradas agora.") + "\n\n" + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc)),
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def on_show_youtube_music_moods(self, panel=None, anchor_window=None):
        panel = panel or self._get_youtube_music_panel()
        if panel is None:
            return False

        service = self._get_youtube_music_service()
        self._announce(_("Carregando as categorias de moods e gêneros do YouTube Music."))

        def worker():
            return service.get_mood_categories()

        def on_success(sections):
            if not sections:
                message = _("Nenhuma categoria de moods e gêneros está disponível agora.")
                self._youtube_music_library_status_message = message
                self._refresh_youtube_music_screen_later()
                self._announce(message)
                return
            self._announce(
                _("Escolha uma categoria de moods e gêneros no menu para carregar as playlists.")
            )
            self._show_youtube_music_mood_menu(panel, anchor_window, sections)

        def on_error(exc):
            wx.MessageBox(
                _("Não foi possível carregar as categorias de moods e gêneros agora.") + "\n\n" + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc)),
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def _show_youtube_music_mood_menu(self, panel, anchor_window, sections):
        menu = wx.Menu()
        for section_title, categories in sections:
            submenu = wx.Menu()
            for category in categories:
                menu_item = submenu.Append(wx.ID_ANY, category.title)
                submenu.Bind(
                    wx.EVT_MENU,
                    lambda _event, chosen=category: self._load_youtube_music_mood_playlists(chosen),
                    id=menu_item.GetId(),
                )
            menu.AppendSubMenu(submenu, section_title or "Categorias")

        anchor = anchor_window or getattr(panel, "moods_button", None) or self
        try:
            anchor.PopupMenu(menu)
        finally:
            menu.Destroy()

    def _load_youtube_music_mood_playlists(self, category):
        category_title = str(getattr(category, "title", "") or "").strip() or "Categoria"
        service = self._get_youtube_music_service()
        self._announce(_("Carregando playlists de {category}.").format(category=category_title))

        def worker():
            return service.get_mood_playlists(category.params, badge=category_title)

        def on_success(results):
            result_count = len(results)
            if result_count == 0:
                search_summary = _("Moods e gêneros — {category}: nenhuma playlist disponível.").format(category=category_title)
            else:
                search_summary = (
                    _("Moods e gêneros — {category}: {count} playlist(s).").format(category=category_title, count=result_count)
                )
            self._set_youtube_music_search_results(
                results,
                search_summary=search_summary,
                status_message=search_summary,
            )
            self._announce(search_summary)

        def on_error(exc):
            wx.MessageBox(
                _("Não foi possível carregar as playlists desta categoria agora.") + "\n\n" + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc)),
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def on_show_youtube_music_liked(self):
        if self._get_youtube_music_panel() is None:
            return False
        if not self._ensure_youtube_music_authenticated():
            return False

        service = self._get_youtube_music_service()
        self._announce(_("Carregando suas músicas curtidas do YouTube Music."))

        def worker():
            return service.get_liked_songs(limit=self._YOUTUBE_MUSIC_LIKED_SONGS_LIMIT)

        def on_success(results):
            result_count = len(results)
            if result_count == 0:
                search_summary = _("Curtidas: nenhuma faixa curtida encontrada.")
            else:
                search_summary = _("Curtidas: {count} faixa(s).").format(count=result_count)
            self._set_youtube_music_search_results(
                results,
                search_summary=search_summary,
                status_message=search_summary,
            )
            self._announce(search_summary)

        def on_error(exc):
            wx.MessageBox(
                _("Não foi possível carregar suas músicas curtidas agora.") + "\n\n" + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc)),
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def on_show_youtube_music_history(self):
        if self._get_youtube_music_panel() is None:
            return False
        if not self._ensure_youtube_music_authenticated():
            return False

        service = self._get_youtube_music_service()
        self._announce(_("Carregando seu histórico do YouTube Music."))

        def worker():
            return service.get_history()

        def on_success(results):
            result_count = len(results)
            if result_count == 0:
                search_summary = _("Histórico: nenhuma faixa recente encontrada.")
            else:
                search_summary = _("Histórico: {count} faixa(s) recentes.").format(count=result_count)
            self._set_youtube_music_search_results(
                results,
                search_summary=search_summary,
                status_message=search_summary,
            )
            self._announce(search_summary)

        def on_error(exc):
            wx.MessageBox(
                _("Não foi possível carregar seu histórico agora.") + "\n\n" + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc)),
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def on_refresh_youtube_music_library(self, _event=None, announce=True):
        if not self._ensure_youtube_music_authenticated():
            return False

        # Don't issue API calls while the dependency update may be refreshing
        # ytmusicapi files or replacing the managed yt-dlp executable.
        if getattr(self, "_youtube_music_dependency_update_in_progress", False):
            message = (
                "Atualizando recursos adicionais do YouTube Music. Tente novamente em instantes."
            )
            self._youtube_music_library_status_message = message
            self._refresh_youtube_music_screen_later()
            if announce:
                self._announce(message)
            return False

        service = self._get_youtube_music_service()
        if announce:
            self._announce(_("Atualizando playlists e mixes do YouTube Music."))

        page_size = int(self._youtube_music_library_page_size())
        self._youtube_music_library_limit = page_size
        home_limit = self._youtube_music_home_discovery_limit()

        def worker():
            # Run the three independent network calls in parallel: account
            # name, library playlists, and personalized mixes (home rows).
            # ytmusicapi reuses a single requests.Session under the hood and
            # the cached visitor id, so concurrent calls share TLS/cookies.
            results = {}

            def run_account():
                try:
                    results["account_name"] = service.get_connected_account_name()
                except Exception as exc:
                    results["account_error"] = exc

            def run_playlists():
                try:
                    playlists, has_more = service.get_user_library_playlists(limit=page_size)
                    results["playlists"] = (playlists, has_more)
                except Exception as exc:
                    results["playlists_error"] = exc

            def run_mixes():
                try:
                    results["mixes"] = service.get_personalized_mixes(limit=home_limit)
                except Exception as exc:
                    results["mixes_error"] = exc

            threads = [
                threading.Thread(target=run_account, daemon=True),
                threading.Thread(target=run_playlists, daemon=True),
                threading.Thread(target=run_mixes, daemon=True),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            # Library playlists are required; account name and mixes are
            # best-effort enhancements.
            if "playlists_error" in results:
                raise results["playlists_error"]

            account_name = results.get("account_name", "") or ""
            playlists, has_more = results["playlists"]
            mixes = results.get("mixes") or []
            return account_name, playlists, has_more, mixes

        def on_success(result):
            account_name, playlists, has_more, mixes = result
            self._set_youtube_music_account_name(account_name)

            existing_ids = {playlist.playlist_id for playlist in playlists}
            merged = list(playlists)
            mix_added = 0
            for mix in mixes or []:
                if mix.playlist_id in existing_ids:
                    continue
                merged.append(mix)
                existing_ids.add(mix.playlist_id)
                mix_added += 1
            merged.sort(key=lambda playlist: playlist.title.casefold())

            playlist_count = len(playlists)
            if has_more:
                summary_message = (
                    f"Biblioteca do YouTube Music: {playlist_count} playlist(s) carregada(s)"
                    f" e {mix_added} mix(es) personalizada(s)."
                    " Use 'Carregar mais' ou desça até o final da lista para trazer mais."
                )
            else:
                summary_message = (
                    f"Biblioteca do YouTube Music: {playlist_count} playlist(s) carregada(s)"
                    f" e {mix_added} mix(es) personalizada(s)."
                )
            self._set_youtube_music_library_cache(
                merged,
                status_message=summary_message,
                has_more_playlists=has_more,
            )
            self._refresh_youtube_music_menu_state()
            if announce:
                self._announce(
                    f"Biblioteca do YouTube Music atualizada: {playlist_count} playlist(s)"
                    f" e {mix_added} mix(es)."
                )

        def on_error(exc):
            self._refresh_youtube_music_menu_state()
            self._youtube_music_library_status_message = _("Não foi possível atualizar a biblioteca do YouTube Music.")
            self._refresh_youtube_music_screen_later()
            wx.MessageBox(
                _("Não foi possível listar as playlists do YouTube Music.") + "\n\n" + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc)),
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def _on_youtube_music_load_more_playlists_button(self):
        self._load_more_youtube_music_playlists()

    def _load_more_youtube_music_playlists(self):
        if not self._youtube_music_library_has_more_playlists():
            self._announce(_("Não há mais playlists para carregar."))
            return False

        if not self._ensure_youtube_music_authenticated():
            return False

        service = self._get_youtube_music_service()
        next_limit = self._youtube_music_current_library_limit() + int(self._youtube_music_library_page_size())
        self._announce(_("Carregando mais playlists do YouTube Music."))

        def worker():
            return service.get_user_library_playlists(limit=next_limit)

        def on_success(result):
            playlists, has_more = result
            existing_playlists = self._youtube_music_library_cache()
            existing_mix_ids = {
                playlist.playlist_id
                for playlist in existing_playlists
                if str(getattr(playlist, "source_badge", "") or "").strip()
            }
            existing_mixes = [
                playlist
                for playlist in existing_playlists
                if playlist.playlist_id in existing_mix_ids
            ]
            previous_user_playlist_count = sum(
                1
                for playlist in existing_playlists
                if playlist.playlist_id not in existing_mix_ids
            )

            new_playlist_ids = {playlist.playlist_id for playlist in playlists}
            merged = list(playlists)
            for mix in existing_mixes:
                if mix.playlist_id in new_playlist_ids:
                    continue
                merged.append(mix)
                new_playlist_ids.add(mix.playlist_id)
            merged.sort(key=lambda playlist: playlist.title.casefold())

            playlist_count = len(playlists)
            if playlist_count <= previous_user_playlist_count:
                has_more = False

            self._youtube_music_library_limit = next_limit
            if has_more:
                summary_message = (
                    f"Biblioteca do YouTube Music: {playlist_count} playlist(s) carregada(s)."
                    " Há mais para carregar."
                )
            else:
                summary_message = (
                    f"Biblioteca do YouTube Music: {playlist_count} playlist(s) carregada(s) (todas)."
                )
            self._set_youtube_music_library_cache(
                merged,
                status_message=summary_message,
                has_more_playlists=has_more,
            )
            self._refresh_youtube_music_menu_state()
            self._announce(_("{count} playlist(s) na biblioteca agora.").format(count=playlist_count))

        def on_error(exc):
            wx.MessageBox(
                _("Não foi possível carregar mais playlists do YouTube Music.") + "\n\n" + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc)),
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def _refresh_youtube_music_personalized_mixes(self, announce=False):
        service = self._get_youtube_music_service()
        home_limit = self._youtube_music_home_discovery_limit()

        def worker():
            return service.get_personalized_mixes(limit=home_limit)

        def on_success(mixes):
            existing_playlists = self._youtube_music_library_cache()
            existing_ids = {playlist.playlist_id for playlist in existing_playlists}
            merged = list(existing_playlists)
            added = 0
            for mix in mixes or []:
                if mix.playlist_id in existing_ids:
                    continue
                merged.append(mix)
                existing_ids.add(mix.playlist_id)
                added += 1
            merged.sort(key=lambda playlist: playlist.title.casefold())
            summary_message = (
                f"Biblioteca do YouTube Music: {len(merged)} item(ns) "
                f"({added} mix(es) personalizada(s) adicionada(s))."
            )
            self._set_youtube_music_library_cache(merged, status_message=summary_message)
            self._refresh_youtube_music_menu_state()
            if announce and added:
                self._announce(_("{count} mix(es) personalizada(s) carregada(s).").format(count=added))

        def on_error(_exc):
            existing_playlists = self._youtube_music_library_cache()
            summary_message = (
                f"Biblioteca do YouTube Music: {len(existing_playlists)} item(ns)."
                " Não foi possível carregar mixes personalizadas."
            )
            self._youtube_music_library_status_message = summary_message
            self._refresh_youtube_music_screen_later()
            self._refresh_youtube_music_menu_state()

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)
