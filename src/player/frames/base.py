import wx

from ..accessibility import ScreenReaderAnnouncer
from ..constants import APP_TITLE, DEFAULT_WINDOW_SIZE
from ..preferences import load_settings, save_settings
from .commands import FrameCommandMixin
from .equalizer import FrameEqualizerMixin
from .library import FrameLibraryMixin
from .playback import FramePlaybackMixin
from .recents import FrameRecentsMixin
from .session import FrameSessionMixin
from .smtc import FrameSmtcMixin
from .ui import FrameUIMixin
from .update import FrameUpdateMixin
from .youtube_music import FrameYouTubeMusicMixin


class MediaPlayerFrame(
    FrameYouTubeMusicMixin,
    FrameCommandMixin,
    FrameSessionMixin,
    FrameRecentsMixin,
    FrameEqualizerMixin,
    FrameLibraryMixin,
    FramePlaybackMixin,
    FrameSmtcMixin,
    FrameUpdateMixin,
    FrameUIMixin,
    wx.Frame,
):
    def __init__(self, initial_paths=None):
        super().__init__(None, title=APP_TITLE, size=DEFAULT_WINDOW_SIZE)

        self.settings = load_settings()
        self._initial_paths = initial_paths or []
        self._initialize_equalizer_support()
        self.current_volume = self.settings.default_volume
        self.playlists = []
        self.active_playlist_index = None
        self.announcer = ScreenReaderAnnouncer()
        self._suppress_tab_change_event = False
        self._recent_menu_actions = {}
        self._recent_menu_ids = []
        self._startup_update_check_scheduled = False
        self._update_check_in_progress = False
        self._update_restart_pending = False

        self._create_player_backend()
        self._create_library_loader()
        self._initialize_smtc_service()

        self._build_menu_bar()
        self._build_ui()
        self._bind_events()
        self._refresh_youtube_music_menu_state()

        self.Centre()
        self.Show()
        wx.CallAfter(self._initialize_player_state)
        wx.CallAfter(self._open_initial_paths)
        wx.CallAfter(self._verify_youtube_music_connection)
        wx.CallAfter(self._prime_equalizer_ui)
        wx.CallAfter(self._schedule_startup_update_check)

    def _announce(self, message):
        if not self.settings.announcements_enabled:
            return
        self.announcer.speak(message)

    def _save_settings(self):
        try:
            save_settings(self.settings)
        except OSError:
            return False
        return True

    def _open_initial_paths(self):
        if not self._initial_paths:
            return
        paths = self._initial_paths
        self._initial_paths = []
        self._open_selected_files(paths)

    def receive_external_files(self, paths):
        """Open files sent by another instance via IPC without forcing focus."""
        if paths:
            self._open_external_files(paths)

        if self.IsIconized():
            self.Iconize(False)

        if hasattr(self, "RequestUserAttention"):
            self.RequestUserAttention()
