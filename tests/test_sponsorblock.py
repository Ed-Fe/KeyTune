from __future__ import annotations

import hashlib
import io
import json
import pathlib
import sys
import types
import unittest
import urllib.error
from unittest.mock import Mock, patch


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.frames.playback.sponsorblock import SponsorBlockMixin
from player.preferences.models import AppSettings
from player.youtube_music import sponsorblock


VIDEO_ID = "dQw4w9WgXcQ"


def _payload(*segments, video_id=VIDEO_ID):
    return [{"videoID": video_id, "segments": list(segments)}]


def _segment(start, end, category="sponsor", uuid="u1", action="skip"):
    return {"segment": [start, end], "category": category, "UUID": uuid, "actionType": action}


class SponsorBlockClientTests(unittest.TestCase):
    def test_parse_keeps_only_this_video_wanted_categories_skips_and_mutes(self):
        payload = _payload(
            _segment(30, 40, uuid="b"),
            _segment(5, 10, category="intro", uuid="intro"),
            _segment(1, 2, action="mute", uuid="mute"),
            _segment(3, 4, action="poi", uuid="poi"),
            _segment(9, 3, uuid="backwards"),
            _segment(0, 4, uuid="a"),
        ) + _payload(_segment(0, 9, uuid="other"), video_id="another")

        segments = sponsorblock.parse_segments(payload, VIDEO_ID, ["sponsor"])

        self.assertEqual([segment.uuid for segment in segments], ["a", "mute", "b"])
        self.assertEqual(segments[1].action_type, "mute")

    def test_hook_is_a_known_category(self):
        self.assertIn("hook", sponsorblock.CATEGORIES)
        self.assertNotEqual(sponsorblock.category_label("hook"), "hook")

    def test_fetch_queries_by_hash_prefix(self):
        with patch.object(sponsorblock, "_request", return_value=json.dumps(_payload(_segment(1, 5)))) as request:
            segments = sponsorblock.fetch_segments(VIDEO_ID, ["sponsor", "unknown"])

        path = request.call_args.args[0]
        self.assertEqual(path, "skipSegments/" + hashlib.sha256(VIDEO_ID.encode()).hexdigest()[:4])
        self.assertNotIn(VIDEO_ID, path)
        self.assertEqual(json.loads(request.call_args.kwargs["params"]["categories"]), ["sponsor"])
        self.assertEqual(len(segments), 1)

    def test_fetch_never_raises(self):
        not_found = urllib.error.HTTPError("url", 404, "Not Found", {}, None)
        with patch.object(sponsorblock, "_request", side_effect=not_found):
            self.assertEqual(sponsorblock.fetch_segments(VIDEO_ID, ["sponsor"]), [])
        server_error = urllib.error.HTTPError("url", 502, "Bad Gateway", {}, None)
        for error in (server_error, urllib.error.URLError("offline"), OSError("boom")):
            with patch.object(sponsorblock, "_request", side_effect=error):
                # None: falhou, vale tentar de novo; diferente de "não há trechos".
                self.assertIsNone(sponsorblock.fetch_segments(VIDEO_ID, ["sponsor"]))

    def test_refusal_carries_the_server_reason(self):
        refused = urllib.error.HTTPError(
            "url", 400, "Bad Request", {}, io.BytesIO(b"Segments must be longer than 1 second long")
        )
        with patch.object(sponsorblock, "_request", side_effect=refused):
            with self.assertRaises(sponsorblock.SponsorBlockError) as caught:
                sponsorblock.submit_segment(VIDEO_ID, "user", 1, 5, "sponsor")
        self.assertIn("longer than 1 second", str(caught.exception))

        missing = urllib.error.HTTPError("url", 404, "Not Found", {}, None)
        with patch.object(sponsorblock, "_request", side_effect=missing):
            with self.assertRaises(sponsorblock.SponsorBlockError) as caught:
                sponsorblock.vote_segment("u1", "user", False)
        self.assertNotIn("falar com", str(caught.exception))

    def test_contribution_errors_become_messages(self):
        limited = urllib.error.HTTPError("url", 429, "Too Many", {}, None)
        with patch.object(sponsorblock, "_request", side_effect=limited):
            with self.assertRaises(sponsorblock.SponsorBlockError):
                sponsorblock.vote_segment("u1", "user", True)
            with self.assertRaises(sponsorblock.SponsorBlockError):
                sponsorblock.submit_segment(VIDEO_ID, "user", 1, 5, "sponsor")

    def test_submit_sends_segment(self):
        with patch.object(sponsorblock, "_request", return_value="") as request:
            sponsorblock.submit_segment(VIDEO_ID, "user", 1.23456, 5, "selfpromo", 200)

        body = request.call_args.kwargs["body"]
        self.assertEqual(body["videoID"], VIDEO_ID)
        self.assertEqual(body["segments"][0], {"segment": [1.235, 5.0], "category": "selfpromo", "actionType": "skip"})
        self.assertEqual(body["videoDuration"], 200.0)

    def test_generated_user_id_is_long_enough(self):
        self.assertGreaterEqual(len(sponsorblock.generate_user_id()), 30)


