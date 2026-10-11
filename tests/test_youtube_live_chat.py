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

from player.frames.youtube_music import live_chat as frame_live_chat
from player.frames.youtube_music.comments import CommentsMixin
from player.frames.youtube_music.live_chat import LiveChatContext, LiveChatMixin
from player.frames.youtube_music.navigation import ResultsNavigationMixin, YouTubeResultsView
from player.youtube_music import live_chat
from player.youtube_music.live_chat import LiveChatUpdate, message_from_entry
from player.youtube_music.models import YOUTUBE_SEARCH_SOURCE_YOUTUBE, YouTubeMediaSearchResult


URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def _message(index, **extra):
    return message_from_entry({"id": f"m{index}", "author": f"@pessoa{index}", "text": f"Mensagem {index}", **extra})


class LiveChatTests(unittest.TestCase):
    def test_the_wait_follows_what_the_youtube_asks_within_limits(self):
        self.assertEqual(live_chat.poll_seconds_for(0), live_chat.LIVE_CHAT_POLL_SECONDS)
        self.assertEqual(live_chat.poll_seconds_for(1000), live_chat.LIVE_CHAT_POLL_SECONDS)
        self.assertEqual(live_chat.poll_seconds_for(8000), 8)
        self.assertEqual(live_chat.poll_seconds_for(120000), live_chat.LIVE_CHAT_MAX_POLL_SECONDS)
        self.assertEqual(live_chat.poll_seconds_for("lixo"), live_chat.LIVE_CHAT_POLL_SECONDS)

    def test_the_update_carries_the_wait_the_youtube_asked(self):
        with patch.object(live_chat, "youtubejs_resolver_enabled", return_value=True), patch.object(
            live_chat.youtubejs_runtime, "live_chat", return_value=([], False, False, "", 9000)
        ), patch.object(live_chat, "optional_account_session", return_value=("", 0)):
            update = live_chat.live_chat_update("https://www.youtube.com/watch?v=abc123DEF45")

        self.assertEqual(update.poll_seconds, 9)

    def setUp(self):
        patcher = patch.object(live_chat, "youtubejs_resolver_enabled", return_value=True)
        self.addCleanup(patcher.stop)
        self.youtubejs_enabled = patcher.start()
        account = patch.object(live_chat, "optional_account_session", return_value=("", 0))
        self.addCleanup(account.stop)
        self.account = account.start()

    def test_the_row_says_who_wrote_and_what(self):
        self.assertEqual(_message(1, text="Oi\n gente").choice_label, "@pessoa1: Oi gente")
        self.assertEqual(_message(2, amount="R$ 10,00").choice_label, "@pessoa2: R$ 10,00 Mensagem 2")
        self.assertEqual(live_chat.message_reading_text(_message(1)), "Mensagem 1\n\n@pessoa1")

    def test_entries_without_id_or_content_are_dropped(self):
        self.assertIsNone(message_from_entry({"id": "m1", "text": " "}))
        self.assertIsNone(message_from_entry({"text": "sem id"}))
        self.assertIsNotNone(message_from_entry({"id": "m1", "amount": "R$ 5,00"}))

    def test_without_the_account_the_chat_is_read_only(self):
        entries = [{"id": "m1", "author": "@a", "text": "Oi"}, {"id": ""}]
        with patch.object(live_chat.youtubejs_runtime, "live_chat", return_value=(entries, False, False)) as chat:
            update = live_chat.live_chat_update(URL, restart=True)

        chat.assert_called_once_with(URL, restart=True)
        self.assertEqual([message.message_id for message in update.messages], ["m1"])
        self.assertFalse(update.can_send)

    def test_with_the_account_the_chat_comes_through_it(self):
        self.account.return_value = ("SID=abc", 2)
        with patch.object(live_chat.youtubejs_runtime, "live_chat", return_value=([], True, False)) as chat:
            update = live_chat.live_chat_update(URL)

        chat.assert_called_once_with(URL, restart=False, cookie_header="SID=abc", account_index=2)
        self.assertTrue(update.can_send)

    def test_sending_needs_the_account_and_some_text(self):
        with patch.object(live_chat, "require_account_session", return_value=("SID=abc", 1)), patch.object(
            live_chat.youtubejs_runtime, "live_chat_send"
        ) as send:
            live_chat.send_live_chat_message(URL, "  boa   noite ")
            with self.assertRaisesRegex(RuntimeError, "vazia"):
                live_chat.send_live_chat_message(URL, "   ")

        send.assert_called_once_with("SID=abc", URL, "boa noite", account_index=1)

    def test_the_chat_needs_youtubejs(self):
        self.youtubejs_enabled.return_value = False

        with self.assertRaisesRegex(RuntimeError, "YouTube.js"):
            live_chat.live_chat_update(URL)

    def test_the_account_name_comes_with_the_update(self):
        self.account.return_value = ("SID=abc", 0)
        with patch.object(live_chat.youtubejs_runtime, "live_chat", return_value=([], True, False, "@eu")):
            self.assertEqual(live_chat.live_chat_update(URL).viewer, "@eu")

    def test_the_sound_is_the_one_of_the_most_important_message(self):
        plain = _message(1)
        paid = _message(2, amount="R$ 10,00")
        mention = _message(3, text="oi @EU, tudo bem?")
        own = message_from_entry({"id": "m4", "author": "@eu", "text": "eu sou @eu"})

        self.assertEqual(live_chat.messages_sound([plain], "@eu"), "chat_message")
        self.assertEqual(live_chat.messages_sound([plain, paid], "@eu"), "chat_paid")
        self.assertEqual(live_chat.messages_sound([paid, mention], "@eu"), "chat_mention")
        self.assertEqual(live_chat.messages_sound([mention]), "chat_message")
        self.assertEqual(live_chat.messages_sound([own], "@eu"), "chat_message")

    def test_only_the_latest_messages_are_spoken(self):
        spoken = live_chat.spoken_messages([_message(index) for index in range(1, 7)])

        self.assertEqual(spoken, ["@pessoa4: Mensagem 4", "@pessoa5: Mensagem 5", "@pessoa6: Mensagem 6"])


