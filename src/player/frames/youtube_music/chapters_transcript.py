"""Capítulos e transcrição de um vídeo do YouTube."""

import wx

from player.youtube_music import chapters as youtube_chapters
from player.youtube_music import transcript as youtube_transcript
from player.youtube_music.models import (
    YOUTUBE_SEARCH_SOURCE_YOUTUBE,
    YouTubeMediaSearchResult,
    YouTubeResultPage,
)
from player.youtube_music.playlists import build_youtube_watch_url, extract_video_id_from_text

from ...i18n import _
from .navigation import YouTubeResultsView


class ChaptersTranscriptMixin:
    def _youtube_music_chapters_menu_entries(self, result):
        """Capítulos e transcrição, para o menu de ações de um vídeo."""
        if getattr(result, "result_type", "") not in ("video", "song") or not self._youtube_music_comments_url(result):
            return []
        return [
            (_("Ver capítulos"), lambda: self.show_youtube_music_chapters(result)),
            (_("Ver transcrição"), lambda: self.show_youtube_music_transcript(result)),
        ]

    def _chapters_transcript_target(self, result, missing_message):
        if result is None:
            result = self._selected_youtube_music_search_result()
        media_url = self._youtube_music_comments_url(result)
        if not media_url:
            self._announce(missing_message)
            return "", ""
        return media_url, getattr(result, "title", "")

    def _current_media_for_chapters_transcript(self, missing_message):
        state = self._get_active_playlist_state()
        media_path = str(getattr(state, "current_media_path", "") or "").strip()
        if not media_path or not extract_video_id_from_text(media_path):
            self._announce(missing_message)
            return "", ""
        return media_path, self._media_label(media_path)

    def show_youtube_music_chapters(self, result=None):
        media_url, title = self._chapters_transcript_target(
            result, _("Este item não tem capítulos para mostrar.")
        )
        return self._open_youtube_music_chapters(media_url, title) if media_url else False

    def show_current_media_chapters(self):
        media_url, title = self._current_media_for_chapters_transcript(
            _("A mídia atual não é do YouTube: não há capítulos para mostrar.")
        )
        if not media_url:
            return False
        self.on_open_youtube_music(None)
        if self._get_youtube_music_panel() is None:
            return False
        return self._open_youtube_music_chapters(media_url, title)

    def _open_youtube_music_chapters(self, media_url, media_title):
        video_id = extract_video_id_from_text(media_url)
        view_title = _("Capítulos de {title}").format(title=media_title) if media_title else _("Capítulos")

        def fetch_page(_start, _count):
            chapters = youtube_chapters.media_chapters(media_url)
            if not chapters:
                raise RuntimeError(_("Este vídeo não tem capítulos."))
            results = tuple(
                YouTubeMediaSearchResult(
                    source=YOUTUBE_SEARCH_SOURCE_YOUTUBE,
                    result_type="video",
                    title=chapter.title,
                    subtitle=youtube_transcript.format_clock(chapter.start_seconds),
                    video_id=video_id,
                    playback_url=build_youtube_watch_url(video_id),
                    source_badge="YouTube",
                    resume_seconds=chapter.start_seconds,
                )
                for chapter in chapters
            )
            return YouTubeResultPage(results=results, has_more=False)

        self._announce(_("Abrindo {title}.").format(title=view_title))
        return self._load_youtube_music_results_view(
            YouTubeResultsView(title=view_title, fetch_page=fetch_page),
            mode="push",
            error_message=_("Não foi possível carregar os capítulos agora."),
            focus_results=True,
        )

    def show_youtube_music_transcript(self, result=None):
        media_url, title = self._chapters_transcript_target(
            result, _("Este item não tem transcrição para mostrar.")
        )
        return self._open_youtube_music_transcript(media_url, title) if media_url else False

    def show_current_media_transcript(self):
        media_url, title = self._current_media_for_chapters_transcript(
            _("A mídia atual não é do YouTube: não há transcrição para mostrar.")
        )
        return self._open_youtube_music_transcript(media_url, title) if media_url else False

    def _open_youtube_music_transcript(self, media_url, media_title):
        def worker():
            return youtube_transcript.media_transcript(media_url)

        def on_success(transcript):
            self._show_reading_dialog(
                title=_("Transcrição de {title}").format(title=media_title) if media_title else _("Transcrição"),
                text=youtube_transcript.transcript_reading_text(transcript),
                label=_("Transcrição"),
            )

        def on_error(exc):
            wx.MessageBox(
                _("Não foi possível carregar a transcrição agora.")
                + "\n\n"
                + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc)),
                "KeyTube",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        self._announce(_("Carregando a transcrição."))
        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)
