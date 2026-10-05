from dataclasses import dataclass, field

from ..i18n import _
from .media import build_radio_media_path


RADIO_SCREEN_ID = "online-radio"
RADIO_RESULTS_PAGE_SIZE = 50
_LABEL_TAG_LIMIT = 3


def _text(value):
    return str(value or "").strip()


def _number(value):
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


@dataclass(frozen=True)
class RadioStation:
    """Uma estação do diretório (ou um stream colado pelo usuário, sem ``station_uuid``)."""

    name: str
    stream_url: str
    station_uuid: str = ""
    homepage: str = ""
    country: str = ""
    country_code: str = ""
    state: str = ""
    language: str = ""
    tags: tuple = ()
    codec: str = ""
    bitrate: int = 0
    votes: int = 0
    click_count: int = 0

    result_type = "station"
    can_browse = False
    opens_on_enter = False

    @classmethod
    def from_api(cls, payload):
        """Lê uma estação da resposta do Radio Browser; ``None`` quando não dá para tocá-la."""
        if not isinstance(payload, dict):
            return None
        # ``url_resolved`` já vem sem playlist nem redirecionamento no caminho.
        stream_url = _text(payload.get("url_resolved")) or _text(payload.get("url"))
        name = _text(payload.get("name"))
        if not name or not build_radio_media_path(stream_url):
            return None
        return cls(
            name=name,
            stream_url=stream_url,
            station_uuid=_text(payload.get("stationuuid")),
            homepage=_text(payload.get("homepage")),
            country=_text(payload.get("country")),
            country_code=_text(payload.get("countrycode")).upper(),
            state=_text(payload.get("state")),
            language=_text(payload.get("language")),
            tags=tuple(tag for tag in (_text(tag) for tag in _text(payload.get("tags")).split(",")) if tag),
            codec=_text(payload.get("codec")),
            bitrate=_number(payload.get("bitrate")),
            votes=_number(payload.get("votes")),
            click_count=_number(payload.get("clickcount")),
        )

    @classmethod
    def from_dict(cls, payload):
        """Lê uma estação guardada nos favoritos ou nas recentes."""
        if not isinstance(payload, dict):
            return None
        name = _text(payload.get("name"))
        stream_url = _text(payload.get("stream_url"))
        if not name or not build_radio_media_path(stream_url):
            return None
        raw_tags = payload.get("tags")
        return cls(
            name=name,
            stream_url=stream_url,
            station_uuid=_text(payload.get("station_uuid")),
            homepage=_text(payload.get("homepage")),
            country=_text(payload.get("country")),
            country_code=_text(payload.get("country_code")).upper(),
            state=_text(payload.get("state")),
            language=_text(payload.get("language")),
            tags=tuple(_text(tag) for tag in raw_tags if _text(tag)) if isinstance(raw_tags, (list, tuple)) else (),
            codec=_text(payload.get("codec")),
            bitrate=_number(payload.get("bitrate")),
            votes=_number(payload.get("votes")),
            click_count=_number(payload.get("click_count")),
        )

    def to_dict(self):
        return {
            "name": self.name,
            "stream_url": self.stream_url,
            "station_uuid": self.station_uuid,
            "homepage": self.homepage,
            "country": self.country,
            "country_code": self.country_code,
            "state": self.state,
            "language": self.language,
            "tags": list(self.tags),
            "codec": self.codec,
            "bitrate": self.bitrate,
            "votes": self.votes,
            "click_count": self.click_count,
        }

    @property
    def key(self):
        """Identidade da estação: o uuid do diretório ou, sem ele, o endereço do stream."""
        return self.station_uuid or self.stream_url.casefold()

    @property
    def stable_id(self):
        return f"station:{self.key}"

    @property
    def media_path(self):
        return build_radio_media_path(self.stream_url, self.station_uuid)

    @property
    def location_text(self):
        return ", ".join(part for part in (self.state, self.country) if part)

    @property
    def quality_text(self):
        if self.codec and self.bitrate:
            return _("{codec} {bitrate} kbps").format(codec=self.codec, bitrate=self.bitrate)
        if self.bitrate:
            return _("{bitrate} kbps").format(bitrate=self.bitrate)
        return self.codec

    @property
    def choice_label(self):
        parts = [
            self.name,
            self.location_text,
            ", ".join(self.tags[:_LABEL_TAG_LIMIT]),
            self.quality_text,
        ]
        return " — ".join(part for part in parts if part)


@dataclass(frozen=True)
class RadioFolderItem:
    """Um item que não toca: Enter ou Seta para a direita mostram o que há dentro."""

    kind: str
    title: str
    detail_text: str = ""
    # O que a pasta precisa para ser aberta: código do país, gênero, idioma...
    payload: object = None

    result_type = "folder"
    can_browse = True
    opens_on_enter = True

    @property
    def stable_id(self):
        return f"folder:{self.kind}:{self.title}"

    @property
    def choice_label(self):
        if self.detail_text:
            return f"{self.title} — {self.detail_text}"
        return self.title


@dataclass
class RadioResultPage:
    results: list = field(default_factory=list)
    has_more: bool = False
