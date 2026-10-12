"""Assistir mais tarde: guardar um vídeo do YouTube na playlist fixa da conta e tirá-lo de lá."""

from player.youtube_music import account_lists
from player.youtube_music.models import YOUTUBE_SEARCH_SOURCE_YOUTUBE
from player.youtube_music.playlists import build_youtube_watch_url

from ... import interface_sounds
from ...i18n import _


class WatchLaterMixin:
    def _youtube_music_watch_later_menu_entries(self, result):
        """Salvar em Assistir mais tarde, e tirar da lista quando ela é a de Assistir mais tarde."""
        if (
            getattr(result, "result_type", "") != "video"
            or getattr(result, "source", "") != YOUTUBE_SEARCH_SOURCE_YOUTUBE
            or not getattr(result, "video_id", "")
        ):
            return []
        entries = [(_("Salvar em Assistir mais tarde"), lambda: self._save_youtube_video_to_watch_later(result))]
        view = self._youtube_music_current_results_view()
        if getattr(view, "playlist_id", "") == account_lists.WATCH_LATER_PLAYLIST_ID:
            entries.append(
                (_("Tirar de Assistir mais tarde"), lambda: self._remove_youtube_video_from_watch_later(result))
            )
        return entries

    def _save_youtube_video_to_watch_later(self, result):
        return self._change_youtube_watch_later(
            result,
            account_lists.add_to_playlist,
            _("{title} salvo em Assistir mais tarde."),
            _("Não foi possível salvar em Assistir mais tarde."),
        )

    def _remove_youtube_video_from_watch_later(self, result):
        return self._change_youtube_watch_later(
            result,
            account_lists.remove_from_playlist,
            _("{title} tirado de Assistir mais tarde."),
            _("Não foi possível tirar de Assistir mais tarde."),
        )

    def _change_youtube_watch_later(self, result, change, done_message, error_message):
        if not self._ensure_youtube_music_authenticated():
            return False
        media_url = build_youtube_watch_url(result.video_id)

        def worker():
            if not change(account_lists.WATCH_LATER_PLAYLIST_ID, media_url):
                raise RuntimeError(error_message)
            return True

        def on_done(_result):
            interface_sounds.play_for(self, interface_sounds.SOUND_SUCCESS)
            self._announce(done_message.format(title=result.title))

        def on_error(exc):
            interface_sounds.play_for(self, interface_sounds.SOUND_FAILURE)
            self._announce(
                error_message + " " + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc))
            )

        return self._run_youtube_music_background_task(worker, on_done, on_error=on_error)
