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
        return bool(self.playlist_id or self.video_id or self.feedback_add_token)

    @property
    def save_action_label(self):
        if self.result_type == "playlist":
            return "Salvar playlist na biblioteca"
        if self.result_type == "song" and self.feedback_add_token:
            return "Salvar faixa na biblioteca"
        return "Curtir no YouTube Music"
