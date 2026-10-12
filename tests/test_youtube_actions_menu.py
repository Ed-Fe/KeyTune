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

from player.frames.youtube_music import FrameYouTubeMusicMixin
from player.frames.youtube_music.comments import CommentsContext
from player.frames.youtube_music.navigation import YouTubeResultsView
from player.youtube_music.comments import comment_from_entry
from player.youtube_music.folders import home_folder_items, write_comment_item
from player.youtube_music.models import (
    YOUTUBE_SEARCH_SOURCE_MUSIC,
    YOUTUBE_SEARCH_SOURCE_YOUTUBE,
    YouTubeMediaSearchResult,
)
from player.youtube_music.notifications import notification_from_entry
from player.youtube_music.posts import post_from_entry


URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
CHANNEL_ID = "UC" + "a" * 22


class _Frame(FrameYouTubeMusicMixin):
    def __init__(self, *views):
        self.announcements = []
        self.playlists = []
        self._youtube_music_results_views().extend(views)

    def _announce(self, message, category=None):
        self.announcements.append(message)

    def _get_current_tab_index(self):
        return 0

    def _get_active_playlist_index(self):
        return 0

    def _selected_youtube_music_search_results(self):
        return []


def _labels(frame, *selected):
    """Os rótulos do menu, um bloco por lista; um submenu vira ``rótulo >``."""
    return [
        [label + " >" if isinstance(action, list) else label for label, action in section]
        for section in frame._youtube_music_actions_menu_sections(list(selected))
    ]


def _video(video_id="dQw4w9WgXcQ", **extra):
    return YouTubeMediaSearchResult(
        source=YOUTUBE_SEARCH_SOURCE_YOUTUBE, result_type="video", title="Clipe", video_id=video_id, playback_url=URL, **extra
    )


def _comment(**extra):
    return comment_from_entry({"id": "c1", "author": "@a", "text": "Oi", **extra}, URL)