class _Frame(LiveChatMixin, CommentsMixin, ResultsNavigationMixin):
    def __init__(self):
        self.announcements = []
        self.shown = []
        self.panel = Mock()
        self.panel.get_selected_search_result_ids.return_value = []
        self.busy = False

    def _announce(self, message):
        self.announcements.append(message)

    def _youtube_music_library_page_size(self):
        return 20

    def _get_youtube_music_panel(self):
        return self.panel

    def _set_youtube_music_search_results(self, results, *, status_message=None, view=None):
        self.shown.append(list(results))

    def _refresh_youtube_music_screen_later(self):
        pass

    def _format_youtube_music_error_detail(self, exc):
        return str(exc)

    def _is_youtube_music_operation_in_progress(self):
        return self.busy

    def _ensure_youtube_music_authenticated(self):
        return True

    def _run_youtube_music_background_task(self, worker, on_success, *, on_error=None, timeout_ms=None):
        try:
            result = worker()
        except Exception as exc:
            on_error(exc)
            return True
        on_success(result)
        return True


class LiveChatFrameTests(unittest.TestCase):
    def setUp(self):
        wx_patcher = patch.object(frame_live_chat, "wx")
        self.addCleanup(wx_patcher.stop)
        self.wx = wx_patcher.start()
        self.wx.ID_OK = 5100

    def _live(self):
        return YouTubeMediaSearchResult(
            source=YOUTUBE_SEARCH_SOURCE_YOUTUBE, result_type="video", title="Jornal", video_id="dQw4w9WgXcQ", playback_url=URL, is_live=True
        )

    def _open(self, frame, update):
        with patch.object(live_chat, "live_chat_update", return_value=update) as chat:
            self.assertTrue(frame.show_youtube_music_live_chat(self._live()))
        chat.assert_called_once_with(URL, restart=True)
        return frame._youtube_music_current_results_view()

    def test_the_chat_opens_as_a_list_and_starts_following(self):
        frame = _Frame()
        view = self._open(frame, LiveChatUpdate(messages=(_message(1),), can_send=True))

        self.assertEqual(view.title, "Chat ao vivo de Jornal")
        self.assertEqual([item.choice_label for item in view.results], ["Enviar uma mensagem...", "@pessoa1: Mensagem 1"])
        self.assertFalse(view.has_more)
        self.wx.CallLater.assert_called_once_with(4000, frame._update_youtube_live_chat)

    def test_without_the_account_there_is_no_send_row(self):
        frame = _Frame()
        view = self._open(frame, LiveChatUpdate(messages=(_message(1),)))

        self.assertEqual([item.result_type for item in view.results], ["chat"])

    def test_only_a_live_broadcast_offers_the_chat_in_the_menu(self):
        frame = _Frame()
        recorded = YouTubeMediaSearchResult(
            source=YOUTUBE_SEARCH_SOURCE_YOUTUBE, result_type="video", title="Clipe", video_id="dQw4w9WgXcQ", playback_url=URL
        )

        self.assertEqual([label for label, _a in frame._youtube_music_live_chat_menu_entries(self._live())], ["Ver o chat ao vivo"])
        self.assertEqual(frame._youtube_music_live_chat_menu_entries(recorded), [])

    def test_new_messages_enter_the_list_and_are_spoken(self):
        frame = _Frame()
        view = self._open(frame, LiveChatUpdate(messages=(_message(1),), can_send=True))
        frame.announcements.clear()

        frame._on_youtube_live_chat_updated(view, LiveChatUpdate(messages=(_message(1), _message(2))))

        self.assertEqual([item.stable_id for item in view.results], ["action:send_chat_message", "chat:m1", "chat:m2"])
        self.assertEqual(frame.announcements, ["@pessoa2: Mensagem 2"])
        self.assertEqual(self.wx.CallLater.call_count, 2)

    def test_speech_can_be_turned_off(self):
        frame = _Frame()
        view = self._open(frame, LiveChatUpdate())
        frame.toggle_youtube_live_chat_speech()
        frame.announcements.clear()

        frame._on_youtube_live_chat_updated(view, LiveChatUpdate(messages=(_message(2),)))

        self.assertEqual(frame.announcements, [])
        self.assertEqual(len(view.results), 1)
        self.assertEqual(
            [label for label, _action in frame._youtube_music_live_chat_list_menu_entries()],
            ["Falar as mensagens do chat"],
        )

    def test_the_list_keeps_only_the_latest_messages(self):
        frame = _Frame()
        view = self._open(frame, LiveChatUpdate(can_send=True))
        with patch.object(live_chat, "LIVE_CHAT_MAX_MESSAGES", 3):
            frame._append_youtube_live_chat_messages(view, [_message(index) for index in range(1, 6)])

        self.assertEqual([item.stable_id for item in view.results], ["action:send_chat_message", "chat:m3", "chat:m4", "chat:m5"])

    def test_the_end_of_the_broadcast_stops_the_following(self):
        frame = _Frame()
        view = self._open(frame, LiveChatUpdate())
        self.wx.CallLater.reset_mock()

        frame._on_youtube_live_chat_updated(view, LiveChatUpdate(ended=True))

        self.assertEqual(frame.announcements[-1], "O chat ao vivo terminou.")
        self.wx.CallLater.assert_not_called()

    def test_a_failed_update_tries_again(self):
        frame = _Frame()
        view = self._open(frame, LiveChatUpdate())
        self.wx.CallLater.reset_mock()

        frame._on_youtube_live_chat_updated(view, None)

        self.wx.CallLater.assert_called_once()

    def test_with_another_list_on_top_the_chat_waits(self):
        frame = _Frame()
        self._open(frame, LiveChatUpdate())
        frame._youtube_music_results_views().append(YouTubeResultsView(title="Outra"))
        self.wx.CallLater.reset_mock()
        with patch.object(frame_live_chat.threading, "Thread") as thread:
            self.assertFalse(frame._update_youtube_live_chat())

        thread.assert_not_called()
        self.wx.CallLater.assert_called_once()

    def test_leaving_the_chat_ends_the_following(self):
        frame = _Frame()
        self._open(frame, LiveChatUpdate())
        frame.on_youtube_music_results_back()
        self.wx.CallLater.reset_mock()

        self.assertFalse(frame._update_youtube_live_chat())
        self.wx.CallLater.assert_not_called()

    def test_sending_a_message_announces_it(self):
        frame = _Frame()
        self._open(frame, LiveChatUpdate(can_send=True))
        dialog = self.wx.TextEntryDialog.return_value
        dialog.ShowModal.return_value = self.wx.ID_OK
        dialog.GetValue.return_value = "boa noite"
        with patch.object(live_chat, "send_live_chat_message") as send:
            self.assertTrue(frame.send_youtube_live_chat_message())

        send.assert_called_once_with(URL, "boa noite")
        self.assertEqual(frame.announcements[-1], "Mensagem enviada.")

    def test_outside_a_chat_there_is_nothing_to_send(self):
        frame = _Frame()
        with patch.object(live_chat, "send_live_chat_message") as send:
            self.assertFalse(frame.send_youtube_live_chat_message())

        send.assert_not_called()

    def test_the_current_media_must_be_from_youtube(self):
        frame = _Frame()
        frame._get_active_playlist_state = lambda: SimpleNamespace(current_media_path="C:/musica.mp3")

        self.assertFalse(frame.show_current_media_live_chat())
        self.assertEqual(frame.announcements, ["A mídia atual não é do YouTube: não há chat ao vivo."])


if __name__ == "__main__":
    unittest.main()
