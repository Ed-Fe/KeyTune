import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from player.convert import options
from player.convert.dialog import ConvertDialog, target_formats_for
from player.convert.runner import ConversionResult
from player.frames import convert as convert_frame
from player.frames.convert import FrameConvertMixin
from player.process_control import CancelToken

SOURCE_DIR = os.path.normpath("C:/musicas")
SOURCE_FILE = os.path.join(SOURCE_DIR, "faixa.mp3")
OTHER_DIR = os.path.normpath("D:/Convertidos")


class _Frame(FrameConvertMixin):
    def __init__(self, media_path=""):
        self._state = SimpleNamespace(current_media_path=media_path)
        self.announcements = []
        self.statuses = []
        self._initialize_convert_state()

    def _get_active_playlist_state(self):
        return self._state

    def _announce(self, message):
        self.announcements.append(message)

    def _set_status_message(self, message, *, auto_clear_ms=6000):
        self.statuses.append(message)


class ConvertSourceValidationTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.dir = Path(self._temp.name)

    def _file(self, name):
        path = self.dir / name
        path.write_bytes(b"x")
        return str(path)

    def test_nothing_open_is_announced(self):
        frame = _Frame("")

        self.assertEqual(frame._validated_convert_source(), "")
        self.assertEqual(len(frame.announcements), 1)

    def test_youtube_media_points_to_the_download_shortcut(self):
        frame = _Frame("https://www.youtube.com/watch?v=abc123DEF45")

        self.assertEqual(frame._validated_convert_source(), "")
        self.assertIn("Ctrl+Shift+B", frame.announcements[0])

    def test_missing_and_unsupported_files_are_refused(self):
        for media_path in (str(self.dir / "sumiu.mp3"), self._file("notas.txt")):
            with self.subTest(media_path=media_path):
                frame = _Frame(media_path)

                self.assertEqual(frame._validated_convert_source(), "")
                self.assertEqual(len(frame.announcements), 1)

    def test_audio_and_video_files_are_accepted(self):
        for name in ("faixa.mp3", "filme.mkv"):
            path = self._file(name)
            self.assertEqual(_Frame(path)._validated_convert_source(), path)

    def test_a_mode_for_the_other_kind_of_media_is_explained_and_not_started(self):
        frame = _Frame(self._file("faixa.mp3"))

        with patch.object(convert_frame, "ConvertDialog") as dialog:
            frame.on_convert_video_to_audio()

        dialog.assert_not_called()
        self.assertEqual(len(frame.announcements), 1)

        frame = _Frame(self._file("filme.mp4"))
        with patch.object(convert_frame, "ConvertDialog") as dialog:
            frame.on_convert_audio_to_video()

        dialog.assert_not_called()
        self.assertEqual(len(frame.announcements), 1)

    def test_the_shortcut_offers_only_the_modes_that_fit_the_media(self):
        offered = {}

        class _FakeChoiceDialog:
            def __init__(self, _parent, _message, _title, choices):
                offered["choices"] = choices

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def ShowModal(self):
                return convert_frame.wx.ID_CANCEL

        frame = _Frame(self._file("faixa.flac"))
        with patch.object(convert_frame.wx, "SingleChoiceDialog", _FakeChoiceDialog):
            frame.on_convert_current_media()

        self.assertEqual(
            offered["choices"],
            [options.mode_label(options.MODE_AUDIO_TO_AUDIO), options.mode_label(options.MODE_AUDIO_TO_VIDEO)],
        )


class ConvertFfmpegPromptTests(unittest.TestCase):
    def setUp(self):
        self.frame = _Frame()

    def test_no_prompt_when_ffmpeg_exists(self):
        with patch.object(convert_frame, "find_ffmpeg_directory", return_value=Path("C:\\ffmpeg")), patch.object(
            convert_frame.wx, "MessageBox"
        ) as message_box:
            self.assertFalse(self.frame._confirm_convert_ffmpeg())

        message_box.assert_not_called()

    def test_answers_map_to_install_or_give_up(self):
        wx = convert_frame.wx
        with patch.object(convert_frame, "find_ffmpeg_directory", return_value=None), patch.object(
            convert_frame, "ffmpeg_install_supported", return_value=True
        ):
            for answer, expected in ((wx.YES, True), (wx.NO, None)):
                with self.subTest(answer=answer), patch.object(wx, "MessageBox", return_value=answer):
                    self.assertIs(self.frame._confirm_convert_ffmpeg(), expected)

    def test_unsupported_platform_gives_up_with_a_message(self):
        with patch.object(convert_frame, "find_ffmpeg_directory", return_value=None), patch.object(
            convert_frame, "ffmpeg_install_supported", return_value=False
        ):
            self.assertIsNone(self.frame._confirm_convert_ffmpeg())

        self.assertEqual(len(self.frame.announcements), 1)


class ConvertOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.frame = _Frame()
        self.token = CancelToken()
        self.frame._convert_token = self.token

    def test_finished_conversion_announces_the_file_and_frees_the_slot(self):
        self.frame._on_conversion_finished(self.token, ConversionResult(path="D:\\a\\faixa.mp3"))

        self.assertFalse(self.frame._convert_in_progress())
        self.assertIn("faixa.mp3", self.frame.announcements[-1])

    def test_failure_and_cancel_release_the_slot(self):
        self.frame._on_conversion_failed(self.token, "Invalid data")
        self.assertIn("Invalid data", self.frame.announcements[-1])
        self.assertFalse(self.frame._convert_in_progress())

        self.frame._convert_token = self.token
        self.frame._on_conversion_cancelled(self.token)
        self.assertFalse(self.frame._convert_in_progress())

    def test_a_stale_result_does_not_touch_a_newer_conversion(self):
        newer = CancelToken()
        self.frame._convert_token = newer

        self.frame._on_conversion_failed(self.token, "old")

        self.assertIs(self.frame._convert_token, newer)
        self.assertFalse(self.frame.announcements)

    def test_a_running_conversion_offers_to_cancel(self):
        self.frame._convert_percent = 30
        media_path = str(Path(tempfile.gettempdir()) / "x.mp3")

        with patch.object(convert_frame.wx, "MessageBox", return_value=convert_frame.wx.YES) as message_box:
            self.frame._begin_conversion(options.MODE_AUDIO_TO_AUDIO, source_path=media_path)

        self.assertIn("30%", message_box.call_args.args[0])
        self.assertTrue(self.token.cancelled)

    def test_shutdown_cancels_a_running_conversion(self):
        self.frame._shutdown_convert()

        self.assertTrue(self.token.cancelled)


class DialogFormatTests(unittest.TestCase):
    def test_video_container_choices_leave_out_the_source_format(self):
        formats = target_formats_for(options.MODE_VIDEO_TO_VIDEO, "C:\\v\\filme.MP4")

        self.assertNotIn("mp4", formats)
        self.assertIn("mkv", formats)

    def test_other_modes_offer_their_full_list(self):
        self.assertEqual(target_formats_for(options.MODE_AUDIO_TO_AUDIO, "a.mp3"), options.AUDIO_FORMAT_IDS)
        self.assertEqual(target_formats_for(options.MODE_VIDEO_TO_AUDIO, "a.mp4"), options.AUDIO_FORMAT_IDS)
        self.assertEqual(target_formats_for(options.MODE_AUDIO_TO_VIDEO, "a.mp3"), options.AUDIO_TO_VIDEO_FORMATS)


class ConvertDialogDestinationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = convert_frame.wx.App.Get() or convert_frame.wx.App()

    def _dialog(self, **kwargs):
        dialog = ConvertDialog(None, options.MODE_AUDIO_TO_AUDIO, SOURCE_FILE, **kwargs)
        self.addCleanup(dialog.Destroy)
        return dialog

    def test_by_default_it_saves_next_to_the_original_and_the_folder_field_is_off(self):
        dialog = self._dialog(other_directory=OTHER_DIR)

        self.assertEqual(dialog.get_request().output_directory, SOURCE_DIR)
        self.assertFalse(dialog.directory_ctrl.IsEnabled())
        self.assertFalse(dialog.directory_ctrl.browse_button.IsEnabled())

    def test_choosing_another_folder_enables_the_field_and_uses_it(self):
        dialog = self._dialog(other_directory=OTHER_DIR)

        dialog.destination_choice.SetSelection(1)
        dialog._refresh_destination_controls()

        self.assertTrue(dialog.directory_ctrl.IsEnabled())
        self.assertTrue(dialog.directory_ctrl.browse_button.IsEnabled())
        self.assertEqual(dialog.get_request().output_directory, OTHER_DIR)
        self.assertEqual(dialog.other_directory(), OTHER_DIR)

    def test_another_folder_left_empty_is_not_accepted(self):
        dialog = self._dialog()
        dialog.destination_choice.SetSelection(1)
        dialog._refresh_destination_controls()

        with patch.object(convert_frame.wx, "MessageBox") as message_box, patch.object(dialog, "EndModal") as end_modal:
            dialog._on_confirm(None)

        message_box.assert_called_once()
        end_modal.assert_not_called()

    def test_the_same_folder_option_needs_no_typed_folder(self):
        dialog = self._dialog()

        with patch.object(dialog, "EndModal") as end_modal:
            dialog._on_confirm(None)

        end_modal.assert_called_once()


if __name__ == "__main__":
    unittest.main()
