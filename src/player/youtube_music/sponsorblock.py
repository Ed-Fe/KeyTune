"""Cliente do SponsorBlock: os trechos marcados pela comunidade num vídeo do YouTube.

A consulta usa o prefixo do SHA-256 do id do vídeo, então o servidor não fica
sabendo qual vídeo está tocando. Enviar trechos e votar exige um id de usuário
privado, gerado aqui e guardado nas preferências. Os dados são da comunidade
SponsorBlock (sponsor.ajay.app), sob a licença CC BY-NC-SA 4.0.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from ..constants import (
    APP_TITLE,
    APP_VERSION,
    DEFAULT_SPONSORBLOCK_CATEGORIES as DEFAULT_CATEGORIES,
    SPONSORBLOCK_CATEGORIES as CATEGORIES,
    SPONSORBLOCK_MODE_NOTIFY as MODE_NOTIFY,
    SPONSORBLOCK_MODE_SKIP as MODE_SKIP,
    SPONSORBLOCK_MODES as MODES,
)
from ..i18n import _
from ..log import get_logger


_logger = get_logger(__name__)

SPONSORBLOCK_API_URL = "https://sponsor.ajay.app/api"
_REQUEST_TIMEOUT_SECONDS = 8
_HASH_PREFIX_LENGTH = 4

# O único tipo de ação que o player cumpre: pular. Silenciar e capítulos ficam de fora.
_SUPPORTED_ACTION_TYPES = ("skip",)


def category_labels():
    return {
        "sponsor": _("Patrocínio"),
        "selfpromo": _("Autopromoção"),
        "interaction": _("Pedido de interação (curtir, inscrever-se)"),
        "intro": _("Abertura"),
        "outro": _("Encerramento"),
        "preview": _("Prévia ou resumo"),
        "filler": _("Enrolação fora do assunto"),
        "music_offtopic": _("Trecho sem música em clipe"),
    }


def category_label(category):
    return category_labels().get(category, category)


@dataclass(frozen=True)
class SponsorSegment:
    uuid: str
    category: str
    action_type: str
    start_seconds: float
    end_seconds: float


class SponsorBlockError(RuntimeError):
    """Uma falha que vale contar ao usuário (envio ou voto recusado)."""


def normalize_categories(value):
    """As categorias conhecidas de *value*, sem repetir, na ordem de ``CATEGORIES``."""
    wanted = {str(item or "").strip() for item in (value or ())}
    return [category for category in CATEGORIES if category in wanted]


def generate_user_id():
    """Um id privado novo; o SponsorBlock pede ao menos 30 caracteres."""
    return secrets.token_hex(32)


def _user_agent():
    return f"{APP_TITLE}/{APP_VERSION}"


def _request(path, *, params=None, body=None, method="GET"):
    url = f"{SPONSORBLOCK_API_URL}/{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    data = None
    headers = {"Accept": "application/json", "User-Agent": _user_agent()}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=_REQUEST_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_segments(payload, video_id, categories=None):
    """Os trechos de *video_id* na resposta da busca por prefixo, em ordem de início."""
    allowed = set(categories) if categories is not None else set(CATEGORIES)
    segments = []
    for video in payload if isinstance(payload, list) else ():
        if not isinstance(video, dict) or video.get("videoID") != video_id:
            continue
        for entry in video.get("segments") or ():
            if not isinstance(entry, dict):
                continue
            category = str(entry.get("category") or "")
            action_type = str(entry.get("actionType") or "skip")
            if category not in allowed or action_type not in _SUPPORTED_ACTION_TYPES:
                continue
            try:
                start, end = (float(value) for value in entry.get("segment") or ())
            except (TypeError, ValueError):
                continue
            if end <= start:
                continue
            segments.append(SponsorSegment(str(entry.get("UUID") or ""), category, action_type, start, end))
    return sorted(segments, key=lambda segment: segment.start_seconds)


def fetch_segments(video_id, categories):
    """Os trechos de *video_id* nas *categories*; lista vazia quando não há ou a rede falha."""
    video_id = str(video_id or "").strip()
    categories = normalize_categories(categories)
    if not video_id or not categories:
        return []
    prefix = hashlib.sha256(video_id.encode("utf-8")).hexdigest()[:_HASH_PREFIX_LENGTH]
    params = {
        "categories": json.dumps(categories),
        "actionTypes": json.dumps(list(_SUPPORTED_ACTION_TYPES)),
    }
    try:
        payload = json.loads(_request(f"skipSegments/{prefix}", params=params))
    except urllib.error.HTTPError as exc:
        # 404 é a resposta normal para "nenhum vídeo com esse prefixo tem trechos".
        if exc.code != 404:
            _logger.debug("SponsorBlock respondeu %s para %s", exc.code, video_id)
        return []
    except (urllib.error.URLError, OSError, ValueError) as exc:
        _logger.debug("SponsorBlock indisponível: %s", exc)
        return []
    return parse_segments(payload, video_id, categories)


def _raise_for_contribution(exc, action):
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code == 429:
            raise SponsorBlockError(_("O SponsorBlock recebeu muitos pedidos; tente mais tarde.")) from exc
        if exc.code == 409:
            raise SponsorBlockError(_("Esse trecho já foi enviado.")) from exc
        if exc.code == 403:
            raise SponsorBlockError(_("O SponsorBlock recusou o {action}.").format(action=action)) from exc
    raise SponsorBlockError(_("Não foi possível falar com o SponsorBlock agora.")) from exc


def submit_segment(video_id, user_id, start_seconds, end_seconds, category, video_duration=0.0):
    """Envia um trecho novo; levanta ``SponsorBlockError`` quando não dá."""
    if category not in CATEGORIES:
        raise ValueError(category)
    body = {
        "videoID": str(video_id),
        "userID": str(user_id),
        "userAgent": _user_agent(),
        "segments": [
            {
                "segment": [round(float(start_seconds), 3), round(float(end_seconds), 3)],
                "category": category,
                "actionType": "skip",
            }
        ],
    }
    if video_duration and video_duration > 0:
        body["videoDuration"] = round(float(video_duration), 3)
    try:
        _request("skipSegments", body=body, method="POST")
    except (urllib.error.URLError, OSError) as exc:
        _raise_for_contribution(exc, _("envio"))


def vote_segment(segment_uuid, user_id, upvote):
    """Vota a favor (*upvote*) ou contra um trecho."""
    params = {"UUID": str(segment_uuid), "userID": str(user_id), "type": 1 if upvote else 0}
    try:
        _request("voteOnSponsorTime", params=params, method="POST")
    except (urllib.error.URLError, OSError) as exc:
        _raise_for_contribution(exc, _("voto"))


def report_skip(segment_uuid):
    """Conta um pulo para o trecho; é o que mostra aos autores que o trecho ajudou."""
    try:
        _request("viewedVideoSponsorTime", params={"UUID": str(segment_uuid)}, method="POST")
    except (urllib.error.URLError, OSError) as exc:
        _logger.debug("SponsorBlock não contou o pulo: %s", exc)
