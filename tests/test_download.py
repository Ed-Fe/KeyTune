from pathlib import Path
import io
import os
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from player.download import ffmpeg as ffmpeg_module
from player.download import runner
from player.download.options import (
    AUDIO_QUALITIES,
    SAMPLE_RATES,
    VIDEO_QUALITIES,
    normalize_audio_quality,
    normalize_download_kind,
    normalize_sample_rate,
    normalize_video_quality,
    resolve_download_directory,
)
from player.download.plan import (
    DownloadChoice,
    build_download_plan,
    describe_quality_difference,
    download_source_url,
    requires_ffmpeg,
)


def _choice(**overrides):
    values = {
        "kind": "audio",
        "audio_quality": "original",
        "video_quality": "best",
        "sample_rate": 0,
        "directory": "",
    }
    values.update(overrides)
    return DownloadChoice(**values)


class DownloadOptionsTests(unittest.TestCase):
    def test_normalizers_fall_back_on_unknown_values(self):
        self.assertEqual(normalize_download_kind("VIDEO"), "video")
        self.assertEqual(normalize_download_kind("gif"), "audio")
        self.assertEqual(normalize_audio_quality("mp3_320"), "mp3_320")
        self.assertEqual(normalize_audio_quality("wav"), "original")
        self.assertEqual(normalize_video_quality("1080"), "1080")
        self.assertEqual(normalize_video_quality("999"), "best")
        self.assertEqual(normalize_sample_rate("48000"), 48000)
        self.assertEqual(normalize_sample_rate(96000), 0)
        self.assertEqual(normalize_sample_rate("abc"), 0)

    def test_every_option_table_starts_with_the_no_conversion_choice(self):
        self.assertEqual(AUDIO_QUALITIES[0], "original")
        self.assertEqual(VIDEO_QUALITIES[0], "best")
        self.assertEqual(SAMPLE_RATES[0], 0)

    def test_blank_directory_resolves_to_the_default_folder(self):
        self.assertTrue(resolve_download_directory("").endswith(os.path.join("Downloads", "KeyTune")))
        self.assertEqual(resolve_download_directory("  D:\\Musicas "), "D:\\Musicas")


class DownloadSourceUrlTests(unittest.TestCase):
    def test_accepts_single_youtube_videos(self):
        for url in (
            "https://www.youtube.com/watch?v=abc123DEF45",
            "https://music.youtube.com/watch?v=abc123DEF45&list=RDAMVM",
            "https://youtu.be/abc123DEF45",
            "https://www.youtube.com/shorts/abc123DEF45",
        ):
            with self.subTest(url=url):
                self.assertEqual(download_source_url(url), url)

    def test_rejects_playlists_local_files_and_other_sites(self):
        for value in (
            "https://www.youtube.com/playlist?list=PL123",
            "https://www.youtube.com/watch?list=PL123",
            "https://www.youtube.com/@canal",
            "ytmusic://playlist/PL123",
            "https://example.com/audio.mp3",
            "C:\\Musicas\\faixa.mp3",
            "",
            None,
        ):
            with self.subTest(value=value):
                self.assertEqual(download_source_url(value), "")


