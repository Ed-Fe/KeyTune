from ...i18n import _, ngettext
import threading

import wx

from player.youtube_music import subscriptions
from player.youtube_music.folders import (
    FOLDER_CHART_COUNTRY,
    FOLDER_CHART_GROUP,
    FOLDER_CHARTS,
    FOLDER_HISTORY,
    FOLDER_LIBRARY,
    FOLDER_LIKED,
    FOLDER_MOOD_CATEGORY,
    FOLDER_MOOD_SECTION,
    FOLDER_MOODS,
    FOLDER_SUBSCRIBED_CHANNELS,
    FOLDER_SUBSCRIPTION_VIDEOS,
    chart_country_items,
    chart_folder_items,
    mood_category_items,
    mood_folder_items,
)
from player.youtube_music.models import YOUTUBE_CHART_DEFAULT_COUNTRY_CODE, YouTubeResultPage

from .navigation import YouTubeResultsView


class BrowseMixin:
    def _build_youtube_music_folder_view(self, folder):
        """A lista de dentro de uma pasta do início: biblioteca, curtidas, em alta, moods..."""
        service = self._get_youtube_music_service()
        kind = folder.kind
        payload = folder.payload

        def whole_list(fetch):
            # Estas listas chegam inteiras de uma vez: não há página seguinte.
            return lambda _start, _count: YouTubeResultPage(results=tuple(fetch()), has_more=False)

        if kind == FOLDER_LIBRARY:
            return self._build_youtube_music_library_view()
        if kind == FOLDER_LIKED:
            return YouTubeResultsView(
                title=folder.title,
                fetch_page=service.fetch_liked_songs_page,
                fetch_rest=lambda start: service.fetch_liked_songs_page(start, None),
            )
        if kind == FOLDER_HISTORY:
            return YouTubeResultsView(title=folder.title, fetch_page=whole_list(service.get_history))
        if kind == FOLDER_SUBSCRIPTION_VIDEOS:
            return YouTubeResultsView(title=folder.title, fetch_page=subscriptions.subscription_videos_page)
        if kind == FOLDER_SUBSCRIBED_CHANNELS:
            return YouTubeResultsView(title=folder.title, fetch_page=subscriptions.subscribed_channels_page)
        if kind == FOLDER_CHARTS:
            return YouTubeResultsView(title=folder.title, results=chart_folder_items())
        if kind == FOLDER_CHART_GROUP:
            return YouTubeResultsView(
                title=_("Em alta — {group}").format(group=folder.title),
                results=chart_country_items(payload or ()),
            )
        if kind == FOLDER_CHART_COUNTRY:
            # "Global" não é um país: "Em alta em Global" soaria estranho.
            title_format = _("Em alta — {group}") if payload == YOUTUBE_CHART_DEFAULT_COUNTRY_CODE else _("Em alta em {country}")
            return YouTubeResultsView(
                title=title_format.format(group=folder.title, country=folder.title),
                fetch_page=whole_list(lambda: service.get_charts(payload)),
            )
        if kind == FOLDER_MOODS:
            return YouTubeResultsView(
                title=folder.title,
                fetch_page=whole_list(lambda: mood_folder_items(service.get_mood_categories())),
            )
        if kind == FOLDER_MOOD_SECTION:
            return YouTubeResultsView(
                title=_("Moods e gêneros — {category}").format(category=folder.title),
                results=mood_category_items(payload or ()),
            )
        if kind == FOLDER_MOOD_CATEGORY:
            return YouTubeResultsView(
                title=_("Moods e gêneros — {category}").format(category=folder.title),
                fetch_page=whole_list(lambda: service.get_mood_playlists(payload.params, badge=payload.title)),
            )
        return None

    def on_refresh_youtube_music_library(self, _event=None, announce=True):
        if not self._ensure_youtube_music_authenticated():
            return False

        # Don't issue API calls while the dependency update may be refreshing
        # ytmusicapi files or replacing the managed yt-dlp executable.
        if getattr(self, "_youtube_music_dependency_update_in_progress", False):
            message = _(
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
            # Run the independent network calls in parallel: account name,
            # library playlists, personalized mixes, and account feedback.
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

            def run_feedback():
                try:
                    results["feedback_count"] = service.sync_account_feedback(force=True)
                except Exception as exc:
                    results["feedback_error"] = exc

            threads = [
                threading.Thread(target=run_account, daemon=True),
                threading.Thread(target=run_playlists, daemon=True),
                threading.Thread(target=run_mixes, daemon=True),
                threading.Thread(target=run_feedback, daemon=True),
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
                summary_message = " ".join(
                    (
                        ngettext(
                            "Biblioteca do YouTube Music: {count} playlist carregada.",
                            "Biblioteca do YouTube Music: {count} playlists carregadas.",
                            playlist_count,
                        ).format(count=playlist_count),
                        ngettext(
                            "{count} mix personalizada.",
                            "{count} mixes personalizadas.",
                            mix_added,
                        ).format(count=mix_added),
                        _("Desça até o fim da lista para carregar mais."),
                    )
                )
            else:
                summary_message = " ".join(
                    (
                        ngettext(
                            "Biblioteca do YouTube Music: {count} playlist carregada.",
                            "Biblioteca do YouTube Music: {count} playlists carregadas.",
                            playlist_count,
                        ).format(count=playlist_count),
                        ngettext(
                            "{count} mix personalizada.",
                            "{count} mixes personalizadas.",
                            mix_added,
                        ).format(count=mix_added),
                    )
                )
            self._set_youtube_music_library_cache(
                merged,
                status_message=summary_message,
                has_more_playlists=has_more,
            )
            self._refresh_youtube_music_menu_state()
            if announce:
                self._announce(
                    " ".join(
                        (
                            ngettext(
                                "Biblioteca do YouTube Music atualizada: {count} playlist.",
                                "Biblioteca do YouTube Music atualizada: {count} playlists.",
                                playlist_count,
                            ).format(count=playlist_count),
                            ngettext(
                                "{count} mix.",
                                "{count} mixes.",
                                mix_added,
                            ).format(count=mix_added),
                        )
                    )
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

    def _load_more_youtube_music_playlists(self, *, load_all=False):
        if not self._youtube_music_library_has_more_playlists():
            self._announce(_("Não há mais playlists para carregar."))
            return False

        if not self._ensure_youtube_music_authenticated():
            return False

        service = self._get_youtube_music_service()
        if load_all:
            next_limit = None
            self._announce(_("Carregando todas as playlists do YouTube Music."))
        else:
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

            if next_limit is None:
                has_more = False
            else:
                self._youtube_music_library_limit = next_limit
            if has_more:
                summary_message = " ".join(
                    (
                        ngettext(
                            "Biblioteca do YouTube Music: {count} playlist carregada.",
                            "Biblioteca do YouTube Music: {count} playlists carregadas.",
                            playlist_count,
                        ).format(count=playlist_count),
                        _("Há mais para carregar."),
                    )
                )
            else:
                summary_message = ngettext(
                    "Biblioteca do YouTube Music: {count} playlist carregada (todas).",
                    "Biblioteca do YouTube Music: {count} playlists carregadas (todas).",
                    playlist_count,
                ).format(count=playlist_count)
            self._set_youtube_music_library_cache(
                merged,
                status_message=summary_message,
                has_more_playlists=has_more,
            )
            self._refresh_youtube_music_menu_state()
            self._announce(
                ngettext(
                    "{count} playlist na biblioteca agora.",
                    "{count} playlists na biblioteca agora.",
                    playlist_count,
                ).format(count=playlist_count)
            )

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
            summary_message = " ".join(
                (
                    ngettext(
                        "Biblioteca do YouTube Music: {count} item.",
                        "Biblioteca do YouTube Music: {count} itens.",
                        len(merged),
                    ).format(count=len(merged)),
                    ngettext(
                        "{count} mix personalizada adicionada.",
                        "{count} mixes personalizadas adicionadas.",
                        added,
                    ).format(count=added),
                )
            )
            self._set_youtube_music_library_cache(merged, status_message=summary_message)
            self._refresh_youtube_music_menu_state()
            if announce and added:
                self._announce(
                    ngettext(
                        "{count} mix personalizada carregada.",
                        "{count} mixes personalizadas carregadas.",
                        added,
                    ).format(count=added)
                )

        def on_error(_exc):
            existing_playlists = self._youtube_music_library_cache()
            summary_message = " ".join(
                (
                    ngettext(
                        "Biblioteca do YouTube Music: {count} item.",
                        "Biblioteca do YouTube Music: {count} itens.",
                        len(existing_playlists),
                    ).format(count=len(existing_playlists)),
                    _("Não foi possível carregar mixes personalizadas."),
                )
            )
            self._youtube_music_library_status_message = summary_message
            self._refresh_youtube_music_screen_later()
            self._refresh_youtube_music_menu_state()

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)
