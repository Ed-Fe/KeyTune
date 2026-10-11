"""As ações do YouTube.js que o KeyTune pede ao processo Node: uma função por ação.

Cada uma só monta o pedido e devolve a resposta no formato que o resto do KeyTune
espera. Quem manda o pedido ao processo e cuida de falhas e de tempo é o
``youtubejs_runtime``; é por ele que estas funções também podem ser chamadas
(``youtubejs_runtime.comments_page(...)``).
"""

from __future__ import annotations

__all__ = [
    "search_page",
    "comments_page",
    "comment_replies_page",
    "post_comments_page",
    "create_comment",
    "comment_action",
    "notifications_page",
    "notification_action",
    "channel_state",
    "channel_action",
    "channel_posts_page",
    "channel_about",
    "channel_search_page",
    "post_vote",
    "watch_history_page",
    "add_to_watch_history",
    "live_chat",
    "live_chat_send",
    "audio_tracks",
    "media_details",
    "subscription_videos_page",
    "subscribed_channels_page",
]


def _request_action(action, **fields):
    """Pede *action* ao processo do YouTube.js, com o idioma e a região do conteúdo."""
    from . import youtubejs_runtime

    return youtubejs_runtime.request_action(action, **fields)


def _account_fields(cookie_header, account_index):
    return {"cookie": str(cookie_header or "").strip(), "account_index": int(account_index or 0)}


def search_page(query, kind, *, start, count):
    """Uma página da busca do YouTube: entradas no formato da listagem do yt-dlp e se há mais."""
    response = _request_action("search", query=str(query or "").strip(), kind=str(kind or ""), start=start, count=count)
    return list(response.get("entries") or []), bool(response.get("has_more"))


def comments_page(media_url, *, start, count, cookie_header="", account_index=0, sort="", linked_comment=""):
    """Uma página dos comentários de um vídeo, se há mais e se a conta pode comentar ali.

    Com os cookies, os comentários vêm pela conta. *sort* ``"newest"`` traz os mais
    recentes primeiro, e *linked_comment* põe na frente a conversa desse comentário.
    """
    response = _request_action(
        "comments",
        media_url=str(media_url or "").strip(),
        start=start,
        count=count,
        sort=str(sort or ""),
        linked_comment=str(linked_comment or "").strip(),
        **_account_fields(cookie_header, account_index),
    )
    return list(response.get("entries") or []), bool(response.get("has_more")), bool(response.get("can_comment"))


def comment_replies_page(media_url, comment_id, *, start, count, cookie_header="", account_index=0):
    """Uma página das respostas a um comentário aberto por :func:`comments_page`."""
    response = _request_action(
        "comment_replies",
        media_url=str(media_url or "").strip(),
        comment_id=str(comment_id or "").strip(),
        start=start,
        count=count,
        **_account_fields(cookie_header, account_index),
    )
    return list(response.get("entries") or []), bool(response.get("has_more"))


def post_comments_page(post_id, channel_id, *, start, count, cookie_header="", account_index=0, sort=""):
    """Uma página dos comentários de um post de canal, se há mais e se a conta pode comentar ali."""
    response = _request_action(
        "post_comments",
        post_id=str(post_id or "").strip(),
        channel_id=str(channel_id or "").strip(),
        start=start,
        count=count,
        sort=str(sort or ""),
        **_account_fields(cookie_header, account_index),
    )
    return list(response.get("entries") or []), bool(response.get("has_more")), bool(response.get("can_comment"))


def create_comment(cookie_header, text, *, media_url="", post_id="", channel_id="", account_index=0):
    """Publica um comentário no vídeo *media_url* ou no post *post_id* de *channel_id*."""
    return _request_action(
        "create_comment",
        text=str(text or ""),
        media_url=str(media_url or "").strip(),
        post_id=str(post_id or "").strip(),
        channel_id=str(channel_id or "").strip(),
        **_account_fields(cookie_header, account_index),
    )


def comment_action(cookie_header, comment_id, operation, *, text="", account_index=0):
    """Responde, avalia, edita ou apaga um comentário que veio numa lista aberta com a conta."""
    return _request_action(
        "comment_action",
        comment_id=str(comment_id or "").strip(),
        operation=str(operation or ""),
        text=str(text or ""),
        **_account_fields(cookie_header, account_index),
    )


def notifications_page(cookie_header, *, start, count, account_index=0):
    """Uma página da caixa de notificações da conta e se há mais."""
    response = _request_action(
        "notifications", start=start, count=count, **_account_fields(cookie_header, account_index)
    )
    return list(response.get("entries") or []), bool(response.get("has_more"))


def notification_action(cookie_header, notification_id, operation, *, account_index=0):
    """Marca uma notificação como lida (``read``) ou a tira da caixa (``hide``)."""
    return _request_action(
        "notification_action",
        notification_id=str(notification_id or "").strip(),
        operation=str(operation or ""),
        **_account_fields(cookie_header, account_index),
    )


