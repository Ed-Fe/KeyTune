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

from player.frames.youtube_music import comment_actions as frame_comment_actions
from player.frames.youtube_music.comment_actions import CommentActionsMixin
from player.frames.youtube_music.comments import CommentsContext, CommentsMixin
from player.frames.youtube_music.navigation import ResultsNavigationMixin, YouTubeResultsView
from player.youtube_music import comment_actions
from player.youtube_music.comments import comment_from_entry
from player.youtube_music.models import YouTubeResultPage


URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def _comment(index=1, **extra):
    entry = {"id": f"c{index}", "author": f"@pessoa{index}", "text": f"Comentário {index}", "can_rate": True, "can_reply": True, **extra}
    return comment_from_entry(entry, URL)


class CommentActionsTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(comment_actions, "require_account_session", return_value=("SID=abc", 1))
        self.addCleanup(patcher.stop)
        patcher.start()

    def test_a_new_comment_goes_to_the_video_or_to_the_post(self):
        post = SimpleNamespace(post_id="p1", channel_id="UCx")
        with patch.object(comment_actions.youtubejs_runtime, "create_comment") as create:
            comment_actions.post_comment("  Muito bom  ", media_url=URL)
            comment_actions.post_comment("No post", post=post)

        self.assertEqual(
            [call.kwargs for call in create.call_args_list],
            [
                {"media_url": URL, "post_id": "", "channel_id": "", "account_index": 1},
                {"media_url": "", "post_id": "p1", "channel_id": "UCx", "account_index": 1},
            ],
        )
        self.assertEqual(create.call_args_list[0].args, ("SID=abc", "Muito bom"))

    def test_an_empty_text_is_never_sent(self):
        with patch.object(comment_actions.youtubejs_runtime, "create_comment") as create, patch.object(
            comment_actions.youtubejs_runtime, "comment_action"
        ) as action:
            with self.assertRaisesRegex(RuntimeError, "vazio"):
                comment_actions.post_comment("   ", media_url=URL)
            with self.assertRaisesRegex(RuntimeError, "vazio"):
                comment_actions.reply_to_comment(_comment(), "")

        create.assert_not_called()
        action.assert_not_called()

    def test_replying_editing_and_deleting_act_on_the_comment(self):
        with patch.object(comment_actions.youtubejs_runtime, "comment_action") as action:
            comment_actions.reply_to_comment(_comment(), "Concordo")
            edited = comment_actions.edit_comment(_comment(), "Texto novo")
            comment_actions.delete_comment(_comment())

        self.assertEqual(
            [(call.args[1:], call.kwargs["text"]) for call in action.call_args_list],
            [(("c1", "reply"), "Concordo"), (("c1", "edit"), "Texto novo"), (("c1", "delete"), "")],
        )
        self.assertEqual(edited.text, "Texto novo")

    def test_the_ratings_offered_follow_the_current_state(self):
        self.assertEqual(
            [operation for operation, _label in comment_actions.rating_operations(_comment())], ["like", "dislike"]
        )
        self.assertEqual(
            [operation for operation, _label in comment_actions.rating_operations(_comment(liked=True))],
            ["unlike", "dislike"],
        )
        self.assertEqual(
            [operation for operation, _label in comment_actions.rating_operations(_comment(disliked=True))],
            ["like", "undislike"],
        )
        self.assertEqual(comment_actions.rating_operations(_comment(can_rate=False)), [])

    def test_rating_returns_the_comment_as_it_became(self):
        with patch.object(
            comment_actions.youtubejs_runtime, "comment_action", return_value={"liked": True, "disliked": False}
        ):
            rated = comment_actions.rate_comment(_comment(disliked=True), comment_actions.RATING_LIKE)

        self.assertTrue(rated.liked)
        self.assertFalse(rated.disliked)
        self.assertEqual(comment_actions.rating_done_message(comment_actions.RATING_LIKE), "Comentário curtido.")


class _Frame(CommentActionsMixin, CommentsMixin, ResultsNavigationMixin):
    def __init__(self, view=None):
        self.announcements = []
        self.typed = "Texto digitado"
        self.shown = []
        self.panel = Mock()
        self.panel.get_selected_search_result_ids.return_value = []
        if view is not None:
            self._youtube_music_results_views().append(view)

    def _announce(self, message, category=None):
        self.announcements.append(message)

    def _ensure_youtube_music_authenticated(self):
        return True

    def _ask_youtube_music_comment_text(self, title, prompt, value=""):
        self.asked = (title, prompt, value)
        return self.typed

    def _youtube_music_library_page_size(self):
        return 20

    def _get_youtube_music_panel(self):
        return self.panel

    def _set_youtube_music_search_results(self, results, *, status_message=None, view=None):
        self.shown.append(list(results))

    def _format_youtube_music_error_detail(self, exc):
        return str(exc)

    def _run_youtube_music_background_task(self, worker, on_success, *, on_error=None, timeout_ms=None):
        try:
            result = worker()
        except Exception as exc:
            on_error(exc)
            return True
        on_success(result)
        return True


def _labels(frame, result):
    return [label for label, _action in frame._youtube_music_comment_menu_entries(result)]


