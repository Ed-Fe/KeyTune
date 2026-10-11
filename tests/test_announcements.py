import unittest
from types import SimpleNamespace

from player import announcements


class AnnouncementCategoryTests(unittest.TestCase):
    def _settings(self, **fields):
        return SimpleNamespace(**fields)

    def test_a_message_without_category_always_speaks(self):
        self.assertTrue(announcements.should_speak(self._settings(), None, window_active=True))

    def test_a_disabled_category_is_silent(self):
        settings = self._settings(announcements_disabled=[announcements.ANNOUNCE_CHAT_MESSAGES])
        self.assertFalse(
            announcements.should_speak(settings, announcements.ANNOUNCE_CHAT_MESSAGES, window_active=False)
        )
        self.assertTrue(
            announcements.should_speak(settings, announcements.ANNOUNCE_NOTIFICATIONS, window_active=False)
        )

    def test_events_can_stay_silent_while_the_window_is_active(self):
        settings = self._settings(announcements_in_window=False)
        self.assertFalse(
            announcements.should_speak(settings, announcements.ANNOUNCE_NOTIFICATIONS, window_active=True)
        )
        self.assertTrue(
            announcements.should_speak(settings, announcements.ANNOUNCE_NOTIFICATIONS, window_active=False)
        )

    def test_events_speak_in_the_window_by_default(self):
        self.assertTrue(
            announcements.should_speak(self._settings(), announcements.ANNOUNCE_CHAT_MESSAGES, window_active=True)
        )

    def test_the_disabled_list_keeps_only_known_categories_in_order(self):
        self.assertEqual(
            announcements.normalize_disabled_announcements(["timer", "nope", "chat_messages"]),
            ["chat_messages", "timer"],
        )
        self.assertEqual(announcements.normalize_disabled_announcements("timer"), [])

    def test_every_category_has_a_label(self):
        self.assertEqual(
            [name for name, _label in announcements.announcement_labels()],
            list(announcements.ANNOUNCEMENT_CATEGORIES),
        )


if __name__ == "__main__":
    unittest.main()
