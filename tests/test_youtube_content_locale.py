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

from player.preferences.models import AppSettings
from player.youtube_music import content_locale, youtubejs_runtime
from player.youtube_music.client_provider import YouTubeMusicClientProvider


class ContentLocaleTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(content_locale.configure_content_locale)
        content_locale.configure_content_locale()

    def test_without_a_choice_the_language_follows_keytune(self):
        for app_language, expected in (("pt_BR", "pt"), ("en", "en"), ("es", "es"), ("xx", "en")):
            with self.subTest(app_language=app_language), patch.object(
                content_locale, "get_active_language", return_value=app_language
            ):
                self.assertEqual(content_locale.content_language(), expected)

    def test_a_chosen_language_and_region_go_with_every_youtubejs_request(self):
        content_locale.configure_content_locale(language="pt_pt", region="pt")

        self.assertEqual(content_locale.youtubejs_locale(), {"lang": "pt-PT", "location": "PT"})

    def test_unknown_codes_fall_back_to_the_defaults(self):
        content_locale.configure_content_locale(language="klingon", region="ZZ")

        self.assertEqual(content_locale.content_region(), "")
        with patch.object(content_locale, "get_active_language", return_value="es"):
            self.assertEqual(content_locale.content_language(), "es")

    def test_configure_tells_whether_anything_changed(self):
        self.assertTrue(content_locale.configure_content_locale(language="en", region="US"))
        self.assertFalse(content_locale.configure_content_locale(language="en", region="us"))

    def test_the_search_request_carries_language_and_region(self):
        content_locale.configure_content_locale(language="es", region="AR")
        with patch.object(youtubejs_runtime, "_request_worker") as request_worker:
            request_worker.return_value = {"entries": [{"id": "a", "title": "A"}], "has_more": True}

            entries, has_more = youtubejs_runtime.search_page("rock", "videos", start=20, count=20)

        self.assertEqual(
            request_worker.call_args.args[0],
            {"action": "search", "lang": "es", "location": "AR", "query": "rock", "kind": "videos", "start": 20, "count": 20},
        )
        self.assertEqual(entries, [{"id": "a", "title": "A"}])
        self.assertTrue(has_more)

    def test_a_worker_error_becomes_an_exception(self):
        with patch.object(youtubejs_runtime, "_request_worker", return_value={"error": "falhou"}):
            with self.assertRaisesRegex(RuntimeError, "falhou"):
                youtubejs_runtime.search_page("rock", "videos", start=0, count=20)

    def test_settings_keep_the_language_and_region(self):
        restored = AppSettings.from_dict(
            AppSettings(youtube_content_language="pt-PT", youtube_content_region="PT").to_dict()
        )

        self.assertEqual(restored.youtube_content_language, "pt-PT")
        self.assertEqual(restored.youtube_content_region, "PT")
        self.assertEqual(AppSettings.from_dict({}).youtube_content_language, "")


class ClientLocationTests(unittest.TestCase):
    def _module(self):
        return SimpleNamespace(YTMusic=Mock(), constants=SimpleNamespace(SUPPORTED_LOCATIONS={"BR", "US"}))

    def test_the_region_goes_to_the_youtube_music_client(self):
        module = self._module()

        YouTubeMusicClientProvider().get_client(ytmusicapi_module=module, require_auth=False, location="br")

        module.YTMusic.assert_called_once_with(location="BR")

    def test_a_region_ytmusicapi_does_not_know_is_left_out(self):
        module = self._module()

        YouTubeMusicClientProvider().get_client(ytmusicapi_module=module, require_auth=False, location="UY")

        module.YTMusic.assert_called_once_with()

    def test_changing_the_region_rebuilds_the_client(self):
        module = self._module()
        provider = YouTubeMusicClientProvider()

        provider.get_client(ytmusicapi_module=module, require_auth=False, location="BR")
        provider.get_client(ytmusicapi_module=module, require_auth=False, location="BR")
        provider.get_client(ytmusicapi_module=module, require_auth=False, location="US")

        self.assertEqual(module.YTMusic.call_count, 2)


if __name__ == "__main__":
    unittest.main()
