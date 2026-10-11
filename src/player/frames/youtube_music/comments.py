"""Comentários de vídeos, músicas e posts na lista da aba do YouTube Music."""

from dataclasses import dataclass, replace

from player.youtube_music import comments as youtube_comments
from player.youtube_music import posts as youtube_posts
from player.youtube_music.dependencies import youtubejs_resolver_enabled
from player.youtube_music.playlists import extract_video_id_from_text

from ...i18n import _
from .navigation import YouTubeResultsView


@dataclass(frozen=True)
class CommentsContext:
    """De quem são os comentários de uma lista e em que ordem ela está."""

    # De um vídeo (*media_url*) ou de um *post* de canal.
    media_url: str = ""
    post: object = None
    # O título da lista sem a ordem, para trocar de ordem sem perdê-lo.
    title: str = ""
    # Os mais recentes primeiro, em vez dos principais.
    newest: bool = False
    # A conversa que vem na frente: o comentário de que uma notificação fala.
    linked_comment: str = ""


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

    def _build_youtube_music_comments_view(self, context):
        """A lista dos comentários de *context*, na ordem que ele diz."""
        if context.post is not None:
            def fetch_page(start, count):
                return youtube_posts.post_comments_page(context.post, start, count, newest=context.newest)
        else:
            def fetch_page(start, count):
                return youtube_comments.comments_page(
                    context.media_url,
                    start,
                    count,
                    newest=context.newest,
                    linked_comment=context.linked_comment,
                )

        title = youtube_comments.newest_view_title(context.title) if context.newest else context.title
        return YouTubeResultsView(title=title, fetch_page=fetch_page, context=context)

    def _open_youtube_music_comments_view(self, media_url, media_title, *, linked_comment=""):
        context = CommentsContext(
            media_url=media_url,
            title=youtube_comments.comments_view_title(media_title),
            linked_comment=linked_comment,
        )
        view = self._build_youtube_music_comments_view(context)
        self._announce(_("Abrindo {title}.").format(title=view.title))
        return self._load_youtube_music_results_view(
            view,
            mode="push",
            error_message=_("Não foi possível carregar os comentários agora."),
            # Aberta pelo menu ou pelo atalho: sem isto o foco fica no campo de busca.
            focus_results=True,
        )

    def _youtube_music_comments_list_menu_entries(self):
        """A troca de ordem, para o menu de ações de uma lista de comentários."""
        context = self._youtube_music_current_results_view().context
        # A conversa de uma notificação tem a ordem dela; o yt-dlp só traz os principais.
        if not isinstance(context, CommentsContext) or context.linked_comment or not youtubejs_resolver_enabled():
            return []
        label = _("Ordenar pelos principais") if context.newest else _("Ordenar pelos mais recentes")
        return [(label, self.toggle_youtube_music_comments_order)]

    def toggle_youtube_music_comments_order(self):
        """Troca a lista de comentários na tela entre os principais e os mais recentes."""
        context = self._youtube_music_current_results_view().context
        if not isinstance(context, CommentsContext):
            return False
        view = self._build_youtube_music_comments_view(replace(context, newest=not context.newest))
        self._announce(_("Abrindo {title}.").format(title=view.title))
        return self._load_youtube_music_results_view(
            view,
            mode="replace",
            error_message=_("Não foi possível carregar os comentários agora."),
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
