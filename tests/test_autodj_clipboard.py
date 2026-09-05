from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from player.frames.autodj import FrameAutoDJMixin
from player.frames.commands.open_commands import OpenCommandsMixin
from player.playlists import PlaylistState


class ClipboardFrame(OpenCommandsMixin, FrameAutoDJMixin):
    def __init__(self):
        self.state = PlaylistState(title="AutoDJ")
        self.state.set_items(["current.mp3", "prepared.mp3"])
        self.state.autodj_session = True
        self.state.autodj_source_items = list(self.state.items)
        self.state.autodj_source_labels = list(self.state.items)
        self._get_playlist_state = Mock(return_value=self.state)
        self._open_media_paths = Mock(return_value=True)
        self._open_external_media_paths = Mock(return_value=True)
        self._announce = Mock()
        self._refresh_playlist_browser = Mock()
        self._maybe_fill_autodj_session = Mock()
        self._normalize_path = lambda path: str(Path(path).resolve())


class AutoDJClipboardTests(unittest.TestCase):
    def test_paste_adds_candidates_without_replacing_current_or_prepared_tracks(self):
        frame = ClipboardFrame()
        paths = ["https://music.youtube.com/watch?v=abc123DEF45",
                 "https://music.youtube.com/watch?v=xyz123DEF45"]
        frame._open_from_clipboard_text("\n".join(paths + paths))
        self.assertEqual(frame.state.items, ["current.mp3", "prepared.mp3"])
        self.assertEqual(frame.state.current_media_path, "current.mp3")
        self.assertEqual(frame.state.autodj_remaining_items, paths)
        self.assertEqual(frame.state.autodj_source_items[-2:], paths)
        frame._maybe_fill_autodj_session.assert_called_once_with(frame.state)
        frame._open_external_media_paths.assert_not_called()
        frame._open_media_paths.assert_not_called()

    def test_single_local_path_can_be_pasted(self):
        frame = ClipboardFrame()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "song.mp3"
            path.touch()
            frame._open_from_clipboard_text(f'"{path}"')
            self.assertEqual(frame.state.autodj_remaining_items, [str(path)])

    def test_duplicate_paste_does_not_add_or_restart_preparation(self):
        frame = ClipboardFrame()
        path = "https://music.youtube.com/watch?v=abc123DEF45"
        frame._open_from_clipboard_text(path)
        frame._maybe_fill_autodj_session.reset_mock()
        frame._open_from_clipboard_text(path)
        self.assertEqual(frame.state.autodj_remaining_items, [path])
        frame._maybe_fill_autodj_session.assert_not_called()

    def test_force_new_playlist_keeps_existing_behavior(self):
        frame = ClipboardFrame()
        path = "https://music.youtube.com/watch?v=abc123DEF45"
        frame._open_from_clipboard_text(path, force_new_playlist=True)
        frame._open_media_paths.assert_called_once_with([path])
        self.assertEqual(frame.state.autodj_remaining_items, [])

    def test_ordinary_playlist_keeps_existing_behavior(self):
        frame = ClipboardFrame()
        frame.state.autodj_session = False
        path = "https://music.youtube.com/watch?v=abc123DEF45"
        frame._open_from_clipboard_text(path)
        frame._open_external_media_paths.assert_called_once_with([path])

    def test_pasting_does_not_resume_paused_preparation(self):
        frame = ClipboardFrame()
        frame.state.autodj_preparation_paused = True
        frame._open_from_clipboard_text("https://music.youtube.com/watch?v=abc123DEF45")
        self.assertTrue(frame.state.autodj_preparation_paused)
        frame.autodj_service = object()
        frame.playlists = [frame.state]
        self.assertFalse(FrameAutoDJMixin._maybe_fill_autodj_session(frame, frame.state))

    def test_video_is_not_added_as_an_audio_candidate(self):
        frame = ClipboardFrame()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "video.mp4"
            path.touch()
            frame._open_from_clipboard_text(str(path))
        self.assertEqual(frame.state.autodj_remaining_items, [])
        frame._maybe_fill_autodj_session.assert_not_called()
