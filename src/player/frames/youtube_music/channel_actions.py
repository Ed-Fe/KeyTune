"""O que dá para fazer com um canal do YouTube: inscrição, sino, "Sobre" e os posts."""

import wx

from player.youtube_music import channel_about as youtube_channel_about
from player.youtube_music import channel_search as youtube_channel_search
from player.youtube_music import posts as youtube_posts
from player.youtube_music import subscriptions
from player.youtube_music.models import YOUTUBE_SEARCH_SOURCE_YOUTUBE
from player.youtube_music.playlists import build_youtube_watch_url

from ... import interface_sounds
from ...i18n import _
from .comments import CommentsContext
from .navigation import YouTubeResultsView


_BELL_CHOICES = (
    (subscriptions.BELL_ALL, _("Receber todas as notificações")),
    (subscriptions.BELL_PERSONALIZED, _("Receber notificações personalizadas")),
    (subscriptions.BELL_NONE, _("Não receber notificações")),
)


class ChannelActionsMixin:
    def _youtube_music_channel_menu_entries(self, result):
        """As ações de um canal do YouTube no menu de ações; as mesmas das linhas de dentro dele."""
        if (
            getattr(result, "result_type", "") != "channel"
            or getattr(result, "source", "") != YOUTUBE_SEARCH_SOURCE_YOUTUBE
            or not getattr(result, "browse_id", "")
        ):
            return []
        return [
            (_("Inscrição e notificações do canal..."), lambda: self.manage_youtube_channel_subscription(result)),
            (_("Sobre o canal"), lambda: self.show_youtube_channel_about(result)),
        ]

    def _youtube_music_post_menu_entries(self, result):
        """Votar na enquete de um post, para o menu de ações."""
        if getattr(result, "result_type", "") != "post" or not result.can_vote:
            return []
        return [(_("Votar na enquete..."), lambda: self.vote_in_youtube_post_poll(result))]

    def _show_youtube_channel_error(self, message, exc):
        interface_sounds.play_for(self, interface_sounds.SOUND_FAILURE)
        wx.MessageBox(
            message + "\n\n" + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc)),
            "KeyTube",
            wx.OK | wx.ICON_ERROR,
            self,
        )

    def _announce_youtube_channel_action_done(self, message):
        interface_sounds.play_for(self, interface_sounds.SOUND_SUCCESS)
        self._announce(message)

    def manage_youtube_channel_subscription(self, channel):
        """Mostra a inscrição da conta em *channel* e deixa mudá-la."""
        if not self._ensure_youtube_music_authenticated():
            return False

        def worker():
            return subscriptions.channel_subscription(channel.browse_id)

        def on_error(exc):
            self._show_youtube_channel_error(_("Não foi possível consultar a inscrição neste canal."), exc)

        self._announce(_("Consultando a inscrição em {channel}.").format(channel=channel.title))
        return self._run_youtube_music_background_task(
            worker,
            lambda subscription: self._choose_youtube_channel_subscription(channel, subscription),
            on_error=on_error,
        )

    def _choose_youtube_channel_subscription(self, channel, subscription):
        if not subscription.subscribed:
            interface_sounds.play_for(self, interface_sounds.SOUND_QUESTION)
            answer = wx.MessageBox(
                _("Você não está inscrito em {channel}. Inscrever-se?").format(channel=channel.title),
                _("Inscrição no canal"),
                wx.YES_NO | wx.ICON_QUESTION,
                self,
            )
            if answer != wx.YES:
                return False
            return self._apply_youtube_channel_action(
                channel,
                lambda: subscriptions.subscribe_to_channel(channel.browse_id),
                _("Inscrição feita em {channel}.").format(channel=channel.title),
            )

        levels = [level for level, _label in _BELL_CHOICES]
        dialog = wx.SingleChoiceDialog(
            self,
            _("Você está inscrito em {channel}. O que este canal avisa:").format(channel=channel.title),
            _("Inscrição no canal"),
            [label for _level, label in _BELL_CHOICES] + [_("Cancelar a inscrição")],
        )
        try:
            if subscription.notifications in levels:
                dialog.SetSelection(levels.index(subscription.notifications))
            if dialog.ShowModal() != wx.ID_OK:
                return False
            selection = dialog.GetSelection()
        finally:
            dialog.Destroy()

        if selection >= len(levels):
            return self._apply_youtube_channel_action(
                channel,
                lambda: subscriptions.unsubscribe_from_channel(channel.browse_id),
                _("Inscrição cancelada em {channel}.").format(channel=channel.title),
            )
        level = levels[selection]
        if level == subscription.notifications:
            return False
        return self._apply_youtube_channel_action(
            channel,
            lambda: subscriptions.set_channel_notifications(channel.browse_id, level),
            _("{channel}: {level}.").format(channel=channel.title, level=subscriptions.bell_label(level)),
        )

    def _apply_youtube_channel_action(self, channel, action, done_message):
        def on_error(exc):
            self._show_youtube_channel_error(
                _("O YouTube não aceitou a mudança em {channel}.").format(channel=channel.title), exc
            )

        return self._run_youtube_music_background_task(
            action, lambda _result: self._announce_youtube_channel_action_done(done_message), on_error=on_error
        )

    def show_youtube_channel_about(self, channel):
        """Mostra a página "Sobre" de *channel* numa caixa de leitura."""

        def worker():
            return youtube_channel_about.channel_about(channel.browse_id)

        def on_success(about):
            self._show_reading_dialog(
                title=_("Sobre {channel}").format(channel=about.title or channel.title),
                text=youtube_channel_about.about_reading_text(about),
                label=_("Sobre o canal"),
            )

        def on_error(exc):
            self._show_youtube_channel_error(_("Não foi possível carregar os dados do canal agora."), exc)

        self._announce(_("Carregando os dados do canal."))
        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def search_youtube_channel(self, channel):
        """Pede o que buscar e mostra os vídeos de *channel* que batem com o texto."""
        dialog = wx.TextEntryDialog(
            self,
            _("Buscar nos vídeos de {channel}:").format(channel=channel.title),
            _("Buscar neste canal"),
        )
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return False
            query = " ".join(str(dialog.GetValue() or "").split())
        finally:
            dialog.Destroy()
        if not query:
            self._announce(_("Digite algo para buscar no canal."))
            return False

        def fetch_page(start, count):
            return youtube_channel_search.channel_search_page(channel.browse_id, query, start, count)

        view = YouTubeResultsView(
            title=youtube_channel_search.channel_search_view_title(query, channel.title), fetch_page=fetch_page
        )
        self._announce(_("Pesquisando {query}.").format(query=query))
        return self._load_youtube_music_results_view(
            view,
            mode="push",
            error_message=_("Não foi possível concluir a busca agora."),
            focus_results=True,
        )

    def vote_in_youtube_post_poll(self, post):
        """Mostra as opções da enquete de *post* e registra o voto na escolhida."""
        if not post.can_vote or not self._ensure_youtube_music_authenticated():
            return False
        dialog = wx.SingleChoiceDialog(
            self,
            _("Enquete de {author}. Votar em:").format(author=post.author),
            _("Votar na enquete"),
            list(post.poll_choices),
        )
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return False
            choice = dialog.GetSelection()
        finally:
            dialog.Destroy()
        if not 0 <= choice < len(post.poll_choices):
            return False

        def on_error(exc):
            self._show_youtube_channel_error(_("O YouTube não registrou o voto."), exc)

        return self._run_youtube_music_background_task(
            lambda: youtube_posts.vote_in_poll(post, choice),
            lambda _result: self._announce_youtube_channel_action_done(
                _("Voto registrado: {choice}.").format(choice=post.poll_choices[choice])
            ),
            on_error=on_error,
        )

    def _build_youtube_channel_posts_view(self, channel):
        def fetch_page(start, count):
            return youtube_posts.channel_posts_page(channel.browse_id, start, count)

        return YouTubeResultsView(title=youtube_posts.posts_view_title(channel.title), fetch_page=fetch_page)

    def _build_youtube_music_post_comments_view(self, post):
        return self._build_youtube_music_comments_view(
            CommentsContext(post=post, title=youtube_posts.post_comments_view_title(post))
        )

    def _read_youtube_music_post(self, post):
        """Mostra o post inteiro numa caixa de leitura; a linha da lista corta os longos."""
        actions = [(_("Ver &comentários"), lambda: self.on_browse_youtube_music_search_result(post, focus_results=True))]
        if post.attachment_video_id:
            actions.append((_("&Tocar o vídeo do post"), lambda: self._play_youtube_music_post_video(post)))
        if post.can_vote:
            actions.append((_("&Votar na enquete..."), lambda: self.vote_in_youtube_post_poll(post)))
        return self._show_reading_dialog(
            title=_("Post de {author}").format(author=post.author),
            text=youtube_posts.post_reading_text(post),
            label=_("Post"),
            actions=actions,
        )

    def _play_youtube_music_post_video(self, post):
        title = post.attachment_text or _("Vídeo do YouTube ({id})").format(id=post.attachment_video_id)
        video_url = build_youtube_watch_url(post.attachment_video_id)
        self._open_prepared_media_playlist(
            [video_url],
            title,
            browser_item_labels=[title],
            source_path=video_url,
            announce_message=_("Vídeo do YouTube aberto: {title}.").format(title=title),
        )
        return True
