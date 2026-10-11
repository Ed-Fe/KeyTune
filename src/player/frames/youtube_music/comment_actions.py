"""Escrever, responder, avaliar, editar e apagar comentários com a conta do YouTube."""

import wx

from player.youtube_music import comment_actions

from ... import interface_sounds
from ...i18n import _


class CommentActionsMixin:
    def _youtube_music_comment_menu_entries(self, result):
        """O que a conta pode fazer com o comentário *result*, para o menu de ações."""
        if getattr(result, "result_type", "") != "comment":
            return []
        entries = []
        if result.can_reply:
            entries.append((_("Responder..."), lambda: self.reply_to_youtube_music_comment(result)))
        for operation, label in comment_actions.rating_operations(result):
            entries.append((label, lambda operation=operation: self.rate_youtube_music_comment(result, operation)))
        if result.can_edit:
            entries.append((_("Editar o meu comentário..."), lambda: self.edit_youtube_music_comment(result)))
        if result.can_delete:
            entries.append((_("Apagar o meu comentário..."), lambda: self.delete_youtube_music_comment(result)))
        return entries

    def _ask_youtube_music_comment_text(self, title, prompt, value=""):
        """Pede o texto de um comentário; devolve vazio quando a pessoa desiste."""
        dialog = wx.TextEntryDialog(self, prompt, title, value, style=wx.OK | wx.CANCEL | wx.TE_MULTILINE)
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return ""
            text = str(dialog.GetValue() or "").strip()
        finally:
            dialog.Destroy()
        if not text:
            self._announce(_("Nada foi escrito: o comentário não foi enviado."))
        return text

    def _run_youtube_music_comment_action(
        self, action, on_done, error_message, *, done_sound=interface_sounds.SOUND_SUCCESS
    ):
        def on_success(result):
            interface_sounds.play_for(self, done_sound)
            on_done(result)

        def on_error(exc):
            interface_sounds.play_for(self, interface_sounds.SOUND_FAILURE)
            wx.MessageBox(
                error_message + "\n\n" + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc)),
                "KeyTube",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(action, on_success, on_error=on_error)

    def write_youtube_music_comment(self, context):
        """Publica um comentário novo no vídeo ou no post de *context*, o da lista na tela."""
        if context is None or not self._ensure_youtube_music_authenticated():
            return False
        text = self._ask_youtube_music_comment_text(
            _("Escrever um comentário"), _("Comentário, publicado com a sua conta do YouTube:")
        )
        if not text:
            return False
        view = self._youtube_music_current_results_view()

        def action():
            comment_actions.post_comment(text, media_url=context.media_url, post=context.post)

        def on_done(_result):
            self._announce(_("Comentário publicado."))
            if view.context is context:
                # A lista na tela é a dos comentários que acabou de ganhar um.
                self._reload_youtube_music_results_view(view)

        return self._run_youtube_music_comment_action(action, on_done, _("Não foi possível publicar o comentário."))

    def reply_to_youtube_music_comment(self, comment):
        text = self._ask_youtube_music_comment_text(
            _("Responder a {author}").format(author=comment.author),
            _("Resposta, publicada com a sua conta do YouTube:"),
        )
        if not text:
            return False
        return self._run_youtube_music_comment_action(
            lambda: comment_actions.reply_to_comment(comment, text),
            lambda _result: self._announce(_("Resposta publicada.")),
            _("Não foi possível publicar a resposta."),
        )

    def rate_youtube_music_comment(self, comment, operation):
        def on_done(rated_comment):
            self._replace_youtube_music_result(comment, rated_comment)
            self._announce(comment_actions.rating_done_message(operation))

        return self._run_youtube_music_comment_action(
            lambda: comment_actions.rate_comment(comment, operation),
            on_done,
            _("Não foi possível avaliar o comentário."),
            done_sound=(
                interface_sounds.SOUND_LIKE
                if operation == comment_actions.RATING_LIKE
                else interface_sounds.SOUND_UNLIKE
            ),
        )

    def edit_youtube_music_comment(self, comment):
        text = self._ask_youtube_music_comment_text(
            _("Editar o meu comentário"), _("Novo texto do comentário:"), comment.text
        )
        if not text or text == comment.text:
            return False

        def on_done(edited_comment):
            self._replace_youtube_music_result(comment, edited_comment)
            self._announce(_("Comentário editado."))

        return self._run_youtube_music_comment_action(
            lambda: comment_actions.edit_comment(comment, text),
            on_done,
            _("Não foi possível editar o comentário."),
        )

    def delete_youtube_music_comment(self, comment):
        interface_sounds.play_for(self, interface_sounds.SOUND_QUESTION)
        answer = wx.MessageBox(
            _("Apagar este comentário da sua conta do YouTube? Isto não pode ser desfeito."),
            _("Apagar o meu comentário"),
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
            self,
        )
        if answer != wx.YES:
            return False

        def on_done(_result):
            self._replace_youtube_music_result(comment)
            self._announce(_("Comentário apagado."))

        return self._run_youtube_music_comment_action(
            lambda: comment_actions.delete_comment(comment),
            on_done,
            _("Não foi possível apagar o comentário."),
        )