class DownloadPlanTests(unittest.TestCase):
    def test_original_audio_needs_no_ffmpeg_and_is_not_converted(self):
        choice = _choice()

        plan = build_download_plan(choice, ffmpeg_available=False)

        self.assertFalse(requires_ffmpeg(choice))
        self.assertEqual(plan.format_selector, "bestaudio/best")
        self.assertEqual(plan.arguments, ())
        self.assertFalse(plan.reduced_without_ffmpeg)

    def test_original_audio_embeds_metadata_when_ffmpeg_exists(self):
        plan = build_download_plan(_choice(sample_rate=44100), ffmpeg_available=True)

        # A taxa só vale ao converter: com áudio original ela é ignorada.
        self.assertEqual(plan.arguments, ("--embed-metadata",))

    def test_mp3_conversion_sets_codec_bitrate_and_sample_rate(self):
        choice = _choice(audio_quality="mp3_192", sample_rate=44100)

        plan = build_download_plan(choice, ffmpeg_available=True)

        self.assertTrue(requires_ffmpeg(choice))
        self.assertEqual(
            plan.arguments,
            (
                "--embed-metadata",
                "-x", "--audio-format", "mp3",
                "--audio-quality", "192K",
                "--postprocessor-args", "ExtractAudio:-ar 44100",
            ),
        )

    def test_flac_has_no_bitrate_and_original_sample_rate_adds_no_resample(self):
        plan = build_download_plan(_choice(audio_quality="flac"), ffmpeg_available=True)

        self.assertIn("flac", plan.arguments)
        self.assertNotIn("--audio-quality", plan.arguments)
        self.assertNotIn("--postprocessor-args", plan.arguments)

    def test_conversion_without_ffmpeg_falls_back_to_original_audio(self):
        plan = build_download_plan(_choice(audio_quality="mp3_320"), ffmpeg_available=False)

        self.assertEqual(plan.arguments, ())
        self.assertTrue(plan.reduced_without_ffmpeg)

    def test_video_selector_falls_back_to_best_when_the_height_is_missing(self):
        plan = build_download_plan(_choice(kind="video", video_quality="1080"), ffmpeg_available=True)

        self.assertEqual(plan.format_selector, "bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b")
        self.assertEqual(plan.arguments, ("--embed-metadata", "--merge-output-format", "mp4"))

    def test_best_video_has_no_height_limit(self):
        plan = build_download_plan(_choice(kind="video"), ffmpeg_available=True)

        self.assertEqual(plan.format_selector, "bv*+ba/b")

    def test_video_without_ffmpeg_uses_progressive_formats_only(self):
        limited = build_download_plan(_choice(kind="video", video_quality="720"), ffmpeg_available=False)
        best = build_download_plan(_choice(kind="video"), ffmpeg_available=False)

        self.assertEqual(limited.format_selector, "b[height<=720]/b")
        self.assertEqual(best.format_selector, "b")
        self.assertTrue(limited.reduced_without_ffmpeg)
        self.assertEqual(limited.arguments, ())

    def test_quality_difference_is_reported_only_for_a_different_height(self):
        video = _choice(kind="video", video_quality="1080")

        self.assertEqual(describe_quality_difference(video, 1080), "")
        self.assertEqual(describe_quality_difference(video, None), "")
        self.assertIn("720p", describe_quality_difference(video, 720))
        self.assertEqual(describe_quality_difference(_choice(kind="video"), 480), "")
        self.assertEqual(describe_quality_difference(_choice(), 480), "")


