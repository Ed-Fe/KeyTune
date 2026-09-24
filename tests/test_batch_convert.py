import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from player.convert import options
from player.convert.plan import ConvertRequest, build_batch_requests, modes_for_sources
from player.convert.runner import ConversionCancelled, ConversionResult, run_conversion
from player.download.ffmpeg import FFMPEG_EXECUTABLE_NAME, find_ffmpeg_directory
from player.frames import convert as convert_frame
from player.frames.convert import FrameConvertMixin
from player.process_control import CancelToken


class BatchPlanTests(unittest.TestCase):
    def test_modes_are_offered_only_for_the_kinds_present(self):
        self.assertEqual(
            modes_for_sources(["a.mp3", "b.flac"]),
            {options.MODE_AUDIO_TO_AUDIO: 2, options.MODE_AUDIO_TO_VIDEO: 2},
        )
        self.assertEqual(
            modes_for_sources(["a.mp3", "v.mp4", "notas.txt"]),
            {
                options.MODE_AUDIO_TO_AUDIO: 1,
                options.MODE_AUDIO_TO_VIDEO: 1,
                options.MODE_VIDEO_TO_AUDIO: 1,
                options.MODE_VIDEO_TO_VIDEO: 1,
            },
        )
        self.assertEqual(modes_for_sources(["notas.txt"]), {})

    def test_same_folder_sends_each_file_next_to_its_original(self):
        template = ConvertRequest(options.MODE_AUDIO_TO_AUDIO, "x.mp3", "IGNORED", "flac")
        first = os.path.join("D:\\", "um", "a.mp3")
        second = os.path.join("D:\\", "dois", "b.wav")

        requests, skipped = build_batch_requests(template, [first, second], same_folder=True)

        self.assertEqual(skipped, 0)
        self.assertEqual([r.source_path for r in requests], [first, second])
        self.assertEqual([r.output_directory for r in requests], [os.path.dirname(first), os.path.dirname(second)])
        self.assertTrue(all(r.target_format == "flac" for r in requests))

    def test_another_folder_is_shared_by_every_file(self):
        template = ConvertRequest(options.MODE_AUDIO_TO_AUDIO, "x.mp3", "E:\\Saida", "mp3")

        requests, _skipped = build_batch_requests(template, ["D:\\a.wav", "D:\\b.flac"], same_folder=False)

        self.assertEqual({r.output_directory for r in requests}, {"E:\\Saida"})

    def test_files_of_the_wrong_kind_or_already_in_the_target_container_are_skipped(self):
        template = ConvertRequest(options.MODE_VIDEO_TO_VIDEO, "x.mp4", "", "mkv")

        requests, skipped = build_batch_requests(
            template, ["D:\\a.mp4", "D:\\b.mkv", "D:\\c.mp3", "D:\\d.avi"], same_folder=True
        )

        self.assertEqual([os.path.basename(r.source_path) for r in requests], ["a.mp4", "d.avi"])
        self.assertEqual(skipped, 2)


class _Frame(FrameConvertMixin):
    def __init__(self):
        self.announcements = []
        self.statuses = []
        self._initialize_convert_state()

    def _announce(self, message):
        self.announcements.append(message)

    def _set_status_message(self, message, *, auto_clear_ms=6000):
        self.statuses.append(message)


class SelectionFlowTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.dir = Path(self._temp.name)

    def _file(self, name):
        path = self.dir / name
        path.write_bytes(b"x")
        return str(path)

    def _entries(self, *names):
        return [(self._file(name), name) for name in names]

    def _choose(self, mode_index):
        offered = {}

        class _Dialog:
            def __init__(self, _parent, _message, _title, choices):
                offered["choices"] = choices

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def ShowModal(self):
                return convert_frame.wx.ID_OK

            def GetSelection(self):
                return mode_index

        return offered, _Dialog

    def test_nothing_convertible_selected_is_announced(self):
        frame = _Frame()
        entries = self._entries("notas.txt") + [("https://www.youtube.com/watch?v=abc123DEF45", "YT")]

        with patch.object(convert_frame, "selected_list_entries", return_value=entries):
            frame.on_convert_selection()

        self.assertEqual(len(frame.announcements), 1)

    def test_several_files_offer_modes_with_counts_and_start_a_batch(self):
        frame = _Frame()
        entries = self._entries("a.mp3", "b.wav", "c.mp4")
        offered, dialog_class = self._choose(0)

        with patch.object(convert_frame, "selected_list_entries", return_value=entries), patch.object(
            convert_frame.wx, "SingleChoiceDialog", dialog_class
        ), patch.object(frame, "_begin_batch_conversion") as begin_batch:
            frame.on_convert_selection()

        self.assertEqual(len(offered["choices"]), 4)
        self.assertIn("2", offered["choices"][0])
        mode, paths = begin_batch.call_args.args[:2]
        self.assertEqual(mode, options.MODE_AUDIO_TO_AUDIO)
        self.assertEqual([os.path.basename(p) for p in paths], ["a.mp3", "b.wav"])
        self.assertEqual(begin_batch.call_args.kwargs["total_selected"], 3)

    def test_a_single_selected_file_uses_the_single_flow(self):
        frame = _Frame()
        entries = self._entries("a.mp3")
        _offered, dialog_class = self._choose(1)

        with patch.object(convert_frame, "selected_list_entries", return_value=entries), patch.object(
            convert_frame.wx, "SingleChoiceDialog", dialog_class
        ), patch.object(frame, "_begin_conversion") as begin_single:
            frame.on_convert_selection()

        self.assertEqual(begin_single.call_args.args[0], options.MODE_AUDIO_TO_VIDEO)

    def test_the_batch_dialog_builds_one_request_per_file(self):
        frame = _Frame()
        first = self._file("a.mp3")
        second = self._file("b.wav")

        class _FakeDialog:
            def __init__(self, *_args, **kwargs):
                self.item_count = kwargs["item_count"]

            def ShowModal(self):
                return convert_frame.wx.ID_OK

            def get_request(self):
                return ConvertRequest(options.MODE_AUDIO_TO_AUDIO, first, "", "flac")

            def saves_in_same_folder(self):
                return True

            def other_directory(self):
                return ""

            def Destroy(self):
                pass

        with patch.object(convert_frame, "ConvertDialog", _FakeDialog), patch.object(
            frame, "_confirm_convert_ffmpeg", return_value=False
        ), patch.object(frame, "_start_conversion") as start:
            frame._begin_batch_conversion(options.MODE_AUDIO_TO_AUDIO, [first, second], total_selected=3)

        requests = start.call_args.args[0]
        self.assertEqual(len(requests), 2)
        self.assertEqual(start.call_args.kwargs["skipped"], 1)


