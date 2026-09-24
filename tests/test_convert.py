from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from player import process_control
from player.convert import options
from player.convert import runner
from player.convert.plan import (
    ConvertRequest,
    build_conversion_command,
    default_output_stem,
    output_extension,
    unique_output_path,
)
from player.convert.probe import MediaInfo, StreamInfo, parse_probe_output
from player.download.ffmpeg import FFMPEG_EXECUTABLE_NAME, FFPROBE_EXECUTABLE_NAME, find_ffmpeg_directory


def _info(*streams, duration=10.0):
    return MediaInfo(duration_seconds=duration, streams=tuple(streams))


AUDIO = StreamInfo(0, "audio", "mp3")
COVER = StreamInfo(1, "video", "png", attached_pic=True)


def _request(mode, target, **overrides):
    values = {"source_path": "C:\\m\\faixa.mp3", "output_directory": "C:\\out"}
    values.update(overrides)
    return ConvertRequest(mode=mode, target_format=target, **values)


def _pairs(command, flag):
    return [command[i + 1] for i, item in enumerate(command) if item == flag]


class ConvertOptionsTests(unittest.TestCase):
    def test_media_kind_follows_the_extension(self):
        self.assertEqual(options.media_kind("a.MP3"), "audio")
        self.assertEqual(options.media_kind("C:\\v\\filme.mkv"), "video")
        self.assertEqual(options.media_kind("nota.txt"), "")
        self.assertEqual(options.media_kind(None), "")

    def test_every_mode_maps_a_source_and_a_target_kind(self):
        for mode in options.MODES:
            self.assertIn(options.MODE_SOURCE_KIND[mode], (options.KIND_AUDIO, options.KIND_VIDEO))
            self.assertIn(options.MODE_TARGET_KIND[mode], (options.KIND_AUDIO, options.KIND_VIDEO))

    def test_video_widths_are_even_and_sixteen_by_nine(self):
        self.assertEqual(options.video_width_for_height(720), 1280)
        self.assertEqual(options.video_width_for_height(1080), 1920)
        self.assertEqual(options.video_width_for_height(480) % 2, 0)


class ProbeTests(unittest.TestCase):
    def test_parses_streams_duration_and_attached_pictures(self):
        payload = json.dumps(
            {
                "streams": [
                    {"index": 0, "codec_type": "video", "codec_name": "h264", "disposition": {"attached_pic": 0}},
                    {"index": 1, "codec_type": "audio", "codec_name": "aac"},
                    {"index": 2, "codec_type": "video", "codec_name": "mjpeg", "disposition": {"attached_pic": 1}},
                    {"index": 3, "codec_type": "subtitle", "codec_name": "subrip"},
                    {"index": "x", "codec_type": "data"},
                ],
                "format": {"duration": "12.5"},
            }
        )

        info = parse_probe_output(payload)

        self.assertEqual(info.duration_seconds, 12.5)
        self.assertEqual([s.index for s in info.video_streams], [0])
        self.assertEqual([s.index for s in info.cover_streams], [2])
        self.assertEqual([s.index for s in info.audio_streams], [1])
        self.assertEqual([s.index for s in info.subtitle_streams], [3])

    def test_invalid_output_is_reported(self):
        with self.assertRaises(RuntimeError):
            parse_probe_output("not json")
        with self.assertRaises(RuntimeError):
            parse_probe_output("[]")