class DownloadCommandTests(unittest.TestCase):
    def test_command_carries_the_plan_and_keeps_the_url_last(self):
        choice = _choice(kind="video", video_quality="720")
        plan = build_download_plan(choice, ffmpeg_available=True)

        command = runner.build_command(
            "yt-dlp.exe",
            "https://www.youtube.com/watch?v=abc123DEF45",
            choice,
            plan,
            output_directory="D:\\Downloads",
            ffmpeg_directory="C:\\ffmpeg\\bin",
            cookie_file_path="cookies.txt",
            http_headers={"User-Agent": "x", "Empty": " "},
            js_runtimes={"node": "C:\\node.exe"},
        )

        self.assertEqual(command[-2:], ["--", "https://www.youtube.com/watch?v=abc123DEF45"])
        self.assertIn("--no-playlist", command)
        self.assertEqual(command[command.index("--format") + 1], plan.format_selector)
        self.assertEqual(command[command.index("--paths") + 1], "D:\\Downloads")
        self.assertEqual(command[command.index("--ffmpeg-location") + 1], "C:\\ffmpeg\\bin")
        self.assertEqual(command[command.index("--cookies") + 1], "cookies.txt")
        self.assertEqual(command[command.index("--add-header") + 1], "User-Agent:x")
        self.assertNotIn("Empty: ", command)
        self.assertEqual(command[command.index("--js-runtimes") + 1], "node:C:\\node.exe")
        self.assertIn("--merge-output-format", command)

    def test_progress_lines_are_parsed_with_total_or_estimate(self):
        exact = runner.parse_progress_line("KTP|downloading|1024|2048|NA")
        estimated = runner.parse_progress_line("KTP|downloading|512|NA|1024")
        unknown = runner.parse_progress_line("KTP|downloading|512|NA|NA")
        finished = runner.parse_progress_line("KTP|finished|2048|2048|NA")

        self.assertEqual(exact.percent, 50)
        self.assertFalse(exact.finished)
        self.assertEqual(estimated.percent, 50)
        self.assertIsNone(unknown.percent)
        self.assertTrue(finished.finished)
        self.assertIsNone(runner.parse_progress_line("[download] 50%"))
        self.assertIsNone(runner.parse_progress_line("KTP|downloading|NA|NA|NA"))

    def test_result_line_keeps_pipes_inside_the_path(self):
        self.assertEqual(
            runner.parse_result_line("KTF|D:\\Musica\\a | b [id].mp4|720|NA"),
            ("D:\\Musica\\a | b [id].mp4", 720),
        )
        self.assertEqual(runner.parse_result_line("KTF|D:\\a.mp3|NA|128.5"), ("D:\\a.mp3", None))
        self.assertIsNone(runner.parse_result_line("[info] something"))


class _FakeProcess:
    def __init__(self, lines, return_code=0):
        self.stdout = iter(lines)
        self.pid = 4242
        self._return_code = return_code
        self._done = False

    def poll(self):
        return self._return_code if self._done else None

    def wait(self):
        self._done = True
        return self._return_code


class RunDownloadTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp_dir.cleanup)
        self.output_dir = Path(self._temp_dir.name).resolve()
        self.plan = build_download_plan(_choice(audio_quality="mp3_192"), ffmpeg_available=True)
        self.choice = _choice(audio_quality="mp3_192", directory=str(self.output_dir))

    def _run(self, lines, return_code=0, **kwargs):
        with patch.object(runner, "find_yt_dlp_executable_path", return_value=Path("yt-dlp.exe")), patch.object(
            runner.subprocess, "Popen", return_value=_FakeProcess(lines, return_code)
        ):
            return runner.run_download("https://youtu.be/abc123DEF45", self.choice, self.plan, **kwargs)

    def test_collects_the_final_file_and_reports_progress_and_processing(self):
        final_file = self.output_dir / "faixa [id].mp3"
        final_file.write_bytes(b"data")
        progress = []
        processing = []

        result = self._run(
            [
                "KTP|downloading|1024|2048|NA\n",
                "\x1b[0mKTP|finished|2048|2048|NA\n",
                f"KTF|{final_file}|NA|128\n",
            ],
            progress_callback=progress.append,
            processing_callback=lambda: processing.append(True),
        )

        self.assertEqual(result.paths, (str(final_file),))
        self.assertEqual([item.percent for item in progress], [50, 100])
        self.assertEqual(processing, [True])

    def test_ignores_a_reported_path_outside_the_download_folder(self):
        with tempfile.TemporaryDirectory() as other_dir:
            outsider = Path(other_dir) / "fora.mp3"
            outsider.write_bytes(b"x")

            with self.assertRaises(RuntimeError):
                self._run([f"KTF|{outsider}|NA|NA\n"])

    def test_failure_reports_the_last_yt_dlp_error(self):
        with self.assertRaises(RuntimeError) as raised:
            self._run(
                ["WARNING: aviso\n", "ERROR: [youtube] abc: Video unavailable\n"],
                return_code=1,
            )

        self.assertIn("Video unavailable", str(raised.exception))

    def test_cancelled_token_raises_download_cancelled(self):
        token = runner.DownloadCancelToken()
        token.cancel()

        with patch.object(runner.process_control, "terminate_process_tree"):
            with self.assertRaises(runner.DownloadCancelled):
                self._run(["KTP|downloading|1|2|NA\n"], return_code=1, cancel_token=token)

    def test_requires_a_destination_folder(self):
        choice = _choice(directory="  ")
        with patch.object(runner, "find_yt_dlp_executable_path", return_value=Path("yt-dlp.exe")):
            with self.assertRaises(RuntimeError):
                runner.run_download("https://youtu.be/abc123DEF45", choice, self.plan)

    def test_reports_a_missing_yt_dlp(self):
        with patch.object(runner, "find_yt_dlp_executable_path", return_value=None):
            with self.assertRaises(RuntimeError):
                runner.run_download("https://youtu.be/abc123DEF45", self.choice, self.plan)


