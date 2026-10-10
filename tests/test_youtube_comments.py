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

from player.frames.youtube_music.comments import CommentsMixin
from player.frames.youtube_music.navigation import ResultsNavigationMixin
from player.youtube_music import comments
from player.youtube_music.comments import YouTubeCommentItem, comment_from_entry
from player.youtube_music.models import (
    YOUTUBE_SEARCH_SOURCE_YOUTUBE,
    YouTubeMediaSearchResult,
    YouTubeResultPage,
)


URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def _entry(index, **extra):
    return {"id": f"c{index}", "author": f"@pessoa{index}", "text": f"Comentário {index}", **extra}


class CommentItemTests(unittest.TestCase):
    def test_the_row_shows_author_text_and_details(self):
        comment = comment_from_entry(
            _entry(1, text="Linha um\n\nlinha dois", likes="12 mil", published="há 1 ano", reply_count="9", has_replies=True, pinned=True),
            URL,
        )

        self.assertEqual(
            comment.choice_label,
            "@pessoa1: Linha um linha dois — fixado · há 1 ano · 12 mil curtidas · 9 respostas",
        )
        self.assertTrue(comment.can_browse)
        self.assertFalse(comment.opens_on_enter)

    def test_a_comment_without_replies_does_not_open(self):
        comment = comment_from_entry(_entry(1, likes="0"), URL)

        self.assertFalse(comment.can_browse)
        self.assertEqual(comment.choice_label, "@pessoa1: Comentário 1")

    def test_entries_without_text_are_dropped(self):
        self.assertIsNone(comment_from_entry({"id": "c1", "text": " "}, URL))
        self.assertIsNone(comment_from_entry("texto", URL))

    def test_the_reading_text_keeps_the_line_breaks(self):
        comment = comment_from_entry(_entry(1, text="Linha um\nlinha dois", published="há 2 dias"), URL)

        self.assertEqual(comments.comment_reading_text(comment), "Linha um\nlinha dois\n\n@pessoa1\nhá 2 dias")


class CommentsPageTests(unittest.TestCase):
    def setUp(self):
        patcher = patch("player.youtube_music.comments.youtubejs_resolver_enabled", return_value=True)
        self.addCleanup(patcher.stop)
        self.youtubejs_enabled = patcher.start()

    def test_youtubejs_brings_each_page(self):
        with patch.object(comments.youtubejs_runtime, "comments_page", return_value=([_entry(1), _entry(2)], True)) as page_fn:
            page = comments.comments_page(URL, 20, 20)

        page_fn.assert_called_once_with(URL, start=20, count=20)
        self.assertEqual([comment.comment_id for comment in page.results], ["c1", "c2"])
        self.assertTrue(page.has_more)
        self.assertEqual(page.results[0].media_url, URL)

    def test_without_youtubejs_yt_dlp_brings_only_the_first_batch(self):
        self.youtubejs_enabled.return_value = False
        data = {
            "comments": [
                {"id": "c1", "author": "@a", "text": "Principal", "like_count": 3, "_time_text": "1 year ago", "parent": "root", "is_pinned": True},
                {"id": "c1.r", "author": "@b", "text": "Resposta", "parent": "c1"},
            ]
        }
        with patch.object(comments, "ensure_yt_dlp_executable_available"), patch.object(
            comments, "extract_yt_dlp_info", return_value=SimpleNamespace(data=data)
        ) as extract:
            first = comments.comments_page(URL, 0, 20)
            second = comments.comments_page(URL, 20, 20)

        extract.assert_called_once()
        self.assertTrue(extract.call_args.kwargs["write_comments"])
        self.assertEqual([comment.text for comment in first.results], ["Principal"])
        self.assertEqual(first.results[0].likes, "3")
        self.assertTrue(first.results[0].pinned)
        self.assertFalse(first.has_more)
        self.assertEqual(second.results, ())

    def test_when_youtubejs_fails_the_first_page_comes_from_yt_dlp(self):
        with patch.object(comments.youtubejs_runtime, "comments_page", side_effect=RuntimeError("sem Node")), patch.object(
            comments, "ensure_yt_dlp_executable_available"
        ), patch.object(comments, "extract_yt_dlp_info", return_value=SimpleNamespace(data={"comments": [_entry(1)]})):
            page = comments.comments_page(URL, 0, 20)

        self.assertEqual(len(page.results), 1)

    def test_replies_need_youtubejs(self):
        comment = comment_from_entry(_entry(1, has_replies=True), URL)
        with patch.object(comments.youtubejs_runtime, "comment_replies_page", return_value=([_entry(2)], False)) as replies:
            page = comments.comment_replies_page(comment, 0, 20)
        replies.assert_called_once_with(URL, "c1", start=0, count=20)
        self.assertEqual(len(page.results), 1)

        self.youtubejs_enabled.return_value = False
        with self.assertRaisesRegex(RuntimeError, "YouTube.js"):
            comments.comment_replies_page(comment, 0, 20)


