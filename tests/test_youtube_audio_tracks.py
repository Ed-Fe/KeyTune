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

from player.frames.youtube_music.audio_tracks import AudioTrackMixin
from player.preferences.models import AppSettings
from player.youtube_music import audio_tracks, streams
from player.youtube_music.audio_tracks import YouTubeAudioTrack


URL = "https://www.youtube.com/watch?v=0e3GPea1Tyg"
ENTRIES = [
    {"id": "en-US.4", "name": "Inglês (US) original", "language": "en-US", "default": True, "original": True},
    {"id": "pt.3", "name": "Português", "language": "pt"},
    {"id": "es.9", "name": "Espanhol (descrição)", "language": "es", "descriptive": True},
    {"id": "es.3", "name": "Espanhol", "language": "es"},
]


def _tracks():
    with patch.object(audio_tracks.youtubejs_runtime, "audio_tracks", return_value=ENTRIES):
        return audio_tracks._youtubejs_tracks(URL, names=True)


class _AudioChoiceCase(unittest.TestCase):
    def setUp(self):
        self._reset()
        self.addCleanup(self._reset)
        patcher = patch.object(audio_tracks, "youtubejs_resolver_enabled", return_value=True)
        self.addCleanup(patcher.stop)
        self.youtubejs_enabled = patcher.start()

    @staticmethod
    def _reset():
        audio_tracks.configure_audio_preference("")
        audio_tracks._media_choices.clear()


class PickTrackTests(unittest.TestCase):
    def test_a_track_is_found_by_id_by_original_or_by_language(self):
        tracks = _tracks()

        self.assertEqual(audio_tracks.pick_track(tracks, "pt.3").track_id, "pt.3")
        self.assertEqual(audio_tracks.pick_track(tracks, "original").track_id, "en-US.4")
        self.assertEqual(audio_tracks.pick_track(tracks, "en").track_id, "en-US.4")
        self.assertIsNone(audio_tracks.pick_track(tracks, "ja"))
        self.assertIsNone(audio_tracks.pick_track(tracks, ""))

    def test_the_plain_track_of_a_language_comes_before_the_audio_description(self):
        self.assertEqual(audio_tracks.pick_track(_tracks(), "es").track_id, "es.3")

    def test_yt_dlp_keeps_only_the_formats_of_the_requested_track(self):
        formats = [
            {"format_id": "140-1", "language": "en-US", "language_preference": 10},
            {"format_id": "140-2", "language": "pt", "language_preference": -1},
            {"format_id": "140-3", "language": "pt-BR", "language_preference": -1},
        ]

        def ids(selector):
            return [fmt["format_id"] for fmt in audio_tracks.yt_dlp_formats_for_selector(formats, selector)]

        self.assertEqual(ids("pt"), ["140-2"])
        self.assertEqual(ids("pt-PT"), ["140-2", "140-3"])
        self.assertEqual(ids("original"), ["140-1"])
        # Um vídeo sem a faixa pedida toca como sempre tocou.
        self.assertEqual(ids("ja"), ["140-1", "140-2", "140-3"])
        self.assertEqual(ids(""), ["140-1", "140-2", "140-3"])

    def test_the_stream_comes_from_the_requested_track(self):
        info = {
            "formats": [
                {"format_id": "251-1", "url": "https://a.googlevideo.com/en", "vcodec": "none", "acodec": "opus", "abr": 160, "language": "en-US", "language_preference": 10},
                {"format_id": "140-2", "url": "https://a.googlevideo.com/pt", "vcodec": "none", "acodec": "mp4a", "abr": 128, "language": "pt", "language_preference": -1},
            ]
        }

        self.assertEqual(streams._preferred_stream_from_info(info).stream_url, "https://a.googlevideo.com/en")
        self.assertEqual(
            streams._preferred_stream_from_info(info, audio_track="pt").stream_url, "https://a.googlevideo.com/pt"
        )


class SelectorForPlaybackTests(_AudioChoiceCase):
    def _selector(self, entries=ENTRIES, error=None):
        with patch.object(audio_tracks.youtubejs_runtime, "audio_tracks", return_value=entries, side_effect=error) as lister:
            return audio_tracks.yt_dlp_selector_for_playback(URL), lister

    def test_without_a_preference_nothing_is_asked(self):
        selector, lister = self._selector()

        self.assertEqual(selector, "")
        lister.assert_not_called()

    def test_a_dub_in_the_preferred_language_goes_through_yt_dlp(self):
        audio_tracks.configure_audio_preference("pt")

        self.assertEqual(self._selector()[0], "pt")

    def test_the_default_track_keeps_the_usual_path(self):
        audio_tracks.configure_audio_preference("original")
        self.assertEqual(self._selector()[0], "")

        audio_tracks.configure_audio_preference("en")
        self.assertEqual(self._selector()[0], "")

    def test_a_video_without_the_track_keeps_the_usual_path(self):
        audio_tracks.configure_audio_preference("pt")

        self.assertEqual(self._selector(entries=[])[0], "")

    def test_the_choice_for_this_media_comes_before_the_preference(self):
        audio_tracks.configure_audio_preference("pt")
        audio_tracks.set_media_audio_choice(URL, "es.3")

        self.assertEqual(self._selector()[0], "es")
        self.assertEqual(audio_tracks.audio_choice_for("https://www.youtube.com/watch?v=dQw4w9WgXcQ"), ("pt", False))

    def test_when_the_listing_fails_only_an_explicit_choice_insists(self):
        audio_tracks.configure_audio_preference("pt")
        self.assertEqual(self._selector(error=RuntimeError("sem Node"))[0], "")

        audio_tracks.set_media_audio_choice(URL, "es.3")
        self.assertEqual(self._selector(error=RuntimeError("sem Node"))[0], "es")

    def test_without_youtubejs_yt_dlp_looks_for_the_track_itself(self):
        self.youtubejs_enabled.return_value = False
        audio_tracks.configure_audio_preference("pt")

        selector, lister = self._selector()

        self.assertEqual(selector, "pt")
        lister.assert_not_called()

    def test_unknown_preferences_mean_the_default(self):
        self.assertEqual(audio_tracks.normalize_audio_preference("klingon"), "")
        self.assertEqual(audio_tracks.normalize_audio_preference("original"), "original")
        self.assertTrue(audio_tracks.configure_audio_preference("es"))
        self.assertFalse(audio_tracks.configure_audio_preference("es"))
        self.assertEqual(AppSettings.from_dict(AppSettings(youtube_audio_language="es").to_dict()).youtube_audio_language, "es")