class AudioCommandTests(unittest.TestCase):
    def test_mp3_sets_codec_bitrate_and_sample_rate(self):
        request = _request(options.MODE_AUDIO_TO_AUDIO, "mp3", audio_bitrate_kbps=256, sample_rate=44100)

        command = build_conversion_command("ffmpeg", request, _info(AUDIO), "out.mp3")

        self.assertEqual(_pairs(command, "-c:a"), ["libmp3lame"])
        self.assertEqual(_pairs(command, "-b:a"), ["256k"])
        self.assertEqual(_pairs(command, "-ar"), ["44100"])
        self.assertEqual(_pairs(command, "-map"), ["0:0"])
        self.assertEqual(command[-1], "out.mp3")

    def test_lossless_formats_have_no_bitrate(self):
        for target in ("flac", "wav"):
            with self.subTest(target=target):
                command = build_conversion_command(
                    "ffmpeg", _request(options.MODE_AUDIO_TO_AUDIO, target), _info(AUDIO), "out"
                )
                self.assertNotIn("-b:a", command)

    def test_opus_never_receives_a_sample_rate(self):
        request = _request(options.MODE_AUDIO_TO_AUDIO, "opus", sample_rate=44100)

        command = build_conversion_command("ffmpeg", request, _info(AUDIO), "out.opus")

        self.assertNotIn("-ar", command)

    def test_cover_follows_audio_to_audio_only_for_formats_that_hold_one(self):
        info = _info(AUDIO, COVER)

        with_cover = build_conversion_command(
            "ffmpeg", _request(options.MODE_AUDIO_TO_AUDIO, "mp3"), info, "o.mp3"
        )
        without_cover = build_conversion_command(
            "ffmpeg", _request(options.MODE_AUDIO_TO_AUDIO, "ogg"), info, "o.ogg"
        )

        self.assertEqual(_pairs(with_cover, "-map"), ["0:0", "0:1"])
        self.assertIn("attached_pic", with_cover)
        self.assertEqual(_pairs(without_cover, "-map"), ["0:0"])

    def test_extracting_audio_from_a_video_never_copies_its_picture(self):
        info = _info(StreamInfo(0, "video", "h264"), StreamInfo(1, "audio", "aac"), COVER)

        command = build_conversion_command(
            "ffmpeg", _request(options.MODE_VIDEO_TO_AUDIO, "mp3", source_path="C:\\m\\v.mp4"), info, "o.mp3"
        )

        self.assertEqual(_pairs(command, "-map"), ["0:1"])

    def test_media_without_audio_is_rejected(self):
        with self.assertRaises(RuntimeError):
            build_conversion_command(
                "ffmpeg",
                _request(options.MODE_AUDIO_TO_AUDIO, "mp3"),
                _info(StreamInfo(0, "video", "h264")),
                "o.mp3",
            )


class AudioToVideoCommandTests(unittest.TestCase):
    def test_black_background_uses_a_generated_color_source(self):
        request = _request(options.MODE_AUDIO_TO_VIDEO, "mp4", video_height=480)

        command = build_conversion_command("ffmpeg", request, _info(AUDIO), "o.mp4")

        self.assertIn("-f", command)
        self.assertTrue(any(item.startswith("color=c=black:s=854x480") for item in command))
        self.assertIn("-shortest", command)
        self.assertEqual(_pairs(command, "-c:v"), ["libx264"])
        self.assertIn("+faststart", command)

    def test_a_cover_image_becomes_the_looped_picture(self):
        request = _request(options.MODE_AUDIO_TO_VIDEO, "mkv")

        command = build_conversion_command("ffmpeg", request, _info(AUDIO, COVER), "o.mkv", cover_path="cover.png")

        self.assertIn("-loop", command)
        self.assertIn("cover.png", command)
        self.assertNotIn("lavfi", command)
        self.assertNotIn("+faststart", command)

    def test_webm_uses_vp9_and_opus(self):
        command = build_conversion_command(
            "ffmpeg", _request(options.MODE_AUDIO_TO_VIDEO, "webm"), _info(AUDIO), "o.webm"
        )

        self.assertEqual(_pairs(command, "-c:v"), ["libvpx-vp9"])
        self.assertEqual(_pairs(command, "-c:a"), ["libopus"])


