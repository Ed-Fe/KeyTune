from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from player.download.plan import (
    DownloadChoice,
    DownloadItem,
    DownloadPlan,
    safe_folder_name,
    select_download_items,
    unique_folder_name,
)
from player.download.runner import DownloadCancelled, DownloadCancelToken, DownloadProgress, DownloadResult
from player.frames import download as download_frame
from player.frames.download import FrameDownloadMixin
from player.preferences.models import AppSettings

WATCH = "https://www.youtube.com/watch?v={}"


def _entries(*ids):
    return [(WATCH.format(video_id), f"Faixa {video_id}") for video_id in ids]


class SelectDownloadItemsTests(unittest.TestCase):
    def test_keeps_remote_items_and_counts_the_rest_as_skipped(self):
        entries = _entries("a1", "b2") + [
            ("C:\\musicas\\local.mp3", "Local"),
            ("https://example.com/x.mp3", "Site"),
            ("https://radio.example.com/stream#keytune-radio=abc", "Rádio"),
            ("https://example.com/lista.m3u", "Playlist"),
        ]

        selection = select_download_items(entries)

        self.assertEqual([item.title for item in selection.items], ["Faixa a1", "Faixa b2", "Site"])
        self.assertEqual(selection.skipped, 3)

    def test_a_repeated_track_is_downloaded_once(self):
        selection = select_download_items(_entries("a1", "a1", "b2"))

        self.assertEqual(len(selection.items), 2)
        self.assertEqual(selection.skipped, 0)

    def test_a_long_queue_is_kept_whole(self):
        selection = select_download_items(_entries(*[f"v{i:04d}" for i in range(500)]))

        self.assertEqual(len(selection.items), 500)

    def test_an_entry_may_say_which_subfolder_it_goes_to(self):
        entries = [
            (WATCH.format("a1"), "A", "Rock"),
            (WATCH.format("a1"), "A", "Rock"),
            (WATCH.format("a1"), "A", "Pop"),
            (WATCH.format("a1"), "A"),
        ]

        selection = select_download_items(entries)

        # A mesma faixa entra uma vez em cada pasta, para cada playlist ficar completa.
        self.assertEqual([item.folder for item in selection.items], ["Rock", "Pop", ""])

    def test_folder_names_do_not_repeat_within_a_queue(self):
        used = set()

        self.assertEqual(
            [unique_folder_name(name, used) for name in ("Mix", "mix", "Mix", "Outra")],
            ["Mix", "mix (2)", "Mix (3)", "Outra"],
        )

    def test_safe_folder_name_removes_what_windows_refuses(self):
        self.assertEqual(safe_folder_name('Rock: "Hits" / 2024?'), "Rock_ _Hits_ _ 2024_")
        self.assertEqual(safe_folder_name("  ...  "), "Playlist")
        self.assertEqual(safe_folder_name(None), "Playlist")
        self.assertEqual(safe_folder_name("Fim."), "Fim")
        self.assertLessEqual(len(safe_folder_name("x" * 300)), 100)


class _Frame(FrameDownloadMixin):
    def __init__(self, *, entries=None, playlist_items=None, title="Minha lista", settings=None):
        self.settings = settings or AppSettings(download_always_ask=False, download_directory="D:\\Musicas")
        self._entries = entries or []
        self._playlist = SimpleNamespace(
            title=title,
            items=list(playlist_items or []),
            browser_item_labels=[f"Faixa {i}" for i in range(len(playlist_items or []))],
            is_folder_tab=False,
        )
        self.announcements = []
        self.statuses = []
        self.started = []
        self._initialize_download_state()

    def _get_playlist_state(self):
        return self._playlist

    def _announce(self, message):
        self.announcements.append(message)

    def _set_status_message(self, message, *, auto_clear_ms=6000):
        self.statuses.append(message)

    def _save_settings(self):
        return True

    def _start_download(self, items, choice, *, install_ffmpeg, folder_name=""):
        self.started.append((items, choice, install_ffmpeg, folder_name))


