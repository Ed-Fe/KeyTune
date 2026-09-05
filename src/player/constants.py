from .i18n import _

APP_TITLE = "KeyTune"
APP_VERSION = "2.0.1"
APP_LICENSE = "MIT"
DEFAULT_WINDOW_SIZE = (980, 620)
DEFAULT_VOLUME = 80
DEFAULT_CROSSFADE_SECONDS = 0
DEFAULT_CROSSFADE_ON_MANUAL_TRACK_CHANGE = False
DEFAULT_AUTODJ_ENABLED = False
DEFAULT_AUTODJ_OPTIONAL_RESOURCES_CONFIRMED = False
DEFAULT_AUTODJ_TRANSITION_SOUNDS_ENABLED = False
DEFAULT_AUTODJ_PROFILE = "smooth"
DEFAULT_AUTODJ_BEATS = 16
AUTODJ_PROFILES = ("smooth", "party", "electronic")
AUTODJ_BEAT_COUNTS = (8, 16, 32)
SEEK_STEP_MS = 5000
LARGE_SEEK_STEP_MS = 60000
VOLUME_STEP = 5
PROGRESS_GAUGE_RANGE = 1000
PROGRESS_TIMER_INTERVAL_MS = 500
CROSSFADE_TIMER_INTERVAL_MS = 15
MAX_CROSSFADE_SECONDS = 12
SHORT_FADE_MS = 180
SHORT_FADE_STEPS = 8
PLAYBACK_RESTART_THRESHOLD_MS = 3000
EXPLORER_PREVIEW_DELAY_MS = 120
STARTUP_UPDATE_CHECK_DELAY_MS = 2000
UPDATE_HTTP_TIMEOUT_SECONDS = 20
UPDATE_DOWNLOAD_CHUNK_SIZE = 256 * 1024
DEFAULT_RESTORE_SESSION_ON_STARTUP = True
DEFAULT_REMEMBER_WINDOW_SIZE = True
DEFAULT_REMEMBER_LAST_FOLDER = True
DEFAULT_CONFIRM_ON_EXIT = False
DEFAULT_ANNOUNCEMENTS_ENABLED = True
DEFAULT_DISABLE_VIDEO_OUTPUT = True
DEFAULT_NEW_PLAYLIST_SHUFFLE = False
DEFAULT_YOUTUBE_MUSIC_MANAGE_DEPENDENCIES = False
DEFAULT_YOUTUBE_MUSIC_AUTO_UPDATE_DEPENDENCIES = True
DEFAULT_YOUTUBE_MUSIC_USE_NIGHTLY_YT_DLP = True
DEFAULT_YOUTUBE_MUSIC_USE_YOUTUBEJS = True
DEFAULT_YOUTUBE_MUSIC_DEPENDENCY_UPDATE_INTERVAL_HOURS = 24
DEFAULT_YOUTUBE_MUSIC_LIBRARY_PAGE_SIZE = 25
DEFAULT_YOUTUBE_MUSIC_HOME_DISCOVERY_LIMIT = 30
DEFAULT_YOUTUBE_MUSIC_AUTOPLAY_RELATED = False
DEFAULT_YOUTUBE_MUSIC_SAVE_HISTORY = True
YOUTUBE_MUSIC_RADIO_FETCH_LIMIT = 50
YOUTUBE_MUSIC_RADIO_RECENT_LIMIT = 200
YOUTUBE_MUSIC_RADIO_NEW_STATION_ATTEMPTS = 3
# How long before the end of the last track we start fetching related content
# (radio) proactively, so the new items and their stream are ready in time for a
# seamless transition instead of pausing on the last frame while we look them up.
YOUTUBE_MUSIC_RADIO_PREFETCH_LEAD_MS = 30000
# A radio seeded on the last track overlaps heavily with the radio that produced
# it, so a fetch can come back with nothing but tracks the playlist already has.
# When that happens we re-seed from an earlier track, up to this many seeds.
YOUTUBE_MUSIC_RADIO_MAX_SEED_ATTEMPTS = 3
MIN_YOUTUBE_MUSIC_LIBRARY_PAGE_SIZE = 5
MAX_YOUTUBE_MUSIC_LIBRARY_PAGE_SIZE = 200
MIN_YOUTUBE_MUSIC_HOME_DISCOVERY_LIMIT = 5
MAX_YOUTUBE_MUSIC_HOME_DISCOVERY_LIMIT = 200
RECENT_ITEMS_LIMIT = 10

