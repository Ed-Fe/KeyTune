from ...i18n import _, ngettext
import wx

from player.youtube_music.dialog import YouTubeMusicCreatePlaylistDialog
from player.youtube_music.playlists import (
    extract_playlist_id_from_source,
    extract_video_id_from_text,
    is_watch_playlist_id,
    is_youtube_music_media,
)


class PlaylistEditMixin:
    # Sentinel returned by the playlist picker when the user chooses to create
    # a brand-new playlist instead of selecting an existing one.
    _CREATE_NEW_PLAYLIST_CHOICE = object()

    _PLAYLIST_PRIVACY_LABELS = {
        "PRIVATE": _("privada"),
        "UNLISTED": _("não listada"),
        "PUBLIC": _("pública"),
    }

    def _rate_current_youtube_music_media(self, rating):
        state = self._get_playlist_state()
        media_path = str(getattr(state, "current_media_path", "") or "").strip() if state is not None else ""
        if not media_path:
            self._announce(_("Nenhuma mídia está carregada para avaliar."))
            return False

        if not is_youtube_music_media(media_path):
            self._announce(_("A mídia atual não veio do YouTube Music ou do YouTube."))
            return False

        service = self._get_youtube_music_service()
        if not service.has_saved_browser_auth() and not self._ensure_youtube_music_authenticated():
            return False

        current_status = self._get_youtube_music_media_feedback_status(media_path)
        normalized_rating = str(rating or "").strip().upper()
        if current_status == normalized_rating:
            if normalized_rating == "DISLIKE":
                normalized_message = _("A mídia atual já está marcada como não gostei no YouTube Music.")
            else:
                normalized_message = _("A mídia atual já está curtida no YouTube Music.")
            self._youtube_music_library_status_message = normalized_message
            self._refresh_youtube_music_screen_later()
            self._announce(normalized_message)
            if hasattr(self, "_set_status_message"):
                self._set_status_message(normalized_message)
            return False

        def worker():
            return service.rate_media_feedback(media_path, rating)

        def on_success(message):
            normalized_message = str(message or _("Avaliação da mídia atual enviada ao YouTube Music.")).strip()
            self._youtube_music_library_status_message = normalized_message
            self._refresh_youtube_music_screen_later()
            self._announce(normalized_message)
            if hasattr(self, "_set_status_message"):
                self._set_status_message(normalized_message)
            current_state = self._get_playlist_state()
            current_media_path = str(getattr(current_state, "current_media_path", "") or "").strip()
            if normalized_rating == "DISLIKE" and current_media_path == media_path:
                self._play_adjacent_item(1)

        def on_error(exc):
            wx.MessageBox(
                _("Não foi possível avaliar a mídia atual no YouTube Music.") + "\n\n" + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc)),
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def _youtube_music_video_ids_from_paths(self, media_paths):
        """Extract the YouTube Music video ids from a list of media paths.

        Non-YouTube items are skipped and duplicates are collapsed while
        preserving order, mirroring how the rating flow filters its selection.
        """
        video_ids = []
        seen_video_ids = set()
        for media_path in media_paths or []:
            normalized_media_path = str(media_path or "").strip()
            if not normalized_media_path or not is_youtube_music_media(normalized_media_path):
                continue
            video_id = extract_video_id_from_text(normalized_media_path)
            if video_id and video_id not in seen_video_ids:
                video_ids.append(video_id)
                seen_video_ids.add(video_id)
        return video_ids

    def _current_tab_youtube_music_playlist_id(self):
        """Return the editable remote playlist id backing the current tab.

        Returns ``None`` unless the active tab is a YouTube Music *user*
        playlist (watch playlists / mixes are not editable).
        """
        state = self._get_playlist_state()
        if state is None or state.is_folder_tab:
            return None
        playlist_id = extract_playlist_id_from_source(getattr(state, "source_path", None))
        if not playlist_id or is_watch_playlist_id(playlist_id):
            return None
        return playlist_id

    def _editable_youtube_music_playlists(self):
        """Return only the playlists the user can edit.

        Personalized mixes / radios (watch playlist ids starting with ``RD``)
        share the library cache but cannot receive ``add_playlist_items``
        edits, so they are excluded from the picker.
        """
        return [
            playlist
            for playlist in self._youtube_music_library_cache()
            if not is_watch_playlist_id(getattr(playlist, "playlist_id", ""))
        ]

    def _prompt_for_youtube_music_playlist(self, playlists, prompt, *, allow_create=False):
        """Pick a target playlist, optionally offering to create a new one.

        When ``allow_create`` is set, the first entry is a "create new
        playlist" choice (mirroring the YouTube Music app's own add dialog).
        Returns the chosen playlist, the :data:`_CREATE_NEW_PLAYLIST_CHOICE`
        sentinel, or ``None`` when cancelled.
        """
        choice_labels = []
        if allow_create:
            choice_labels.append("Criar nova playlist...")
        choice_labels.extend(playlist.choice_label for playlist in playlists)

        dialog = wx.SingleChoiceDialog(self, prompt, "Playlists do YouTube Music", choice_labels)
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return None
            selected_index = dialog.GetSelection()
        finally:
            dialog.Destroy()

        if not 0 <= selected_index < len(choice_labels):
            return None
        if allow_create:
            if selected_index == 0:
                return self._CREATE_NEW_PLAYLIST_CHOICE
            selected_index -= 1
        if not 0 <= selected_index < len(playlists):
            return None
        return playlists[selected_index]

    def _add_current_media_to_youtube_playlist(self):
        state = self._get_playlist_state()
        media_path = str(getattr(state, "current_media_path", "") or "").strip() if state is not None else ""
        if not media_path:
            self._announce(_("Nenhuma mídia está tocando para ser adicionada."))
            return False
        return self._add_media_paths_to_youtube_playlist([media_path])

    def _add_selected_media_to_youtube_playlist(self, media_paths):
        return self._add_media_paths_to_youtube_playlist(media_paths)

    def _add_media_paths_to_youtube_playlist(self, media_paths):
        video_ids = self._youtube_music_video_ids_from_paths(media_paths)
        if not video_ids:
            self._announce(_("A seleção não contém faixas do YouTube Music para adicionar."))
            return False

        service = self._get_youtube_music_service()
        if not service.has_saved_browser_auth() and not self._ensure_youtube_music_authenticated():
            return False

        track_count = len(video_ids)
        track_label = _("faixa") if track_count == 1 else _("faixas")

        playlists = self._editable_youtube_music_playlists()
        if not playlists:
            # With no editable playlists yet, the only sensible action is to
            # create one seeded with the current selection.
            return self._create_youtube_music_playlist_with_video_ids(video_ids)

        selected_playlist = self._prompt_for_youtube_music_playlist(
            playlists,
            _("Selecione a playlist para adicionar {count} {label}:").format(count=track_count, label=track_label),
            allow_create=True,
        )
        if selected_playlist is None:
            return False
        if selected_playlist is self._CREATE_NEW_PLAYLIST_CHOICE:
            return self._create_youtube_music_playlist_with_video_ids(video_ids)

        def worker():
            return service.add_tracks_to_playlist(selected_playlist.playlist_id, video_ids)

        def on_success(added_count):
            try:
                normalized_added = int(added_count)
            except (TypeError, ValueError):
                normalized_added = track_count
            message = ngettext(
                "{count} faixa adicionada à playlist {title} no YouTube Music.",
                "{count} faixas adicionadas à playlist {title} no YouTube Music.",
                normalized_added,
            ).format(count=normalized_added, title=selected_playlist.title)
            self._youtube_music_library_status_message = message
            self._refresh_youtube_music_screen_later()
            self._announce(message)
            if hasattr(self, "_set_status_message"):
                self._set_status_message(message)

        def on_error(exc):
            wx.MessageBox(
                _("Não foi possível adicionar à playlist do YouTube Music.") + "\n\n" + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc)),
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        self._announce(_("Adicionando {count} {label} à playlist {title}...").format(count=track_count, label=track_label, title=selected_playlist.title))
        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def _remove_selected_media_from_youtube_playlist(self, media_paths, item_indexes):
        state = self._get_playlist_state()
        if state is None or state.is_folder_tab:
            self._announce(_("Abra uma playlist do YouTube Music para remover faixas dela."))
            return False

        playlist_id = extract_playlist_id_from_source(getattr(state, "source_path", None))
        if not playlist_id or is_watch_playlist_id(playlist_id):
            self._announce(_("A aba atual não é uma playlist editável do YouTube Music."))
            return False

        video_ids = self._youtube_music_video_ids_from_paths(media_paths)
        if not video_ids:
            self._announce(_("A seleção não contém faixas do YouTube Music para remover."))
            return False

        service = self._get_youtube_music_service()
        if not service.has_saved_browser_auth() and not self._ensure_youtube_music_authenticated():
            return False

        playlist_summary = self._playlist_summary_by_id(playlist_id)
        playlist_title = (
            playlist_summary.title
            if playlist_summary is not None
            else str(getattr(state, "title", "") or "playlist")
        )

        track_count = len(video_ids)
        track_label = _("faixa") if track_count == 1 else _("faixas")

        # Editing a remote playlist changes the user's account and is not
        # undoable from the player, so confirm before touching the server.
        confirmation = wx.MessageBox(
            ngettext(
                "Remover {count} faixa da playlist \"{title}\" no YouTube Music?",
                "Remover {count} faixas da playlist \"{title}\" no YouTube Music?",
                track_count,
            ).format(count=track_count, title=playlist_title)
            + "\n\n"
            + _("Isso altera a playlist diretamente na sua conta e não pode ser desfeito pelo player."),
            _("Remover da playlist do YouTube Music"),
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
            self,
        )
        if confirmation != wx.YES:
            return False

        local_indexes = list(item_indexes or [])

        def worker():
            return service.remove_tracks_from_playlist(playlist_id, video_ids)

        def on_success(removed_count):
            try:
                normalized_removed = int(removed_count)
            except (TypeError, ValueError):
                normalized_removed = track_count
            # Mirror the removal in the open tab so the list matches the server.
            # This announces its own result, so we only update the status line.
            if local_indexes:
                self._remove_items_from_current_playlist(
                    local_indexes,
                    announce_prefix=_("Removido da playlist do YouTube Music"),
                )
            message = ngettext(
                "{count} faixa removida da playlist {title} no YouTube Music.",
                "{count} faixas removidas da playlist {title} no YouTube Music.",
                normalized_removed,
            ).format(count=normalized_removed, title=playlist_title)
            self._youtube_music_library_status_message = message
            self._refresh_youtube_music_screen_later()
            if hasattr(self, "_set_status_message"):
                self._set_status_message(message)
            if not local_indexes:
                self._announce(message)

        def on_error(exc):
            wx.MessageBox(
                _("Não foi possível remover da playlist do YouTube Music.") + "\n\n" + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc)),
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        self._announce(_("Removendo {count} {label} da playlist {title}...").format(count=track_count, label=track_label, title=playlist_title))
        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def _prompt_for_new_youtube_music_playlist(self, *, track_count=0, default_name=""):
        """Ask for the new playlist's name and privacy level.

        Returns a ``(name, privacy_status)`` tuple, or ``None`` when cancelled.
        """
        dialog = YouTubeMusicCreatePlaylistDialog(
            self,
            default_name=default_name,
            track_count=track_count,
        )
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return None
            return dialog.get_playlist_name(), dialog.get_privacy_status()
        finally:
            dialog.Destroy()

    def _on_youtube_music_create_playlist_button(self):
        return self._create_empty_youtube_music_playlist()

    def _create_empty_youtube_music_playlist(self):
        service = self._get_youtube_music_service()
        if not service.has_saved_browser_auth() and not self._ensure_youtube_music_authenticated():
            return False
        return self._create_youtube_music_playlist_with_video_ids([])

    def _create_youtube_music_playlist_with_video_ids(self, video_ids):
        """Create a new remote playlist, optionally seeded with ``video_ids``.

        Authentication is assumed to be ensured by the caller (the add flow and
        the central panel both do so before reaching here). The user picks the
        name and privacy level (Private/Unlisted/Public) in the dialog.
        """
        service = self._get_youtube_music_service()
        normalized_video_ids = list(video_ids or [])
        track_count = len(normalized_video_ids)

        prompt_result = self._prompt_for_new_youtube_music_playlist(track_count=track_count)
        if not prompt_result:
            return False
        playlist_name, privacy_status = prompt_result
        privacy_label = self._PLAYLIST_PRIVACY_LABELS.get(privacy_status, "privada")

        def worker():
            return service.create_playlist(
                playlist_name,
                privacy_status=privacy_status,
                video_ids=normalized_video_ids or None,
            )

        def on_success(_new_playlist_id):
            if track_count:
                message = ngettext(
                    "Playlist \"{name}\" ({privacy}) criada no YouTube Music com {count} faixa.",
                    "Playlist \"{name}\" ({privacy}) criada no YouTube Music com {count} faixas.",
                    track_count,
                ).format(name=playlist_name, privacy=privacy_label, count=track_count)
            else:
                message = _("Playlist \"{name}\" ({privacy}) criada no YouTube Music.").format(name=playlist_name, privacy=privacy_label)
            self._youtube_music_library_status_message = message
            self._refresh_youtube_music_screen_later()
            self._announce(message)
            if hasattr(self, "_set_status_message"):
                self._set_status_message(message)
            # Surface the new playlist in the library list right away.
            self.on_refresh_youtube_music_library(None, announce=False)

        def on_error(exc):
            wx.MessageBox(
                _("Não foi possível criar a playlist no YouTube Music.") + "\n\n" + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc)),
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        self._announce(_("Criando a playlist \"{name}\" no YouTube Music...").format(name=playlist_name))
        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def _on_youtube_music_delete_playlist_button(self):
        return self._delete_selected_youtube_music_library_playlist()

    def _delete_selected_youtube_music_library_playlist(self):
        panel = self._get_youtube_music_panel()
        if panel is None:
            return False

        playlist_id = panel.get_selected_playlist_id()
        if not playlist_id:
            self._announce(_("Selecione uma playlist do YouTube Music para excluir."))
            return False
        if is_watch_playlist_id(playlist_id):
            self._announce(_("Mixes e rádios do YouTube Music não podem ser excluídos."))
            return False

        service = self._get_youtube_music_service()
        if not service.has_saved_browser_auth() and not self._ensure_youtube_music_authenticated():
            return False

        playlist_summary = self._playlist_summary_by_id(playlist_id)
        playlist_title = playlist_summary.title if playlist_summary is not None else "playlist"

        # Deleting a remote playlist removes it from the account entirely and
        # is not undoable from the player, so confirm before touching the server.
        confirmation = wx.MessageBox(
            _("Excluir a playlist \"{title}\" do YouTube Music?").format(title=playlist_title)
            + "\n\n"
            + _("Isso remove a playlist inteira da sua conta e não pode ser desfeito pelo player."),
            _("Excluir playlist do YouTube Music"),
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
            self,
        )
        if confirmation != wx.YES:
            return False

        def worker():
            return service.delete_playlist(playlist_id)

        def on_success(_deleted_playlist_id):
            message = _("Playlist \"{title}\" excluída do YouTube Music.").format(title=playlist_title)
            self._youtube_music_library_status_message = message
            self._refresh_youtube_music_screen_later()
            self._announce(message)
            if hasattr(self, "_set_status_message"):
                self._set_status_message(message)
            self.on_refresh_youtube_music_library(None, announce=False)

        def on_error(exc):
            wx.MessageBox(
                _("Não foi possível excluir a playlist do YouTube Music.") + "\n\n" + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc)),
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        self._announce(_("Excluindo a playlist \"{title}\" do YouTube Music...").format(title=playlist_title))
        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def _rate_selected_playlist_items(self, media_paths, rating):
        normalized_media_paths = [
            str(media_path or "").strip()
            for media_path in (media_paths or [])
            if str(media_path or "").strip()
        ]
        youtube_media_paths = [media_path for media_path in normalized_media_paths if is_youtube_music_media(media_path)]
        if not youtube_media_paths:
            self._announce(_("A seleção atual não contém itens do YouTube Music ou do YouTube."))
            return False

        service = self._get_youtube_music_service()
        if not service.has_saved_browser_auth() and not self._ensure_youtube_music_authenticated():
            return False

        rateable_media_paths = self._selected_youtube_music_media_paths_to_rate(youtube_media_paths, rating)
        if not rateable_media_paths:
            if str(rating or "").strip().upper() == "DISLIKE":
                normalized_message = _("Os itens selecionados já estão marcados como não gostei no YouTube Music.")
            else:
                normalized_message = _("Os itens selecionados já estão curtidos no YouTube Music.")
            self._youtube_music_library_status_message = normalized_message
            self._refresh_youtube_music_screen_later()
            self._announce(normalized_message)
            if hasattr(self, "_set_status_message"):
                self._set_status_message(normalized_message)
            return False

        def worker():
            rated_count = 0
            for media_path in rateable_media_paths:
                service.rate_media_feedback(media_path, rating)
                rated_count += 1
            return rated_count

        def on_success(rated_count):
            if str(rating or "").strip().upper() == "DISLIKE":
                normalized_message = ngettext(
                    "Item marcado como não gostei no YouTube Music.",
                    "{count} itens marcados como não gostei no YouTube Music.",
                    rated_count,
                ).format(count=rated_count)
            else:
                normalized_message = ngettext(
                    "Item curtido no YouTube Music.",
                    "{count} itens curtidos no YouTube Music.",
                    rated_count,
                ).format(count=rated_count)
            self._youtube_music_library_status_message = normalized_message
            self._refresh_youtube_music_screen_later()
            self._announce(normalized_message)
            if hasattr(self, "_set_status_message"):
                self._set_status_message(normalized_message)

        def on_error(exc):
            wx.MessageBox(
                _("Não foi possível avaliar a seleção atual no YouTube Music.") + "\n\n" + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc)),
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)
