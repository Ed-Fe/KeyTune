from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from player.frames.fullscreen import FrameFullscreenMixin
from player.widgets import wrap_text_to_width


class _FixedWidthControl:
    """Cada caractere mede 10 px."""

    def GetTextExtent(self, text):
        return SimpleNamespace(Width=len(text) * 10)


class WrapTextToWidthTests(unittest.TestCase):
    def test_long_line_breaks_between_words(self):
        wrapped = wrap_text_to_width(_FixedWidthControl(), "um dois tres quatro", 90)

        self.assertEqual(wrapped, "um dois\ntres\nquatro")

    def test_existing_line_breaks_are_kept(self):
        wrapped = wrap_text_to_width(_FixedWidthControl(), "Titulo\n\nfrase curta", 200)

        self.assertEqual(wrapped, "Titulo\n\nfrase curta")

    def test_a_word_wider_than_the_line_stays_alone(self):
        wrapped = wrap_text_to_width(_FixedWidthControl(), "a palavragrande b", 50)

        self.assertEqual(wrapped, "a\npalavragrande\nb")


class _Frame(FrameFullscreenMixin):
    def __init__(self, page):
        self.notebook = Mock()
        self.notebook.GetCurrentPage.return_value = page
        self._announce = Mock()
        self.ShowFullScreen = Mock()
        self.Layout = Mock()
        self._layout_video_page = Mock()
        self._focus_player_surface = Mock(return_value=True)


class VideoFullscreenTests(unittest.TestCase):
    def test_a_tab_without_video_area_only_announces(self):
        frame = _Frame(SimpleNamespace())

        frame.on_toggle_video_fullscreen()

        frame._announce.assert_called_once_with("Esta aba não tem área de vídeo.")
        frame.ShowFullScreen.assert_not_called()
        self.assertFalse(frame._video_fullscreen_active())

    def test_toggling_enters_and_leaves_full_screen(self):
        page = SimpleNamespace(video_panel=Mock(), Layout=Mock())
        frame = _Frame(page)

        with patch("player.frames.fullscreen.wx.Window.FindFocus", return_value=None):
            frame.on_toggle_video_fullscreen()

        self.assertTrue(frame._video_fullscreen_active())
        frame._focus_player_surface.assert_called_once_with(page.video_panel)
        self.assertEqual(frame._announce.call_args.args[0], "Tela cheia ativada. Esc ou Alt+Enter para sair.")

        frame.on_toggle_video_fullscreen()

        self.assertFalse(frame._video_fullscreen_active())
        self.assertEqual(frame.ShowFullScreen.call_args.args, (False,))
        self.assertEqual(frame._announce.call_args.args[0], "Tela cheia desativada.")

    def test_leaving_when_not_in_full_screen_does_nothing(self):
        frame = _Frame(SimpleNamespace())

        frame._exit_video_fullscreen()

        frame.ShowFullScreen.assert_not_called()
        frame._announce.assert_not_called()


if __name__ == "__main__":
    unittest.main()
