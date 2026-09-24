from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from player.download.plan import download_file_stem, unique_file_stem
from player.download.runner import FILENAME_TEMPLATE, build_command, output_template
from player.download.plan import DownloadChoice, DownloadPlan
from player.frames import download as download_frame
from player.frames.convert import FrameConvertMixin
from player.frames.download import FrameDownloadMixin
from player.frames.task_progress import TaskProgressMixin
from player.download.runner import DownloadCancelToken
from player.process_control import CancelToken


class FileNameTests(unittest.TestCase):
    def test_the_stem_is_the_title_shown_in_the_player(self):
        title = "Matheus & Kauan - Topic \u2014 Chora De Tabela (Ao Vivo)"

        self.assertEqual(download_file_stem(title), title)

    def test_characters_windows_refuses_are_replaced_and_spaces_collapsed(self):
        self.assertEqual(download_file_stem('  AC/DC:  "Hells"?  '), "AC_DC_ _Hells__")
        self.assertEqual(download_file_stem("Fim..."), "Fim")

    def test_no_usable_title_falls_back_to_the_yt_dlp_name(self):
        for value in ("", None, "  ", "https://www.youtube.com/watch?v=abc123DEF45", "watch?v=abc123DEF45"):
            with self.subTest(value=value):
                self.assertEqual(download_file_stem(value), "")

    def test_long_titles_are_cut(self):
        self.assertLessEqual(len(download_file_stem("x" * 500)), 180)

    def test_repeated_names_in_one_queue_get_a_number(self):
        used = set()

        self.assertEqual(unique_file_stem("Faixa", used), "Faixa")
        self.assertEqual(unique_file_stem("faixa", used), "faixa (2)")
        self.assertEqual(unique_file_stem("Faixa", used), "Faixa (3)")
        self.assertEqual(unique_file_stem("", used), "")

    def test_output_template_uses_the_stem_and_escapes_percent(self):
        self.assertEqual(output_template(""), FILENAME_TEMPLATE)
        self.assertEqual(output_template("100% Hits"), "100%% Hits.%(ext)s")

    def test_the_command_receives_the_output_name(self):
        plan = DownloadPlan("bestaudio/best", (), False, reduced_without_ffmpeg=False)
        choice = DownloadChoice("audio", "original", "best", 0, "D:\\")

        command = build_command("yt-dlp", "https://youtu.be/abc123DEF45", choice, plan, output_directory="D:\\", file_stem="Meu nome")

        self.assertEqual(command[command.index("--output") + 1], "Meu nome.%(ext)s")


class _FakeGauge:
    def __init__(self):
        self.shown = False
        self.value = None
        self.pulses = 0
        self.size = None

    def Show(self):
        self.shown = True

    def Hide(self):
        self.shown = False

    def SetValue(self, value):
        self.value = value

    def Pulse(self):
        self.pulses += 1

    def SetSize(self, *args):
        self.size = args


class _FakeStatusBar:
    def __init__(self):
        self.widths = None

    def SetStatusWidths(self, widths):
        self.widths = list(widths)

    def GetFieldRect(self, _field):
        return SimpleNamespace(x=100, y=0, width=180, height=20)


class _Host(TaskProgressMixin):
    def __init__(self):
        self._task_progress_gauge = _FakeGauge()
        self.status_bar = _FakeStatusBar()


