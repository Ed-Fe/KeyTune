from __future__ import annotations

import pathlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.frames.youtube_music import lifecycle as lifecycle_module
from player.frames.youtube_music.dependencies import DependencyMixin
from player.frames.youtube_music.lifecycle import LifecycleMixin


class _Frame(LifecycleMixin, DependencyMixin):
    def __init__(self, *, open_on_startup=True, update_running=False, panel_open=False):
        self.settings = SimpleNamespace(open_keytube_on_startup=open_on_startup)
        self._youtube_music_dependency_update_in_progress = update_running
        self._panel_open = panel_open
        self.on_open_youtube_music = Mock()
        self._refresh_youtube_music_menu_state = Mock()
        self._refresh_youtube_music_screen_later = Mock()

    def _youtube_music_integration_enabled(self):
        return True

    def _get_youtube_music_panel(self):
        return object() if self._panel_open else None


def _run_call_after_immediately():
    return patch.object(lifecycle_module.wx, "CallAfter", lambda function, *args: function(*args))


class OpenKeyTubeOnStartupTests(unittest.TestCase):
    def test_opens_at_once_when_nothing_is_updating(self):
        frame = _Frame()
        with _run_call_after_immediately():
            frame._open_keytube_on_startup_if_enabled()
        frame.on_open_youtube_music.assert_called_once_with(None)

    def test_does_nothing_when_the_option_is_off(self):
        frame = _Frame(open_on_startup=False)
        with _run_call_after_immediately():
            frame._open_keytube_on_startup_if_enabled()
        frame.on_open_youtube_music.assert_not_called()

    def test_waits_for_the_dependency_update_instead_of_giving_up(self):
        # A atualização automática dos recursos roda na abertura, uma vez por dia,
        # e a central recusa abrir enquanto ela dura.
        frame = _Frame(update_running=True)
        with _run_call_after_immediately():
            frame._open_keytube_on_startup_if_enabled()
            frame.on_open_youtube_music.assert_not_called()

            frame._finish_youtube_music_dependency_update(Mock(), Mock(), SimpleNamespace(), None)

        frame.on_open_youtube_music.assert_called_once_with(None)

    def test_opens_even_when_the_update_fails(self):
        frame = _Frame(update_running=True)
        with _run_call_after_immediately():
            frame._open_keytube_on_startup_if_enabled()
            frame._finish_youtube_music_dependency_update(Mock(), Mock(), None, RuntimeError("sem rede"))
        frame.on_open_youtube_music.assert_called_once_with(None)

    def test_opens_only_once_after_the_wait(self):
        frame = _Frame(update_running=True)
        with _run_call_after_immediately():
            frame._open_keytube_on_startup_if_enabled()
            frame._finish_youtube_music_dependency_update(Mock(), Mock(), SimpleNamespace(), None)
            frame._finish_youtube_music_dependency_update(Mock(), Mock(), SimpleNamespace(), None)
        frame.on_open_youtube_music.assert_called_once_with(None)

    def test_a_later_manual_update_does_not_open_the_tab(self):
        frame = _Frame(update_running=False)
        with _run_call_after_immediately():
            frame._finish_youtube_music_dependency_update(Mock(), Mock(), SimpleNamespace(), None)
        frame.on_open_youtube_music.assert_not_called()

    def test_does_not_steal_focus_when_the_tab_was_opened_meanwhile(self):
        frame = _Frame(update_running=True)
        with _run_call_after_immediately():
            frame._open_keytube_on_startup_if_enabled()
            frame._panel_open = True
            frame._finish_youtube_music_dependency_update(Mock(), Mock(), SimpleNamespace(), None)
        frame.on_open_youtube_music.assert_not_called()


if __name__ == "__main__":
    unittest.main()
