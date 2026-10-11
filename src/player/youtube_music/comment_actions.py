"""O que a conta faz com os comentários: escrever, responder, avaliar, editar e apagar.

Tudo passa pelo YouTube.js com os cookies da conta, e só vale para comentários
de uma lista aberta com ela: é dessa lista que o YouTube.js tira o que cada ação
precisa.
"""

from __future__ import annotations

from dataclasses import replace

from ..i18n import _
from . import youtubejs_runtime
from .account_session import require_account_session


RATING_LIKE = "like"
RATING_UNLIKE = "unlike"
RATING_DISLIKE = "dislike"
RATING_UNDISLIKE = "undislike"


def _clean_text(text):
    text = str(text or "").strip()
    if not text:
        raise RuntimeError(_("O comentário está vazio."))
    return text


def post_comment(text, *, media_url="", post=None):
    """Publica um comentário novo no vídeo *media_url* ou no *post* de um canal."""
    cookie_header, account_index = require_account_session()
    youtubejs_runtime.create_comment(
        cookie_header,
        _clean_text(text),
        media_url=media_url,
        post_id=getattr(post, "post_id", ""),
        channel_id=getattr(post, "channel_id", ""),
        account_index=account_index,
    )


def _comment_action(comment, operation, text=""):
    cookie_header, account_index = require_account_session()
    return youtubejs_runtime.comment_action(
        cookie_header, comment.comment_id, operation, text=text, account_index=account_index
    )


def reply_to_comment(comment, text):
    _comment_action(comment, "reply", _clean_text(text))


def edit_comment(comment, text):
    """Troca o texto de um comentário da conta; devolve o comentário com o texto novo."""
    text = _clean_text(text)
    _comment_action(comment, "edit", text)
    return replace(comment, text=text)


def delete_comment(comment):
    _comment_action(comment, "delete")


def rating_operations(comment):
    """As avaliações que cabem agora em *comment*: ``(operação, rótulo)``."""
    if not comment.can_rate:
        return []
    like = (RATING_UNLIKE, _("Remover a curtida")) if comment.liked else (RATING_LIKE, _("Curtir o comentário"))
    dislike = (
        (RATING_UNDISLIKE, _("Remover o não gostei"))
        if comment.disliked
        else (RATING_DISLIKE, _("Não gostei do comentário"))
    )
    return [like, dislike]


def rate_comment(comment, operation):
    """Avalia *comment* e o devolve como ficou."""
    response = _comment_action(comment, operation)
    return replace(comment, liked=bool(response.get("liked")), disliked=bool(response.get("disliked")))


def rating_done_message(operation):
    return {
        RATING_LIKE: _("Comentário curtido."),
        RATING_UNLIKE: _("Curtida removida."),
        RATING_DISLIKE: _("Comentário marcado com não gostei."),
        RATING_UNDISLIKE: _("Não gostei removido."),
    }.get(operation, "")
