"""Posts da aba "Posts" (comunidade) de um canal do YouTube e os comentários deles.

O YouTube.js lê os posts sem precisar da conta. Os comentários de um post são
comentários como os de um vídeo, e com a conta conectada dá para agir neles.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..i18n import _
from . import youtubejs_runtime
from .account_session import require_account_session
from .comments import _comments_page, account_fields, sort_fields
from .dependencies import youtubejs_resolver_enabled
from .models import YouTubeResultPage


@dataclass(frozen=True)
class YouTubePostItem:
    """Um post na lista: Enter lê o texto inteiro, Seta para a direita abre os comentários."""

    post_id: str
    channel_id: str
    author: str
    text: str
    published: str = ""
    likes: str = ""
    reply_count: str = ""
    # O vídeo ou a enquete que acompanha o post, em texto.
    attachment_text: str = ""
    attachment_video_id: str = ""
    has_image: bool = False
    has_poll: bool = False
    poll_choices: tuple = ()
    # A lista veio pela conta e a enquete aceita o voto dela.
    can_vote: bool = False

    # A lista trata o post como um resultado que não toca nem é salvo.
    result_type = "post"
    source = ""
    playlist_id = ""
    video_id = ""
    browse_id = ""
    playback_url = ""
    library_playlist = False
    can_browse = True
    opens_on_enter = False
    can_save = False
    can_open = False

    @property
    def stable_id(self):
        return f"post:{self.post_id}"

    @property
    def title(self):
        return self.author

    @property
    def attachment_label(self):
        if self.attachment_video_id:
            return _("vídeo: {title}").format(title=self.attachment_text or self.attachment_video_id)
        if self.has_poll:
            return _("enquete: {choices}").format(choices=self.attachment_text) if self.attachment_text else _("enquete")
        if self.has_image:
            return _("com imagem")
        return ""

    @property
    def detail_text(self):
        parts = []
        if self.published:
            parts.append(self.published)
        if self.attachment_label:
            parts.append(self.attachment_label)
        if self.likes and self.likes != "0":
            parts.append(_("{count} curtidas").format(count=self.likes))
        if self.reply_count and self.reply_count != "0":
            parts.append(_("{count} comentários").format(count=self.reply_count))
        return " · ".join(parts)

    @property
    def choice_label(self):
        text = " ".join(self.text.split()) or self.attachment_label or _("post sem texto")
        label = f"{self.author}: {text}"
        return f"{label} — {self.detail_text}" if self.detail_text else label


def post_from_entry(entry):
    if not isinstance(entry, dict):
        return None
    post_id = str(entry.get("id") or "").strip()
    channel_id = str(entry.get("channel_id") or "").strip()
    if not post_id or not channel_id:
        return None
    return YouTubePostItem(
        post_id=post_id,
        channel_id=channel_id,
        author=str(entry.get("author") or "").strip() or _("Autor desconhecido"),
        text=str(entry.get("text") or "").strip(),
        published=str(entry.get("published") or "").strip(),
        likes=str(entry.get("likes") or "").strip(),
        reply_count=str(entry.get("reply_count") or "").strip(),
        attachment_text=str(entry.get("attachment_text") or "").strip(),
        attachment_video_id=str(entry.get("attachment_video_id") or "").strip(),
        has_image=bool(entry.get("has_image")),
        has_poll=bool(entry.get("has_poll")),
        poll_choices=tuple(str(choice or "").strip() for choice in entry.get("poll_choices") or []),
        can_vote=bool(entry.get("can_vote")),
    )


def _require_youtubejs():
    if not youtubejs_resolver_enabled():
        raise RuntimeError(_("Os posts dos canais precisam do YouTube.js, ativado em Preferências > Recursos adicionais."))


def channel_posts_page(channel_id, start, count):
    """Os posts de *channel_id*, do mais recente para o mais antigo."""
    _require_youtubejs()
    # Com a conta, as enquetes vêm prontas para votar.
    entries, has_more = youtubejs_runtime.channel_posts_page(channel_id, start=start, count=count, **account_fields())
    posts = [post_from_entry(entry) for entry in entries]
    return YouTubeResultPage(results=tuple(post for post in posts if post is not None), has_more=has_more)


def post_comments_page(post, start, count, *, newest=False):
    """Os comentários de *post*, de *start* em diante; com *newest*, os mais recentes primeiro."""
    _require_youtubejs()
    listing = youtubejs_runtime.post_comments_page(
        post.post_id, post.channel_id, start=start, count=count, **account_fields(), **sort_fields(newest)
    )
    return _comments_page(listing, "", start)


def vote_in_poll(post, choice_index):
    """Vota na opção *choice_index* da enquete de *post*; votar em outra troca o voto."""
    cookie_header, account_index = require_account_session()
    youtubejs_runtime.post_vote(cookie_header, post.post_id, choice_index, account_index=account_index)


def posts_view_title(channel_title):
    return _("Posts de {channel}").format(channel=str(channel_title or "").strip())


def post_comments_view_title(post):
    return _("Comentários do post de {author}").format(author=post.author)


def post_reading_text(post):
    """O post inteiro, para a caixa de leitura."""
    lines = [post.text] if post.text else []
    if post.attachment_label:
        lines.extend(["", post.attachment_label] if lines else [post.attachment_label])
    lines.extend(["", post.author])
    details = [part for part in (post.published,) if part]
    if post.likes and post.likes != "0":
        details.append(_("{count} curtidas").format(count=post.likes))
    if post.reply_count and post.reply_count != "0":
        details.append(_("{count} comentários").format(count=post.reply_count))
    if details:
        lines.append(" · ".join(details))
    return "\n".join(lines)