class ActionsMenuTests(unittest.TestCase):
    def setUp(self):
        patcher = patch("player.frames.youtube_music.comments.youtubejs_resolver_enabled", return_value=True)
        self.addCleanup(patcher.stop)
        self.youtubejs_enabled = patcher.start()

    def test_a_video_plays_shows_about_itself_and_goes_elsewhere(self):
        frame = _Frame()

        self.assertEqual(
            _labels(frame, _video(owner_browse_id=CHANNEL_ID, owner_title="Canal")),
            [
                ["Tocar (Enter)", "Adicionar sem tocar (Shift+Enter)"],
                ["Ver comentários", "Ver detalhes", "Ir para o canal Canal", "Salvar em Assistir mais tarde", "Ver capítulos", "Ver transcrição"],
                ["Adicionar seleção... >", "Baixar seleção...\tCtrl+Shift+B"],
            ],
        )

    def test_a_home_folder_only_opens(self):
        frame = _Frame()

        self.assertEqual(_labels(frame, home_folder_items()[0]), [["Abrir (Enter)"]])

    def test_a_channel_opens_and_has_its_account_actions(self):
        frame = _Frame()
        channel = YouTubeMediaSearchResult(
            source=YOUTUBE_SEARCH_SOURCE_YOUTUBE, result_type="channel", title="Canal", browse_id=CHANNEL_ID
        )

        self.assertEqual(
            _labels(frame, channel),
            [["Abrir (Enter)"], ["Inscrição e notificações do canal...", "Sobre o canal"]],
        )

    def test_a_playlist_plays_and_shows_what_is_inside(self):
        frame = _Frame()
        playlist = YouTubeMediaSearchResult(
            source=YOUTUBE_SEARCH_SOURCE_MUSIC, result_type="playlist", title="Mix", playlist_id="PL123"
        )

        self.assertEqual(
            _labels(frame, playlist),
            [
                ["Tocar (Enter)", "Adicionar sem tocar (Shift+Enter)", "Ver conteúdo (Seta para a direita)"],
                ["Adicionar seleção... >", "Baixar seleção...\tCtrl+Shift+B", "Salvar no YouTube Music"],
            ],
        )

    def test_my_own_playlist_can_be_deleted(self):
        frame = _Frame()
        playlist = YouTubeMediaSearchResult(
            source=YOUTUBE_SEARCH_SOURCE_MUSIC, result_type="playlist", title="Minha", playlist_id="PL123", library_playlist=True
        )

        self.assertEqual(_labels(frame, playlist)[1][-1], "Excluir playlist do YouTube Music...")

    def test_a_comment_reads_shows_replies_and_takes_the_account_actions(self):
        comment = _comment(has_replies=True, can_rate=True, can_reply=True)
        row = write_comment_item()
        frame = _Frame(YouTubeResultsView(title="Comentários", results=[row, comment], context=CommentsContext(media_url=URL)))

        self.assertEqual(
            _labels(frame, comment),
            [
                ["Ler o comentário inteiro (Enter)", "Ver respostas (Seta para a direita)"],
                ["Responder...", "Curtir o comentário", "Não gostei do comentário"],
                ["Escrever um comentário...", "Ordenar pelos mais recentes", "Voltar à lista anterior (Backspace)"],
            ],
        )

    def test_the_order_entry_names_the_other_order(self):
        context = CommentsContext(media_url=URL, title="Comentários", newest=True)
        frame = _Frame(YouTubeResultsView(title="Comentários", results=[_comment()], context=context))

        self.assertEqual(_labels(frame, _comment())[-1][0], "Ordenar pelos principais")

    def test_the_order_cannot_change_without_youtubejs_or_in_a_notification_conversation(self):
        linked = CommentsContext(media_url=URL, title="Conversa", linked_comment="c9")
        frame = _Frame(YouTubeResultsView(title="Conversa", results=[_comment()], context=linked))
        self.assertEqual(_labels(frame, _comment())[-1], ["Voltar à lista anterior (Backspace)"])

        self.youtubejs_enabled.return_value = False
        frame = _Frame(YouTubeResultsView(title="Comentários", results=[_comment()], context=CommentsContext(media_url=URL)))
        self.assertEqual(_labels(frame, _comment())[-1], ["Voltar à lista anterior (Backspace)"])

    def test_a_live_broadcast_offers_its_chat(self):
        frame = _Frame()

        self.assertEqual(
            _labels(frame, _video(is_live=True))[1],
            ["Ver comentários", "Ver detalhes", "Ver o chat ao vivo", "Salvar em Assistir mais tarde", "Ver capítulos", "Ver transcrição"],
        )

    def test_a_chat_message_reads_and_the_list_has_the_chat_commands(self):
        from player.frames.youtube_music.live_chat import LiveChatContext
        from player.youtube_music.folders import send_chat_message_item
        from player.youtube_music.live_chat import message_from_entry

        message = message_from_entry({"id": "m1", "author": "@a", "text": "Oi"})
        row = send_chat_message_item()
        frame = _Frame(YouTubeResultsView(title="Chat", results=[row, message], context=LiveChatContext(media_url=URL)))

        self.assertEqual(
            _labels(frame, message),
            [
                ["Ler a mensagem inteira (Enter)"],
                ["Enviar uma mensagem...", "Parar de falar as mensagens do chat", "Voltar à lista anterior (Backspace)"],
            ],
        )

    def test_a_poll_post_can_be_voted_with_the_account(self):
        frame = _Frame()
        post = post_from_entry(
            {"id": "p1", "channel_id": CHANNEL_ID, "author": "Canal", "text": "Qual?", "has_poll": True, "poll_choices": ["A", "B"], "can_vote": True}
        )

        self.assertEqual(_labels(frame, post)[1], ["Votar na enquete..."])

    def test_a_comment_notification_opens_the_conversation(self):
        frame = _Frame()
        notification = notification_from_entry(
            {"id": "n1", "title": "Ana respondeu", "video_id": "dQw4w9WgXcQ", "comment_id": "c1.r1"}
        )

        self.assertEqual(
            _labels(frame, notification)[0],
            ["Tocar (Enter)", "Adicionar sem tocar (Shift+Enter)", "Ver a conversa (Seta para a direita)"],
        )

    def test_a_read_only_comment_only_reads(self):
        frame = _Frame(YouTubeResultsView(title="Comentários", results=[_comment()]))

        self.assertEqual(
            _labels(frame, _comment()),
            [["Ler o comentário inteiro (Enter)"], ["Voltar à lista anterior (Backspace)"]],
        )

    def test_the_write_row_is_not_offered_twice(self):
        row = write_comment_item()
        frame = _Frame(YouTubeResultsView(title="Comentários", results=[row], context=CommentsContext(media_url=URL)))

        self.assertEqual(
            _labels(frame, row),
            [["Escrever um comentário..."], ["Ordenar pelos mais recentes", "Voltar à lista anterior (Backspace)"]],
        )

    def test_writing_a_comment_is_not_offered_outside_the_comments_list(self):
        frame = _Frame()

        self.assertNotIn("Escrever um comentário...", sum(_labels(frame, _video()), []))

    def test_a_post_reads_and_shows_its_comments(self):
        frame = _Frame()
        post = post_from_entry({"id": "p1", "channel_id": CHANNEL_ID, "author": "Canal", "text": "Novidade"})

        self.assertEqual(
            _labels(frame, post),
            [["Ler o post inteiro (Enter)", "Ver comentários (Seta para a direita)"]],
        )

    def test_a_notification_plays_and_can_be_read_or_hidden(self):
        frame = _Frame()
        notification = notification_from_entry({"id": "n1", "title": "Canal enviou o vídeo X", "video_id": "dQw4w9WgXcQ"})

        self.assertEqual(
            _labels(frame, notification)[:2],
            [
                ["Tocar (Enter)", "Adicionar sem tocar (Shift+Enter)"],
                ["Ver comentários", "Ver detalhes", "Marcar como lida", "Ocultar esta notificação"],
            ],
        )

    def test_several_items_only_get_what_works_for_all(self):
        frame = _Frame()

        self.assertEqual(
            _labels(frame, _video(), _video(video_id="outro000001")),
            [
                ["Tocar (Enter)", "Adicionar sem tocar (Shift+Enter)"],
                ["Adicionar seleção... >", "Baixar seleção...\tCtrl+Shift+B"],
            ],
        )

    def test_the_list_actions_come_last(self):
        frame = _Frame(YouTubeResultsView(title="Busca", results=[_video()], has_more=True, fetch_page=Mock()))

        self.assertEqual(
            _labels(frame, _video())[-1],
            ["Carregar a lista inteira", "Voltar à lista anterior (Backspace)"],
        )

    def test_the_open_playlists_are_targets_of_the_selection(self):
        from player.playlists import PlaylistState

        frame = _Frame()
        frame.playlists = [PlaylistState("Rock")]
        section = frame._youtube_music_actions_menu_sections([_video()])[2]
        targets = section[0][1]

        self.assertEqual(targets[0][0], "Abrir seleção em nova playlist")
        self.assertIsNone(targets[1])
        self.assertEqual(targets[2][0], "Rock (aba atual)")

    def test_with_nothing_to_offer_the_menu_says_so(self):
        frame = _Frame()

        self.assertFalse(frame._on_youtube_music_show_search_actions_menu(None))
        self.assertEqual(frame.announcements, ["Não há ações para este item."])


if __name__ == "__main__":
    unittest.main()
