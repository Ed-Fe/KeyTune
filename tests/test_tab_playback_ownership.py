"""Looking at a playlist tab never changes what is playing; starting something in it does."""

from __future__ import annotations

import pathlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.frames.commands.browser_commands import BrowserCommandsMixin
from player.frames.library_tabs.item_removal import PlaylistItemRemovalMixin
from player.frames.library_tabs.tabs import TabManagementMixin
from player.frames.playback.controls import PlaybackControlsMixin
from player.frames.session import FrameSessionMixin
from player.playlists import PlaylistState, ScreenTabState


def _playlist(title, items=(), *, position_ms=0, was_playing=False):
    state = PlaylistState(title=title)
    if items:
        state.set_items(list(items), start_index=0)
    state.last_position_ms = position_ms
    state.was_playing = was_playing
    return state


class _TabsFrame(TabManagementMixin, FrameSessionMixin):
    """Two playlists: the first owns the player, the second is the one on screen."""

    def __init__(self, playlists, *, selected, active):
        self.playlists = list(playlists)
        self.active_playlist_index = active
        self.notebook = Mock()
        self.notebook.GetSelection.return_value = selected
        self.notebook.GetPageCount.return_value = len(self.playlists)
        self.player = Mock()
        self.player.get_media.return_value = object()
        self.player.get_time.return_value = 41000
        self.player.is_playing.return_value = True
        self.announcements = []
        self._announce = self.announcements.append
        self._update_title = Mock()
        self._update_time_bar = Mock()
        self._refresh_playlist_browser = Mock()
        self._unload_player = Mock()
        self._queue_media_start = Mock()
        self._apply_equalizer_state = Mock()
        self._bind_player_to_window = Mock()
        self._player_has_loaded_media = Mock(return_value=False)
        self._describe_playlist_position = lambda state: state.current_media_path or ""


class SelectingATabTests(unittest.TestCase):
    def test_showing_another_playlist_leaves_the_player_and_its_owner_alone(self):
        frame = _TabsFrame([_playlist("Rock", ["a.mp3"]), _playlist("Livro", ["b.mp3"])], selected=1, active=0)

        frame._activate_tab(1, announce=True)

        self.assertEqual(frame.active_playlist_index, 0)
        frame._unload_player.assert_not_called()
        frame._queue_media_start.assert_not_called()
        frame._apply_equalizer_state.assert_not_called()
        self.assertEqual(frame.announcements, ["Aba 2: Livro. b.mp3"])

    def test_showing_an_empty_playlist_does_not_stop_the_music(self):
        frame = _TabsFrame([_playlist("Rock", ["a.mp3"]), _playlist("Nova")], selected=1, active=0)

        frame._activate_tab(1, announce=True)

        frame._unload_player.assert_not_called()
        self.assertEqual(frame.announcements, ["Nova. Nenhuma mídia tocando agora."])

    def test_position_is_only_saved_into_the_playlist_that_owns_the_player(self):
        owner = _playlist("Rock", ["a.mp3"])
        other = _playlist("Livro", ["b.mp3"], position_ms=900)
        frame = _TabsFrame([owner, other], selected=1, active=0)

        frame._capture_tab_state(1)
        frame._capture_tab_state(0)

        self.assertEqual(other.last_position_ms, 900)
        self.assertEqual(owner.last_position_ms, 41000)

    def test_the_selected_playlist_falls_back_to_the_playing_one_on_a_screen_tab(self):
        frame = _TabsFrame(
            [_playlist("Rock", ["a.mp3"]), ScreenTabState(title="KeyTube", screen_id="keytube")], selected=1, active=0
        )

        self.assertEqual(frame._get_selected_playlist_index(), 0)


class TakingThePlayerTests(unittest.TestCase):
    def test_handing_the_player_over_saves_the_position_of_the_playlist_that_loses_it(self):
        owner = _playlist("Rock", ["a.mp3"])
        frame = _TabsFrame([owner, _playlist("Livro", ["b.mp3"])], selected=1, active=0)

        self.assertFalse(frame._set_active_playlist(1))

        self.assertEqual(frame.active_playlist_index, 1)
        self.assertEqual(owner.last_position_ms, 41000)
        self.assertTrue(frame._set_active_playlist(1))

    def test_resuming_a_playlist_loads_its_media_where_it_had_stopped(self):
        book = _playlist("Livro", ["b.mp3"], position_ms=900, was_playing=False)
        frame = _TabsFrame([_playlist("Rock", ["a.mp3"]), book], selected=1, active=0)

        self.assertTrue(frame._resume_playlist_tab(1, announce=False))

        self.assertEqual(frame.active_playlist_index, 1)
        frame._apply_equalizer_state.assert_called_once_with(book)
        frame._queue_media_start.assert_called_once_with(
            "b.mp3", tab_index=1, announce_message=None, restore_position_ms=900, pause_after_start=True
        )

    def test_resuming_on_request_plays_even_if_the_playlist_had_been_paused(self):
        book = _playlist("Livro", ["b.mp3"], position_ms=900, was_playing=False)
        frame = _TabsFrame([_playlist("Rock", ["a.mp3"]), book], selected=1, active=0)

        frame._resume_playlist_tab(1, announce=False, force_play=True)

        self.assertFalse(frame._queue_media_start.call_args.kwargs["pause_after_start"])
        self.assertTrue(book.was_playing)

    def test_resuming_an_empty_playlist_unloads_the_player(self):
        frame = _TabsFrame([_playlist("Rock", ["a.mp3"]), _playlist("Nova")], selected=1, active=0)

        self.assertFalse(frame._resume_playlist_tab(1, announce=False))

        frame._unload_player.assert_called_once_with()
        frame._queue_media_start.assert_not_called()


