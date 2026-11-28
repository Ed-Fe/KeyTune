"""KeyTune como navegador padrão: quais links ele toca e como repassa os outros."""

from __future__ import annotations

import pathlib
import sys
import unittest
from unittest.mock import Mock, patch


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import main
from player import link_router
from player.frames.commands.open_commands import OpenCommandsMixin
from player.preferences.models import AppSettings
from player.youtube_links import is_youtube_link, normalize_youtube_link, youtube_playlist_id

VIDEO = "dQw4w9WgXcQ"


class YouTubeLinkClassificationTests(unittest.TestCase):
    def test_video_and_playlist_links_are_youtube(self):
        for url in (
            f"https://www.youtube.com/watch?v={VIDEO}",
            f"https://youtube.com/watch?v={VIDEO}&t=42s",
            f"https://m.youtube.com/watch?v={VIDEO}",
            f"https://music.youtube.com/watch?v={VIDEO}&list=RDAMVM{VIDEO}",
            f"https://youtu.be/{VIDEO}?si=abc",
            f"https://www.youtube.com/shorts/{VIDEO}",
            f"https://www.youtube.com/live/{VIDEO}?feature=share",
            f"https://www.youtube.com/embed/{VIDEO}",
            "https://www.youtube.com/playlist?list=PLabcdefgh",
            "https://music.youtube.com/playlist?list=OLAK5uy_abc",
            f"HTTPS://WWW.YOUTUBE.COM/watch?v={VIDEO}",
        ):
            with self.subTest(url=url):
                self.assertTrue(is_youtube_link(url))

    def test_other_links_go_to_the_browser(self):
        for url in (
            "https://www.youtube.com/",
            "https://www.youtube.com/@canal",
            "https://www.youtube.com/results?search_query=musica",
            "https://www.youtube.com/watch",
            "https://www.youtube.com/watch?v=curto",
            "https://www.youtube.com/playlist",
            "https://music.youtube.com/",
            "https://youtu.be/",
            "https://example.com/watch?v=" + VIDEO,
            "https://notyoutube.com/watch?v=" + VIDEO,
            "https://youtube.com.example.com/watch?v=" + VIDEO,
            "ftp://youtube.com/watch?v=" + VIDEO,
            f"youtube.com/watch?v={VIDEO}",
            "",
            None,
        ):
            with self.subTest(url=url):
                self.assertFalse(is_youtube_link(url))

    def test_links_become_the_watch_address_the_player_opens(self):
        self.assertEqual(normalize_youtube_link(f"https://youtu.be/{VIDEO}?t=3"), f"https://www.youtube.com/watch?v={VIDEO}")
        self.assertEqual(
            normalize_youtube_link(f"https://www.youtube.com/shorts/{VIDEO}"), f"https://www.youtube.com/watch?v={VIDEO}"
        )
        self.assertEqual(
            normalize_youtube_link(f"https://music.youtube.com/watch?v={VIDEO}&list=RDX12345"),
            f"https://music.youtube.com/watch?v={VIDEO}",
        )
        self.assertEqual(
            normalize_youtube_link("https://m.youtube.com/playlist?list=PLabcdefgh"),
            "https://www.youtube.com/playlist?list=PLabcdefgh",
        )
        self.assertEqual(normalize_youtube_link("https://example.com/x"), "https://example.com/x")

    def test_only_playlist_pages_count_as_playlists(self):
        self.assertEqual(youtube_playlist_id("https://www.youtube.com/playlist?list=PLabcdefgh"), "PLabcdefgh")
        self.assertIsNone(youtube_playlist_id(f"https://www.youtube.com/watch?v={VIDEO}&list=PLabcdefgh"))
        self.assertIsNone(youtube_playlist_id("https://example.com/playlist?list=PLabcdefgh"))