class VideoToVideoCommandTests(unittest.TestCase):
    H264 = StreamInfo(0, "video", "h264")
    AAC = StreamInfo(1, "audio", "aac")

    def _convert(self, target, *streams):
        request = _request(options.MODE_VIDEO_TO_VIDEO, target, source_path="C:\\m\\v.mp4")
        return build_conversion_command("ffmpeg", request, _info(*streams), "out")

    def test_compatible_streams_are_copied(self):
        command = self._convert("mkv", self.H264, self.AAC)

        self.assertEqual(_pairs(command, "-c:0"), ["copy"])
        self.assertEqual(_pairs(command, "-c:1"), ["copy"])

    def test_incompatible_streams_are_reencoded_per_stream(self):
        command = self._convert("webm", self.H264, self.AAC)

        self.assertEqual(_pairs(command, "-c:0"), ["libvpx-vp9"])
        self.assertEqual(_pairs(command, "-c:1"), ["libopus"])

    def test_only_the_incompatible_stream_is_reencoded(self):
        command = self._convert("avi", self.H264, self.AAC)

        self.assertEqual(_pairs(command, "-c:0"), ["copy"])
        self.assertEqual(_pairs(command, "-c:1"), ["libmp3lame"])

    def test_hevc_is_tagged_for_apple_players_in_mp4(self):
        command = self._convert("mov", StreamInfo(0, "video", "hevc"), self.AAC)

        self.assertEqual(_pairs(command, "-tag:0"), ["hvc1"])

    def test_cover_pictures_and_subtitles_are_dropped_except_in_mkv(self):
        subtitle = StreamInfo(3, "subtitle", "subrip")
        streams = (self.H264, self.AAC, COVER, subtitle)

        self.assertEqual(_pairs(self._convert("mp4", *streams), "-map"), ["0:0", "0:1"])
        self.assertEqual(_pairs(self._convert("mkv", *streams), "-map"), ["0:0", "0:1", "0:3"])

    def test_a_file_without_video_is_rejected(self):
        with self.assertRaises(RuntimeError):
            self._convert("mkv", self.AAC)


class OutputPathTests(unittest.TestCase):
    def test_existing_files_are_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "faixa.mp3").write_bytes(b"")
            (Path(directory) / "faixa (1).mp3").write_bytes(b"")

            self.assertEqual(unique_output_path(directory, "faixa", "mp3").name, "faixa (2).mp3")
            self.assertEqual(unique_output_path(directory, "outra", "mp3").name, "outra.mp3")

    def test_extension_follows_the_target_kind(self):
        self.assertEqual(output_extension(_request(options.MODE_AUDIO_TO_AUDIO, "m4a")), "m4a")
        self.assertEqual(output_extension(_request(options.MODE_VIDEO_TO_VIDEO, "mkv")), "mkv")
        self.assertEqual(default_output_stem("C:\\m\\Minha faixa.mp3"), "Minha faixa")


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


class RunFfmpegTests(unittest.TestCase):
    def _run(self, lines, return_code=0, **kwargs):
        with patch.object(runner.subprocess, "Popen", return_value=_FakeProcess(lines, return_code)):
            return runner._run_ffmpeg(["ffmpeg"], 10.0, kwargs.pop("progress", None), kwargs.pop("token", None))

    def test_reports_progress_from_out_time(self):
        progress = []

        self._run(
            ["frame=1\n", "out_time_us=2500000\n", "progress=continue\n", "out_time_us=10000000\n"],
            progress=progress.append,
        )

        self.assertEqual(progress, [25, 100])

    def test_progress_percentage_needs_a_known_duration(self):
        self.assertIsNone(runner.parse_progress_percent("out_time_us=1000000", 0))
        self.assertIsNone(runner.parse_progress_percent("out_time_us=N/A", 10))
        self.assertIsNone(runner.parse_progress_percent("bitrate=128kbits/s", 10))

    def test_failure_reports_the_last_error_line(self):
        with self.assertRaises(RuntimeError) as raised:
            self._run(["out_time_us=1\n", "Error opening input: Invalid data\n"], return_code=1)

        self.assertIn("Invalid data", str(raised.exception))

    def test_cancelled_token_raises_conversion_cancelled(self):
        token = process_control.CancelToken()
        token.cancel()

        with patch.object(process_control, "terminate_process_tree"):
            with self.assertRaises(runner.ConversionCancelled):
                self._run(["out_time_us=1\n"], return_code=1, token=token)


