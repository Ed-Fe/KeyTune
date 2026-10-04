from dataclasses import dataclass

from ..i18n import _


YOUTUBE_MUSIC_SCREEN_ID = "youtube_music"
YOUTUBE_SEARCH_SOURCE_MUSIC = "youtube_music"
YOUTUBE_SEARCH_SOURCE_YOUTUBE = "youtube"
YOUTUBE_SEARCH_SCOPE_MUSIC_SONGS = "music_songs"
YOUTUBE_SEARCH_SCOPE_MUSIC_VIDEOS = "music_videos"
YOUTUBE_SEARCH_SCOPE_MUSIC_PLAYLISTS = "music_playlists"
YOUTUBE_SEARCH_SCOPE_YOUTUBE_VIDEOS = "youtube_videos"
YOUTUBE_SEARCH_SCOPE_MUSIC_ALBUMS = "music_albums"
YOUTUBE_SEARCH_SCOPE_MUSIC_ARTISTS = "music_artists"
YOUTUBE_SEARCH_SCOPE_YOUTUBE_CHANNELS = "youtube_channels"
YOUTUBE_SEARCH_SCOPE_YOUTUBE_PLAYLISTS = "youtube_playlists"

# Tipos de resultado do YouTube comum (``YouTubeSearchScopeOption.youtube_kind``).
YOUTUBE_KIND_VIDEOS = "videos"
YOUTUBE_KIND_CHANNELS = "channels"
YOUTUBE_KIND_PLAYLISTS = "playlists"

# Quantos itens cada página das listas de resultados traz.
YOUTUBE_RESULTS_PAGE_SIZE = 20


@dataclass(frozen=True)
class YouTubeSearchScopeOption:
    scope_id: str
    label: str
    source: str
    requires_auth: bool = False
    music_filter: str = ""
    limit: int = YOUTUBE_RESULTS_PAGE_SIZE
    youtube_kind: str = ""
    # O nome só do tipo ("Músicas"), para a caixa que fica ao lado da de onde buscar.
    type_label: str = ""

    @property
    def kind(self):
        """O tipo de resultado, igual nas duas fontes quando ambas o têm (vídeos, playlists)."""
        return self.music_filter or self.youtube_kind


YOUTUBE_SEARCH_SCOPE_OPTIONS = (
    YouTubeSearchScopeOption(
        scope_id=YOUTUBE_SEARCH_SCOPE_MUSIC_SONGS,
        label=_("YouTube Music — músicas"),
        type_label=_("Músicas"),
        source=YOUTUBE_SEARCH_SOURCE_MUSIC,
        requires_auth=False,
        music_filter="songs",
    ),
    YouTubeSearchScopeOption(
        scope_id=YOUTUBE_SEARCH_SCOPE_MUSIC_VIDEOS,
        label=_("YouTube Music — vídeos"),
        type_label=_("Vídeos"),
        source=YOUTUBE_SEARCH_SOURCE_MUSIC,
        requires_auth=False,
        music_filter="videos",
    ),
    YouTubeSearchScopeOption(
        scope_id=YOUTUBE_SEARCH_SCOPE_MUSIC_ALBUMS,
        label=_("YouTube Music — álbuns"),
        type_label=_("Álbuns"),
        source=YOUTUBE_SEARCH_SOURCE_MUSIC,
        music_filter="albums",
    ),
    YouTubeSearchScopeOption(
        scope_id=YOUTUBE_SEARCH_SCOPE_MUSIC_ARTISTS,
        label=_("YouTube Music — artistas"),
        type_label=_("Artistas"),
        source=YOUTUBE_SEARCH_SOURCE_MUSIC,
        music_filter="artists",
    ),
    YouTubeSearchScopeOption(
        scope_id=YOUTUBE_SEARCH_SCOPE_MUSIC_PLAYLISTS,
        label=_("YouTube Music — playlists"),
        type_label=_("Playlists"),
        source=YOUTUBE_SEARCH_SOURCE_MUSIC,
        requires_auth=False,
        music_filter="playlists",
    ),
    YouTubeSearchScopeOption(
        scope_id=YOUTUBE_SEARCH_SCOPE_YOUTUBE_VIDEOS,
        label=_("YouTube — vídeos"),
        type_label=_("Vídeos"),
        source=YOUTUBE_SEARCH_SOURCE_YOUTUBE,
        requires_auth=False,
        youtube_kind=YOUTUBE_KIND_VIDEOS,
    ),
    YouTubeSearchScopeOption(
        scope_id=YOUTUBE_SEARCH_SCOPE_YOUTUBE_CHANNELS,
        label=_("YouTube — canais"),
        type_label=_("Canais"),
        source=YOUTUBE_SEARCH_SOURCE_YOUTUBE,
        youtube_kind=YOUTUBE_KIND_CHANNELS,
    ),
    YouTubeSearchScopeOption(
        scope_id=YOUTUBE_SEARCH_SCOPE_YOUTUBE_PLAYLISTS,
        label=_("YouTube — playlists"),
        type_label=_("Playlists"),
        source=YOUTUBE_SEARCH_SOURCE_YOUTUBE,
        youtube_kind=YOUTUBE_KIND_PLAYLISTS,
    ),
)

