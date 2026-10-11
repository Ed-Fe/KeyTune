"""O chat de uma transmissão ao vivo do YouTube: ler o que chega e enviar mensagens.

O YouTube.js devolve, a cada pedido, só as mensagens que chegaram desde o
anterior. Sem a conta dá para ler; enviar precisa dela.
"""

from __future__ import annotations

from dataclasses import dataclass

from .. import interface_sounds
from ..i18n import _
from . import youtubejs_runtime
from .account_session import optional_account_session, require_account_session
from .dependencies import youtubejs_resolver_enabled


# De quanto em quanto tempo a janela pede as mensagens novas.
LIVE_CHAT_POLL_SECONDS = 4
# Quantas mensagens a lista guarda; as mais antigas saem.
LIVE_CHAT_MAX_MESSAGES = 500
# Num chat movimentado, quantas das mensagens novas são faladas a cada vez.
LIVE_CHAT_SPOKEN_MESSAGES = 3


@dataclass(frozen=True)
class YouTubeChatMessage:
    """Uma mensagem do chat na lista: Enter lê o texto inteiro."""

    message_id: str
    author: str
    text: str
    # O valor de uma mensagem paga (Super Chat), como o YouTube o escreve.
    amount: str = ""

    # A lista trata a mensagem como um resultado que não toca nem abre.
    result_type = "chat"
    source = ""
    playlist_id = ""
    video_id = ""
    browse_id = ""
    playback_url = ""
    library_playlist = False
    can_browse = False
    opens_on_enter = False
    can_save = False
    can_open = False

    @property
    def stable_id(self):
        return f"chat:{self.message_id}"

    @property
    def title(self):
        return self.author

    @property
    def detail_text(self):
        return self.amount

    @property
    def choice_label(self):
        text = " ".join(self.text.split())
        if self.amount:
            text = f"{self.amount} {text}".strip()
        return f"{self.author}: {text}"


@dataclass(frozen=True)
class LiveChatUpdate:
    """O que um pedido ao chat trouxe: as mensagens novas, se dá para enviar e se acabou."""

    messages: tuple = ()
    can_send: bool = False
    ended: bool = False
    # Como a conta aparece no chat; vazio sem conta ou quando o YouTube não diz.
    viewer: str = ""
    # O motivo que o YouTube dá para a conta não poder escrever (chat só de inscritos, por exemplo).
    restriction: str = ""


def message_from_entry(entry):
    if not isinstance(entry, dict):
        return None
    message_id = str(entry.get("id") or "").strip()
    text = str(entry.get("text") or "").strip()
    amount = str(entry.get("amount") or "").strip()
    if not message_id or not (text or amount):
        return None
    return YouTubeChatMessage(
        message_id=message_id,
        author=str(entry.get("author") or "").strip() or _("Autor desconhecido"),
        text=text,
        amount=amount,
    )


def live_chat_update(media_url, *, restart=False):
    """As mensagens que chegaram no chat de *media_url*; *restart* recomeça das mais recentes."""
    if not youtubejs_resolver_enabled():
        raise RuntimeError(_("O chat ao vivo precisa do YouTube.js, ativado em Preferências > Recursos adicionais."))
    cookie_header, account_index = optional_account_session()
    account = {"cookie_header": cookie_header, "account_index": account_index} if cookie_header else {}
    entries, can_send, ended, *extra = youtubejs_runtime.live_chat(media_url, restart=restart, **account)
    viewer, restriction = (list(extra) + ["", ""])[:2]
    messages = [message_from_entry(entry) for entry in entries]
    return LiveChatUpdate(
        messages=tuple(message for message in messages if message is not None),
        can_send=can_send,
        ended=ended,
        viewer=str(viewer or "").strip(),
        restriction="" if can_send else str(restriction or "").strip(),
    )


def send_live_chat_message(media_url, text):
    text = " ".join(str(text or "").split())
    if not text:
        raise RuntimeError(_("A mensagem está vazia."))
    cookie_header, account_index = require_account_session()
    youtubejs_runtime.live_chat_send(cookie_header, media_url, text, account_index=account_index)


def live_chat_view_title(media_title):
    media_title = str(media_title or "").strip()
    if media_title:
        return _("Chat ao vivo de {title}").format(title=media_title)
    return _("Chat ao vivo")


def message_reading_text(message):
    """A mensagem inteira, para a caixa de leitura."""
    lines = [message.text] if message.text else []
    if message.amount:
        lines.append(message.amount)
    lines.extend(["", message.author])
    return "\n".join(lines)


def mentions_viewer(message, viewer):
    """Se *message*, escrita por outra pessoa, cita o nome de *viewer*."""
    name = str(viewer or "").strip().lstrip("@").casefold()
    if not name or message.author.strip().lstrip("@").casefold() == name:
        return False
    return name in str(message.text or "").casefold()


def messages_sound(messages, viewer=""):
    """O som das mensagens que chegaram: o da mais importante entre elas."""
    messages = list(messages)
    if any(mentions_viewer(message, viewer) for message in messages):
        return interface_sounds.SOUND_CHAT_MENTION
    if any(message.amount for message in messages):
        return interface_sounds.SOUND_CHAT_PAID
    return interface_sounds.SOUND_CHAT_MESSAGE


def spoken_messages(messages):
    """O que falar das mensagens que chegaram: as últimas, cada uma com quem escreveu."""
    return [message.choice_label for message in list(messages)[-LIVE_CHAT_SPOKEN_MESSAGES:]]
