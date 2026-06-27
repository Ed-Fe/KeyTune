from dataclasses import dataclass, field

from ..audio_output import is_selectable_audio_output_device_id, normalize_audio_output_device_id
from ..constants import (
    DEFAULT_ANNOUNCEMENTS_ENABLED,
    DEFAULT_CONFIRM_ON_EXIT,
    DEFAULT_CROSSFADE_ON_MANUAL_TRACK_CHANGE,
    DEFAULT_CROSSFADE_SECONDS,
    DEFAULT_DISABLE_VIDEO_OUTPUT,
    DEFAULT_LOGGING_ENABLED,
    DEFAULT_LOGGING_LEVEL,
    DEFAULT_NEW_PLAYLIST_SHUFFLE,
    DEFAULT_REMEMBER_LAST_FOLDER,
    DEFAULT_REMEMBER_WINDOW_SIZE,
    DEFAULT_RESTORE_SESSION_ON_STARTUP,
    DEFAULT_VOLUME,
    DEFAULT_YOUTUBE_MUSIC_AUTO_UPDATE_DEPENDENCIES,
    DEFAULT_YOUTUBE_MUSIC_AUTOPLAY_RELATED,
    DEFAULT_YOUTUBE_MUSIC_DEPENDENCY_UPDATE_INTERVAL_HOURS,
    DEFAULT_YOUTUBE_MUSIC_HOME_DISCOVERY_LIMIT,
    DEFAULT_YOUTUBE_MUSIC_LIBRARY_PAGE_SIZE,
    DEFAULT_YOUTUBE_MUSIC_MANAGE_DEPENDENCIES,
    DEFAULT_YOUTUBE_MUSIC_USE_NIGHTLY_YT_DLP,
    LOGGING_LEVELS,
    MAX_CROSSFADE_SECONDS,
    MAX_YOUTUBE_MUSIC_HOME_DISCOVERY_LIMIT,
    MAX_YOUTUBE_MUSIC_LIBRARY_PAGE_SIZE,
    MIN_YOUTUBE_MUSIC_HOME_DISCOVERY_LIMIT,
    MIN_YOUTUBE_MUSIC_LIBRARY_PAGE_SIZE,
    REPEAT_MODES,
    REPEAT_OFF,
    SEEK_STEP_MS,
    VOLUME_STEP,
)
from ..equalizer.models import EqualizerPreset