class BatchEntryPointTests(unittest.TestCase):
    def test_selection_starts_a_batch_after_confirmation(self):
        frame = _Frame()
        with patch.object(download_frame, "selected_list_entries", return_value=_entries("a1", "b2")), patch.object(
            download_frame.wx, "MessageBox", return_value=download_frame.wx.YES
        ) as message_box:
            frame.on_download_selection()

        items, choice, _install, folder_name = frame.started[0]
        self.assertEqual(len(items), 2)
        self.assertEqual(folder_name, "")
        self.assertIn("2", message_box.call_args.args[0])
        self.assertIn("D:\\Musicas", message_box.call_args.args[0])

    def test_declining_the_confirmation_starts_nothing(self):
        frame = _Frame()
        with patch.object(download_frame, "selected_list_entries", return_value=_entries("a1", "b2")), patch.object(
            download_frame.wx, "MessageBox", return_value=download_frame.wx.NO
        ):
            frame.on_download_selection()

        self.assertFalse(frame.started)

    def test_one_selected_item_needs_no_confirmation(self):
        frame = _Frame()
        with patch.object(download_frame, "selected_list_entries", return_value=_entries("a1")), patch.object(
            download_frame.wx, "MessageBox"
        ) as message_box:
            frame.on_download_selection()

        message_box.assert_not_called()
        self.assertEqual(len(frame.started[0][0]), 1)

    def test_nothing_selected_or_nothing_downloadable_is_announced(self):
        frame = _Frame()
        with patch.object(download_frame, "selected_list_entries", return_value=[]):
            frame.on_download_selection()
        with patch.object(
            download_frame, "selected_list_entries", return_value=[("C:\\musicas\\a.mp3", "Local")]
        ):
            frame.on_download_selection()

        self.assertFalse(frame.started)
        self.assertEqual(len(frame.announcements), 2)

    def test_skipped_items_are_mentioned_in_the_confirmation(self):
        frame = _Frame()
        entries = _entries("a1", "b2") + [("C:\\musicas\\a.mp3", "Local")]
        with patch.object(download_frame, "selected_list_entries", return_value=entries), patch.object(
            download_frame.wx, "MessageBox", return_value=download_frame.wx.YES
        ) as message_box:
            frame.on_download_selection()

        self.assertIn("1", message_box.call_args.args[0])
        self.assertEqual(len(frame.started[0][0]), 2)

    def test_whole_playlist_goes_to_a_folder_named_after_it(self):
        frame = _Frame(playlist_items=[WATCH.format("a1"), WATCH.format("b2"), WATCH.format("c3")], title='Rock: "Hits"')
        with patch.object(download_frame.wx, "MessageBox", return_value=download_frame.wx.YES):
            frame.on_download_playlist()

        items, _choice, _install, folder_name = frame.started[0]
        self.assertEqual(len(items), 3)
        self.assertEqual(folder_name, "Rock_ _Hits_")

    def test_a_folder_tab_or_empty_playlist_has_nothing_to_download(self):
        frame = _Frame()
        frame.on_download_playlist()
        frame._playlist.is_folder_tab = True
        frame._playlist.items = [WATCH.format("a1")]
        frame.on_download_playlist()

        self.assertFalse(frame.started)
        self.assertEqual(len(frame.announcements), 2)

    def test_entries_from_other_screens_use_the_same_flow(self):
        frame = _Frame()
        with patch.object(download_frame.wx, "MessageBox", return_value=download_frame.wx.YES):
            frame.download_media_entries(_entries("a1", "b2"))

        self.assertEqual(len(frame.started[0][0]), 2)


class _WorkerFrame(_Frame):
    """Roda o worker de verdade, com as chamadas de interface executadas na hora."""

    def run_worker(
        self, items, run_download_side_effect, *, install_ffmpeg=False, folder_name="Lista", parallel=1
    ):
        token = DownloadCancelToken()
        self._download_token = token
        self._download_batch_total = len(items)
        choice = DownloadChoice("audio", "original", "best", 0, "D:\\Musicas")
        fake_auth = SimpleNamespace(cookie_header="", yt_dlp_http_headers={})
        with patch.object(download_frame.wx, "CallAfter", side_effect=lambda fn, *args: fn(*args)), patch(
            "player.youtube_music.dependencies.ensure_yt_dlp_executable_available"
        ), patch("player.youtube_music.auth.load_saved_playback_auth", return_value=fake_auth), patch(
            "player.youtube_music.yt_dlp_runtime.find_all_available_javascript_runtimes", return_value={}
        ), patch.object(download_frame, "find_ffmpeg_directory", return_value=Path("C:\\ffmpeg")), patch.object(
            download_frame, "PARALLEL_DOWNLOADS", parallel
        ), patch.object(download_frame, "run_download", side_effect=run_download_side_effect) as run_download:
            self._download_worker(tuple(items), choice, token, install_ffmpeg, folder_name)
        return token, run_download


def _result(name):
    return DownloadResult(paths=(f"D:\\Musicas\\Lista\\{name}.webm",))