def _real_ffmpeg_directory():
    directory = find_ffmpeg_directory()
    if directory is None:
        return None
    try:
        result = subprocess.run(
            [str(directory / FFMPEG_EXECUTABLE_NAME), "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    encoders = result.stdout
    needed = ("libmp3lame", "libx264", "aac", "flac")
    return directory if all(name in encoders for name in needed) else None


@unittest.skipUnless(_real_ffmpeg_directory(), "FFmpeg completo não está disponível")
class RealFfmpegConversionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ffmpeg_dir = _real_ffmpeg_directory()
        cls.temp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.temp.name)
        ffmpeg = str(cls.ffmpeg_dir / FFMPEG_EXECUTABLE_NAME)

        def make(*args):
            subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", *args], check=True, timeout=60)

        make("-f", "lavfi", "-i", "sine=frequency=440:duration=2:sample_rate=48000", str(cls.dir / "tom.wav"))
        make(
            "-f", "lavfi", "-i", "testsrc=size=160x120:rate=10:duration=2",
            "-f", "lavfi", "-i", "sine=frequency=330:duration=2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(cls.dir / "clipe.mp4"),
        )

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def _probe(self, path):
        probe = subprocess.run(
            [
                str(self.ffmpeg_dir / FFPROBE_EXECUTABLE_NAME), "-v", "error", "-show_streams", "-of", "json", path,
            ],
            capture_output=True,
            text=True,
        )
        return {s["codec_type"]: s for s in json.loads(probe.stdout)["streams"]}

    def _convert(self, mode, source, target, **overrides):
        request = ConvertRequest(
            mode=mode,
            source_path=str(self.dir / source),
            output_directory=str(self.dir / "saida"),
            target_format=target,
            **overrides,
        )
        return runner.run_conversion(request, ffmpeg_directory=self.ffmpeg_dir).path

    def test_audio_to_audio_changes_codec_and_sample_rate(self):
        path = self._convert(options.MODE_AUDIO_TO_AUDIO, "tom.wav", "flac", sample_rate=44100)

        audio = self._probe(path)["audio"]
        self.assertEqual((audio["codec_name"], audio["sample_rate"]), ("flac", "44100"))

    def test_video_to_audio_extracts_only_the_sound(self):
        path = self._convert(options.MODE_VIDEO_TO_AUDIO, "clipe.mp4", "mp3")

        streams = self._probe(path)
        self.assertEqual(streams["audio"]["codec_name"], "mp3")
        self.assertNotIn("video", streams)

    def test_audio_to_video_makes_a_still_picture_with_the_sound(self):
        path = self._convert(options.MODE_AUDIO_TO_VIDEO, "tom.wav", "mp4", video_height=480)

        streams = self._probe(path)
        self.assertEqual((streams["video"]["width"], streams["video"]["height"]), (854, 480))
        self.assertEqual(streams["audio"]["codec_name"], "aac")

    def test_video_to_video_copies_compatible_streams(self):
        path = self._convert(options.MODE_VIDEO_TO_VIDEO, "clipe.mp4", "mkv")

        streams = self._probe(path)
        self.assertEqual((streams["video"]["codec_name"], streams["audio"]["codec_name"]), ("h264", "aac"))
        self.assertTrue(path.endswith(".mkv"))

    def test_a_failed_conversion_leaves_no_partial_file(self):
        (self.dir / "quebrado.wav").write_bytes(b"isto nao e um audio")

        with self.assertRaises(RuntimeError):
            self._convert(options.MODE_AUDIO_TO_AUDIO, "quebrado.wav", "mp3")

        self.assertFalse((self.dir / "saida" / "quebrado.mp3").exists())


if __name__ == "__main__":
    unittest.main()
