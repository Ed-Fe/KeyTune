from dataclasses import dataclass


YOUTUBE_MUSIC_SCREEN_ID = "youtube_music"
YOUTUBE_SEARCH_SOURCE_MUSIC = "youtube_music"
YOUTUBE_SEARCH_SOURCE_YOUTUBE = "youtube"
YOUTUBE_SEARCH_SCOPE_MUSIC_SONGS = "music_songs"
YOUTUBE_SEARCH_SCOPE_MUSIC_VIDEOS = "music_videos"
YOUTUBE_SEARCH_SCOPE_MUSIC_PLAYLISTS = "music_playlists"
YOUTUBE_SEARCH_SCOPE_YOUTUBE_VIDEOS = "youtube_videos"


@dataclass(frozen=True)
class YouTubeSearchScopeOption:
    scope_id: str
    label: str
    source: str
    requires_auth: bool = False
    music_filter: str = ""
    limit: int = 15


YOUTUBE_SEARCH_SCOPE_OPTIONS = (
    YouTubeSearchScopeOption(
        scope_id=YOUTUBE_SEARCH_SCOPE_MUSIC_SONGS,
        label="YouTube Music — músicas",
        source=YOUTUBE_SEARCH_SOURCE_MUSIC,
        requires_auth=False,
        music_filter="songs",
    ),
    YouTubeSearchScopeOption(
        scope_id=YOUTUBE_SEARCH_SCOPE_MUSIC_VIDEOS,
        label="YouTube Music — vídeos",
        source=YOUTUBE_SEARCH_SOURCE_MUSIC,
        requires_auth=False,
        music_filter="videos",
    ),
    YouTubeSearchScopeOption(
        scope_id=YOUTUBE_SEARCH_SCOPE_MUSIC_PLAYLISTS,
        label="YouTube Music — playlists",
        source=YOUTUBE_SEARCH_SOURCE_MUSIC,
        requires_auth=False,
        music_filter="playlists",
    ),
    YouTubeSearchScopeOption(
        scope_id=YOUTUBE_SEARCH_SCOPE_YOUTUBE_VIDEOS,
        label="YouTube — vídeos",
        source=YOUTUBE_SEARCH_SOURCE_YOUTUBE,
        requires_auth=False,
    ),
)

YOUTUBE_SEARCH_SCOPE_OPTIONS_BY_ID = {
    option.scope_id: option for option in YOUTUBE_SEARCH_SCOPE_OPTIONS
}


def get_search_scope_option(scope_id):
    normalized_scope_id = str(scope_id or "").strip()
    return YOUTUBE_SEARCH_SCOPE_OPTIONS_BY_ID.get(
        normalized_scope_id,
        YOUTUBE_SEARCH_SCOPE_OPTIONS_BY_ID[YOUTUBE_SEARCH_SCOPE_MUSIC_SONGS],
    )


# Charts / "em alta" by country.  Codes are ISO 3166-1 alpha-2 as accepted by
# ``YTMusic.get_charts`` (``ZZ`` = Global).  Labels are in Portuguese and the
# tuple order is the order shown in the country picker (Global and Brasil first,
# then alphabetical by label).
YOUTUBE_CHART_DEFAULT_COUNTRY_CODE = "ZZ"

YOUTUBE_CHART_COUNTRIES = (
    ("ZZ", "Global"),
    ("BR", "Brasil"),
    ("ZA", "África do Sul"),
    ("DE", "Alemanha"),
    ("SA", "Arábia Saudita"),
    ("AR", "Argentina"),
    ("AU", "Austrália"),
    ("AT", "Áustria"),
    ("BE", "Bélgica"),
    ("BO", "Bolívia"),
    ("CA", "Canadá"),
    ("CL", "Chile"),
    ("CO", "Colômbia"),
    ("KR", "Coreia do Sul"),
    ("CR", "Costa Rica"),
    ("DK", "Dinamarca"),
    ("EG", "Egito"),
    ("SV", "El Salvador"),
    ("AE", "Emirados Árabes Unidos"),
    ("EC", "Equador"),
    ("ES", "Espanha"),
    ("US", "Estados Unidos"),
    ("EE", "Estônia"),
    ("FI", "Finlândia"),
    ("FR", "França"),
    ("GT", "Guatemala"),
    ("NL", "Holanda"),
    ("HN", "Honduras"),
    ("HU", "Hungria"),
    ("IN", "Índia"),
    ("ID", "Indonésia"),
    ("IE", "Irlanda"),
    ("IS", "Islândia"),
    ("IL", "Israel"),
    ("IT", "Itália"),
    ("JP", "Japão"),
    ("LU", "Luxemburgo"),
    ("MX", "México"),
    ("NI", "Nicarágua"),
    ("NG", "Nigéria"),
    ("NO", "Noruega"),
    ("NZ", "Nova Zelândia"),
    ("PA", "Panamá"),
    ("PY", "Paraguai"),
    ("PE", "Peru"),
    ("PL", "Polônia"),
    ("PT", "Portugal"),
    ("KE", "Quênia"),
    ("GB", "Reino Unido"),
    ("CZ", "República Tcheca"),
    ("DO", "República Dominicana"),
    ("RO", "Romênia"),
    ("RU", "Rússia"),
    ("SE", "Suécia"),
    ("CH", "Suíça"),
    ("TR", "Turquia"),
    ("UA", "Ucrânia"),
    ("UY", "Uruguai"),
)

