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

from player.frames.youtube_music.browse import BrowseMixin
from player.youtube_music import subscriptions
from player.youtube_music.folders import (
    FOLDER_SUBSCRIBED_CHANNELS,
    FOLDER_SUBSCRIPTION_VIDEOS,
    home_folder_items,
)


CHANNEL_ID = "UC" + "a" * 22


class SubscriptionsTests(unittest.TestCase):
    def setUp(self):
        self.youtubejs_enabled = self._patch(subscriptions, "youtubejs_resolver_enabled", True)
        self.auth = self._patch(subscriptions, "load_saved_playback_auth", SimpleNamespace(cookie_header="SID=abc"))

    def _patch(self, target, name, return_value):
        patcher = patch.object(target, name, return_value=return_value)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def test_the_new_videos_come_with_duration_views_and_date(self):
        entries = [
            {
                "id": "video000001",
                "title": "Vídeo novo",
                "channel": "Canal Um e Canal Dois",
                "duration_text": "14:15",
                "view_count_number_text": "652 mil",
                "published": "há 2 dias",
            }
        ]
        with patch.object(subscriptions.youtubejs_runtime, "subscription_videos_page", return_value=(entries, True)) as page_fn:
            page = subscriptions.subscription_videos_page(20, 20)

        page_fn.assert_called_once_with("SID=abc", start=20, count=20)
        video = page.results[0]
        self.assertEqual(video.result_type, "video")
        self.assertEqual(video.subtitle, "Canal Um e Canal Dois")
        self.assertEqual(video.detail_text, "14:15 · 652 mil visualizações · há 2 dias")
        self.assertTrue(page.has_more)

    def test_the_subscribed_channels_open_like_any_channel(self):
        entries = [
            {
                "id": CHANNEL_ID,
                "title": "Canal",
                "url": f"https://www.youtube.com/channel/{CHANNEL_ID}",
                "channel_id": CHANNEL_ID,
                "detail_text": "433 mil inscritos",
            }
        ]
        with patch.object(subscriptions.youtubejs_runtime, "subscribed_channels_page", return_value=(entries, False)):
            page = subscriptions.subscribed_channels_page(0, 20)

        channel = page.results[0]
        self.assertEqual((channel.result_type, channel.browse_id, channel.detail_text), ("channel", CHANNEL_ID, "433 mil inscritos"))
        self.assertTrue(channel.can_browse)

    def test_subscriptions_need_youtubejs(self):
        self.youtubejs_enabled.return_value = False

        with self.assertRaisesRegex(RuntimeError, "YouTube.js"):
            subscriptions.subscription_videos_page(0, 20)

    def test_subscriptions_need_the_account(self):
        self.auth.return_value = SimpleNamespace(cookie_header="")

        with self.assertRaisesRegex(RuntimeError, "Conecte a conta"):
            subscriptions.subscribed_channels_page(0, 20)

    def test_the_home_folders_load_page_by_page_and_ask_for_the_account(self):
        folders = {folder.kind: folder for folder in home_folder_items()}
        frame = BrowseMixin()
        frame._get_youtube_music_service = Mock()

        videos = frame._build_youtube_music_folder_view(folders[FOLDER_SUBSCRIPTION_VIDEOS])
        channels = frame._build_youtube_music_folder_view(folders[FOLDER_SUBSCRIBED_CHANNELS])

        self.assertEqual((videos.title, channels.title), ("Vídeos das inscrições", "Canais inscritos"))
        self.assertIs(videos.fetch_page, subscriptions.subscription_videos_page)
        self.assertIs(channels.fetch_page, subscriptions.subscribed_channels_page)
        self.assertTrue(folders[FOLDER_SUBSCRIPTION_VIDEOS].requires_auth)
        self.assertTrue(folders[FOLDER_SUBSCRIBED_CHANNELS].requires_auth)


if __name__ == "__main__":
    unittest.main()