class FFmpegTests(unittest.TestCase):
    def test_finds_the_ffmpeg_folder_from_the_environment_override(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / ffmpeg_module.FFMPEG_EXECUTABLE_NAME).write_bytes(b"")
            (Path(directory) / ffmpeg_module.FFPROBE_EXECUTABLE_NAME).write_bytes(b"")

            with patch.dict(os.environ, {ffmpeg_module.FFMPEG_PATH_ENV: directory}):
                self.assertEqual(ffmpeg_module.find_ffmpeg_directory(), Path(directory))

    def test_a_folder_with_only_ffmpeg_and_no_ffprobe_is_not_enough(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / ffmpeg_module.FFMPEG_EXECUTABLE_NAME).write_bytes(b"")

            with patch.dict(os.environ, {ffmpeg_module.FFMPEG_PATH_ENV: directory}), patch.object(
                ffmpeg_module, "get_managed_ffmpeg_dir", return_value=Path(directory) / "nada"
            ), patch.object(ffmpeg_module.shutil, "which", return_value=None):
                self.assertIsNone(ffmpeg_module.find_ffmpeg_directory())

    def test_expected_checksum_reads_the_matching_asset_line(self):
        digest = "a" * 64
        text = f"{'b' * 64}  other.zip\n{digest} *ffmpeg-master-latest-win64-gpl-shared.zip\n"

        self.assertEqual(
            ffmpeg_module.expected_checksum(text, "ffmpeg-master-latest-win64-gpl-shared.zip"),
            digest,
        )
        with self.assertRaises(RuntimeError):
            ffmpeg_module.expected_checksum(text, "missing.zip")

    def test_extraction_keeps_only_binaries_and_libraries_from_bin(self):
        archive_bytes = io.BytesIO()
        with zipfile.ZipFile(archive_bytes, "w") as archive:
            archive.writestr("ffmpeg-build/bin/ffmpeg.exe", b"exe")
            archive.writestr("ffmpeg-build/bin/ffprobe.exe", b"probe")
            archive.writestr("ffmpeg-build/bin/avcodec-61.dll", b"dll")
            archive.writestr("ffmpeg-build/bin/ffplay.exe", b"play")
            archive.writestr("ffmpeg-build/doc/readme.txt", b"doc")
            archive.writestr("ffmpeg-build/bin/../../escape.dll", b"bad")

        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "ffmpeg.zip"
            archive_path.write_bytes(archive_bytes.getvalue())
            destination = Path(directory) / "out"

            with patch.object(ffmpeg_module, "FFMPEG_EXECUTABLE_NAME", "ffmpeg.exe"), patch.object(
                ffmpeg_module, "_EXTRACTED_NAMES", frozenset({"ffmpeg.exe", "ffprobe.exe"})
            ):
                ffmpeg_module._extract_binaries(archive_path, destination)

            extracted = sorted(path.name for path in destination.iterdir())
            self.assertEqual(extracted, ["avcodec-61.dll", "ffmpeg.exe", "ffprobe.exe"])
            self.assertFalse((Path(directory) / "escape.dll").exists())


if __name__ == "__main__":
    unittest.main()
