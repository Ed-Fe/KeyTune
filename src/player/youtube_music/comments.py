"""Comentários de um vídeo ou música do YouTube.

O YouTube.js traz os comentários aos poucos e as respostas de cada um. Sem ele,
o yt-dlp entrega só o primeiro lote, sem respostas.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..i18n import _
from ..log import get_logger
from . import youtubejs_runtime
from .dependencies import ensure_yt_dlp_executable_available, youtubejs_resolver_enabled
from .models import YouTubeResultPage
from .search import _clean_external_tool_error
from .yt_dlp_runtime import extract_info as extract_yt_dlp_info


_logger = get_logger(__name__)

YT_DLP_COMMENT_LIMIT = 20
YT_DLP_COMMENTS_SOCKET_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class YouTubeCommentItem:
    """Um comentário na lista: Enter lê o texto inteiro, Seta para a direita abre as respostas."""

    comment_id: str
    author: str
    text: str
    media_url: str = ""
    likes: str = ""
    published: str = ""
    reply_count: str = ""
    has_replies: bool = False
    pinned: bool = False

    # A lista trata o comentário como um resultado que não toca nem é salvo.
    result_type = "comment"
    source = ""
    playlist_id = ""
    video_id = ""
    browse_id = ""
    playback_url = ""
    library_playlist = False
    opens_on_enter = False
    can_save = False
    can_open = False

    @property
    def can_browse(self):
        return self.has_replies

    @property
    def stable_id(self):
        return f"comment:{self.comment_id}"

    @property
    def title(self):
        return self.author

    @property
    def detail_text(self):
        parts = []
        if self.pinned:
            parts.append(_("fixado"))
        if self.published:
            parts.append(self.published)
        if self.likes and self.likes != "0":
            parts.append(_("{count} curtidas").format(count=self.likes))
        if self.has_replies:
            parts.append(_("{count} respostas").format(count=self.reply_count or "?"))
        return " · ".join(parts)

    @property
    def choice_label(self):
        label = f"{self.author}: {' '.join(self.text.split())}"
        return f"{label} — {self.detail_text}" if self.detail_text else label


def comment_from_entry(entry, media_url):
    if not isinstance(entry, dict):
        return None
    comment_id = str(entry.get("id") or "").strip()
    text = str(entry.get("text") or "").strip()
    if not comment_id or not text:
        return None
    return YouTubeCommentItem(
        comment_id=comment_id,
        author=str(entry.get("author") or "").strip() or _("Autor desconhecido"),
        text=text,
        media_url=media_url,
        likes=_count_text(entry.get("likes", entry.get("like_count"))),
        published=str(entry.get("published") or entry.get("_time_text") or "").strip(),
        reply_count=_count_text(entry.get("reply_count")),
        has_replies=bool(entry.get("has_replies")),
        pinned=bool(entry.get("pinned", entry.get("is_pinned"))),
    )


def _count_text(value):
    return "" if value is None else str(value).strip()


def _comments_page(entries, has_more, media_url):
    comments = [comment_from_entry(entry, media_url) for entry in entries]
    return YouTubeResultPage(results=tuple(comment for comment in comments if comment is not None), has_more=has_more)


def comments_page(media_url, start, count):
    """Os comentários de *media_url*, de *start* em diante."""
    media_url = str(media_url or "").strip()
    if youtubejs_resolver_enabled():
        try:
            entries, has_more = youtubejs_runtime.comments_page(media_url, start=start, count=count)
            return _comments_page(entries, has_more, media_url)
        except Exception as exc:
            _logger.warning("O YouTube.js não trouxe os comentários; usando o yt-dlp: %s", exc)
    if start:
        # O yt-dlp não continua de onde parou: o primeiro lote é tudo o que ele mostra.
        return YouTubeResultPage()
    return _yt_dlp_comments_page(media_url)


def comment_replies_page(comment, start, count):
    """As respostas a *comment*; só o YouTube.js as traz."""
    if not youtubejs_resolver_enabled():
        raise RuntimeError(_("As respostas dos comentários precisam do YouTube.js, ativado em Preferências > Recursos adicionais."))
    entries, has_more = youtubejs_runtime.comment_replies_page(
        comment.media_url, comment.comment_id, start=start, count=count
    )
    return _comments_page(entries, has_more, comment.media_url)


def _yt_dlp_comments_page(media_url):
    ensure_yt_dlp_executable_available()
    try:
        response = extract_yt_dlp_info(
            media_url,
            noplaylist=True,
            write_comments=True,
            ignore_no_formats_error=True,
            extractor_args={
                "youtube": {
                    "max_comments": [f"{YT_DLP_COMMENT_LIMIT},{YT_DLP_COMMENT_LIMIT},0,0"],
                    "comment_sort": ["top"],
                }
            },
            socket_timeout_seconds=YT_DLP_COMMENTS_SOCKET_TIMEOUT_SECONDS,
            quiet=True,
            no_warnings=True,
        )
    except Exception as exc:
        raise RuntimeError(
            _clean_external_tool_error(exc) or _("O yt-dlp não conseguiu trazer os comentários.")
        ) from exc

    entries = [
        entry
        for entry in (response.data or {}).get("comments") or []
        if isinstance(entry, dict) and str(entry.get("parent") or "root") == "root"
    ]
    return _comments_page(entries, False, media_url)


def comments_view_title(media_title):
    media_title = str(media_title or "").strip()
    if media_title:
        return _("Comentários de {title}").format(title=media_title)
    return _("Comentários")


def replies_view_title(comment):
    return _("Respostas a {author}").format(author=comment.author)


def comment_reading_text(comment):
    """O comentário inteiro, para a caixa de leitura."""
    lines = [comment.text, "", comment.author]
    if comment.detail_text:
        lines.append(comment.detail_text)
    return "\n".join(lines)
