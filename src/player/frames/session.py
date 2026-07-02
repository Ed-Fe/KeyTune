from ..constants import DEFAULT_VOLUME
from ..playlists import PlaylistState
from ..i18n import _
from ..session import load_session, save_session


class FrameSessionMixin:
    def _capture_tab_state(self, index=None):
        state = self._get_playlist_state(index)
        if not state or not state.current_media_path or not self.player.get_media():
            return

        current_time = self.player.get_time()
        state.last_position_ms = max(0, current_time) if current_time is not None and current_time >= 0 else 0
        state.was_playing = bool(self.player.is_playing())

    def _capture_active_playlist_state(self):
        active_index = self._get_active_playlist_index()
        if active_index is None or active_index < 0:
            return

        self._capture_tab_state(active_index)

    def _restore_session(self):
        session_payload = load_session()
        if not session_payload:
            return False

        playlist_payloads = session_payload.get("playlists")
        if not isinstance(playlist_payloads, list) or not playlist_payloads:
            return False

        self._reset_playlist_tabs()

        restored_states = []
        for payload in playlist_payloads:
            state = PlaylistState.from_dict(payload)
            restored_states.append(state)

        remember_restored_youtube_music_states = getattr(self, "_remember_restored_youtube_music_states", None)
        if callable(remember_restored_youtube_music_states):
            remember_restored_youtube_music_states(restored_states)

        self.playlists[0] = restored_states[0]
        self.notebook.SetPageText(0, restored_states[0].title)

        for state in restored_states[1:]:
            target_index = self._create_empty_playlist_tab(select=False)
            self.playlists[target_index] = state
            self.notebook.SetPageText(target_index, state.title)

        try:
            saved_volume = int(session_payload.get("volume", DEFAULT_VOLUME))
        except (TypeError, ValueError):
            saved_volume = DEFAULT_VOLUME

        self.current_volume = max(0, min(100, saved_volume))
        self._apply_current_volume()

        try:
            saved_playback_rate = float(session_payload.get("playback_rate", 1.0))
        except (TypeError, ValueError):
            saved_playback_rate = 1.0

        self.current_playback_rate = max(0.25, min(3.0, saved_playback_rate))
        self._apply_current_playback_rate()

        try:
            saved_pitch_semitones = int(session_payload.get("pitch_semitones", 0))
        except (TypeError, ValueError):
            saved_pitch_semitones = 0

        self.current_pitch_semitones = max(-12, min(12, saved_pitch_semitones))
        self._apply_equalizer_state_to_current_playback()

        if self.settings.remember_window_size:
            saved_window_size = session_payload.get("window_size")
            if (
                isinstance(saved_window_size, list)
                and len(saved_window_size) == 2
                and all(isinstance(value, int) for value in saved_window_size)
            ):
                self.SetSize(tuple(saved_window_size))

        selected_tab = session_payload.get("selected_tab", 0)
        if not isinstance(selected_tab, int):
            selected_tab = 0

        selected_tab = max(0, min(selected_tab, len(self.playlists) - 1))
        if selected_tab == self._get_current_tab_index():
            self._activate_tab(selected_tab, announce=False)
        else:
            self._select_tab(selected_tab, announce=False)

        current_state = self._get_playlist_state(selected_tab)
        if current_state and current_state.current_media_path:
            self._announce(
                _("Sessão restaurada com {count} abas. {title}. {position}").format(count=len(self.playlists), title=current_state.title, position=self._describe_playlist_position(current_state))
            )
        else:
            self._announce(_("Sessão restaurada com {count} abas.").format(count=len(self.playlists)))

        if hasattr(self, "_set_status_message"):
            self._set_status_message(
                _("Sessão anterior restaurada com {count} abas.").format(count=len(self.playlists))
            )

        return True

    def _save_session(self):
        active_playlist_index = self._get_active_playlist_index()
        self._capture_active_playlist_state()

        playlist_states = []
        selected_tab = 0
        for index, state in enumerate(self.playlists):
            if not isinstance(state, PlaylistState):
                continue

            if index == active_playlist_index:
                selected_tab = len(playlist_states)

            playlist_states.append(state.to_dict())

        payload = {
            "selected_tab": selected_tab,
            "volume": self.current_volume,
            "playback_rate": self.current_playback_rate,
            "pitch_semitones": self.current_pitch_semitones,
            "playlists": playlist_states,
        }

        if self.settings.remember_window_size:
            payload["window_size"] = list(self.GetSize())

        try:
            save_session(payload)
        except OSError:
            return
