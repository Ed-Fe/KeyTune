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

from player.frames.youtube_music import channel_actions as frame_channel_actions
from player.frames.youtube_music.channel_actions import ChannelActionsMixin
from player.frames.youtube_music.comments import CommentsContext, CommentsMixin
from player.youtube_music import channel_about, channel_search, posts, subscriptions
from player.youtube_music.models import (
    YOUTUBE_SEARCH_SOURCE_MUSIC,
    YOUTUBE_SEARCH_SOURCE_YOUTUBE,
    YouTubeMediaSearchResult,
)
from player.youtube_music.posts import post_from_entry


CHANNEL_ID = "UC" + "a" * 22


def _channel():
    return YouTubeMediaSearchResult(
        source=YOUTUBE_SEARCH_SOURCE_YOUTUBE, result_type="channel", title="Canal", browse_id=CHANNEL_ID
    )


def _post(**extra):
    return post_from_entry(
        {"id": "p1", "channel_id": CHANNEL_ID, "author": "Canal", "text": "Novidade\nna sexta", "published": "há 2 dias", **extra}
    )


class SubscriptionTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(subscriptions, "_account", return_value=("SID=abc", 1))
        self.addCleanup(patcher.stop)
        patcher.start()

    def test_the_state_says_if_subscribed_and_what_the_bell_does(self):
        state = {"subscribed": True, "notifications": "personalized"}
        with patch.object(subscriptions.youtubejs_runtime, "channel_state", return_value=state) as channel_state:
            subscription = subscriptions.channel_subscription(CHANNEL_ID)

        channel_state.assert_called_once_with("SID=abc", CHANNEL_ID, account_index=1)
        self.assertTrue(subscription.subscribed)
        self.assertEqual(subscriptions.bell_label(subscription.notifications), "notificações personalizadas")

    def test_each_change_is_one_operation_on_the_channel(self):
        with patch.object(subscriptions.youtubejs_runtime, "channel_action") as action:
            subscriptions.subscribe_to_channel(CHANNEL_ID)
            subscriptions.unsubscribe_from_channel(CHANNEL_ID)
            subscriptions.set_channel_notifications(CHANNEL_ID, subscriptions.BELL_NONE)

        self.assertEqual(
            [call.args[2] for call in action.call_args_list], ["subscribe", "unsubscribe", "notify_none"]
        )

    def test_an_unknown_bell_level_is_refused(self):
        with self.assertRaises(ValueError):
            subscriptions.set_channel_notifications(CHANNEL_ID, "tudo")


class PostTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(posts, "youtubejs_resolver_enabled", return_value=True)
        self.addCleanup(patcher.stop)
        self.youtubejs_enabled = patcher.start()
        # Sem conta conectada, a não ser no teste que a põe.
        account = patch.object(posts, "account_fields", return_value={})
        self.addCleanup(account.stop)
        self.account = account.start()

    def test_the_row_shows_author_text_and_details(self):
        post = _post(likes="77", reply_count="46")

        self.assertEqual(post.choice_label, "Canal: Novidade na sexta — há 2 dias · 77 curtidas · 46 comentários")
        self.assertTrue(post.can_browse)
        self.assertFalse(post.opens_on_enter)

    def test_a_post_with_only_a_video_is_described_by_it(self):
        post = _post(text="", published="", attachment_text="Clipe novo", attachment_video_id="dQw4w9WgXcQ")

        self.assertEqual(post.choice_label, "Canal: vídeo: Clipe novo — vídeo: Clipe novo")
        self.assertEqual(posts.post_reading_text(post), "vídeo: Clipe novo\n\nCanal")

    def test_the_reading_text_keeps_the_line_breaks(self):
        post = _post(likes="3", has_poll=True, attachment_text="Sim / Não")

        self.assertEqual(
            posts.post_reading_text(post),
            "Novidade\nna sexta\n\nenquete: Sim / Não\n\nCanal\nhá 2 dias · 3 curtidas",
        )

    def test_the_posts_of_a_channel_come_page_by_page(self):
        entries = [{"id": "p1", "channel_id": CHANNEL_ID, "author": "Canal", "text": "Oi"}, {"id": "sem canal"}]
        with patch.object(posts.youtubejs_runtime, "channel_posts_page", return_value=(entries, True)) as page_fn:
            page = posts.channel_posts_page(CHANNEL_ID, 20, 20)

        page_fn.assert_called_once_with(CHANNEL_ID, start=20, count=20)
        self.assertEqual([post.post_id for post in page.results], ["p1"])
        self.assertTrue(page.has_more)

    def test_the_comments_of_a_post_use_the_account_when_there_is_one(self):
        entries = [{"id": "c1", "author": "@a", "text": "Legal", "can_reply": True}]
        self.account.return_value = {"cookie_header": "SID=abc", "account_index": 0}
        with patch.object(posts.youtubejs_runtime, "post_comments_page", return_value=(entries, False)) as page_fn:
            page = posts.post_comments_page(_post(), 0, 20)
            posts.post_comments_page(_post(), 0, 20, newest=True)

        page_fn.assert_any_call("p1", CHANNEL_ID, start=0, count=20, cookie_header="SID=abc", account_index=0)
        self.assertEqual(page_fn.call_args.kwargs["sort"], "newest")
        self.assertTrue(page.results[0].can_reply)

    def test_with_the_account_a_poll_comes_ready_to_vote(self):
        self.account.return_value = {"cookie_header": "SID=abc", "account_index": 1}
        entry = {"id": "p1", "channel_id": CHANNEL_ID, "author": "Canal", "text": "Qual?", "has_poll": True, "poll_choices": ["Sim", "Não"], "can_vote": True}
        with patch.object(posts.youtubejs_runtime, "channel_posts_page", return_value=([entry], False)) as page_fn:
            post = posts.channel_posts_page(CHANNEL_ID, 0, 20).results[0]

        page_fn.assert_called_once_with(CHANNEL_ID, start=0, count=20, cookie_header="SID=abc", account_index=1)
        self.assertEqual((post.poll_choices, post.can_vote), (("Sim", "Não"), True))
        with patch.object(posts, "require_account_session", return_value=("SID=abc", 1)), patch.object(
            posts.youtubejs_runtime, "post_vote"
        ) as vote:
            posts.vote_in_poll(post, 1)
        vote.assert_called_once_with("SID=abc", "p1", 1, account_index=1)

    def test_posts_need_youtubejs(self):
        self.youtubejs_enabled.return_value = False

        with self.assertRaisesRegex(RuntimeError, "YouTube.js"):
            posts.channel_posts_page(CHANNEL_ID, 0, 20)