class SpaceTests(unittest.TestCase):
    def _frame(self, *, player_has_media):
        frame = PlaybackControlsMixin.__new__(PlaybackControlsMixin)
        frame.playing = _playlist("Rock", ["a.mp3"], was_playing=True)
        frame.viewed = _playlist("Livro", ["b.mp3"], position_ms=900)
        frame.player = Mock()
        frame.player.get_media.return_value = object() if player_has_media else None
        frame.player.is_playing.return_value = False
        frame._crossfade_state = None
        frame._get_active_playlist_state = lambda: frame.playing
        frame._get_selected_playlist_index = lambda: 1
        frame._get_playlist_state = lambda index=None: frame.viewed if index == 1 else frame.playing
        frame._media_start_is_pending = Mock(return_value=False)
        frame._resume_playlist_tab = Mock()
        frame._bind_player_to_window = Mock()
        frame._update_time_bar = Mock()
        frame._announce = Mock()
        frame.on_open = Mock()
        return frame

    def test_space_controls_what_is_in_the_player_whatever_playlist_is_on_screen(self):
        frame = self._frame(player_has_media=True)

        frame._toggle_play_pause()

        frame.player.play.assert_called_once_with()
        frame._resume_playlist_tab.assert_not_called()
        self.assertTrue(frame.playing.was_playing)
        self.assertEqual(frame.viewed.last_position_ms, 900)

    def test_space_with_an_empty_player_resumes_the_playlist_on_screen(self):
        frame = self._frame(player_has_media=False)

        frame._toggle_play_pause()

        frame._resume_playlist_tab.assert_called_once_with(1, announce=False, force_play=True)
        frame.on_open.assert_not_called()


class EnterOnAnItemTests(unittest.TestCase):
    def _frame(self, state, *, owns_player):
        frame = BrowserCommandsMixin.__new__(BrowserCommandsMixin)
        frame._get_playlist_state = lambda index=None: state
        frame._get_selected_playlist_index = lambda: 1
        frame._is_active_playlist_state = lambda _state: owns_player
        frame._block_sensitive_action_during_youtube_music = Mock(return_value=False)
        frame._play_media = Mock()
        frame._resume_playlist_tab = Mock()
        return frame

    def test_plays_in_the_playlist_on_screen(self):
        state = _playlist("Livro", ["a.mp3", "b.mp3"])
        frame = self._frame(state, owns_player=False)

        frame.on_playlist_browser_activate_item(1)

        self.assertEqual(state.current_media_path, "b.mp3")
        frame._play_media.assert_called_once_with(index=1, allow_crossfade=False)

    def test_the_item_where_another_playlist_had_stopped_resumes_from_there(self):
        state = _playlist("Livro", ["a.mp3", "b.mp3"], position_ms=900)
        frame = self._frame(state, owns_player=False)

        frame.on_playlist_browser_activate_item(0)

        frame._resume_playlist_tab.assert_called_once_with(1, announce=False, force_play=True)
        frame._play_media.assert_not_called()

    def test_the_current_item_of_the_playing_playlist_restarts(self):
        state = _playlist("Rock", ["a.mp3"], position_ms=900)
        frame = self._frame(state, owns_player=True)

        frame.on_playlist_browser_activate_item(0)

        frame._play_media.assert_called_once_with(index=1, allow_crossfade=False)


class RemovingItemsTests(unittest.TestCase):
    def _frame(self, state, *, owns_player):
        frame = PlaylistItemRemovalMixin.__new__(PlaylistItemRemovalMixin)
        frame.settings = SimpleNamespace()
        frame._get_playlist_state = lambda index=None: state
        frame._is_active_playlist_state = lambda _state: owns_player
        frame._block_sensitive_action_during_youtube_music = Mock(return_value=False)
        frame._media_label = lambda path: path
        frame._cancel_crossfade_transition = Mock()
        frame._stop_all_players = Mock()
        frame._unload_player = Mock()
        frame._play_media = Mock()
        frame._update_title = Mock()
        frame._refresh_playlist_browser = Mock()
        frame._announce = Mock()
        return frame

    def test_removing_the_current_item_of_a_playlist_that_is_not_playing_keeps_the_music(self):
        state = _playlist("Livro", ["a.mp3", "b.mp3"], position_ms=900)
        frame = self._frame(state, owns_player=False)

        frame._remove_item_from_current_playlist(0)

        self.assertEqual(state.items, ["b.mp3"])
        self.assertEqual(state.current_media_path, "b.mp3")
        self.assertEqual(state.last_position_ms, 0)
        for untouched in (frame._stop_all_players, frame._unload_player, frame._play_media):
            untouched.assert_not_called()

    def test_emptying_a_playlist_that_is_not_playing_keeps_the_music(self):
        frame = self._frame(_playlist("Livro", ["a.mp3"]), owns_player=False)

        frame._remove_item_from_current_playlist(0)

        frame._unload_player.assert_not_called()

    def test_removing_the_playing_item_moves_on_to_the_next(self):
        state = _playlist("Rock", ["a.mp3", "b.mp3"])
        frame = self._frame(state, owns_player=True)
        frame._get_active_playlist_index = Mock(return_value=0)

        frame._remove_item_from_current_playlist(0)

        frame._stop_all_players.assert_called_once_with(unload=False)
        frame._play_media.assert_called_once()
        self.assertEqual(state.current_media_path, "b.mp3")


if __name__ == "__main__":
    unittest.main()