# --- Biblioteca inteligente (busca global, favoritos, histórico, retomada) ---
DEFAULT_SMART_LIBRARY_ENABLED = True
DEFAULT_SMART_LIBRARY_INDEX_OPENED_FOLDERS = True
DEFAULT_SMART_LIBRARY_HISTORY_ENABLED = True
DEFAULT_SMART_LIBRARY_HISTORY_LIMIT = 500
MIN_SMART_LIBRARY_HISTORY_LIMIT = 50
MAX_SMART_LIBRARY_HISTORY_LIMIT = 20000
DEFAULT_SMART_LIBRARY_RESUME_ENABLED = True
# Só mídias longas ganham ponto de retomada: podcasts, audiolivros e vídeos.
DEFAULT_SMART_LIBRARY_RESUME_MINIMUM_MINUTES = 10
MIN_SMART_LIBRARY_RESUME_MINIMUM_MINUTES = 1
MAX_SMART_LIBRARY_RESUME_MINIMUM_MINUTES = 240
# Margem ignorada nas duas pontas: quem parou logo no começo quer recomeçar, e
# quem chegou perto do fim já terminou.
DEFAULT_SMART_LIBRARY_RESUME_EDGE_SECONDS = 30
MIN_SMART_LIBRARY_RESUME_EDGE_SECONDS = 5
MAX_SMART_LIBRARY_RESUME_EDGE_SECONDS = 300
DEFAULT_SMART_LIBRARY_CACHE_LIMIT = 5000
MIN_SMART_LIBRARY_CACHE_LIMIT = 100
MAX_SMART_LIBRARY_CACHE_LIMIT = 100000
# Quanto tempo de reprodução conta como "ouvida" para entrar no histórico.
SMART_LIBRARY_HISTORY_MINIMUM_MS = 20000
SMART_LIBRARY_HISTORY_PROGRESS_FRACTION = 0.25
# Intervalo entre gravações da posição de retomada, em milissegundos.
SMART_LIBRARY_RESUME_SAVE_INTERVAL_MS = 5000
SMART_LIBRARY_MAX_RATING = 5

GITHUB_REPOSITORY_OWNER = "ed-fe"
GITHUB_REPOSITORY_NAME = "KeyTune"
# Installer-driven updates: the app downloads and silently runs the setup .exe.
WINDOWS_SETUP_EXECUTABLE_NAME = "KeyTune-Setup.exe"
WINDOWS_SETUP_CHECKSUM_NAME = f"{WINDOWS_SETUP_EXECUTABLE_NAME}.sha256"

DEFAULT_LOGGING_ENABLED = True
DEFAULT_LOGGING_LEVEL = "WARNING"
LOGGING_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
LOGGING_LEVEL_LABELS = {
    "DEBUG": _("Depuração (DEBUG)"),
    "INFO": _("Informativo (INFO)"),
    "WARNING": _("Avisos (WARNING)"),
    "ERROR": _("Apenas erros (ERROR)"),
}

# Sleep timer (temporizador de desligamento): a contagem regressiva pausa a
# reprodução ao chegar a zero; o modo "fim da faixa" espera a faixa atual
# terminar em vez de contar tempo.
SLEEP_TIMER_MODE_OFF = "off"
SLEEP_TIMER_MODE_COUNTDOWN = "countdown"
SLEEP_TIMER_MODE_END_OF_TRACK = "end_of_track"
SLEEP_TIMER_PRESET_MINUTES = (5, 10, 15, 30, 45, 60, 90, 120)
SLEEP_TIMER_MIN_MINUTES = 1
SLEEP_TIMER_MAX_MINUTES = 720
SLEEP_TIMER_DEFAULT_MINUTES = 30
SLEEP_TIMER_TICK_INTERVAL_MS = 1000
# Avisos falados enquanto a contagem regressiva corre, em minutos restantes.
SLEEP_TIMER_WARNING_MINUTES = (5, 1)

REPEAT_OFF = "off"
REPEAT_ONE = "one"
REPEAT_ALL = "all"
REPEAT_MODES = (REPEAT_OFF, REPEAT_ONE, REPEAT_ALL)
REPEAT_MODE_LABELS = {
    REPEAT_OFF: _("Repetição desligada"),
    REPEAT_ONE: _("Repetir faixa atual"),
    REPEAT_ALL: _("Repetir playlist"),
}

PLAYLIST_WILDCARD = (
    f"{_('Playlists')}|*.m3u;*.m3u8|"
    f"{_('Playlist M3U8')}|*.m3u8|"
    f"{_('Playlist M3U')}|*.m3u|"
    f"{_('Todos os arquivos')}|*.*"
)

# Standard container/codec extensions playable by the bundled MPV (FFmpeg)
# runtime, mirroring what mainstream players (VLC, MPC-HC) offer for
# association. Keep these in sync with installer/keytune.iss.
VIDEO_EXTENSIONS = {
    ".mp4",
    ".m4v",
    ".mkv",
    ".avi",
    ".mov",
    ".webm",
    ".flv",
    ".wmv",
    ".mpg",
    ".mpeg",
    ".3gp",
    ".ts",
    ".m2ts",
    ".mts",
    ".ogv",
}

AUDIO_ONLY_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".flac",
    ".aac",
    ".ogg",
    ".oga",
    ".m4a",
    ".opus",
    ".wma",
    ".aiff",
    ".aif",
    ".ac3",
    ".mka",
    ".wv",
    ".ape",
}

SUPPORTED_MEDIA_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_ONLY_EXTENSIONS