YOUTUBE_SEARCH_SCOPE_OPTIONS_BY_ID = {
    option.scope_id: option for option in YOUTUBE_SEARCH_SCOPE_OPTIONS
}


# As fontes da busca, na ordem da caixa "Em".
YOUTUBE_SEARCH_SOURCE_LABELS = (
    (YOUTUBE_SEARCH_SOURCE_MUSIC, "YouTube Music"),
    (YOUTUBE_SEARCH_SOURCE_YOUTUBE, "YouTube"),
)


def get_search_scope_options_for_source(source):
    """Os tipos de resultado que dá para buscar numa fonte."""
    return tuple(option for option in YOUTUBE_SEARCH_SCOPE_OPTIONS if option.source == source)


def get_search_scope_option(scope_id):
    normalized_scope_id = str(scope_id or "").strip()
    return YOUTUBE_SEARCH_SCOPE_OPTIONS_BY_ID.get(
        normalized_scope_id,
        YOUTUBE_SEARCH_SCOPE_OPTIONS_BY_ID[YOUTUBE_SEARCH_SCOPE_MUSIC_SONGS],
    )


@dataclass(frozen=True)
class YouTubeBrowseSection:
    """Um filtro do conteúdo de um canal ou artista (vídeos, playlists, álbuns...)."""

    section_id: str
    label: str


YOUTUBE_CHANNEL_SECTION_VIDEOS = "videos"
YOUTUBE_CHANNEL_SECTION_SHORTS = "shorts"
YOUTUBE_CHANNEL_SECTION_STREAMS = "streams"
YOUTUBE_CHANNEL_SECTION_PLAYLISTS = "playlists"

YOUTUBE_CHANNEL_SECTIONS = (
    YouTubeBrowseSection(YOUTUBE_CHANNEL_SECTION_VIDEOS, _("Vídeos")),
    YouTubeBrowseSection(YOUTUBE_CHANNEL_SECTION_SHORTS, _("Shorts")),
    YouTubeBrowseSection(YOUTUBE_CHANNEL_SECTION_STREAMS, _("Ao vivo")),
    YouTubeBrowseSection(YOUTUBE_CHANNEL_SECTION_PLAYLISTS, _("Playlists")),
)

YOUTUBE_ARTIST_SECTION_SONGS = "songs"
YOUTUBE_ARTIST_SECTION_ALBUMS = "albums"
YOUTUBE_ARTIST_SECTION_SINGLES = "singles"
YOUTUBE_ARTIST_SECTION_VIDEOS = "videos"
YOUTUBE_ARTIST_SECTION_RELATED = "related"