class CommentActionsFrameTests(unittest.TestCase):
    def setUp(self):
        wx_patcher = patch.object(frame_comment_actions, "wx")
        self.addCleanup(wx_patcher.stop)
        self.wx = wx_patcher.start()
        self.wx.YES = 2

    def _comments_view(self, *comments_in_view):
        return YouTubeResultsView(
            title="Comentários de Clipe",
            results=list(comments_in_view),
            fetch_page=Mock(return_value=YouTubeResultPage(results=tuple(comments_in_view))),
            context=CommentsContext(media_url=URL),
        )

    def test_the_menu_of_a_comment_offers_what_the_account_can_do(self):
        comment = _comment(liked=True)
        frame = _Frame(self._comments_view(comment))

        self.assertEqual(_labels(frame, comment), ["Responder...", "Remover a curtida", "Não gostei do comentário"])

    def test_my_own_comment_can_be_edited_and_deleted(self):
        comment = _comment(mine=True, can_edit=True, can_delete=True)
        frame = _Frame(self._comments_view(comment))

        self.assertEqual(_labels(frame, comment)[-2:], ["Editar o meu comentário...", "Apagar o meu comentário..."])

    def test_a_read_only_comment_has_no_account_actions(self):
        comment = _comment(can_rate=False, can_reply=False)
        frame = _Frame(self._comments_view(comment))

        self.assertEqual(_labels(frame, comment), [])
        self.assertEqual(_labels(frame, SimpleNamespace(result_type="video")), [])

    def test_the_write_row_of_the_list_opens_the_text_box(self):
        from player.youtube_music.folders import write_comment_item

        row = write_comment_item()
        view = self._comments_view(row, _comment())
        frame = _Frame(view)
        with patch.object(comment_actions, "post_comment") as post_comment:
            self.assertTrue(frame.on_browse_youtube_music_search_result(row))

        post_comment.assert_called_once_with("Texto digitado", media_url=URL, post=None)

    def test_outside_a_comments_list_there_is_nowhere_to_write(self):
        frame = _Frame()
        with patch.object(comment_actions, "post_comment") as post_comment:
            self.assertFalse(frame.write_youtube_music_comment(None))

        post_comment.assert_not_called()

    def test_writing_a_comment_publishes_it_and_reloads_the_list(self):
        view = self._comments_view(_comment())
        frame = _Frame(view)
        with patch.object(comment_actions, "post_comment") as post_comment:
            self.assertTrue(frame.write_youtube_music_comment(view.context))

        post_comment.assert_called_once_with("Texto digitado", media_url=URL, post=None)
        self.assertEqual(frame.announcements, ["Comentário publicado."])
        view.fetch_page.assert_called_once_with(0, 20)

    def test_giving_up_on_the_text_sends_nothing(self):
        view = self._comments_view(_comment())
        frame = _Frame(view)
        frame.typed = ""
        with patch.object(comment_actions, "post_comment") as post_comment, patch.object(
            comment_actions, "reply_to_comment"
        ) as reply:
            self.assertFalse(frame.write_youtube_music_comment(view.context))
            self.assertFalse(frame.reply_to_youtube_music_comment(_comment()))

        post_comment.assert_not_called()
        reply.assert_not_called()

    def test_replying_announces_when_it_is_published(self):
        comment = _comment()
        frame = _Frame(self._comments_view(comment))
        with patch.object(comment_actions, "reply_to_comment") as reply:
            frame.reply_to_youtube_music_comment(comment)

        reply.assert_called_once_with(comment, "Texto digitado")
        self.assertEqual(frame.asked[0], "Responder a @pessoa1")
        self.assertEqual(frame.announcements, ["Resposta publicada."])

    def test_rating_updates_the_row_in_the_list(self):
        comment = _comment()
        frame = _Frame(self._comments_view(comment, _comment(2)))
        with patch.object(
            comment_actions.youtubejs_runtime, "comment_action", return_value={"liked": True, "disliked": False}
        ), patch.object(comment_actions, "require_account_session", return_value=("SID=abc", 0)):
            frame.rate_youtube_music_comment(comment, comment_actions.RATING_LIKE)

        self.assertTrue(frame._youtube_music_current_results_view().results[0].liked)
        self.assertEqual(frame.announcements, ["Comentário curtido."])
        self.assertEqual(frame._youtube_music_pending_result_selection, "comment:c1")

    def test_editing_shows_the_current_text_and_keeps_the_new_one(self):
        comment = _comment(can_edit=True)
        frame = _Frame(self._comments_view(comment))
        with patch.object(comment_actions.youtubejs_runtime, "comment_action"), patch.object(
            comment_actions, "require_account_session", return_value=("SID=abc", 0)
        ):
            frame.edit_youtube_music_comment(comment)

        self.assertEqual(frame.asked[2], "Comentário 1")
        self.assertEqual(frame._youtube_music_current_results_view().results[0].text, "Texto digitado")
        self.assertEqual(frame.announcements, ["Comentário editado."])

    def test_deleting_asks_first_and_takes_the_row_out(self):
        comment = _comment(can_delete=True)
        other = _comment(2)
        frame = _Frame(self._comments_view(comment, other))
        with patch.object(comment_actions, "delete_comment") as delete:
            self.wx.MessageBox.return_value = 8
            self.assertFalse(frame.delete_youtube_music_comment(comment))
            delete.assert_not_called()

            self.wx.MessageBox.return_value = self.wx.YES
            frame.delete_youtube_music_comment(comment)

        delete.assert_called_once_with(comment)
        self.assertEqual(frame._youtube_music_current_results_view().results, [other])
        self.assertEqual(frame.announcements, ["Comentário apagado."])

    def test_a_refused_action_is_reported_and_changes_nothing(self):
        comment = _comment()
        frame = _Frame(self._comments_view(comment))
        with patch.object(comment_actions, "rate_comment", side_effect=RuntimeError("HTTP 403")):
            frame.rate_youtube_music_comment(comment, comment_actions.RATING_LIKE)

        self.assertIn("HTTP 403", self.wx.MessageBox.call_args.args[0])
        self.assertEqual(frame.announcements, [])
        self.assertFalse(frame._youtube_music_current_results_view().results[0].liked)


if __name__ == "__main__":
    unittest.main()