YOUTUBE_CHART_COUNTRY_LABELS_BY_CODE = {code: label for code, label in YOUTUBE_CHART_COUNTRIES}


def get_chart_country_label(country_code):
    normalized_code = str(country_code or "").strip().upper()
    return YOUTUBE_CHART_COUNTRY_LABELS_BY_CODE.get(normalized_code, normalized_code or "Global")


# Continent grouping for the "em alta" menu.  The country list itself stays the
# single source of truth for labels; this only maps each code to a continent so
# the menu can show submenus (mirroring the moods & genres menu).  ``Global``
# (``ZZ``) is intentionally not mapped here so it can be surfaced as a top-level
# shortcut by :func:`get_chart_country_groups`.
_CHART_CONTINENT_ORDER = (
    "América do Sul",
    "América do Norte e Central",
    "Europa",
    "Ásia",
    "África",
    "Oceania",
)

_CHART_CONTINENT_BY_CODE = {
    # América do Sul
    "BR": "América do Sul",
    "AR": "América do Sul",
    "BO": "América do Sul",
    "CL": "América do Sul",
    "CO": "América do Sul",
    "EC": "América do Sul",
    "PY": "América do Sul",
    "PE": "América do Sul",
    "UY": "América do Sul",
    # América do Norte e Central
    "CA": "América do Norte e Central",
    "US": "América do Norte e Central",
    "MX": "América do Norte e Central",
    "CR": "América do Norte e Central",
    "SV": "América do Norte e Central",
    "GT": "América do Norte e Central",
    "HN": "América do Norte e Central",
    "NI": "América do Norte e Central",
    "PA": "América do Norte e Central",
    "DO": "América do Norte e Central",
    # Europa
    "DE": "Europa",
    "AT": "Europa",
    "BE": "Europa",
    "DK": "Europa",
    "ES": "Europa",
    "EE": "Europa",
    "FI": "Europa",
    "FR": "Europa",
    "NL": "Europa",
    "HU": "Europa",
    "IE": "Europa",
    "IS": "Europa",
    "IT": "Europa",
    "LU": "Europa",
    "NO": "Europa",
    "PL": "Europa",
    "PT": "Europa",
    "GB": "Europa",
    "CZ": "Europa",
    "RO": "Europa",
    "RU": "Europa",
    "SE": "Europa",
    "CH": "Europa",
    "UA": "Europa",
    # Ásia
    "SA": "Ásia",
    "KR": "Ásia",
    "AE": "Ásia",
    "IN": "Ásia",
    "ID": "Ásia",
    "IL": "Ásia",
    "JP": "Ásia",
    "TR": "Ásia",
    # África
    "ZA": "África",
    "EG": "África",
    "NG": "África",
    "KE": "África",
    # Oceania
    "AU": "Oceania",
    "NZ": "Oceania",
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

    @property
    def result_kind_label(self):
        return {
            "song": "faixa",
            "video": "vídeo",
            "playlist": "playlist",
        }.get(str(self.result_type or "").strip().lower(), "resultado")

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
    def can_add_to_playlist(self):
        return bool(self.video_id)

    @property
    def can_save(self):
        if self.source != YOUTUBE_SEARCH_SOURCE_MUSIC:
            return False
        if self.result_type == "playlist":
            return bool(self.playlist_id)
        if self.result_type == "song":
            return bool(self.feedback_add_token or self.feedback_remove_token)
        return False

    @property
    def save_action_label(self):
        if self.result_type == "playlist":
            return "Salvar playlist na biblioteca"
        if self.result_type == "song":
            return "Salvar faixa na biblioteca"
        return ""