class SponsorBlockSettingsTests(unittest.TestCase):
    def test_defaults_are_off(self):
        settings = AppSettings()
        self.assertFalse(settings.sponsorblock_enabled)
        self.assertFalse(settings.sponsorblock_contribute)
        self.assertIn("music_offtopic", settings.sponsorblock_categories)

    def test_round_trip_drops_unknown_values(self):
        payload = AppSettings(
            sponsorblock_enabled=True,
            sponsorblock_mode="notify",
            sponsorblock_categories=["intro", "sponsor"],
            sponsorblock_contribute=True,
            sponsorblock_user_id="abc",
        ).to_dict()
        payload["sponsorblock_categories"].append("bogus")

        restored = AppSettings.from_dict(payload)

        self.assertTrue(restored.sponsorblock_enabled)
        self.assertEqual(restored.sponsorblock_mode, "notify")
        self.assertEqual(restored.sponsorblock_categories, ["sponsor", "intro"])
        self.assertTrue(restored.sponsorblock_contribute)
        self.assertEqual(restored.sponsorblock_user_id, "abc")
        self.assertEqual(AppSettings.from_dict({"sponsorblock_mode": "x"}).sponsorblock_mode, "skip")


class _Frame(SponsorBlockMixin):
    def __init__(self, mode="skip", contribute=False):
        self.settings = types.SimpleNamespace(
            sponsorblock_enabled=True,
            sponsorblock_mode=mode,
            sponsorblock_categories=["sponsor"],
            sponsorblock_contribute=contribute,
            sponsorblock_user_id="",
            interface_sounds_enabled=False,
        )
        self.player = Mock()
        self.player.get_media.return_value = object()
        self.player.get_time.return_value = 12000
        self.announcements = []
        self._update_time_bar = Mock()
        self._save_settings = Mock()

    def _player_loaded_media_path(self):
        return f"https://www.youtube.com/watch?v={VIDEO_ID}"

    def _announce(self, message, category=None):
        self.announcements.append(message)

    def load(self, *segments):
        with patch.object(self, "_start_sponsorblock_fetch"):
            state = self._sponsorblock_state_for(VIDEO_ID)
        state["segments"] = list(segments)
        return state


def _model(start, end, uuid="u1", action="skip"):
    return sponsorblock.SponsorSegment(uuid, "sponsor", action, start, end)