class ListTracksTests(_AudioChoiceCase):
    def test_without_youtubejs_the_tracks_come_from_the_yt_dlp_formats(self):
        self.youtubejs_enabled.return_value = False
        data = {
            "formats": [
                {"vcodec": "none", "language": "en-US", "format_note": "English (US) original (default), low", "language_preference": 10},
                {"vcodec": "none", "language": "en-US", "format_note": "English (US) original (default), medium", "language_preference": 10},
                {"vcodec": "none", "language": "pt", "format_note": "Portuguese, low", "language_preference": -1},
                {"vcodec": "avc1", "language": "fr", "format_note": "720p"},
            ]
        }
        with patch.object(audio_tracks, "ensure_yt_dlp_executable_available"), patch.object(
            audio_tracks, "find_all_available_javascript_runtimes", return_value={}
        ), patch.object(audio_tracks, "extract_yt_dlp_info", return_value=SimpleNamespace(data=data)):
            tracks = audio_tracks.list_audio_tracks(URL)

        self.assertEqual([(track.track_id, track.name, track.original) for track in tracks], [
            ("en-US", "English (US) original (default)", True),
            ("pt", "Portuguese", False),
        ])

    def test_a_video_with_one_language_has_no_tracks_to_choose(self):
        self.youtubejs_enabled.return_value = False
        data = {"formats": [{"vcodec": "none", "language": "en", "format_note": "low"}]}
        with patch.object(audio_tracks, "ensure_yt_dlp_executable_available"), patch.object(
            audio_tracks, "find_all_available_javascript_runtimes", return_value={}
        ), patch.object(audio_tracks, "extract_yt_dlp_info", return_value=SimpleNamespace(data=data)):
            self.assertEqual(audio_tracks.list_audio_tracks(URL), [])


class _Frame(AudioTrackMixin):
    def __init__(self, media_path=URL):
        self.announcements = []
        self.state = SimpleNamespace(current_media_path=media_path, last_position_ms=61000, was_playing=True)
        self.service = Mock()
        self._queue_media_start = Mock()
        self._capture_active_playlist_state = Mock()

    def _announce(self, message):
        self.announcements.append(message)

    def _get_active_playlist_state(self):
        return self.state

    def _get_active_playlist_index(self):
        return 2

    def _youtube_music_service_for_playback(self):
        return self.service

    def _format_youtube_music_error_detail(self, exc):
        return str(exc)

    def _run_youtube_music_background_task(self, worker, on_success, *, on_error=None, timeout_ms=None):
        on_success(worker())
        return True


class ChooseAudioTrackTests(_AudioChoiceCase):
    def test_local_media_has_no_tracks_to_choose(self):
        frame = _Frame("C:/musica.mp3")

        self.assertFalse(frame.choose_current_media_audio_track())
        self.assertEqual(frame.announcements, ["A mídia atual não é do YouTube: não há faixas de áudio para escolher."])

    def test_a_single_track_is_announced(self):
        frame = _Frame()
        with patch.object(audio_tracks, "list_audio_tracks", return_value=[]):
            frame.choose_current_media_audio_track()

        self.assertEqual(frame.announcements[-1], "Esta mídia tem só uma faixa de áudio.")
        frame._queue_media_start.assert_not_called()

    def test_the_chosen_track_plays_from_the_same_point(self):
        frame = _Frame()
        track = YouTubeAudioTrack(track_id="pt.3", name="Português", language="pt")

        frame._play_current_media_with_audio_track(URL, track)

        self.assertEqual(audio_tracks.audio_choice_for(URL), ("pt.3", True))
        frame.service.invalidate_cached_stream.assert_called_once_with(URL)
        frame._capture_active_playlist_state.assert_called_once_with()
        frame._queue_media_start.assert_called_once_with(
            URL,
            tab_index=2,
            announce_message="Áudio em Português.",
            restore_position_ms=61000,
            pause_after_start=False,
        )

    def test_if_the_media_changed_meanwhile_nothing_is_asked(self):
        frame = _Frame()
        frame.state.current_media_path = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

        self.assertFalse(frame._pick_audio_track(URL, _tracks()))


if __name__ == "__main__":
    unittest.main()