class BatchWorkerTests(unittest.TestCase):
    def _requests(self, count):
        return tuple(
            ConvertRequest(options.MODE_AUDIO_TO_AUDIO, f"D:\\f{i}.mp3", "D:\\", "flac") for i in range(count)
        )

    def _run(self, requests, side_effect, skipped=0):
        frame = _Frame()
        token = CancelToken()
        frame._convert_token = token
        frame._convert_batch_total = len(requests)
        with patch.object(convert_frame.wx, "CallAfter", side_effect=lambda fn, *args: fn(*args)), patch.object(
            convert_frame, "find_ffmpeg_directory", return_value=Path("C:\\ffmpeg")
        ), patch.object(convert_frame, "run_conversion", side_effect=side_effect) as run:
            frame._convert_worker(requests, token, False, skipped)
        return frame, run

    def test_converts_every_file_and_summarizes(self):
        frame, run = self._run(self._requests(3), [ConversionResult(f"D:\\o{i}.flac") for i in range(3)], skipped=1)

        self.assertEqual(run.call_count, 3)
        self.assertIn("3", frame.announcements[-1])
        self.assertIn("1", frame.announcements[-1])
        self.assertFalse(frame._convert_in_progress())

    def test_a_failing_file_does_not_stop_the_rest(self):
        frame, _run = self._run(
            self._requests(3), [ConversionResult("D:\\o0.flac"), RuntimeError("Invalid data"), ConversionResult("D:\\o2.flac")]
        )

        self.assertIn("2 de 3", frame.announcements[-1])

    def test_all_failing_reports_the_reason(self):
        frame, _run = self._run(self._requests(2), [RuntimeError("Invalid data")] * 2)

        self.assertIn("Invalid data", frame.announcements[-1])

    def test_cancelling_reports_the_partial_result(self):
        def side_effect(*_args, **_kwargs):
            if side_effect.calls:
                raise ConversionCancelled("cancelado")
            side_effect.calls += 1
            return ConversionResult("D:\\o0.flac")

        side_effect.calls = 0
        frame, run = self._run(self._requests(3), side_effect)

        self.assertEqual(run.call_count, 2)
        self.assertIn("1 de 3", frame.announcements[-1])

    def test_a_single_request_keeps_the_single_messages(self):
        frame, _run = self._run(self._requests(1), [ConversionResult("D:\\musica.flac")])

        self.assertIn("musica.flac", frame.announcements[-1])

    def test_queue_position_shows_in_status_and_cancel_prompt(self):
        frame = _Frame()
        token = CancelToken()
        frame._convert_token = token
        frame._convert_batch_total = 4
        frame._on_convert_item_started(token, 2)

        self.assertIn("2", frame.statuses[-1])
        with patch.object(convert_frame.wx, "MessageBox", return_value=convert_frame.wx.YES) as message_box:
            frame._offer_to_cancel_conversion()

        self.assertIn("2", message_box.call_args.args[0])
        self.assertTrue(token.cancelled)


def _real_ffmpeg_directory():
    directory = find_ffmpeg_directory()
    if directory is None:
        return None
    try:
        encoders = subprocess.run(
            [str(directory / FFMPEG_EXECUTABLE_NAME), "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=20,
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    return directory if all(name in encoders for name in ("flac", "libmp3lame")) else None


@unittest.skipUnless(_real_ffmpeg_directory(), "FFmpeg completo não está disponível")
class RealBatchConversionTests(unittest.TestCase):
    def test_a_batch_converts_each_file_into_its_own_or_a_shared_folder(self):
        ffmpeg_dir = _real_ffmpeg_directory()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "um").mkdir()
            (root / "dois").mkdir()
            sources = [root / "um" / "a.wav", root / "dois" / "b.wav"]
            for source in sources:
                subprocess.run(
                    [
                        str(ffmpeg_dir / FFMPEG_EXECUTABLE_NAME), "-hide_banner", "-loglevel", "error", "-y",
                        "-f", "lavfi", "-i", "sine=frequency=440:duration=1", str(source),
                    ],
                    check=True,
                    timeout=60,
                )
            template = ConvertRequest(options.MODE_AUDIO_TO_AUDIO, str(sources[0]), str(root / "todos"), "flac")

            same, _ = build_batch_requests(template, [str(s) for s in sources], same_folder=True)
            shared, _ = build_batch_requests(template, [str(s) for s in sources], same_folder=False)
            same_paths = [run_conversion(r, ffmpeg_directory=ffmpeg_dir).path for r in same]
            shared_paths = [run_conversion(r, ffmpeg_directory=ffmpeg_dir).path for r in shared]

            self.assertEqual([Path(p).parent for p in same_paths], [root / "um", root / "dois"])
            self.assertEqual({Path(p).parent for p in shared_paths}, {root / "todos"})
            self.assertTrue(all(Path(p).is_file() for p in same_paths + shared_paths))


if __name__ == "__main__":
    unittest.main()