YOUTUBE_ARTIST_SECTIONS = (
    YouTubeBrowseSection(YOUTUBE_ARTIST_SECTION_SONGS, _("Músicas")),
    YouTubeBrowseSection(YOUTUBE_ARTIST_SECTION_ALBUMS, _("Álbuns")),
    YouTubeBrowseSection(YOUTUBE_ARTIST_SECTION_SINGLES, _("Singles e EPs")),
    YouTubeBrowseSection(YOUTUBE_ARTIST_SECTION_VIDEOS, _("Vídeos")),
    YouTubeBrowseSection(YOUTUBE_ARTIST_SECTION_RELATED, _("Artistas parecidos")),
)


@dataclass(frozen=True)
class YouTubeResultPage:
    """Uma página de resultados e se ainda há mais para carregar depois dela."""

    results: tuple = ()
    has_more: bool = False


# Charts / "em alta" by country.  Codes are ISO 3166-1 alpha-2 as accepted by
# ``YTMusic.get_charts`` (``ZZ`` = Global).  Labels are in Portuguese and the
# tuple order is the order shown in the country picker (Global and Brasil first,
# then alphabetical by label).
YOUTUBE_CHART_DEFAULT_COUNTRY_CODE = "ZZ"

YOUTUBE_CHART_COUNTRIES = (
    ("ZZ", _("Global")),
    ("BR", _("Brasil")),
    ("ZA", _("África do Sul")),
    ("DE", _("Alemanha")),
    ("SA", _("Arábia Saudita")),
    ("AR", _("Argentina")),
    ("AU", _("Austrália")),
    ("AT", _("Áustria")),
    ("BE", _("Bélgica")),
    ("BO", _("Bolívia")),
    ("CA", _("Canadá")),
    ("CL", _("Chile")),
    ("CO", _("Colômbia")),
    ("KR", _("Coreia do Sul")),
    ("CR", _("Costa Rica")),
    ("DK", _("Dinamarca")),
    ("EG", _("Egito")),
    ("SV", _("El Salvador")),
    ("AE", _("Emirados Árabes Unidos")),
    ("EC", _("Equador")),
    ("ES", _("Espanha")),
    ("US", _("Estados Unidos")),
    ("EE", _("Estônia")),
    ("FI", _("Finlândia")),
    ("FR", _("França")),
    ("GT", _("Guatemala")),
    ("NL", _("Holanda")),
    ("HN", _("Honduras")),
    ("HU", _("Hungria")),
    ("IN", _("Índia")),
    ("ID", _("Indonésia")),
    ("IE", _("Irlanda")),
    ("IS", _("Islândia")),
    ("IL", _("Israel")),
    ("IT", _("Itália")),
    ("JP", _("Japão")),
    ("LU", _("Luxemburgo")),
    ("MX", _("México")),
    ("NI", _("Nicarágua")),
    ("NG", _("Nigéria")),
    ("NO", _("Noruega")),
    ("NZ", _("Nova Zelândia")),
    ("PA", _("Panamá")),
    ("PY", _("Paraguai")),
    ("PE", _("Peru")),
    ("PL", _("Polônia")),
    ("PT", _("Portugal")),
    ("KE", _("Quênia")),
    ("GB", _("Reino Unido")),
    ("CZ", _("República Tcheca")),
    ("DO", _("República Dominicana")),
    ("RO", _("Romênia")),
    ("RU", _("Rússia")),
    ("SE", _("Suécia")),
    ("CH", _("Suíça")),
    ("TR", _("Turquia")),
    ("UA", _("Ucrânia")),
    ("UY", _("Uruguai")),
)

YOUTUBE_CHART_COUNTRY_LABELS_BY_CODE = {code: label for code, label in YOUTUBE_CHART_COUNTRIES}


def get_chart_country_label(country_code):
    normalized_code = str(country_code or "").strip().upper()
    return YOUTUBE_CHART_COUNTRY_LABELS_BY_CODE.get(normalized_code, normalized_code or _("Global"))


