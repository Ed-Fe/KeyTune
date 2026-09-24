from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from player.download.plan import DownloadChoice, DownloadPlan
from player.download.runner import DownloadCancelToken, DownloadResult
from player.frames import download as download_frame
from player.frames.download import FrameDownloadMixin
from player.preferences.models import AppSettings

YOUTUBE_URL = "https://www.youtube.com/watch?v=abc123DEF45"


class _Frame(FrameDownloadMixin):
    def __init__(self, media_path=YOUTUBE_URL, *, live=False, settings=None):
        self.settings = settings or AppSettings(download_always_ask=False)
        self._state = SimpleNamespace(
            current_media_path=media_path,
            browser_item_labels=["Faixa de teste"],
            current_index=0,
        )
        self.player = Mock()
        self.player.get_media.return_value = SimpleNamespace(is_live=live)
        self.announcements = []
        self.statuses = []
        self.started = []
        self._initialize_download_state()

    def _get_active_playlist_state(self):
        return self._state

    def _announce(self, message):
        self.announcements.append(message)

    def _set_status_message(self, message, *, auto_clear_ms=6000):
        self.statuses.append(message)

    def _save_settings(self):
        return True

    def _start_download(self, items, choice, *, install_ffmpeg, folder_name=""):
        self.started.append((items, choice, install_ffmpeg, folder_name))


class DownloadCommandTests(unittest.TestCase):
    def test_starts_a_download_with_the_saved_options_when_the_dialog_is_off(self):
        settings = AppSettings(
            download_always_ask=False,
            download_kind="audio",
            download_audio_quality="original",
            download_directory="D:\\Musicas",
        )
        frame = _Frame(settings=settings)

        frame.on_download_current_media()

        items, choice, install_ffmpeg, folder_name = frame.started[0]
        self.assertEqual([item.url for item in items], [YOUTUBE_URL])
        self.assertEqual(choice.directory, "D:\\Musicas")
        self.assertEqual(items[0].title, "Faixa de teste")
        self.assertFalse(install_ffmpeg)
        self.assertEqual(folder_name, "")

    def test_announces_when_nothing_is_playing(self):
        frame = _Frame(media_path="")

        frame.on_download_current_media()

        self.assertFalse(frame.started)
        self.assertEqual(len(frame.announcements), 1)

    def test_refuses_a_live_broadcast(self):
        frame = _Frame(live=True)

        frame.on_download_current_media()

        self.assertFalse(frame.started)
        self.assertEqual(len(frame.announcements), 1)

    def test_local_files_and_other_sites_are_not_downloaded(self):
        for media_path in ("C:\\Musicas\\faixa.mp3", "https://radio.example.com/stream"):
            with self.subTest(media_path=media_path):
                frame = _Frame(media_path=media_path)

                frame.on_download_current_media()

                self.assertFalse(frame.started)
                self.assertEqual(len(frame.announcements), 1)

    def test_a_running_download_offers_to_cancel_instead_of_starting_another(self):
        frame = _Frame()
        token = DownloadCancelToken()
        frame._download_token = token
        frame._download_percent = 40

        with patch.object(download_frame.wx, "MessageBox", return_value=download_frame.wx.YES) as message_box:
            frame.on_download_current_media()

        self.assertIn("40%", message_box.call_args.args[0])
        self.assertTrue(token.cancelled)
        self.assertFalse(frame.started)

    def test_declining_the_cancel_prompt_keeps_the_download_running(self):
        frame = _Frame()
        token = DownloadCancelToken()
        frame._download_token = token

        with patch.object(download_frame.wx, "MessageBox", return_value=download_frame.wx.NO):
            frame.on_download_current_media()

        self.assertFalse(token.cancelled)


