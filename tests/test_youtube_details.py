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
from player.frames.youtube_music.details import DetailsMixin
from player.youtube_music import details
from player.youtube_music.models import YOUTUBE_SEARCH_SOURCE_YOUTUBE, YouTubeMediaSearchResult


URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


class DetailsTests(unittest.TestCase):
    def test_youtubejs_details_come_already_written_in_the_content_language(self):
        data = {
            "title": "Clipe",
            "channel": "Canal",
            "subscribers": "4,55 mi de inscritos",
            "description": "Linha um\nlinha dois",
            "duration": 213,
            "view_count_text": "1.823 visualizações",
            "like_count": 19458,
            "published": "25 de out. de 2009",
            "relative_date": "há 16 anos",
        }
        with patch.object(details, "youtubejs_resolver_enabled", return_value=True), patch.object(
            details.youtubejs_runtime, "media_details", return_value=data
        ):
            text = details.details_reading_text(details.media_details(URL))

        self.assertEqual(
            text,
            "Clipe\n"
            "Canal: Canal (4,55 mi de inscritos)\n"
            "Duração: 3:33\n"
            "1.823 visualizações\n"
            "19.458 curtidas\n"
            "Publicado: 25 de out. de 2009 (há 16 anos)\n"
            "\n"
            "Descrição:\n"
            "Linha um\nlinha dois",
        )

    def test_without_youtubejs_yt_dlp_brings_the_details(self):
        data = {
            "title": "Clipe",
            "uploader": "Canal",
            "channel_follower_count": 1500,
            "duration": 61,
            "view_count": 2000,
            "upload_date": "20091025",
            "is_live": True,
        }
        with patch.object(details, "youtubejs_resolver_enabled", return_value=False), patch.object(
            details, "ensure_yt_dlp_executable_available"
        ), patch.object(details, "extract_yt_dlp_info", return_value=SimpleNamespace(data=data)):
            text = details.details_reading_text(details.media_details(URL))

        self.assertEqual(
            text,
            "Clipe\nCanal: Canal (1.500 inscritos)\nTransmissão ao vivo\n2.000 visualizações\nPublicado: 25/10/2009\n\nSem descrição.",
        )

    def test_a_youtubejs_failure_falls_back_to_yt_dlp(self):
        with patch.object(details, "youtubejs_resolver_enabled", return_value=True), patch.object(
            details.youtubejs_runtime, "media_details", side_effect=RuntimeError("falhou")
        ), patch.object(details, "ensure_yt_dlp_executable_available"), patch.object(
            details, "extract_yt_dlp_info", return_value=SimpleNamespace(data={"title": "Clipe"})
        ):
            self.assertEqual(details.media_details(URL).title, "Clipe")


class _Frame(DetailsMixin, CommentsMixin):
    def __init__(self):
        self.announcements = []
        self.dialogs = []

    def _announce(self, message):
        self.announcements.append(message)

    def _run_youtube_music_background_task(self, worker, on_success, on_error=None):
        on_success(worker())
        return True

    def _show_reading_dialog(self, **kwargs):
        self.dialogs.append(kwargs)


class DetailsFrameTests(unittest.TestCase):
    def test_the_selected_video_shows_its_details_in_a_reading_box(self):
        frame = _Frame()
        video = YouTubeMediaSearchResult(
            source=YOUTUBE_SEARCH_SOURCE_YOUTUBE, result_type="video", title="Clipe", video_id="dQw4w9WgXcQ", playback_url=URL
        )
        with patch.object(details, "media_details", return_value=details.YouTubeMediaDetails(title="Clipe")) as fetch:
            self.assertTrue(frame.show_youtube_music_details(video))

        fetch.assert_called_once_with(URL)
        self.assertEqual(frame.dialogs[0]["title"], "Detalhes de Clipe")
        self.assertEqual(frame.dialogs[0]["text"], "Clipe\n\nSem descrição.")

    def test_the_details_offer_to_go_to_the_channel(self):
        frame = _Frame()
        frame.on_open_youtube_music = Mock()
        frame._get_youtube_music_panel = Mock(return_value=object())
        frame.on_browse_youtube_music_search_result = Mock(return_value=True)
        found = details.YouTubeMediaDetails(title="Clipe", channel="Canal", channel_id="UC" + "a" * 22)
        with patch.object(details, "media_details", return_value=found):
            frame._open_youtube_music_details(URL)

        ((label, go_to_channel),) = frame.dialogs[0]["actions"]
        self.assertEqual(label, "Ir para o &canal")
        go_to_channel()
        frame.on_open_youtube_music.assert_called_once_with(None)
        channel = frame.on_browse_youtube_music_search_result.call_args.args[0]
        self.assertEqual((channel.result_type, channel.browse_id, channel.title), ("channel", "UC" + "a" * 22, "Canal"))
        self.assertTrue(frame.on_browse_youtube_music_search_result.call_args.kwargs["focus_results"])

    def test_a_music_track_offers_its_artist_instead_of_the_topic_channel(self):
        frame = _Frame()
        found = details.YouTubeMediaDetails(title="Faixa", channel="Ana - Topic", channel_id="UC" + "b" * 22)
        with patch.object(details, "media_details", return_value=found):
            frame._open_youtube_music_details("https://music.youtube.com/watch?v=dQw4w9WgXcQ")

        self.assertEqual(frame.dialogs[0]["actions"][0][0], "Ir para o &artista")
        owner = frame._youtube_music_details_owner("https://music.youtube.com/watch?v=dQw4w9WgXcQ", found)
        self.assertEqual((owner.result_type, owner.title, owner.browse_id), ("artist", "Ana", "UC" + "b" * 22))

    def test_a_playlist_and_a_local_file_have_no_details(self):
        frame = _Frame()
        playlist = YouTubeMediaSearchResult(
            source=YOUTUBE_SEARCH_SOURCE_YOUTUBE, result_type="playlist", title="Lista", playlist_id="PL123"
        )
        frame._get_active_playlist_state = Mock(return_value=SimpleNamespace(current_media_path="C:/musica.mp3"))

        self.assertFalse(frame.show_youtube_music_details(playlist))
        self.assertFalse(frame.show_current_media_details())
        self.assertEqual(
            frame.announcements,
            ["Este item não tem detalhes para mostrar.", "A mídia atual não é do YouTube: não há detalhes para mostrar."],
        )


if __name__ == "__main__":
    unittest.main()
