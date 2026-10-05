"""Comentários de vídeos e músicas na lista da aba do YouTube Music."""

from player.youtube_music import comments as youtube_comments
from player.youtube_music.playlists import extract_video_id_from_text

from ...i18n import _
from .navigation import YouTubeResultsView


class CommentsMixin:
    @staticmethod
    def _youtube_music_comments_url(result):
        """O endereço cujos comentários dá para ver, ou vazio quando *result* não é vídeo nem música."""
        playback_url = str(getattr(result, "playback_url", "") or "").strip()
        if playback_url and extract_video_id_from_text(playback_url):
            return playback_url
        return ""

    def show_youtube_music_comments(self, result=None):
        """Abre, na lista, os comentários do vídeo ou da música selecionada."""
        if result is None:
            result = self._selected_youtube_music_search_result()
        media_url = self._youtube_music_comments_url(result)
        if not media_url:
            self._announce(_("Este item não tem comentários para mostrar."))
            return False
        return self._open_youtube_music_comments_view(media_url, getattr(result, "title", ""))

    def show_current_media_comments(self):
        """Abre a aba do YouTube Music nos comentários da mídia que está tocando."""
        state = self._get_active_playlist_state()
        media_path = str(getattr(state, "current_media_path", "") or "").strip()
        if not media_path or not extract_video_id_from_text(media_path):
            self._announce(_("A mídia atual não é do YouTube: não há comentários para mostrar."))
            return False
        return self.show_media_comments(media_path)

    def show_media_comments(self, media_path):
        """Abre a aba do KeyTube nos comentários de *media_path*, um item de playlist."""
        media_title = self._media_label(media_path)
        self.on_open_youtube_music(None)
        if self._get_youtube_music_panel() is None:
            return False
        return self._open_youtube_music_comments_view(media_path, media_title)

    def _open_youtube_music_comments_view(self, media_url, media_title):
        title = youtube_comments.comments_view_title(media_title)

        def fetch_page(start, count):
            return youtube_comments.comments_page(media_url, start, count)

        self._announce(_("Abrindo {title}.").format(title=title))
        return self._load_youtube_music_results_view(
            YouTubeResultsView(title=title, fetch_page=fetch_page),
            mode="push",
            error_message=_("Não foi possível carregar os comentários agora."),
            # Aberta pelo menu ou pelo atalho: sem isto o foco fica no campo de busca.
            focus_results=True,
        )

    def _build_youtube_music_replies_view(self, comment):
        def fetch_page(start, count):
            return youtube_comments.comment_replies_page(comment, start, count)

        return YouTubeResultsView(title=youtube_comments.replies_view_title(comment), fetch_page=fetch_page)

    def _read_youtube_music_comment(self, comment):
        """Mostra o comentário inteiro numa caixa de leitura; a linha da lista corta os longos."""
        return self._show_reading_dialog(
            title=_("Comentário de {author}").format(author=comment.author),
            text=youtube_comments.comment_reading_text(comment),
            label=_("Comentário"),
        )