@dataclass
class AppSettings:
    restore_session_on_startup: bool = DEFAULT_RESTORE_SESSION_ON_STARTUP
    remember_window_size: bool = DEFAULT_REMEMBER_WINDOW_SIZE
    remember_last_folder: bool = DEFAULT_REMEMBER_LAST_FOLDER
    confirm_on_exit: bool = DEFAULT_CONFIRM_ON_EXIT
    announcements_enabled: bool = DEFAULT_ANNOUNCEMENTS_ENABLED
    disable_video_output: bool = DEFAULT_DISABLE_VIDEO_OUTPUT
    audio_output_device_id: str = ""
    default_volume: int = DEFAULT_VOLUME
    crossfade_seconds: int = DEFAULT_CROSSFADE_SECONDS
    crossfade_on_manual_track_change: bool = DEFAULT_CROSSFADE_ON_MANUAL_TRACK_CHANGE
    volume_step: int = VOLUME_STEP
    seek_step_seconds: int = SEEK_STEP_MS // 1000
    shuffle_new_playlists: bool = DEFAULT_NEW_PLAYLIST_SHUFFLE
    repeat_mode_new_playlists: str = REPEAT_OFF
    youtube_music_manage_dependencies: bool = DEFAULT_YOUTUBE_MUSIC_MANAGE_DEPENDENCIES
    youtube_music_auto_update_dependencies: bool = DEFAULT_YOUTUBE_MUSIC_AUTO_UPDATE_DEPENDENCIES
    youtube_music_use_nightly_yt_dlp: bool = DEFAULT_YOUTUBE_MUSIC_USE_NIGHTLY_YT_DLP
    youtube_music_autoplay_related: bool = DEFAULT_YOUTUBE_MUSIC_AUTOPLAY_RELATED
    youtube_music_dependency_update_interval_hours: int = DEFAULT_YOUTUBE_MUSIC_DEPENDENCY_UPDATE_INTERVAL_HOURS
    youtube_music_dependency_last_auto_update_epoch: int = 0
    youtube_music_library_page_size: int = DEFAULT_YOUTUBE_MUSIC_LIBRARY_PAGE_SIZE
    youtube_music_home_discovery_limit: int = DEFAULT_YOUTUBE_MUSIC_HOME_DISCOVERY_LIMIT
    last_open_dir: str = ""
    recent_media_files: list[str] = field(default_factory=list)
    recent_folders: list[str] = field(default_factory=list)
    recent_playlists: list[str] = field(default_factory=list)
    equalizer_custom_presets: list[EqualizerPreset] = field(default_factory=list)
    logging_enabled: bool = DEFAULT_LOGGING_ENABLED
    logging_level: str = DEFAULT_LOGGING_LEVEL
    welcome_screen_completed: bool = False

    @property
    def seek_step_ms(self):
        return self.seek_step_seconds * 1000

    def to_dict(self):
        return {
            "restore_session_on_startup": self.restore_session_on_startup,
            "remember_window_size": self.remember_window_size,
            "remember_last_folder": self.remember_last_folder,
            "confirm_on_exit": self.confirm_on_exit,
            "announcements_enabled": self.announcements_enabled,
            "disable_video_output": self.disable_video_output,
            "audio_output_device_id": (
                self.audio_output_device_id if is_selectable_audio_output_device_id(self.audio_output_device_id) else ""
            ),
            "default_volume": self.default_volume,
            "crossfade_seconds": self.crossfade_seconds,
            "crossfade_on_manual_track_change": self.crossfade_on_manual_track_change,
            "volume_step": self.volume_step,
            "seek_step_seconds": self.seek_step_seconds,
            "shuffle_new_playlists": self.shuffle_new_playlists,
            "repeat_mode_new_playlists": self.repeat_mode_new_playlists,
            "youtube_music_manage_dependencies": self.youtube_music_manage_dependencies,
            "youtube_music_auto_update_dependencies": self.youtube_music_auto_update_dependencies,
            "youtube_music_use_nightly_yt_dlp": self.youtube_music_use_nightly_yt_dlp,
            "youtube_music_autoplay_related": self.youtube_music_autoplay_related,
            "youtube_music_dependency_update_interval_hours": self.youtube_music_dependency_update_interval_hours,
            "youtube_music_dependency_last_auto_update_epoch": self.youtube_music_dependency_last_auto_update_epoch,
            "youtube_music_library_page_size": self.youtube_music_library_page_size,
            "youtube_music_home_discovery_limit": self.youtube_music_home_discovery_limit,
            "last_open_dir": self.last_open_dir if self.remember_last_folder else "",
            "recent_media_files": list(self.recent_media_files),
            "recent_folders": list(self.recent_folders),
            "recent_playlists": list(self.recent_playlists),
            "equalizer_custom_presets": [preset.to_dict() for preset in self.equalizer_custom_presets],
            "logging_enabled": self.logging_enabled,
            "logging_level": self.logging_level,
            "welcome_screen_completed": self.welcome_screen_completed,
        }

    @classmethod
    def from_dict(cls, data):
        settings = cls()
        settings.restore_session_on_startup = bool(data.get("restore_session_on_startup", settings.restore_session_on_startup))
        settings.remember_window_size = bool(data.get("remember_window_size", settings.remember_window_size))
        settings.remember_last_folder = bool(data.get("remember_last_folder", settings.remember_last_folder))
        settings.confirm_on_exit = bool(data.get("confirm_on_exit", settings.confirm_on_exit))
        settings.announcements_enabled = bool(data.get("announcements_enabled", settings.announcements_enabled))
        settings.disable_video_output = bool(data.get("disable_video_output", settings.disable_video_output))
        raw_audio_output_device_id = normalize_audio_output_device_id(data.get("audio_output_device_id"))
        settings.audio_output_device_id = (
            raw_audio_output_device_id if is_selectable_audio_output_device_id(raw_audio_output_device_id) else ""
        )
        settings.default_volume = _clamp_int(data.get("default_volume"), minimum=0, maximum=100, fallback=settings.default_volume)
        settings.crossfade_seconds = _clamp_int(
            data.get("crossfade_seconds"),
            minimum=0,
            maximum=MAX_CROSSFADE_SECONDS,
            fallback=settings.crossfade_seconds,
        )
        settings.crossfade_on_manual_track_change = bool(
            data.get("crossfade_on_manual_track_change", settings.crossfade_on_manual_track_change)
        )
        settings.volume_step = _clamp_int(data.get("volume_step"), minimum=1, maximum=25, fallback=settings.volume_step)
        settings.seek_step_seconds = _clamp_int(
            data.get("seek_step_seconds"),
            minimum=1,
            maximum=120,
            fallback=settings.seek_step_seconds,
        )
        settings.shuffle_new_playlists = bool(data.get("shuffle_new_playlists", settings.shuffle_new_playlists))

        repeat_mode = data.get("repeat_mode_new_playlists", settings.repeat_mode_new_playlists)
        settings.repeat_mode_new_playlists = repeat_mode if repeat_mode in REPEAT_MODES else REPEAT_OFF
        settings.youtube_music_manage_dependencies = bool(
            data.get("youtube_music_manage_dependencies", settings.youtube_music_manage_dependencies)
        )
        settings.youtube_music_auto_update_dependencies = bool(
            data.get("youtube_music_auto_update_dependencies", settings.youtube_music_auto_update_dependencies)
        )
        settings.youtube_music_use_nightly_yt_dlp = bool(
            data.get("youtube_music_use_nightly_yt_dlp", settings.youtube_music_use_nightly_yt_dlp)
        )
        settings.youtube_music_autoplay_related = bool(
            data.get("youtube_music_autoplay_related", settings.youtube_music_autoplay_related)
        )
        settings.youtube_music_dependency_update_interval_hours = _clamp_int(
            data.get(
                "youtube_music_dependency_update_interval_hours",
                settings.youtube_music_dependency_update_interval_hours,
            ),
            minimum=1,
            maximum=720,
            fallback=settings.youtube_music_dependency_update_interval_hours,
        )
        settings.youtube_music_dependency_last_auto_update_epoch = _clamp_int(
            data.get(
                "youtube_music_dependency_last_auto_update_epoch",
                settings.youtube_music_dependency_last_auto_update_epoch,
            ),
            minimum=0,
            maximum=32503680000,
            fallback=settings.youtube_music_dependency_last_auto_update_epoch,
        )
        settings.youtube_music_library_page_size = _clamp_int(
            data.get("youtube_music_library_page_size", settings.youtube_music_library_page_size),
            minimum=MIN_YOUTUBE_MUSIC_LIBRARY_PAGE_SIZE,
            maximum=MAX_YOUTUBE_MUSIC_LIBRARY_PAGE_SIZE,
            fallback=settings.youtube_music_library_page_size,
        )
        settings.youtube_music_home_discovery_limit = _clamp_int(
            data.get("youtube_music_home_discovery_limit", settings.youtube_music_home_discovery_limit),
            minimum=MIN_YOUTUBE_MUSIC_HOME_DISCOVERY_LIMIT,
            maximum=MAX_YOUTUBE_MUSIC_HOME_DISCOVERY_LIMIT,
            fallback=settings.youtube_music_home_discovery_limit,
        )

        last_open_dir = str(data.get("last_open_dir") or "").strip()
        settings.last_open_dir = last_open_dir if settings.remember_last_folder else ""
        settings.recent_media_files = _string_list(data.get("recent_media_files"))
        settings.recent_folders = _string_list(data.get("recent_folders"))
        settings.recent_playlists = _string_list(data.get("recent_playlists"))
        settings.equalizer_custom_presets = _equalizer_preset_list(data.get("equalizer_custom_presets"))
        settings.logging_enabled = bool(data.get("logging_enabled", settings.logging_enabled))
        raw_logging_level = str(data.get("logging_level") or "").upper()
        settings.logging_level = raw_logging_level if raw_logging_level in LOGGING_LEVELS else DEFAULT_LOGGING_LEVEL
        settings.welcome_screen_completed = bool(data.get("welcome_screen_completed", settings.welcome_screen_completed))
        return settings


def _clamp_int(value, minimum, maximum, fallback):
    try:
        numeric_value = int(value)
    except (TypeError, ValueError):
        return fallback

    return max(minimum, min(maximum, numeric_value))


def _string_list(value):
    if not isinstance(value, list):
        return []

    normalized_items = []
    for item in value:
        normalized_item = str(item or "").strip()
        if normalized_item:
            normalized_items.append(normalized_item)

    return normalized_items


def _equalizer_preset_list(value):
    if not isinstance(value, list):
        return []

    presets = []
    for item in value:
        if not isinstance(item, dict):
            continue
        presets.append(EqualizerPreset.from_dict(item))

    return presets