class LinkArgumentTests(unittest.TestCase):
    def test_first_web_link_is_taken(self):
        self.assertEqual(
            link_router.link_from_arguments(["--enqueue", '"https://a.example/x"', "https://b.example"]),
            "https://a.example/x",
        )

    def test_files_and_long_links_are_not_links(self):
        self.assertIsNone(link_router.link_from_arguments([r"C:\midia\a.mp3", "file:///C:/a.mp3"]))
        self.assertIsNone(link_router.link_from_arguments(["https://a.example/" + "x" * 3000]))
        self.assertIsNone(link_router.link_from_arguments([]))

    def test_collect_initial_paths_keeps_the_link_text(self):
        url = f"https://www.youtube.com/watch?v={VIDEO}&t=10s"
        initial_paths = main._collect_initial_paths(
            [f'"{url}"', r"C:\midia\a.mp3"],
            launch_targets=[r"D:\KeyTune\KeyTune.exe"],
        )
        self.assertEqual(initial_paths, [url, r"C:\midia\a.mp3"])


class BuildCommandTests(unittest.TestCase):
    def test_placeholder_is_replaced(self):
        self.assertEqual(
            link_router.build_command(r'"C:\Firefox\firefox.exe" -osint -url "%1"', "https://a.example/?q=1&b=2"),
            r'"C:\Firefox\firefox.exe" -osint -url "https://a.example/?q=1&b=2"',
        )
        self.assertEqual(
            link_router.build_command(r'"C:\Chrome\chrome.exe" --single-argument %L', "https://a.example"),
            r'"C:\Chrome\chrome.exe" --single-argument https://a.example',
        )

    def test_url_is_appended_when_there_is_no_placeholder(self):
        self.assertEqual(
            link_router.build_command(r'"C:\Chrome\chrome.exe"', "https://a.example"),
            r'"C:\Chrome\chrome.exe" "https://a.example"',
        )

    def test_quotes_and_spaces_cannot_break_out_of_the_argument(self):
        command = link_router.build_command(r'"C:\B\b.exe" "%1"', 'https://a.example/" --evil x')
        self.assertEqual(command, r'"C:\B\b.exe" "https://a.example/%22%20--evil%20x"')

    def test_extra_argument_placeholders_are_dropped(self):
        self.assertEqual(
            link_router.build_command(r'"C:\B\b.exe" "%1" %*', "https://a.example"),
            r'"C:\B\b.exe" "https://a.example"',
        )


class BrowserChoiceTests(unittest.TestCase):
    def test_executable_of_quoted_and_unquoted_commands(self):
        self.assertEqual(link_router.executable_of(r'"C:\Program Files\B\b.exe" -url "%1"'), r"C:\Program Files\B\b.exe")
        self.assertEqual(link_router.executable_of(r"C:\Program Files\B\b.exe -url %1"), r"C:\Program Files\B\b.exe")
        self.assertEqual(link_router.executable_of("b %1"), "b")

    def test_keytune_and_internet_explorer_never_receive_links(self):
        self.assertTrue(link_router.is_forbidden_browser(r'"C:\Apps\KeyTune\KeyTune.exe" "%1"'))
        self.assertTrue(link_router.is_forbidden_browser(r'"C:\Program Files\Internet Explorer\iexplore.exe" %1'))
        self.assertTrue(link_router.is_forbidden_browser(""))
        self.assertFalse(link_router.is_forbidden_browser(r'"C:\Firefox\firefox.exe" "%1"'))

    def test_accessible_reels_never_receives_links(self):
        self.assertTrue(link_router.is_forbidden_browser(r'"C:\Apps\Accessible Reels\Accessible Reels.exe" "%1"'))
        self.assertTrue(link_router.is_forbidden_browser(r'"C:\Python\python.exe" "C:\git\accessible-reels\main.py" "%1"'))
        self.assertIn("accessiblereelsurl", link_router._own_prog_ids())

    def test_preferred_browser_comes_first_without_repeats(self):
        firefox = r'"C:\Firefox\firefox.exe" -url "%1"'
        edge = r'"C:\Edge\msedge.exe" --single-argument %1'
        with patch.object(link_router, "preferred_browser", return_value="Firefox"), patch.object(
            link_router, "registered_browsers", return_value={"Microsoft Edge": edge, "Firefox": firefox}
        ), patch.object(link_router, "current_default_prog_id", return_value="KeyTuneURL"), patch.object(
            link_router, "remembered_prog_id", return_value="MSEdgeHTM"
        ), patch.object(link_router, "_prog_id_command", return_value=edge):
            self.assertEqual(list(link_router.browser_commands()), [firefox, edge])

    def test_previous_default_is_used_when_nothing_is_preferred(self):
        edge = r'"C:\Edge\msedge.exe" --single-argument %1'
        firefox = r'"C:\Firefox\firefox.exe" -url "%1"'
        with patch.object(link_router, "preferred_browser", return_value=""), patch.object(
            link_router, "registered_browsers", return_value={"Firefox": firefox}
        ), patch.object(link_router, "current_default_prog_id", return_value="KeyTuneURL"), patch.object(
            link_router, "remembered_prog_id", return_value="MSEdgeHTM"
        ), patch.object(link_router, "_prog_id_command", return_value=edge):
            self.assertEqual(list(link_router.browser_commands()), [edge, firefox])


class RouteLaunchTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(link_router, "remember_default_browser")
        patcher.start()
        self.addCleanup(patcher.stop)
        platform = patch.object(link_router.sys, "platform", "win32")
        platform.start()
        self.addCleanup(platform.stop)

    def test_youtube_link_and_bare_launch_continue_into_keytune(self):
        with patch.object(link_router, "open_in_browser") as open_in_browser:
            self.assertFalse(link_router.route_launch([f"https://youtu.be/{VIDEO}"]))
            self.assertFalse(link_router.route_launch([]))
            self.assertFalse(link_router.route_launch([r"C:\midia\a.mp3"]))
        open_in_browser.assert_not_called()

    def test_other_link_goes_to_the_browser_and_exits(self):
        with patch.object(link_router, "open_in_browser", return_value=True) as open_in_browser:
            self.assertTrue(link_router.route_launch(["https://example.com/page"]))
        open_in_browser.assert_called_once_with("https://example.com/page")

    def test_warns_when_no_browser_takes_the_link(self):
        with patch.object(link_router, "open_in_browser", return_value=False), patch.object(
            link_router, "_show_no_browser_message"
        ) as warn:
            self.assertTrue(link_router.route_launch(["https://example.com/page"]))
        warn.assert_called_once_with()

    def test_does_nothing_outside_windows(self):
        with patch.object(link_router.sys, "platform", "linux"), patch.object(link_router, "open_in_browser") as opener:
            self.assertFalse(link_router.route_launch(["https://example.com/page"]))
        opener.assert_not_called()


class OpenedLinkTests(unittest.TestCase):
    def test_split_keeps_youtube_links_as_media(self):
        frame = OpenCommandsMixin.__new__(OpenCommandsMixin)
        frame._normalize_path = lambda path: str(path)
        media_paths, playlist_paths = frame._split_selected_files(
            [f"https://www.youtube.com/shorts/{VIDEO}", "https://example.com/video.mp4"]
        )
        self.assertEqual(media_paths, [f"https://www.youtube.com/watch?v={VIDEO}"])
        self.assertEqual(playlist_paths, [])

    def test_playlist_link_opens_the_youtube_playlist(self):
        frame = OpenCommandsMixin.__new__(OpenCommandsMixin)
        frame._load_youtube_music_playlist_by_id = Mock()
        self.assertTrue(frame._open_external_youtube_playlist(["https://www.youtube.com/playlist?list=PLabcdefgh"]))
        frame._load_youtube_music_playlist_by_id.assert_called_once()
        self.assertEqual(frame._load_youtube_music_playlist_by_id.call_args.args, ("PLabcdefgh",))
        self.assertFalse(frame._open_external_youtube_playlist([f"https://youtu.be/{VIDEO}"]))


class LinkBrowserSettingTests(unittest.TestCase):
    def test_round_trip_and_bad_values(self):
        settings = AppSettings.from_dict({"link_browser": " Firefox "})
        self.assertEqual(settings.link_browser, "Firefox")
        self.assertEqual(AppSettings.from_dict(settings.to_dict()).link_browser, "Firefox")
        self.assertEqual(AppSettings.from_dict({"link_browser": 3}).link_browser, "")
        self.assertEqual(AppSettings().link_browser, "")


if __name__ == "__main__":
    unittest.main()
