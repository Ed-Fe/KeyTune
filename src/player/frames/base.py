import wx

from ..accessibility import ScreenReaderAnnouncer
from ..constants import APP_TITLE, DEFAULT_WINDOW_SIZE
from ..log import setup_logging
from ..preferences import load_settings, save_settings
from .commands import FrameCommandMixin
from .equalizer import FrameEqualizerMixin
from .library import FrameLibraryMixin
from .lyrics_panel import LyricsPanel
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
        setup_logging(self.settings.logging_enabled, self.settings.logging_level)
        self._initial_paths = list(initial_paths or [])
        self._initialize_equalizer_support()
        self.current_volume = self.settings.default_volume
        self.current_playback_rate = 1.0
        self.current_pitch_semitones = 0
        self.playlists = []
        self.active_playlist_index = None
        self.announcer = ScreenReaderAnnouncer()
        self._suppress_tab_change_event = False
        self._recent_menu_actions = {}
        self._recent_menu_ids = []
        self._startup_update_check_scheduled = False
        self._update_check_in_progress = False
        self._update_restart_pending = False
        self._startup_initialization_started = False
        self._startup_ready = False
        self._suppress_next_auto_advance = False

        self._build_menu_bar()
        self._build_ui()
        
        # Início da integração do painel de letras
        main_panel = self.notebook.GetParent()
        self.lyrics_panel = LyricsPanel(main_panel)
        self.lyrics_panel.Hide()
        
        # Inserindo o painel de letras no sizer principal, entre o notebook e os controles
        main_sizer = main_panel.GetSizer()
        main_sizer.Insert(1, self.lyrics_panel, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 4)
        
        self._bind_events()
        self._refresh_youtube_music_menu_state()

        self.Centre()
        self.Show()
        wx.CallAfter(self._finish_startup_initialization)

    def _finish_startup_initialization(self):
        if self._startup_initialization_started:
            return

        self._startup_initialization_started = True
        self._create_player_backend()
        self._create_library_loader()
        self._initialize_smtc_service()
        self._startup_ready = True

        self._initialize_player_state()
        self._open_initial_paths()
        self._initialize_youtube_music_startup_state()
        self._schedule_startup_update_check()
        wx.CallAfter(self._show_welcome_screen_if_first_run)

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
        self._open_external_files(paths)

    def receive_external_files(self, paths):
        """Play files sent by another instance via IPC.

        Files opened from Explorer should not steal focus or pull the window to
        the front, so we only request gentle taskbar attention here.
        """
        if not paths:
            return

        if getattr(self, "_startup_ready", False):
            self._open_external_files(paths)
        else:
            self._initial_paths.extend(paths)

        if hasattr(self, "RequestUserAttention"):
            self.RequestUserAttention()

    def focus_from_relaunch(self):
        """Bring the existing window to front when the app is launched again.

        Used when KeyTune is started without a file (Start Menu, shortcut),
        where the user intent is to return to the running instance.
        """
        if self.IsIconized():
            self.Iconize(False)
        self.Raise()
        self._focus_player_surface()