class _Frame(CommentsMixin, ResultsNavigationMixin):
    def __init__(self, selected=None):
        self.announcements = []
        self.selected = selected
        self.panel = Mock()
        self.panel.get_selected_search_result_ids.return_value = []
        self.refreshed = 0

    def _announce(self, message):
        self.announcements.append(message)

    def _youtube_music_library_page_size(self):
        return 20

    def _selected_youtube_music_search_result(self):
        return self.selected

    def _get_youtube_music_panel(self):
        return self.panel

    def _set_youtube_music_search_results(self, results, *, status_message=None, view=None):
        self.shown = list(results)

    def _refresh_youtube_music_screen_later(self):
        self.refreshed += 1

    def _format_youtube_music_error_detail(self, exc):
        return str(exc)

    def _run_youtube_music_background_task(self, worker, on_success, *, on_error=None, timeout_ms=None):
        on_success(worker())
        return True


class CommentsNavigationTests(unittest.TestCase):
    def _video(self):
        return YouTubeMediaSearchResult(
            source=YOUTUBE_SEARCH_SOURCE_YOUTUBE, result_type="video", title="Clipe", video_id="dQw4w9WgXcQ", playback_url=URL
        )

    def test_the_comments_of_a_video_open_over_the_current_list(self):
        frame = _Frame(self._video())
        page = YouTubeResultPage(results=(comment_from_entry(_entry(1, has_replies=True), URL),), has_more=True)
        with patch.object(comments, "comments_page", return_value=page) as comments_page:
            self.assertTrue(frame.show_youtube_music_comments())

        comments_page.assert_called_once_with(URL, 0, 20)
        view = frame._youtube_music_current_results_view()
        self.assertEqual(view.title, "Comentários de Clipe")
        self.assertEqual(len(frame._youtube_music_results_views()), 2)
        self.assertTrue(view.has_more)

    def test_right_arrow_on_a_comment_opens_its_replies(self):
        frame = _Frame()
        comment = comment_from_entry(_entry(1, has_replies=True), URL)
        page = YouTubeResultPage(results=(comment_from_entry(_entry(2), URL),))
        with patch.object(comments, "comment_replies_page", return_value=page) as replies:
            self.assertTrue(frame.on_browse_youtube_music_search_result(comment))

        replies.assert_called_once_with(comment, 0, 20)
        self.assertEqual(frame._youtube_music_current_results_view().title, "Respostas a @pessoa1")

    def test_a_playlist_has_no_comments(self):
        playlist = YouTubeMediaSearchResult(
            source=YOUTUBE_SEARCH_SOURCE_YOUTUBE, result_type="playlist", title="Lista", playlist_id="PL123"
        )
        frame = _Frame(playlist)

        self.assertFalse(frame.show_youtube_music_comments())
        self.assertEqual(frame.announcements, ["Este item não tem comentários para mostrar."])

    def test_the_current_media_must_be_from_youtube(self):
        frame = _Frame()
        frame._get_active_playlist_state = lambda: SimpleNamespace(current_media_path="C:/musica.mp3")
        frame.on_open_youtube_music = Mock()

        self.assertFalse(frame.show_current_media_comments())
        frame.on_open_youtube_music.assert_not_called()

    def test_the_current_media_opens_the_tab_on_its_comments(self):
        frame = _Frame()
        frame._get_active_playlist_state = lambda: SimpleNamespace(current_media_path=URL)
        frame._media_label = lambda path: "Clipe"
        frame.on_open_youtube_music = Mock()
        with patch.object(comments, "comments_page", return_value=YouTubeResultPage()):
            self.assertTrue(frame.show_current_media_comments())

        frame.on_open_youtube_music.assert_called_once_with(None)
        self.assertEqual(frame._youtube_music_current_results_view().title, "Comentários de Clipe")


if __name__ == "__main__":
    unittest.main()