class TaskProgressTests(unittest.TestCase):
    def test_the_bar_appears_with_a_value_and_hides_when_the_task_ends(self):
        host = _Host()

        host._set_task_progress("download", 42.7)

        self.assertTrue(host._task_progress_gauge.shown)
        self.assertEqual(host._task_progress_gauge.value, 42)
        self.assertEqual(host.status_bar.widths[1] > 0, True)

        host._clear_task_progress("download")

        self.assertFalse(host._task_progress_gauge.shown)
        self.assertEqual(host.status_bar.widths, [-1, 0])

    def test_an_unknown_percentage_pulses_instead_of_guessing(self):
        host = _Host()

        host._set_task_progress("download", None)

        self.assertTrue(host._task_progress_gauge.shown)
        self.assertEqual(host._task_progress_gauge.pulses, 1)

    def test_values_are_kept_within_zero_and_one_hundred(self):
        host = _Host()

        host._set_task_progress("download", 250)
        self.assertEqual(host._task_progress_gauge.value, 100)
        host._set_task_progress("download", -5)
        self.assertEqual(host._task_progress_gauge.value, 0)

    def test_two_tasks_share_the_bar_until_both_finish(self):
        host = _Host()

        host._set_task_progress("download", 30)
        host._set_task_progress("convert", 80)
        self.assertEqual(host._task_progress_gauge.value, 80)

        host._clear_task_progress("convert")
        self.assertTrue(host._task_progress_gauge.shown)
        host._set_task_progress("download", 35)
        self.assertEqual(host._task_progress_gauge.value, 35)

        host._clear_task_progress("download")
        self.assertFalse(host._task_progress_gauge.shown)

    def test_without_a_bar_every_call_is_harmless(self):
        host = TaskProgressMixin()

        host._set_task_progress("download", 10)
        host._clear_task_progress("download")


class _DownloadHost(FrameDownloadMixin):
    def __init__(self):
        self._initialize_download_state()
        self.progress = []
        self.statuses = []

    def _set_task_progress(self, source, percent):
        self.progress.append((source, percent))

    def _clear_task_progress(self, source):
        self.progress.append((source, "cleared"))

    def _set_status_message(self, message, *, auto_clear_ms=6000):
        self.statuses.append(message)

    def _announce(self, _message):
        pass


class DownloadProgressBarTests(unittest.TestCase):
    def setUp(self):
        self.host = _DownloadHost()
        self.token = DownloadCancelToken()
        self.host._download_token = self.token

    def test_a_single_download_shows_its_own_percentage(self):
        self.host._update_download_progress(40)

        self.assertEqual(self.host.progress[-1], ("download", 40))

    def test_a_queue_gives_each_item_an_equal_slice(self):
        self.host._download_batch_total = 4
        self.host._download_batch_index = 3

        self.host._update_download_progress(50)

        self.assertEqual(self.host.progress[-1], ("download", 62.5))

    def test_starting_the_first_item_is_indeterminate_and_later_ones_are_not(self):
        self.host._download_batch_total = 4
        self.host._on_download_item_started(self.token, 1)
        self.host._on_download_item_started(self.token, 3)

        self.assertEqual(self.host.progress, [("download", None), ("download", 50.0)])

    def test_processing_fills_the_current_item_and_finishing_clears_the_bar(self):
        self.host._download_batch_total = 2
        self.host._download_batch_index = 1
        self.host._on_download_processing()

        self.assertEqual(self.host.progress[-1], ("download", 50.0))

        self.host._finish_download_state(self.token)

        self.assertEqual(self.host.progress[-1], ("download", "cleared"))

    def test_a_late_update_after_the_download_ended_is_ignored(self):
        self.host._finish_download_state(self.token)
        before = list(self.host.progress)

        self.host._update_download_progress(90)
        self.host._on_download_processing()

        self.assertEqual(self.host.progress, before)


class _ConvertHost(FrameConvertMixin):
    def __init__(self):
        self._initialize_convert_state()
        self.progress = []
        self.statuses = []

    def _set_task_progress(self, source, percent):
        self.progress.append((source, percent))

    def _clear_task_progress(self, source):
        self.progress.append((source, "cleared"))

    def _set_status_message(self, message, *, auto_clear_ms=6000):
        self.statuses.append(message)


class ConvertProgressBarTests(unittest.TestCase):
    def test_conversion_progress_feeds_the_bar_and_clears_at_the_end(self):
        host = _ConvertHost()
        token = CancelToken()
        host._convert_token = token
        host._convert_batch_total = 2
        host._convert_batch_index = 2

        host._update_convert_progress(50)
        host._finish_convert_state(token)

        self.assertEqual(host.progress, [("convert", 75.0), ("convert", "cleared")])
        self.assertIn("2 de 2", host.statuses[0])

    def test_the_first_file_starts_indeterminate(self):
        host = _ConvertHost()
        token = CancelToken()
        host._convert_token = token
        host._convert_batch_total = 3

        host._on_convert_item_started(token, 1)

        self.assertEqual(host.progress, [("convert", None)])


if __name__ == "__main__":
    unittest.main()