# Continent grouping for the "em alta" menu.  The country list itself stays the
# single source of truth for labels; this only maps each code to a continent so
# the menu can show submenus (mirroring the moods & genres menu).  ``Global``
# (``ZZ``) is intentionally not mapped here so it can be surfaced as a top-level
# shortcut by :func:`get_chart_country_groups`.
_CHART_CONTINENT_ORDER = (
    _("América do Sul"),
    _("América do Norte e Central"),
    _("Europa"),
    _("Ásia"),
    _("África"),
    _("Oceania"),
)

_CHART_CONTINENT_BY_CODE = {
    # América do Sul
    "BR": _("América do Sul"),
    "AR": _("América do Sul"),
    "BO": _("América do Sul"),
    "CL": _("América do Sul"),
    "CO": _("América do Sul"),
    "EC": _("América do Sul"),
    "PY": _("América do Sul"),
    "PE": _("América do Sul"),
    "UY": _("América do Sul"),
    # América do Norte e Central
    "CA": _("América do Norte e Central"),
    "US": _("América do Norte e Central"),
    "MX": _("América do Norte e Central"),
    "CR": _("América do Norte e Central"),
    "SV": _("América do Norte e Central"),
    "GT": _("América do Norte e Central"),
    "HN": _("América do Norte e Central"),
    "NI": _("América do Norte e Central"),
    "PA": _("América do Norte e Central"),
    "DO": _("América do Norte e Central"),
    # Europa
    "DE": _("Europa"),
    "AT": _("Europa"),
    "BE": _("Europa"),
    "DK": _("Europa"),
    "ES": _("Europa"),
    "EE": _("Europa"),
    "FI": _("Europa"),
    "FR": _("Europa"),
    "NL": _("Europa"),
    "HU": _("Europa"),
    "IE": _("Europa"),
    "IS": _("Europa"),
    "IT": _("Europa"),
    "LU": _("Europa"),
    "NO": _("Europa"),
    "PL": _("Europa"),
    "PT": _("Europa"),
    "GB": _("Europa"),
    "CZ": _("Europa"),
    "RO": _("Europa"),
    "RU": _("Europa"),
    "SE": _("Europa"),
    "CH": _("Europa"),
    "UA": _("Europa"),
    # Ásia
    "SA": _("Ásia"),
    "KR": _("Ásia"),
    "AE": _("Ásia"),
    "IN": _("Ásia"),
    "ID": _("Ásia"),
    "IL": _("Ásia"),
    "JP": _("Ásia"),
    "TR": _("Ásia"),
    # África
    "ZA": _("África"),
    "EG": _("África"),
    "NG": _("África"),
    "KE": _("África"),
    # Oceania
    "AU": _("Oceania"),
    "NZ": _("Oceania"),
}


def get_chart_country_groups():
    """Return the chart countries grouped for the "em alta" menu.

    The result is a list of ``(section_title, [(code, label), ...])`` pairs,
    mirroring the shape consumed by the moods & genres menu.  ``Global`` is
    returned first as a section with an empty title so callers can surface it as
    a top-level shortcut; the remaining sections are continents in
    :data:`_CHART_CONTINENT_ORDER`, each preserving the order of
    :data:`YOUTUBE_CHART_COUNTRIES`.
    """
    grouped = {continent: [] for continent in _CHART_CONTINENT_ORDER}
    global_entry = None
    for code, label in YOUTUBE_CHART_COUNTRIES:
        if code == YOUTUBE_CHART_DEFAULT_COUNTRY_CODE:
            global_entry = (code, label)
            continue
        continent = _CHART_CONTINENT_BY_CODE.get(code)
        if continent is None:
            continue
        grouped[continent].append((code, label))

    sections = []
    if global_entry is not None:
        sections.append(("", [global_entry]))
    for continent in _CHART_CONTINENT_ORDER:
        if grouped[continent]:
            sections.append((continent, grouped[continent]))
    return sections


