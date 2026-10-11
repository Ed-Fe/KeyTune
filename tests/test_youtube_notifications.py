from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.frames.youtube_music import notifications as frame_notifications
from player.frames.youtube_music.notifications import NotificationsMixin
from player.youtube_music import notifications
from player.youtube_music.folders import FOLDER_NOTIFICATIONS, home_folder_items
from player.youtube_music.notification_store import YouTubeNotificationStore
from player.youtube_music.notifications import notification_from_entry


def _entry(index, **extra):
    return {"id": f"n{index}", "title": f"Canal enviou o vídeo {index}", "published": "há 1 hora", "video_id": "dQw4w9WgXcQ", **extra}


def _notification(index, **extra):
    return notification_from_entry(_entry(index, **extra))


class NotificationItemTests(unittest.TestCase):
    def test_the_row_says_when_it_arrived_and_that_it_is_unread(self):
        notification = _notification(1)

        self.assertEqual(notification.choice_label, "Canal enviou o vídeo 1 — há 1 hora · não lida")
        self.assertEqual(notification.playback_url, "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertTrue(notification.can_open)

    def test_a_read_notification_without_video_only_shows_its_text(self):
        notification = _notification(1, read=True, video_id="", published="")

        self.assertEqual(notification.choice_label, "Canal enviou o vídeo 1")
        self.assertEqual(notification.playback_url, "")
        self.assertFalse(notification.can_open)

    def test_a_comment_notification_leads_to_the_conversation(self):
        notification = _notification(1, comment_id="c1.r1")

        self.assertTrue(notification.can_browse)
        self.assertFalse(notification.opens_on_enter)
        self.assertFalse(_notification(2).can_browse)

    def test_entries_without_id_or_text_are_dropped(self):
        self.assertIsNone(notification_from_entry({"id": "n1", "title": " "}))
        self.assertIsNone(notification_from_entry({"title": "Sem id"}))
        self.assertIsNone(notification_from_entry("texto"))


class NotificationsPageTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(notifications, "require_account_session", return_value=("SID=abc", 2))
        self.addCleanup(patcher.stop)
        self.account = patcher.start()

    def test_the_inbox_comes_from_the_account(self):
        with patch.object(notifications.youtubejs_runtime, "notifications_page", return_value=([_entry(1), {}], True)) as page_fn:
            page = notifications.notifications_page(0, 20)

        page_fn.assert_called_once_with("SID=abc", start=0, count=20, account_index=2)
        self.assertEqual([item.notification_id for item in page.results], ["n1"])
        self.assertTrue(page.has_more)

    def test_reading_and_hiding_act_on_the_notification(self):
        with patch.object(notifications.youtubejs_runtime, "notification_action") as action:
            notifications.mark_notification_read(_notification(1))
            notifications.hide_notification(_notification(2))

        self.assertEqual(
            [call.args for call in action.call_args_list],
            [("SID=abc", "n1", "read"), ("SID=abc", "n2", "hide")],
        )

    def test_without_the_account_there_is_no_inbox(self):
        self.account.side_effect = RuntimeError("Conecte a conta do YouTube para fazer isto.")

        with self.assertRaisesRegex(RuntimeError, "Conecte a conta"):
            notifications.notifications_page(0, 20)


class NewNotificationsTests(unittest.TestCase):
    def test_only_unread_ones_not_seen_before_are_new(self):
        items = [_notification(1), _notification(2, read=True), _notification(3)]

        new = notifications.unseen_notifications(items, {"n3"})

        self.assertEqual([item.notification_id for item in new], ["n1"])

    def test_the_spoken_message_counts_them(self):
        self.assertEqual(notifications.new_notifications_message([]), "")
        self.assertEqual(
            notifications.new_notifications_message([_notification(1)]),
            "Nova notificação do YouTube: Canal enviou o vídeo 1",
        )
        self.assertEqual(
            notifications.new_notifications_message([_notification(1), _notification(2)]),
            "2 novas notificações do YouTube. A mais recente: Canal enviou o vídeo 1",
        )


class NotificationStoreTests(unittest.TestCase):
    def test_what_was_seen_survives_a_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "notifications.json"
            store = YouTubeNotificationStore(path)
            self.assertFalse(store.has_baseline)

            store.remember(["n1", "n2"])
            reopened = YouTubeNotificationStore(path)

        self.assertTrue(reopened.has_baseline)
        self.assertEqual(reopened.seen_ids(), {"n1", "n2"})

    def test_an_empty_inbox_still_counts_as_a_baseline(self):
        with tempfile.TemporaryDirectory() as folder:
            store = YouTubeNotificationStore(pathlib.Path(folder) / "notifications.json")
            store.remember([])

            self.assertTrue(store.has_baseline)

    def test_a_broken_file_starts_over(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "notifications.json"
            path.write_text("{quebrado", encoding="utf-8")

            store = YouTubeNotificationStore(path)

        self.assertFalse(store.has_baseline)
        self.assertEqual(store.seen_ids(), set())


class _Frame(NotificationsMixin):
    def __init__(self, store, minutes=15):
        self.announcements = []
        self.statuses = []
        self.replaced = []
        self.settings = SimpleNamespace(youtube_notification_check_minutes=minutes)
        self._youtube_notification_store_instance = store
        self.integration_enabled = True

    def _announce(self, message):
        self.announcements.append(message)

    def _set_status_message(self, message):
        self.statuses.append(message)

    def _youtube_music_integration_enabled(self):
        return self.integration_enabled

    def _replace_youtube_music_result(self, old_result, new_result=None):
        self.replaced.append((old_result, new_result))


class NotificationCheckTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.store = YouTubeNotificationStore(pathlib.Path(folder.name) / "notifications.json")
        call_later = patch.object(frame_notifications.wx, "CallLater")
        self.addCleanup(call_later.stop)
        self.call_later = call_later.start()

    def test_the_first_check_ever_only_takes_note(self):
        frame = _Frame(self.store)

        frame._on_youtube_notifications_checked([_notification(1), _notification(2)])

        self.assertEqual(frame.announcements, [])
        self.assertEqual(self.store.seen_ids(), {"n1", "n2"})

    def test_what_arrives_later_is_announced_once(self):
        frame = _Frame(self.store)
        self.store.remember(["n1"])

        frame._on_youtube_notifications_checked([_notification(2), _notification(1)])
        frame._on_youtube_notifications_checked([_notification(2), _notification(1)])

        self.assertEqual(frame.announcements, ["Nova notificação do YouTube: Canal enviou o vídeo 2"])
        self.assertEqual(frame.statuses, frame.announcements)

    def test_a_failed_check_says_nothing_and_tries_again_later(self):
        frame = _Frame(self.store)

        frame._on_youtube_notifications_checked(None)

        self.assertEqual(frame.announcements, [])
        self.call_later.assert_called_once_with(15 * 60_000, frame._check_youtube_notifications)

    def test_in_the_background_the_notice_goes_to_windows_instead_of_being_spoken(self):
        frame = _Frame(self.store)
        self.store.remember(["n1"])
        frame._youtube_notification_goes_to_windows = Mock(return_value=True)
        frame._show_youtube_windows_notification = Mock(return_value=True)

        frame._on_youtube_notifications_checked([_notification(2)])

        frame._show_youtube_windows_notification.assert_called_once_with(
            "Nova notificação do YouTube: Canal enviou o vídeo 2"
        )
        self.assertEqual(frame.announcements, [])
        self.assertEqual(len(frame.statuses), 1)

    def test_when_windows_refuses_the_notice_is_spoken(self):
        frame = _Frame(self.store)
        self.store.remember(["n1"])
        frame._youtube_notification_goes_to_windows = Mock(return_value=True)
        frame._show_youtube_windows_notification = Mock(return_value=False)

        frame._on_youtube_notifications_checked([_notification(2)])

        self.assertEqual(len(frame.announcements), 1)

    def test_the_windows_notice_is_only_for_a_window_in_the_background(self):
        frame = _Frame(self.store)
        frame.IsShown = Mock(return_value=True)
        frame.IsIconized = Mock(return_value=False)
        frame.IsActive = Mock(return_value=True)
        self.assertFalse(frame._youtube_notification_goes_to_windows())

        frame.IsActive.return_value = False
        self.assertTrue(frame._youtube_notification_goes_to_windows())

        frame.settings.youtube_notification_windows_toast = False
        self.assertFalse(frame._youtube_notification_goes_to_windows())

    def test_the_conversation_of_a_notification_starts_at_its_comment(self):
        frame = _Frame(self.store)
        frame._build_youtube_music_comments_view = Mock()

        frame._build_youtube_notification_conversation_view(_notification(1, comment_id="c1.r1"))
        context = frame._build_youtube_music_comments_view.call_args.args[0]

        self.assertEqual((context.media_url, context.linked_comment), ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "c1.r1"))
        self.assertIsNone(frame._build_youtube_notification_conversation_view(_notification(2)))

    def test_the_check_is_off_when_the_preference_says_never(self):
        frame = _Frame(self.store, minutes=0)

        self.assertFalse(frame._schedule_youtube_notification_check(first=True))
        self.call_later.assert_not_called()

    def test_the_check_is_off_without_the_youtube_integration(self):
        frame = _Frame(self.store)
        frame.integration_enabled = False

        self.assertFalse(frame._schedule_youtube_notification_check())
        self.call_later.assert_not_called()

    def test_the_first_check_does_not_wait_the_whole_interval(self):
        frame = _Frame(self.store, minutes=30)

        self.assertTrue(frame._schedule_youtube_notification_check(first=True))

        self.call_later.assert_called_once_with(45_000, frame._check_youtube_notifications)

    def test_rescheduling_cancels_the_pending_check(self):
        frame = _Frame(self.store)
        frame._schedule_youtube_notification_check()
        pending = self.call_later.return_value

        frame._schedule_youtube_notification_check()

        pending.Stop.assert_called_once_with()

    def test_opening_the_list_counts_as_seeing_it(self):
        frame = _Frame(self.store)
        page = SimpleNamespace(results=(_notification(1),), has_more=False)
        with patch.object(notifications, "notifications_page", return_value=page):
            view = frame._build_youtube_notifications_view()
            view.fetch_page(0, 20)

        self.assertEqual(view.title, "Notificações")
        self.assertEqual(self.store.seen_ids(), {"n1"})

    def test_the_command_waits_for_the_tab_to_finish_loading(self):
        frame = _Frame(self.store)
        frame.on_open_youtube_music = Mock()
        frame._get_youtube_music_panel = Mock()
        frame._ensure_youtube_music_authenticated = Mock(return_value=True)
        frame._is_youtube_music_operation_in_progress = Mock(return_value=True)
        frame._queue_youtube_music_post_operation_callback = Mock()
        frame._load_youtube_music_results_view = Mock(return_value=True)

        self.assertTrue(frame.on_open_youtube_notifications())
        frame._queue_youtube_music_post_operation_callback.assert_called_once_with(frame._open_youtube_notifications_view)
        frame._load_youtube_music_results_view.assert_not_called()

        frame._is_youtube_music_operation_in_progress.return_value = False
        self.assertTrue(frame.on_open_youtube_notifications())
        view = frame._load_youtube_music_results_view.call_args.args[0]
        self.assertEqual(view.title, "Notificações")
        self.assertTrue(frame._load_youtube_music_results_view.call_args.kwargs["focus_results"])

    def test_marking_as_read_updates_the_row(self):
        frame = _Frame(self.store)
        notification = _notification(1)

        frame._on_youtube_notifications_marked_read([notification], announce=True)

        old, new = frame.replaced[0]
        self.assertIs(old, notification)
        self.assertTrue(new.read)
        self.assertEqual(frame.announcements, ["Notificação marcada como lida."])

    def test_read_notifications_are_not_marked_again(self):
        frame = _Frame(self.store)

        self.assertFalse(frame._mark_youtube_notifications_read([_notification(1, read=True), Mock(result_type="video")]))

    def test_the_menu_offers_what_fits_the_notification(self):
        frame = _Frame(self.store)

        def labels(result):
            return [label for label, _action in frame._youtube_notification_menu_entries(result)]

        self.assertEqual(labels(_notification(1)), ["Marcar como lida", "Ocultar esta notificação"])
        self.assertEqual(labels(_notification(2, read=True)), ["Ocultar esta notificação"])
        self.assertEqual(labels(Mock(result_type="video")), [])


class HomeFolderTests(unittest.TestCase):
    def test_the_inbox_is_on_the_home_list_and_asks_for_the_account(self):
        folders = {folder.kind: folder for folder in home_folder_items()}

        self.assertEqual(folders[FOLDER_NOTIFICATIONS].title, "Notificações")
        self.assertTrue(folders[FOLDER_NOTIFICATIONS].requires_auth)


if __name__ == "__main__":
    unittest.main()