def channel_state(cookie_header, channel_id, *, account_index=0):
    """Se a conta está inscrita em *channel_id* e o que o sino dele avisa."""
    return _request_action(
        "channel_state", channel_id=str(channel_id or "").strip(), **_account_fields(cookie_header, account_index)
    )


def channel_action(cookie_header, channel_id, operation, *, account_index=0):
    """Inscreve, cancela a inscrição ou muda as notificações de *channel_id*."""
    return _request_action(
        "channel_action",
        channel_id=str(channel_id or "").strip(),
        operation=str(operation or ""),
        **_account_fields(cookie_header, account_index),
    )


def channel_posts_page(channel_id, *, start, count, cookie_header="", account_index=0):
    """Uma página dos posts de um canal e se há mais."""
    response = _request_action(
        "channel_posts",
        channel_id=str(channel_id or "").strip(),
        start=start,
        count=count,
        **_account_fields(cookie_header, account_index),
    )
    return list(response.get("entries") or []), bool(response.get("has_more"))


def channel_about(channel_id):
    """A página "Sobre" de um canal: descrição, inscritos, vídeos, visualizações, país e links."""
    return _request_action("channel_about", channel_id=str(channel_id or "").strip())


def channel_search_page(channel_id, query, *, start, count):
    """Uma página do que a busca de dentro de um canal acha nos vídeos dele, e se há mais."""
    response = _request_action(
        "channel_search",
        channel_id=str(channel_id or "").strip(),
        query=str(query or "").strip(),
        start=start,
        count=count,
    )
    return list(response.get("entries") or []), bool(response.get("has_more"))


def post_vote(cookie_header, post_id, choice, *, remove=False, account_index=0):
    """Vota na opção *choice* da enquete de um post, ou tira o voto dela com *remove*."""
    return _request_action(
        "post_vote",
        post_id=str(post_id or "").strip(),
        choice=int(choice),
        operation="unvote" if remove else "vote",
        **_account_fields(cookie_header, account_index),
    )


def watch_history_page(cookie_header, *, start, count, account_index=0):
    """Uma página do histórico do YouTube da conta e se há mais."""
    response = _request_action(
        "watch_history", start=start, count=count, **_account_fields(cookie_header, account_index)
    )
    return list(response.get("entries") or []), bool(response.get("has_more"))


def add_to_watch_history(cookie_header, media_url, *, account_index=0):
    """Põe o vídeo *media_url* no histórico do YouTube da conta; devolve se o YouTube aceitou."""
    response = _request_action(
        "add_to_history", media_url=str(media_url or "").strip(), **_account_fields(cookie_header, account_index)
    )
    return bool(response.get("ok"))


def live_chat(media_url, *, restart=False, cookie_header="", account_index=0):
    """O que chegou no chat ao vivo de *media_url* desde o último pedido.

    Devolve ``(mensagens, se a conta pode enviar, se a transmissão acabou, nome da
    conta no chat, milissegundos que o YouTube pede para esperar até o próximo
    pedido)``; *restart* recomeça das mensagens mais recentes.
    """
    response = _request_action(
        "live_chat",
        media_url=str(media_url or "").strip(),
        restart=bool(restart),
        **_account_fields(cookie_header, account_index),
    )
    return (
        list(response.get("entries") or []),
        bool(response.get("can_send")),
        bool(response.get("ended")),
        str(response.get("viewer") or "").strip(),
        int(response.get("timeout_ms") or 0),
    )


def live_chat_send(cookie_header, media_url, text, *, account_index=0):
    """Envia *text* ao chat ao vivo de *media_url* com a conta."""
    return _request_action(
        "live_chat_send",
        media_url=str(media_url or "").strip(),
        text=str(text or ""),
        **_account_fields(cookie_header, account_index),
    )


def audio_tracks(media_url, *, names=True):
    """As faixas de áudio de um vídeo dublado; com *names*, os nomes vêm no idioma do conteúdo."""
    response = _request_action("audio_tracks", media_url=str(media_url or "").strip(), names=bool(names))
    return list(response.get("tracks") or [])


def media_details(media_url):
    """Os detalhes de um vídeo ou música: descrição, canal, visualizações, curtidas e data."""
    return _request_action("details", media_url=str(media_url or "").strip())


def subscription_videos_page(cookie_header, *, start, count, account_index=0):
    """Uma página dos vídeos novos das inscrições da conta *account_index* de *cookie_header*."""
    response = _request_action(
        "subscription_videos",
        cookie=str(cookie_header or "").strip(),
        account_index=int(account_index or 0),
        start=start,
        count=count,
    )
    return list(response.get("entries") or []), bool(response.get("has_more"))


def subscribed_channels_page(cookie_header, *, start, count, account_index=0):
    """Uma página dos canais em que a conta *account_index* de *cookie_header* está inscrita."""
    response = _request_action(
        "subscribed_channels",
        cookie=str(cookie_header or "").strip(),
        account_index=int(account_index or 0),
        start=start,
        count=count,
    )
    return list(response.get("entries") or []), bool(response.get("has_more"))