@dataclass(frozen=True)
class YouTubeMusicPlaylistSummary:
    playlist_id: str
    title: str
    track_count_text: str = ""
    source_badge: str = ""

    @property
    def choice_label(self):
        details = []
        if self.source_badge:
            details.append(self.source_badge)
        if self.track_count_text:
            details.append(self.track_count_text)
        if details:
            return f"{self.title} — {' · '.join(details)}"
        return self.title

    def as_result(self):
        """A playlist da biblioteca como um item da lista da aba."""
        return YouTubeMediaSearchResult(
            source=YOUTUBE_SEARCH_SOURCE_MUSIC,
            result_type="playlist",
            title=self.title,
            detail_text=self.track_count_text,
            playlist_id=self.playlist_id,
            source_badge=self.source_badge,
            library_playlist=True,
        )


@dataclass(frozen=True)
class YouTubeMusicPlaylistContent:
    playlist_id: str
    title: str
    item_urls: list[str]
    item_labels: list[str]


@dataclass(frozen=True)
class YouTubeMediaSearchResult:
    source: str
    result_type: str
    title: str
    subtitle: str = ""
    detail_text: str = ""
    video_id: str = ""
    playlist_id: str = ""
    browse_id: str = ""
    playback_url: str = ""
    source_badge: str = ""
    feedback_add_token: str = ""
    feedback_remove_token: str = ""
    like_status: str = ""
    in_library: bool = False
    # Veio da biblioteca da conta: Enter abre numa aba própria e ela pode ser excluída.
    library_playlist: bool = False

    @property
    def result_kind_label(self):
        return {
            "song": _("faixa"),
            "video": _("vídeo"),
            "playlist": _("playlist"),
            "album": _("álbum"),
            "artist": _("artista"),
            "channel": _("canal"),
        }.get(str(self.result_type or "").strip().lower(), _("resultado"))

    @property
    def display_source_label(self):
        if self.source_badge:
            return self.source_badge
        if self.source == YOUTUBE_SEARCH_SOURCE_YOUTUBE:
            return "YouTube"
        return "YouTube Music"

    @property
    def stable_id(self):
        for candidate in (self.playlist_id, self.video_id, self.browse_id, self.title):
            normalized_candidate = str(candidate or "").strip()
            if normalized_candidate:
                return f"{self.source}:{self.result_type}:{normalized_candidate}"
        return f"{self.source}:{self.result_type}:sem-id"

    @property
    def choice_label(self):
        details = [self.display_source_label, self.result_kind_label]
        if self.subtitle:
            details.append(self.subtitle)
        if self.detail_text:
            details.append(self.detail_text)
        return f"{self.title} — {' · '.join(details)}" if details else self.title

    @property
    def can_open(self):
        return bool(self.playlist_id or self.playback_url)

    @property
    def can_browse(self):
        """Se dá para abrir o resultado e ver o que há dentro dele."""
        if self.result_type in ("artist", "channel"):
            return bool(self.browse_id)
        if self.result_type in ("playlist", "album"):
            return bool(self.playlist_id or self.browse_id)
        return False

    @property
    def opens_on_enter(self):
        """Canais e artistas não tocam: Enter entra neles."""
        return self.result_type in ("artist", "channel") and self.can_browse

    @property
    def can_add_to_playlist(self):
        return bool(self.video_id)

    @property
    def can_save(self):
        if self.source != YOUTUBE_SEARCH_SOURCE_MUSIC or self.library_playlist:
            return False
        if self.result_type == "playlist":
            return bool(self.playlist_id)
        if self.result_type == "song":
            return bool(self.feedback_add_token or self.feedback_remove_token)
        return False

    @property
    def save_action_label(self):
        if self.result_type == "playlist":
            return _("Salvar playlist na biblioteca")
        if self.result_type == "song":
            return _("Salvar faixa na biblioteca")
        return ""