class ChannelAboutTests(unittest.TestCase):
    def test_the_about_page_becomes_reading_text(self):
        data = {
            "title": "Canal",
            "description": "Vídeos toda semana.",
            "subscribers": "434 mil inscritos",
            "video_count": "2.037 vídeos",
            "joined": "Inscreveu-se em 1 de jan. de 2012",
            "country": "Brasil",
            "url": "https://www.youtube.com/@canal",
            "links": ["Site: canal.example", " "],
        }
        with patch.object(channel_about, "youtubejs_resolver_enabled", return_value=True), patch.object(
            channel_about.youtubejs_runtime, "channel_about", return_value=data
        ):
            about = channel_about.channel_about(CHANNEL_ID)

        self.assertEqual(
            channel_about.about_reading_text(about),
            "Canal\n434 mil inscritos · 2.037 vídeos\nInscreveu-se em 1 de jan. de 2012\nPaís: Brasil\n\n"
            "Vídeos toda semana.\n\nLinks:\nSite: canal.example\n\nhttps://www.youtube.com/@canal",
        )

    def test_the_about_page_needs_youtubejs(self):
        with patch.object(channel_about, "youtubejs_resolver_enabled", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "YouTube.js"):
                channel_about.channel_about(CHANNEL_ID)


class ChannelSearchTests(unittest.TestCase):
    def test_the_search_brings_the_channel_videos_without_repeating_its_name(self):
        entries = [{"id": "video000001", "title": "Pixel novo", "channel": "Canal", "channel_id": CHANNEL_ID, "duration": 559}]
        with patch.object(channel_search, "youtubejs_resolver_enabled", return_value=True), patch.object(
            channel_search.youtubejs_runtime, "channel_search_page", return_value=(entries, True)
        ) as page_fn:
            page = channel_search.channel_search_page(CHANNEL_ID, "pixel", 0, 20)

        page_fn.assert_called_once_with(CHANNEL_ID, "pixel", start=0, count=20)
        self.assertEqual((page.results[0].title, page.results[0].subtitle), ("Pixel novo", ""))
        self.assertTrue(page.has_more)
        self.assertEqual(channel_search.channel_search_view_title("pixel", "Canal"), "Busca por pixel em Canal")

    def test_the_search_needs_youtubejs(self):
        with patch.object(channel_search, "youtubejs_resolver_enabled", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "YouTube.js"):
                channel_search.channel_search_page(CHANNEL_ID, "pixel", 0, 20)


