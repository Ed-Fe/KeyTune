"""Converter e baixar seguem a mesma regra de foco e os mesmos cuidados com arquivos.

Com o foco numa lista (playlist, explorador ou busca do YouTube), Ctrl+Shift+K e
Ctrl+Shift+B agem na seleção dela; fora de uma lista, na mídia atual.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import wx


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.convert import options
from player.convert.dialog import ConvertDialog
from player.download import runner
from player.download.plan import DownloadChoice, build_download_plan, unique_file_stem
from player.frames import convert as convert_frame
from player.frames import download as download_frame
from player.frames.convert import FrameConvertMixin
from player.frames.download import FrameDownloadMixin
from player.frames.selection import SCOPE_EXPLORER, SCOPE_PLAYLIST, SCOPE_SEARCH
from player.preferences.models import AppSettings

YOUTUBE_URL = "https://www.youtube.com/watch?v=abc123DEF45"


def _run_inline(_owner, work, on_done):
    on_done(work())


class _ConvertFrame(FrameConvertMixin):
    def __init__(self):
        self.announcements = []
        self._initialize_convert_state()
        self.on_convert_selection = Mock()
        self.on_convert_current_media = Mock()
        self._explorer_convert_paths = Mock()
        self._explorer_selected_paths = Mock(return_value=["C:\\musicas\\a.mp3"])

    def _announce(self, message):
        self.announcements.append(message)


class ConvertShortcutTests(unittest.TestCase):
    def _press(self, scope):
        frame = _ConvertFrame()
        with patch.object(convert_frame, "focused_list_scope", return_value=scope):
            frame.on_convert_shortcut()
        return frame

    def test_outside_a_list_it_converts_the_current_media(self):
        frame = self._press("")

        frame.on_convert_current_media.assert_called_once_with()
        frame.on_convert_selection.assert_not_called()

    def test_in_the_playlist_it_converts_the_selection(self):
        frame = self._press(SCOPE_PLAYLIST)

        frame.on_convert_selection.assert_called_once_with()
        frame.on_convert_current_media.assert_not_called()

    def test_in_the_explorer_it_converts_the_explorer_selection(self):
        frame = self._press(SCOPE_EXPLORER)

        frame._explorer_convert_paths.assert_called_once_with(["C:\\musicas\\a.mp3"])
        frame.on_convert_current_media.assert_not_called()

    def test_in_the_youtube_search_it_points_to_download(self):
        frame = self._press(SCOPE_SEARCH)

        self.assertIn("Ctrl+Shift+B", frame.announcements[0])
        frame.on_convert_current_media.assert_not_called()
        frame.on_convert_selection.assert_not_called()


@patch("player.frames.convert.run_in_background", _run_inline)
class ConvertSelectionTests(unittest.TestCase):
    def _frame(self):
        frame = FrameConvertMixin.__new__(FrameConvertMixin)
        frame.announcements = []
        frame._announce = frame.announcements.append
        frame._initialize_convert_state()
        return frame

    def test_a_youtube_selection_points_to_download(self):
        frame = self._frame()

        frame._convert_media_paths([YOUTUBE_URL])

        self.assertIn("Ctrl+Shift+B", frame.announcements[0])

    def test_files_that_no_longer_exist_are_announced(self):
        frame = self._frame()
        missing = str(pathlib.Path(tempfile.gettempdir(), "keytune-sumiu.mp3"))

        frame._convert_media_paths([missing])

        self.assertEqual(frame.announcements, ["Os arquivos selecionados não foram encontrados."])

    def test_the_disk_is_checked_off_the_interface_thread(self):
        frame = self._frame()

        with patch("player.frames.convert.run_in_background") as run_in_background:
            with patch("os.path.isfile") as isfile:
                frame._convert_media_paths([r"Z:\rede\a.mp3", r"Z:\rede\b.mp3"])

        run_in_background.assert_called_once()
        isfile.assert_not_called()


class _DownloadFrame(FrameDownloadMixin):
    def __init__(self):
        self.announcements = []
        self._initialize_download_state()
        self.on_download_selection = Mock()
        self.on_download_current_media = Mock()
        self._begin_download = Mock()
        self.download_youtube_music_search_selection = Mock()

    def _announce(self, message):
        self.announcements.append(message)


class DownloadShortcutTests(unittest.TestCase):
    def _press(self, scope):
        frame = _DownloadFrame()
        with patch.object(download_frame, "focused_list_scope", return_value=scope):
            frame.on_download_shortcut()
        return frame

    def test_outside_a_list_it_downloads_the_current_media(self):
        frame = self._press("")

        frame.on_download_current_media.assert_called_once_with()
        frame.on_download_selection.assert_not_called()

    def test_in_the_playlist_it_downloads_the_selection(self):
        frame = self._press(SCOPE_PLAYLIST)

        frame.on_download_selection.assert_called_once_with()
        frame.on_download_current_media.assert_not_called()

    def test_in_the_youtube_search_it_downloads_the_selected_results(self):
        frame = self._press(SCOPE_SEARCH)

        frame.download_youtube_music_search_selection.assert_called_once_with()
        frame.on_download_current_media.assert_not_called()

    def test_in_the_explorer_there_is_nothing_to_download(self):
        frame = self._press(SCOPE_EXPLORER)

        self.assertEqual(frame.announcements, ["Esta mídia já está no seu computador."])
        frame.on_download_current_media.assert_not_called()
        frame._begin_download.assert_not_called()


class DownloadFileSafetyTests(unittest.TestCase):
    def test_a_download_never_reuses_the_name_of_a_file_already_in_the_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            pathlib.Path(folder, "Intro.m4a").write_bytes(b"")

            used_stems = download_frame._existing_file_stems(folder)

            self.assertEqual(unique_file_stem("intro", used_stems), "intro (2)")
            self.assertEqual(unique_file_stem("Outra", used_stems), "Outra")

    def test_a_folder_that_does_not_exist_yet_has_no_names_in_use(self):
        missing = pathlib.Path(tempfile.gettempdir(), "keytune-pasta-inexistente")

        self.assertEqual(download_frame._existing_file_stems(missing), set())

    def test_live_broadcasts_are_filtered_out_of_every_download(self):
        choice = DownloadChoice("audio", "original", "best", 0, "D:\\Musicas")
        plan = build_download_plan(choice, ffmpeg_available=False)

        command = runner.build_command("yt-dlp", YOUTUBE_URL, choice, plan, output_directory="D:\\Musicas")

        self.assertEqual(command[command.index("--match-filter") + 1], "!is_live")
        self.assertNotIn("--playlist-items", command)

    def test_other_sites_only_download_one_item_that_has_a_duration(self):
        choice = DownloadChoice("audio", "original", "best", 0, "D:\\Musicas")
        plan = build_download_plan(choice, ffmpeg_available=False)

        command = runner.build_command(
            "yt-dlp", "https://example.com/pagina", choice, plan, output_directory="D:\\Musicas"
        )

        self.assertEqual(command[command.index("--playlist-items") + 1], "1")
        filters = [command[index + 1] for index, value in enumerate(command) if value == "--match-filter"]
        self.assertEqual(filters, ["!is_live & duration", "!is_live & !direct"])


class ConvertMemoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = wx.App.Get() or wx.App()

    def _dialog(self, mode, source, settings, **kwargs):
        dialog = ConvertDialog(None, mode, source, settings=settings, **kwargs)
        self.addCleanup(dialog.Destroy)
        return dialog

    def test_the_choices_survive_a_settings_round_trip(self):
        settings = AppSettings(
            convert_audio_format="flac",
            convert_audio_bitrate=320,
            convert_sample_rate=48000,
            convert_container_format="mkv",
            convert_video_height=1080,
            convert_use_cover=False,
            convert_same_folder=False,
            convert_directory="D:\\Convertidos",
        )

        restored = AppSettings.from_dict(settings.to_dict())

        for name in (
            "convert_audio_format",
            "convert_audio_bitrate",
            "convert_sample_rate",
            "convert_container_format",
            "convert_video_height",
            "convert_use_cover",
            "convert_same_folder",
            "convert_directory",
        ):
            self.assertEqual(getattr(restored, name), getattr(settings, name), name)

    def test_unknown_saved_values_fall_back_to_the_defaults(self):
        restored = AppSettings.from_dict({"convert_audio_format": "xyz", "convert_audio_bitrate": 7})

        self.assertEqual(restored.convert_audio_format, options.DEFAULT_AUDIO_FORMAT)
        self.assertEqual(restored.convert_audio_bitrate, options.DEFAULT_AUDIO_BITRATE)

    def test_the_dialog_opens_with_the_last_choices(self):
        settings = AppSettings(
            convert_audio_format="ogg",
            convert_audio_bitrate=256,
            convert_same_folder=False,
        )

        dialog = self._dialog(options.MODE_AUDIO_TO_AUDIO, "C:\\m\\a.mp3", settings, other_directory="D:\\Saida")
        request = dialog.get_request()

        self.assertEqual(request.target_format, "ogg")
        self.assertEqual(request.audio_bitrate_kbps, 256)
        self.assertEqual(request.output_directory, "D:\\Saida")

    def test_another_folder_is_not_preselected_without_a_folder_to_use(self):
        settings = AppSettings(convert_same_folder=False)

        dialog = self._dialog(options.MODE_AUDIO_TO_AUDIO, "C:\\m\\a.mp3", settings)

        self.assertTrue(dialog.saves_in_same_folder())

    def test_each_kind_of_conversion_remembers_its_own_format(self):
        settings = AppSettings()
        dialog = self._dialog(options.MODE_AUDIO_TO_VIDEO, "C:\\m\\a.mp3", settings)
        dialog.format_choice.SetSelection(options.AUDIO_TO_VIDEO_FORMATS.index("webm"))
        dialog.cover_checkbox.SetValue(False)

        dialog.store_choices(settings)

        self.assertEqual(settings.convert_video_format, "webm")
        self.assertFalse(settings.convert_use_cover)
        self.assertEqual(settings.convert_audio_format, options.DEFAULT_AUDIO_FORMAT)
        self.assertEqual(settings.convert_container_format, options.DEFAULT_VIDEO_FORMAT)

    def test_the_frame_saves_the_choices_after_the_dialog(self):
        frame = FrameConvertMixin.__new__(FrameConvertMixin)
        frame._initialize_convert_state()
        frame.settings = AppSettings()
        frame._save_settings = Mock()
        dialog = self._dialog(options.MODE_AUDIO_TO_AUDIO, "C:\\m\\a.mp3", frame.settings)
        dialog.format_choice.SetSelection(options.AUDIO_FORMAT_IDS.index("flac"))

        frame._remember_convert_choices(dialog)

        self.assertEqual(frame.settings.convert_audio_format, "flac")
        frame._save_settings.assert_called_once_with()

    def test_no_two_controls_of_the_dialog_share_an_access_key(self):
        dialog = self._dialog(options.MODE_AUDIO_TO_VIDEO, "C:\\m\\a.mp3", SimpleNamespace())
        labels = [
            dialog.convert_button.GetLabel(),
            dialog.cancel_button.GetLabel(),
            dialog.cover_checkbox.GetLabel(),
            dialog.directory_ctrl.browse_button.GetLabel(),
        ]

        keys = [label[label.index("&") + 1].lower() for label in labels]

        self.assertEqual(len(keys), len(set(keys)), keys)


if __name__ == "__main__":
    unittest.main()