class SponsorBlockPlaybackTests(unittest.TestCase):
    def test_skips_once_and_rearms_after_seeking_back(self):
        frame = _Frame()
        frame.load(_model(10, 20))

        self.assertTrue(frame._maybe_handle_sponsorblock_segment())
        frame.player.set_time.assert_called_once_with(20000)
        self.assertFalse(frame._maybe_handle_sponsorblock_segment())

        frame.player.get_time.return_value = 2000
        frame._maybe_handle_sponsorblock_segment()
        frame.player.get_time.return_value = 12000
        self.assertTrue(frame._maybe_handle_sponsorblock_segment())

    def test_undo_returns_to_start_without_skipping_again(self):
        frame = _Frame()
        frame.load(_model(10, 20))
        frame._maybe_handle_sponsorblock_segment()

        self.assertTrue(frame.on_sponsorblock_undo_skip(None))
        frame.player.set_time.assert_called_with(10000)
        frame.player.set_time.reset_mock()
        self.assertFalse(frame._maybe_handle_sponsorblock_segment())
        frame.player.set_time.assert_not_called()

    def test_notify_mode_waits_for_command(self):
        frame = _Frame(mode="notify")
        frame.load(_model(10, 20))

        frame._maybe_handle_sponsorblock_segment()
        frame.player.set_time.assert_not_called()
        self.assertTrue(frame.on_sponsorblock_skip_segment(None))
        frame.player.set_time.assert_called_once_with(20000)

    def test_mute_segment_mutes_and_unmutes_on_leaving(self):
        frame = _Frame()
        frame.load(_model(10, 20, action="mute"))

        self.assertTrue(frame._maybe_handle_sponsorblock_segment())
        frame.player.audio_set_mute.assert_called_once_with(True)
        frame.player.set_time.assert_not_called()

        frame.player.get_time.return_value = 15000
        frame._maybe_handle_sponsorblock_segment()
        frame.player.audio_set_mute.assert_called_once_with(True)

        frame.player.get_time.return_value = 20000
        frame._maybe_handle_sponsorblock_segment()
        frame.player.audio_set_mute.assert_called_with(False)

    def test_mute_ends_when_media_changes_or_feature_is_disabled(self):
        frame = _Frame()
        frame.load(_model(10, 20, action="mute"))
        frame._maybe_handle_sponsorblock_segment()

        with patch.object(frame, "_player_loaded_media_path", return_value="C:/musica.mp3"):
            frame._maybe_handle_sponsorblock_segment()
        frame.player.audio_set_mute.assert_called_with(False)

        frame = _Frame()
        frame.load(_model(10, 20, action="mute"))
        frame._maybe_handle_sponsorblock_segment()
        frame.settings.sponsorblock_enabled = False
        frame._maybe_handle_sponsorblock_segment()
        frame.player.audio_set_mute.assert_called_with(False)

    def test_failed_fetch_is_retried_later(self):
        frame = _Frame()
        delivered = []
        with patch("player.frames.playback.sponsorblock.threading.Thread") as thread, patch(
            "player.frames.playback.sponsorblock.wx.CallAfter", side_effect=lambda fn: delivered.append(fn)
        ), patch.object(sponsorblock, "fetch_segments", return_value=None) as fetch:
            frame._maybe_handle_sponsorblock_segment()
            thread.call_args.kwargs["target"]()
            delivered.pop()()
            state = frame._sponsorblock_state
            self.assertEqual(state["segments"], [])
            self.assertIsNotNone(state["retry_at"])

            state["retry_at"] = 0
            frame._maybe_handle_sponsorblock_segment()
            self.assertEqual(thread.call_count, 2)
            self.assertIsNone(state["retry_at"])
        self.assertEqual(fetch.call_count, 1)

    def test_submit_reads_duration_before_the_dialog(self):
        frame = _Frame(contribute=True)
        frame.player.get_length.return_value = 300000
        frame._sponsorblock_marked_start = (VIDEO_ID, 5.0)

        dialog = Mock()

        def show_modal():
            # Com o diálogo aberto, a mídia avançou para outra de outra duração.
            frame.player.get_length.return_value = 999000
            return 5100

        dialog.ShowModal.side_effect = show_modal
        dialog.GetSelection.return_value = 0
        with patch("player.frames.playback.sponsorblock.wx") as wx_mock, patch(
            "player.frames.playback.sponsorblock.threading.Thread"
        ) as thread, patch.object(sponsorblock, "submit_segment") as submit:
            wx_mock.SingleChoiceDialog.return_value = dialog
            wx_mock.ID_OK = 5100
            wx_mock.CallAfter = lambda *args: None
            self.assertTrue(frame.on_sponsorblock_submit_segment(None))
            thread.call_args.kwargs["target"]()

        self.assertEqual(submit.call_args.args[-1], 300.0)

    def test_disabled_does_nothing(self):
        frame = _Frame()
        frame.settings.sponsorblock_enabled = False
        self.assertFalse(frame._maybe_handle_sponsorblock_segment())

    def test_contribution_requires_opt_in(self):
        frame = _Frame(contribute=False)
        self.assertFalse(frame.on_sponsorblock_mark_start(None))
        frame._save_settings.assert_not_called()

    def test_vote_generates_and_saves_user_id(self):
        frame = _Frame(contribute=True)
        frame.load(_model(10, 20))

        with patch("player.frames.playback.sponsorblock.threading.Thread") as thread:
            frame._maybe_handle_sponsorblock_segment()
            self.assertTrue(frame.on_sponsorblock_vote_up(None))

        self.assertGreaterEqual(len(frame.settings.sponsorblock_user_id), 30)
        frame._save_settings.assert_called_once()
        # Um para contar o pulo, outro para o voto.
        self.assertEqual(thread.return_value.start.call_count, 2)


if __name__ == "__main__":
    unittest.main()