class _Frame(ChannelActionsMixin, CommentsMixin):
    def __init__(self):
        self.announcements = []
        self.reading = []
        self.loaded = []
        self.authenticated = True

    def _load_youtube_music_results_view(self, view, **kwargs):
        self.loaded.append((view, kwargs))
        return True

    def _announce(self, message, category=None):
        self.announcements.append(message)

    def _ensure_youtube_music_authenticated(self):
        return self.authenticated

    def _format_youtube_music_error_detail(self, exc):
        return str(exc)

    def _show_reading_dialog(self, **kwargs):
        self.reading.append(kwargs)
        return True

    def _run_youtube_music_background_task(self, worker, on_success, *, on_error=None, timeout_ms=None):
        try:
            result = worker()
        except Exception as exc:
            on_error(exc)
            return True
        on_success(result)
        return True


class ChannelActionsFrameTests(unittest.TestCase):
    def setUp(self):
        wx_patcher = patch.object(frame_channel_actions, "wx")
        self.addCleanup(wx_patcher.stop)
        self.wx = wx_patcher.start()
        self.wx.YES = 2
        self.wx.ID_OK = 5100

    def test_the_menu_has_the_channel_actions_only_for_youtube_channels(self):
        frame = _Frame()
        artist = YouTubeMediaSearchResult(source=YOUTUBE_SEARCH_SOURCE_MUSIC, result_type="artist", title="Ana", browse_id="UCana")
        video = YouTubeMediaSearchResult(
            source=YOUTUBE_SEARCH_SOURCE_YOUTUBE, result_type="video", title="Clipe", owner_browse_id=CHANNEL_ID
        )

        self.assertEqual(
            [label for label, _action in frame._youtube_music_channel_menu_entries(_channel())],
            ["Inscrição e notificações do canal...", "Sobre o canal"],
        )
        for other in (artist, video, _post(), None):
            self.assertEqual(frame._youtube_music_channel_menu_entries(other), [])

    def test_someone_not_subscribed_is_asked_to_subscribe(self):
        frame = _Frame()
        self.wx.MessageBox.return_value = self.wx.YES
        with patch.object(subscriptions, "channel_subscription", return_value=subscriptions.ChannelSubscription()), patch.object(
            subscriptions, "subscribe_to_channel"
        ) as subscribe:
            self.assertTrue(frame.manage_youtube_channel_subscription(_channel()))

        subscribe.assert_called_once_with(CHANNEL_ID)
        self.assertEqual(frame.announcements[-1], "Inscrição feita em Canal.")

    def test_declining_leaves_the_subscription_alone(self):
        frame = _Frame()
        self.wx.MessageBox.return_value = 8
        with patch.object(subscriptions, "channel_subscription", return_value=subscriptions.ChannelSubscription()), patch.object(
            subscriptions, "subscribe_to_channel"
        ) as subscribe:
            frame.manage_youtube_channel_subscription(_channel())

        subscribe.assert_not_called()

    def _choose(self, frame, selection, current=subscriptions.BELL_ALL):
        dialog = self.wx.SingleChoiceDialog.return_value
        dialog.ShowModal.return_value = self.wx.ID_OK
        dialog.GetSelection.return_value = selection
        state = subscriptions.ChannelSubscription(subscribed=True, notifications=current)
        with patch.object(subscriptions, "channel_subscription", return_value=state):
            frame.manage_youtube_channel_subscription(_channel())
        return dialog

    def test_a_subscriber_picks_what_the_bell_does(self):
        frame = _Frame()
        with patch.object(subscriptions, "set_channel_notifications") as set_bell:
            dialog = self._choose(frame, 2)

        dialog.SetSelection.assert_called_once_with(0)
        set_bell.assert_called_once_with(CHANNEL_ID, subscriptions.BELL_NONE)
        self.assertEqual(frame.announcements[-1], "Canal: nenhuma notificação.")
        self.assertEqual(
            self.wx.SingleChoiceDialog.call_args.args[3][-1],
            "Cancelar a inscrição",
        )

    def test_picking_the_current_bell_changes_nothing(self):
        frame = _Frame()
        with patch.object(subscriptions, "set_channel_notifications") as set_bell:
            self._choose(frame, 0)

        set_bell.assert_not_called()

    def test_the_last_choice_cancels_the_subscription(self):
        frame = _Frame()
        with patch.object(subscriptions, "unsubscribe_from_channel") as unsubscribe:
            self._choose(frame, 3)

        unsubscribe.assert_called_once_with(CHANNEL_ID)
        self.assertEqual(frame.announcements[-1], "Inscrição cancelada em Canal.")

    def test_a_refused_change_is_reported(self):
        frame = _Frame()
        with patch.object(subscriptions, "unsubscribe_from_channel", side_effect=RuntimeError("HTTP 403")):
            self._choose(frame, 3)

        self.assertIn("HTTP 403", self.wx.MessageBox.call_args.args[0])

    def test_without_the_account_nothing_is_asked(self):
        frame = _Frame()
        frame.authenticated = False
        with patch.object(subscriptions, "channel_subscription") as state:
            self.assertFalse(frame.manage_youtube_channel_subscription(_channel()))

        state.assert_not_called()

    def test_the_about_page_opens_in_the_reading_box(self):
        frame = _Frame()
        about = channel_about.YouTubeChannelAbout(title="Canal", description="Vídeos.")
        with patch.object(channel_about, "channel_about", return_value=about):
            frame.show_youtube_channel_about(_channel())

        self.assertEqual(frame.reading[0]["title"], "Sobre Canal")
        self.assertEqual(frame.reading[0]["text"], "Canal\n\nVídeos.")

    def test_the_posts_and_their_comments_open_as_lists(self):
        frame = _Frame()
        post = _post()
        with patch.object(posts, "channel_posts_page") as posts_page, patch.object(posts, "post_comments_page") as comments_page:
            posts_view = frame._build_youtube_channel_posts_view(_channel())
            posts_view.fetch_page(0, 20)
            comments_view = frame._build_youtube_music_post_comments_view(post)
            comments_view.fetch_page(20, 20)

        posts_page.assert_called_once_with(CHANNEL_ID, 0, 20)
        comments_page.assert_called_once_with(post, 20, 20, newest=False)
        self.assertEqual((posts_view.title, comments_view.title), ("Posts de Canal", "Comentários do post de Canal"))
        self.assertEqual(comments_view.context, CommentsContext(post=post, title="Comentários do post de Canal"))

    def test_searching_inside_a_channel_opens_what_it_found(self):
        frame = _Frame()
        dialog = self.wx.TextEntryDialog.return_value
        dialog.ShowModal.return_value = self.wx.ID_OK
        dialog.GetValue.return_value = "  pixel   novo "
        with patch.object(channel_search, "channel_search_page") as page_fn:
            self.assertTrue(frame.search_youtube_channel(_channel()))
            view, kwargs = frame.loaded[0]
            view.fetch_page(0, 20)

        page_fn.assert_called_once_with(CHANNEL_ID, "pixel novo", 0, 20)
        self.assertEqual(view.title, "Busca por pixel novo em Canal")
        self.assertEqual(kwargs["mode"], "push")

    def test_an_empty_search_does_nothing(self):
        frame = _Frame()
        dialog = self.wx.TextEntryDialog.return_value
        dialog.ShowModal.return_value = self.wx.ID_OK
        dialog.GetValue.return_value = "   "

        self.assertFalse(frame.search_youtube_channel(_channel()))
        self.assertEqual(frame.loaded, [])
        self.assertEqual(frame.announcements, ["Digite algo para buscar no canal."])

    def test_voting_in_a_poll_records_the_chosen_option(self):
        frame = _Frame()
        post = _post(has_poll=True, poll_choices=["Sim", "Não"], can_vote=True)
        dialog = self.wx.SingleChoiceDialog.return_value
        dialog.ShowModal.return_value = self.wx.ID_OK
        dialog.GetSelection.return_value = 1
        with patch.object(posts, "vote_in_poll") as vote:
            self.assertTrue(frame.vote_in_youtube_post_poll(post))

        vote.assert_called_once_with(post, 1)
        self.assertEqual(self.wx.SingleChoiceDialog.call_args.args[3], ["Sim", "Não"])
        self.assertEqual(frame.announcements[-1], "Voto registrado: Não.")
        self.assertEqual([label for label, _action in frame._youtube_music_post_menu_entries(post)], ["Votar na enquete..."])

    def test_a_poll_without_the_account_cannot_be_voted(self):
        frame = _Frame()
        post = _post(has_poll=True, poll_choices=["Sim", "Não"])
        with patch.object(posts, "vote_in_poll") as vote:
            self.assertFalse(frame.vote_in_youtube_post_poll(post))

        vote.assert_not_called()
        self.assertEqual(frame._youtube_music_post_menu_entries(post), [])

    def test_reading_a_post_offers_its_comments_and_its_video(self):
        frame = _Frame()
        frame.on_browse_youtube_music_search_result = Mock()
        frame._open_prepared_media_playlist = Mock()
        post = _post(attachment_text="Clipe novo", attachment_video_id="dQw4w9WgXcQ")

        frame._read_youtube_music_post(post)
        (comments_label, open_comments), (video_label, play_video) = frame.reading[0]["actions"]
        open_comments()
        play_video()

        self.assertEqual((comments_label, video_label), ("Ver &comentários", "&Tocar o vídeo do post"))
        frame.on_browse_youtube_music_search_result.assert_called_once_with(post, focus_results=True)
        self.assertEqual(
            frame._open_prepared_media_playlist.call_args.args[0], ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"]
        )


if __name__ == "__main__":
    unittest.main()