class BatchWorkerTests(unittest.TestCase):
    def setUp(self):
        self.items = [DownloadItem(WATCH.format(i), f"Faixa {i}") for i in ("a1", "b2", "c3")]

    def test_downloads_every_item_into_the_playlist_folder_and_summarizes(self):
        frame = _WorkerFrame()

        token, run_download = frame.run_worker(self.items, [_result("a"), _result("b"), _result("c")])

        self.assertEqual(run_download.call_count, 3)
        directories = {call.args[1].directory for call in run_download.call_args_list}
        self.assertEqual(directories, {"D:\\Musicas\\Lista"})
        self.assertFalse(frame._download_in_progress())
        self.assertIn("3", frame.announcements[-1])
        self.assertNotIn("falharam", frame.announcements[-1])

    def test_each_playlist_goes_to_its_subfolder_and_loose_items_to_the_chosen_folder(self):
        frame = _WorkerFrame()
        items = [
            DownloadItem(WATCH.format("a1"), "Faixa a1", "Rock"),
            DownloadItem(WATCH.format("b2"), "Faixa b2", "Pop"),
            DownloadItem(WATCH.format("c3"), "Faixa c3"),
        ]
        results = [
            DownloadResult(paths=("D:\Musicas\Rock\a.webm",)),
            DownloadResult(paths=("D:\Musicas\Pop\b.webm",)),
            DownloadResult(paths=("D:\Musicas\c.webm",)),
        ]

        _token, run_download = frame.run_worker(items, results, folder_name="")

        directories = [call.args[1].directory for call in run_download.call_args_list]
        self.assertEqual(directories, ["D:\Musicas\Rock", "D:\Musicas\Pop", "D:\Musicas"])
        # O resumo cita a pasta escolhida, que contém as subpastas.
        self.assertTrue(frame.announcements[-1].rstrip(".").endswith("D:\Musicas"), frame.announcements[-1])

    def test_a_failing_item_does_not_stop_the_rest(self):
        frame = _WorkerFrame()

        frame.run_worker(self.items, [_result("a"), RuntimeError("Video unavailable"), _result("c")])

        message = frame.announcements[-1]
        self.assertIn("2 de 3", message)
        self.assertIn("1", message)
        self.assertFalse(frame._download_in_progress())

    def test_when_every_item_fails_the_reason_is_reported(self):
        frame = _WorkerFrame()

        frame.run_worker(self.items, [RuntimeError("HTTP 429")] * 3)

        self.assertIn("HTTP 429", frame.announcements[-1])

    def test_cancelling_stops_the_queue_and_reports_the_partial_result(self):
        frame = _WorkerFrame()

        def side_effect(*args, **kwargs):
            if side_effect.calls == 1:
                raise DownloadCancelled("cancelado")
            side_effect.calls += 1
            return _result("a")

        side_effect.calls = 0
        _token, run_download = frame.run_worker(self.items, side_effect)

        self.assertEqual(run_download.call_count, 2)
        self.assertIn("1 de 3", frame.announcements[-1])
        self.assertFalse(frame._download_in_progress())

    def test_items_of_a_queue_are_downloaded_at_the_same_time(self):
        frame = _WorkerFrame()
        together = threading.Barrier(3, timeout=5)

        def side_effect(url, *args, **kwargs):
            # Só passa se os três downloads estiverem rodando juntos.
            together.wait()
            return _result(url[-2:])

        _token, run_download = frame.run_worker(self.items, side_effect, parallel=3)

        self.assertEqual(run_download.call_count, 3)
        self.assertIn("3", frame.announcements[-1])
        self.assertNotIn("falharam", frame.announcements[-1])

    def test_items_of_a_queue_report_the_position_instead_of_their_own_progress(self):
        frame = _WorkerFrame()

        _token, run_download = frame.run_worker(self.items, [_result("a"), _result("b"), _result("c")])

        self.assertIsNone(run_download.call_args.kwargs["progress_callback"])
        self.assertTrue(any("3 de 3" in status for status in frame.statuses), frame.statuses)

    def test_a_single_item_keeps_the_single_download_messages(self):
        frame = _WorkerFrame()

        frame.run_worker(self.items[:1], [_result("a")])

        self.assertIn("a.webm", frame.announcements[-1])

    def test_a_single_failing_item_reports_the_failure(self):
        frame = _WorkerFrame()

        frame.run_worker(self.items[:1], [RuntimeError("Sign in required")])

        self.assertIn("Sign in required", frame.announcements[-1])

    def test_status_and_cancel_prompt_show_the_position_in_the_queue(self):
        frame = _Frame()
        token = DownloadCancelToken()
        frame._download_token = token
        frame._download_batch_total = 5
        frame._on_download_item_started(token, 3)

        self.assertIn("3", frame.statuses[-1])
        self.assertIn("5", frame._download_status_text(40))
        with patch.object(download_frame.wx, "MessageBox", return_value=download_frame.wx.YES) as message_box:
            frame._offer_to_cancel_download()

        self.assertIn("3", message_box.call_args.args[0])
        self.assertTrue(token.cancelled)

    def test_progress_uses_the_queue_position(self):
        frame = _Frame()
        frame._download_batch_total = 4
        frame._download_batch_index = 2

        with patch.object(download_frame.wx, "CallAfter") as call_after:
            frame._on_download_progress(DownloadProgress(50, 100))

        self.assertEqual(frame._download_percent, 50)
        self.assertEqual(call_after.call_args.args, (frame._update_download_progress, 50))

        frame._download_token = DownloadCancelToken()
        frame._update_download_progress(50)
        self.assertIn("2 de 4", frame.statuses[-1])


if __name__ == "__main__":
    unittest.main()