class FFmpegPromptTests(unittest.TestCase):
    def setUp(self):
        self.frame = _Frame()
        self.mp3 = DownloadChoice("audio", "mp3_192", "best", 0, "D:\\a")
        self.original = DownloadChoice("audio", "original", "best", 0, "D:\\a")

    def test_no_prompt_when_the_choice_does_not_need_ffmpeg(self):
        with patch.object(download_frame.wx, "MessageBox") as message_box:
            self.assertFalse(self.frame._confirm_ffmpeg_installation(self.original))

        message_box.assert_not_called()

    def test_no_prompt_when_ffmpeg_is_already_available(self):
        with patch.object(download_frame, "find_ffmpeg_directory", return_value=Path("C:\\ffmpeg")), patch.object(
            download_frame.wx, "MessageBox"
        ) as message_box:
            self.assertFalse(self.frame._confirm_ffmpeg_installation(self.mp3))

        message_box.assert_not_called()

    def test_prompt_answers_map_to_install_original_or_cancel(self):
        wx = download_frame.wx
        with patch.object(download_frame, "find_ffmpeg_directory", return_value=None), patch.object(
            download_frame, "ffmpeg_install_supported", return_value=True
        ):
            for answer, expected in ((wx.YES, True), (wx.NO, False), (wx.CANCEL, None)):
                with self.subTest(answer=answer), patch.object(wx, "MessageBox", return_value=answer):
                    self.assertIs(self.frame._confirm_ffmpeg_installation(self.mp3), expected)

    def test_unsupported_platform_falls_back_without_prompting(self):
        with patch.object(download_frame, "find_ffmpeg_directory", return_value=None), patch.object(
            download_frame, "ffmpeg_install_supported", return_value=False
        ), patch.object(download_frame.wx, "MessageBox") as message_box:
            self.assertFalse(self.frame._confirm_ffmpeg_installation(self.mp3))

        message_box.assert_not_called()
        self.assertEqual(len(self.frame.announcements), 1)


class DownloadOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.frame = _Frame()
        self.token = DownloadCancelToken()
        self.frame._download_token = self.token
        self.plan = DownloadPlan("bestaudio/best", (), True, reduced_without_ffmpeg=False)
        self.choice = DownloadChoice("audio", "original", "best", 0, "D:\\a")

    def test_finished_download_announces_the_file_and_clears_the_state(self):
        result = DownloadResult(paths=("D:\\a\\Faixa [id].webm",))

        self.frame._on_download_finished(self.token, self.choice, self.plan, result)

        self.assertFalse(self.frame._download_in_progress())
        self.assertIn("Faixa [id].webm", self.frame.announcements[-1])

    def test_finished_video_mentions_a_lower_resolution_than_requested(self):
        choice = DownloadChoice("video", "original", "1080", 0, "D:\\a")
        result = DownloadResult(paths=("D:\\a\\v.mp4",), height=720)

        self.frame._on_download_finished(self.token, choice, self.plan, result)

        self.assertIn("1080p", self.frame.announcements[-1])
        self.assertIn("720p", self.frame.announcements[-1])

    def test_finished_without_ffmpeg_says_the_original_quality_was_used(self):
        plan = DownloadPlan("bestaudio/best", (), True, reduced_without_ffmpeg=True)
        result = DownloadResult(paths=("D:\\a\\a.webm",))

        self.frame._on_download_finished(self.token, self.choice, plan, result)

        self.assertIn("FFmpeg", self.frame.announcements[-1])

    def test_failure_and_cancel_report_and_release_the_slot(self):
        self.frame._on_download_failed(self.token, "Video unavailable")
        self.assertIn("Video unavailable", self.frame.announcements[-1])
        self.assertFalse(self.frame._download_in_progress())

        self.frame._download_token = self.token
        self.frame._on_download_cancelled(self.token)
        self.assertFalse(self.frame._download_in_progress())
        self.assertEqual(len(self.frame.announcements), 2)

    def test_a_stale_result_does_not_touch_a_newer_download(self):
        newer = DownloadCancelToken()
        self.frame._download_token = newer

        self.frame._on_download_failed(self.token, "old failure")

        self.assertIs(self.frame._download_token, newer)
        self.assertFalse(self.frame.announcements)

    def test_shutdown_cancels_a_running_download(self):
        self.frame._shutdown_download()

        self.assertTrue(self.token.cancelled)


if __name__ == "__main__":
    unittest.main()
