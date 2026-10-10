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

from player.youtube_music.service import YouTubeMusicDependencyUnavailableError, YouTubeMusicService
from player.youtube_music.feedback_store import YouTubeMusicFeedbackStore
from player.youtube_music.streams import ResolvedStreamPlayback


class YouTubeMusicServiceTests(unittest.TestCase):
    def test_missing_youtube_library_is_not_reported_as_invalid_account(self):
        service = YouTubeMusicService()

        with patch.object(service, "has_saved_browser_auth", return_value=True), patch(
            "player.youtube_music.service.import_ytmusicapi_module",
            side_effect=ModuleNotFoundError(name="ytmusicapi"),
        ):
            with self.assertRaises(YouTubeMusicDependencyUnavailableError) as raised:
                service.validate_saved_authentication()

        self.assertFalse(raised.exception.should_disconnect)
        self.assertIn("recursos adicionais", str(raised.exception))

    def test_save_browser_auth_validates_staged_files_before_replacing_saved_auth(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            auth_path = pathlib.Path(temp_dir) / "ytmusic_browser.json"
            cookie_path = pathlib.Path(temp_dir) / "ytmusic_cookies.txt"
            auth_path.write_text("autenticação anterior", encoding="utf-8")
            cookie_path.write_text("cookies anteriores", encoding="utf-8")

            def fake_setup(*, filepath, headers_raw):
                pathlib.Path(filepath).write_text(headers_raw, encoding="utf-8")

            candidate_client = Mock()
            candidate_client.get_account_info.side_effect = RuntimeError("conta inválida")
            fake_module = SimpleNamespace(
                setup=fake_setup,
                YTMusic=Mock(return_value=candidate_client),
            )
            service = YouTubeMusicService()

            with patch(
                "player.youtube_music.service.get_browser_auth_file_path",
                return_value=str(auth_path),
            ), patch(
                "player.youtube_music.service.get_browser_auth_cookie_file_path",
                return_value=str(cookie_path),
            ), patch(
                "player.youtube_music.service.import_ytmusicapi_module",
                return_value=fake_module,
            ):
                with self.assertRaisesRegex(RuntimeError, "conta inválida"):
                    service.save_browser_auth(headers_raw="Cookie: SID=novo; SAPISID=segredo")

            self.assertEqual(auth_path.read_text(encoding="utf-8"), "autenticação anterior")
            self.assertEqual(cookie_path.read_text(encoding="utf-8"), "cookies anteriores")

    def _account_menu_response(self, logged_in):
        return {
            "responseContext": {
                "serviceTrackingParams": [{"service": "GFEEDBACK", "params": [{"key": "logged_in", "value": logged_in}]}]
            }
        }

    def _client_with_unreadable_account_menu(self, response):
        client = Mock()
        client.get_account_info.side_effect = KeyError("Unable to find 'actions'")
        client._send_request.return_value = response
        return client

    def test_unreadable_account_menu_is_accepted_when_youtube_reports_logged_in(self):
        from player.youtube_music.service import _fetch_account_info

        client = self._client_with_unreadable_account_menu(self._account_menu_response("1"))

        self.assertEqual(_fetch_account_info(client)["accountName"], "")

    def test_unreadable_account_menu_is_refused_when_youtube_reports_logged_out(self):
        from player.youtube_music.service import _fetch_account_info

        client = self._client_with_unreadable_account_menu(self._account_menu_response("0"))

        with self.assertRaisesRegex(RuntimeError, "janela anônima"):
            _fetch_account_info(client)

    def test_unreadable_account_menu_keeps_the_original_error_when_state_is_unknown(self):
        from player.youtube_music.service import _fetch_account_info

        client = self._client_with_unreadable_account_menu({})

        with self.assertRaises(KeyError):
            _fetch_account_info(client)

    def test_server_errors_are_not_retried_as_account_menu_problems(self):
        from player.youtube_music.service import _fetch_account_info

        client = Mock()
        client.get_account_info.side_effect = RuntimeError("Server returned HTTP 401: Unauthorized")

        with self.assertRaisesRegex(RuntimeError, "401"):
            _fetch_account_info(client)
        client._send_request.assert_not_called()

    def _service_with_saved_headers(self, temp_dir, headers):
        import json

        auth_path = pathlib.Path(temp_dir) / "ytmusic_browser.json"
        auth_path.write_text(json.dumps(headers), encoding="utf-8")
        patcher = patch("player.youtube_music.service.get_browser_auth_file_path", return_value=str(auth_path))
        patcher.start()
        self.addCleanup(patcher.stop)
        return YouTubeMusicService(), auth_path

    def _module_answering_accounts(self, names_by_index):
        def make_client(headers):
            index = int(headers["x-goog-authuser"])
            client = Mock()
            if index in names_by_index:
                client.get_account_info.return_value = {"accountName": names_by_index[index]}
            else:
                client.get_account_info.side_effect = KeyError("actions")
                client._send_request.return_value = self._account_menu_response("0")
            return client

        return SimpleNamespace(YTMusic=make_client)

    def test_session_accounts_are_listed_until_youtube_answers_logged_out(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service, _auth_path = self._service_with_saved_headers(temp_dir, {"cookie": "SID=x", "X-Goog-AuthUser": "0"})
            module = self._module_answering_accounts({0: "Pessoal", 1: "Canal"})

            with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=module):
                accounts = service.list_session_accounts()

        self.assertEqual(accounts, [(0, "Pessoal"), (1, "Canal")])

    def test_selecting_a_session_account_saves_its_index_and_keeps_one_header(self):
        import json

        with tempfile.TemporaryDirectory() as temp_dir:
            service, auth_path = self._service_with_saved_headers(temp_dir, {"cookie": "SID=x", "X-Goog-AuthUser": "0"})
            module = self._module_answering_accounts({0: "Pessoal", 1: "Canal"})

            with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=module):
                name = service.select_session_account(1)

            saved = json.loads(auth_path.read_text(encoding="utf-8"))
            self.assertEqual(service.saved_account_index(), 1)

        self.assertEqual(name, "Canal")
        self.assertEqual([key for key in saved if key.lower() == "x-goog-authuser"], ["x-goog-authuser"])
        self.assertEqual(saved["x-goog-authuser"], "1")

    def test_selecting_an_account_that_is_not_in_the_session_leaves_the_file_alone(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service, auth_path = self._service_with_saved_headers(temp_dir, {"cookie": "SID=x", "X-Goog-AuthUser": "0"})
            before = auth_path.read_text(encoding="utf-8")
            module = self._module_answering_accounts({0: "Pessoal"})

            with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=module):
                with self.assertRaises(RuntimeError):
                    service.select_session_account(3)

            self.assertEqual(auth_path.read_text(encoding="utf-8"), before)

    def test_save_browser_auth_replaces_both_files_after_validation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            auth_path = pathlib.Path(temp_dir) / "ytmusic_browser.json"
            cookie_path = pathlib.Path(temp_dir) / "ytmusic_cookies.txt"

            def fake_setup(*, filepath, headers_raw):
                pathlib.Path(filepath).write_text(headers_raw, encoding="utf-8")

            candidate_client = Mock()
            candidate_client.get_account_info.return_value = {"accountName": "Conta nova"}
            fake_module = SimpleNamespace(
                setup=fake_setup,
                YTMusic=Mock(return_value=candidate_client),
            )
            service = YouTubeMusicService()

            with patch(
                "player.youtube_music.service.get_browser_auth_file_path",
                return_value=str(auth_path),
            ), patch(
                "player.youtube_music.service.get_browser_auth_cookie_file_path",
                return_value=str(cookie_path),
            ), patch(
                "player.youtube_music.service.import_ytmusicapi_module",
                return_value=fake_module,
            ):
                saved_path = service.save_browser_auth(
                    headers_raw="Cookie: SID=novo; SAPISID=segredo\nUser-Agent: Teste"
                )
                account_name = service.get_connected_account_name()

            self.assertEqual(saved_path, str(auth_path))
            self.assertEqual(account_name, "Conta nova")
            self.assertIn("SID=novo", auth_path.read_text(encoding="utf-8"))
            self.assertIn("\tSID\tnovo", cookie_path.read_text(encoding="utf-8"))
            fake_module.YTMusic.assert_called_once()

    def test_switches_stream_resolution_to_anonymous_mode_for_the_session(self):
        service = YouTubeMusicService()
        media_path = "https://www.youtube.com/watch?v=abc123DEF45"
        resolved_playback = ResolvedStreamPlayback(
            stream_url="https://rr1---sn.example.googlevideo.com/audio.webm",
        )

        with patch.object(service, "has_saved_browser_auth", return_value=True), patch(
            "player.youtube_music.service.resolve_music_stream_playback",
            return_value=resolved_playback,
        ) as resolve_stream:
            service.resolve_stream_playback(media_path)
            next_mode = service.advance_stream_playback_after_http_403()
            service.resolve_stream_playback(media_path)

        self.assertEqual(next_mode, "web_embedded")
        self.assertEqual(
            [
                (
                    call.kwargs["use_account_cookies"],
                    call.kwargs["anonymous_player_client"],
                )
                for call in resolve_stream.call_args_list
            ],
            [(False, "visionos"), (False, "web_embedded")],
        )

    def test_http_403_advances_stream_profiles_once_per_session(self):
        service = YouTubeMusicService()

        with patch.object(service, "has_saved_browser_auth", return_value=True):
            self.assertEqual(service.advance_stream_playback_after_http_403(), "web_embedded")
            self.assertEqual(service.advance_stream_playback_after_http_403(), "")

        with patch(
            "player.youtube_music.service.resolve_music_stream_playback",
            return_value=ResolvedStreamPlayback(stream_url="https://media.example.invalid/audio.mp4"),
        ) as resolve_stream:
            service.resolve_stream_playback("https://www.youtube.com/watch?v=abc123DEF45")

        self.assertFalse(resolve_stream.call_args.kwargs["use_account_cookies"])
        self.assertEqual(resolve_stream.call_args.kwargs["anonymous_player_client"], "web_embedded")

    def test_cache_ttl_respects_expiring_signed_urls(self):
        service = YouTubeMusicService()
        media_path = "https://www.youtube.com/watch?v=abc123DEF45"
        resolved_playback = ResolvedStreamPlayback(
            stream_url="https://rr1---sn.example.googlevideo.com/videoplayback?expire=760&id=abc",
            http_headers={"User-Agent": "yt-test/1.0"},
            display_title="Vídeo de teste",
            display_artist="Canal de teste",
        )

        with patch("player.youtube_music.stream_cache.time.time", return_value=600), patch(
            "player.youtube_music.stream_cache.time.monotonic", return_value=10
        ):
            service._cache_stream_playback(media_path, resolved_playback)

        cached_entry = service._stream_cache[media_path]
        self.assertEqual(cached_entry["expires_at"], 140)
        self.assertEqual(cached_entry["display_title"], "Vídeo de teste")
        self.assertEqual(cached_entry["display_artist"], "Canal de teste")

    def test_cache_skips_urls_that_are_already_too_close_to_expiring(self):
        service = YouTubeMusicService()
        media_path = "https://www.youtube.com/watch?v=abc123DEF45"
        resolved_playback = ResolvedStreamPlayback(
            stream_url="https://rr1---sn.example.googlevideo.com/videoplayback?expire=620&id=abc",
            http_headers={"User-Agent": "yt-test/1.0"},
            display_title="Vídeo de teste",
            display_artist="Canal de teste",
        )

        with patch("player.youtube_music.stream_cache.time.time", return_value=600), patch(
            "player.youtube_music.stream_cache.time.monotonic", return_value=10
        ):
            returned_playback = service._cache_stream_playback(media_path, resolved_playback)

        self.assertEqual(returned_playback.stream_url, resolved_playback.stream_url)
        self.assertEqual(returned_playback.display_title, "Vídeo de teste")
        self.assertEqual(returned_playback.display_artist, "Canal de teste")
        self.assertNotIn(media_path, service._stream_cache)

    def test_cached_stream_can_be_invalidated_for_retry(self):
        service = YouTubeMusicService()
        media_path = "https://www.youtube.com/watch?v=abc123DEF45"
        resolved_playback = ResolvedStreamPlayback(
            stream_url="https://rr1---sn.example.googlevideo.com/audio.webm",
        )
        service._cache_stream_playback(media_path, resolved_playback)

        self.assertTrue(service.invalidate_cached_stream(media_path))
        self.assertIsNone(service.get_cached_stream_playback(media_path))
        self.assertFalse(service.invalidate_cached_stream(media_path))


    def test_search_uses_public_client_for_youtube_music_catalog(self):
        public_client = Mock()
        public_client.search.return_value = [{"resultType": "song", "videoId": "abc123DEF45", "title": "Faixa"}]
        fake_ytmusic_cls = Mock(return_value=public_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module):
            results = service.search("teste", search_scope="music_songs")

        self.assertEqual(len(results), 1)
        public_client.search.assert_called_once_with("teste", filter="songs", limit=20)
        fake_ytmusic_cls.assert_called_once_with()

    def test_get_playlist_content_uses_public_client_when_auth_is_not_required(self):
        public_client = Mock()
        public_client.get_playlist.return_value = {
            "title": "Playlist pÃºblica",
            "tracks": [{"videoId": "abc123DEF45", "title": "Faixa"}],
        }
        fake_ytmusic_cls = Mock(return_value=public_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module):
            playlist = service.get_playlist_content("PL1234567890")

        self.assertEqual(playlist.playlist_id, "PL1234567890")
        self.assertEqual(playlist.title, "Playlist pÃºblica")
        public_client.get_playlist.assert_called_once_with("PL1234567890", limit=None)
        fake_ytmusic_cls.assert_called_once_with()

    def test_get_playlist_content_uses_authenticated_client_when_requested(self):
        authenticated_client = Mock()
        authenticated_client.get_playlist.return_value = {
            "title": "Playlist autenticada",
            "tracks": [{"videoId": "abc123DEF45", "title": "Faixa"}],
        }
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "has_saved_browser_auth", return_value=True
        ):
            playlist = service.get_playlist_content("PL1234567890", require_auth=True)

        self.assertEqual(playlist.title, "Playlist autenticada")
        authenticated_client.get_playlist.assert_called_once_with("PL1234567890", limit=None)
        fake_ytmusic_cls.assert_called_once_with(service.browser_auth_file_path)

    def test_authenticated_playlist_filters_dislikes_persisted_for_the_account(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = YouTubeMusicFeedbackStore(pathlib.Path(temp_dir) / "feedback.json")
            store.set_active_account({"channelHandle": "@ouvinte"})
            store.record("disliked123", "DISLIKE")
            service = YouTubeMusicService(feedback_store=store)
            service.sync_account_feedback = Mock(return_value=0)
            service._library.get_playlist_content = Mock(
                return_value=SimpleNamespace(
                    playlist_id="PL123",
                    title="Conta",
                    item_urls=[
                        "https://music.youtube.com/watch?v=disliked123",
                        "https://music.youtube.com/watch?v=allowed456",
                    ],
                    item_labels=["Não gostei", "Permitida"],
                )
            )

            with patch.object(service, "has_saved_browser_auth", return_value=True):
                content = service.get_playlist_content("PL123", require_auth=True)

            self.assertEqual(
                content.item_urls,
                ["https://music.youtube.com/watch?v=allowed456"],
            )
            self.assertEqual(content.item_labels, ["Permitida"])

    def test_public_playlist_does_not_apply_the_last_accounts_persistent_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = YouTubeMusicFeedbackStore(pathlib.Path(temp_dir) / "feedback.json")
            store.set_active_account({"channelHandle": "@ouvinte"})
            store.record("disliked123", "DISLIKE")
            service = YouTubeMusicService(feedback_store=store)
            content = SimpleNamespace(
                playlist_id="PL123",
                title="Pública",
                item_urls=["https://music.youtube.com/watch?v=disliked123"],
                item_labels=["Faixa"],
            )
            service._library.get_playlist_content = Mock(return_value=content)

            returned = service.get_playlist_content("PL123", require_auth=False)

            self.assertIs(returned, content)

    def test_add_tracks_to_playlist_returns_added_count_on_success(self):
        authenticated_client = Mock()
        authenticated_client.add_playlist_items.return_value = {
            "status": "STATUS_SUCCEEDED",
            "playlistEditResults": [{"videoId": "abc123DEF45"}, {"videoId": "xyz987WVU54"}],
        }
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "has_saved_browser_auth", return_value=True
        ):
            added = service.add_tracks_to_playlist("PL1234567890", ["abc123DEF45", "abc123DEF45", "xyz987WVU54"])

        self.assertEqual(added, 2)
        # Duplicates in the request are collapsed before hitting the API.
        authenticated_client.add_playlist_items.assert_called_once_with(
            "PL1234567890", ["abc123DEF45", "xyz987WVU54"]
        )

    def test_add_tracks_to_playlist_raises_when_server_rejects(self):
        authenticated_client = Mock()
        authenticated_client.add_playlist_items.return_value = "STATUS_FAILED"
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "has_saved_browser_auth", return_value=True
        ):
            with self.assertRaises(RuntimeError):
                service.add_tracks_to_playlist("PL1234567890", ["abc123DEF45"])

    def test_remove_tracks_from_playlist_maps_set_video_ids(self):
        authenticated_client = Mock()
        authenticated_client.get_playlist.return_value = {
            "owned": True,
            "tracks": [
                {"videoId": "abc123DEF45", "setVideoId": "SET_ABC"},
                {"videoId": "xyz987WVU54", "setVideoId": "SET_XYZ"},
            ],
        }
        authenticated_client.remove_playlist_items.return_value = "STATUS_SUCCEEDED"
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "has_saved_browser_auth", return_value=True
        ):
            removed = service.remove_tracks_from_playlist("PL1234567890", ["abc123DEF45"])

        self.assertEqual(removed, 1)
        authenticated_client.remove_playlist_items.assert_called_once_with(
            "PL1234567890", [{"videoId": "abc123DEF45", "setVideoId": "SET_ABC"}]
        )

    def test_remove_tracks_from_playlist_raises_when_track_absent(self):
        authenticated_client = Mock()
        authenticated_client.get_playlist.return_value = {
            "owned": True,
            "tracks": [{"videoId": "other00ID000", "setVideoId": "SET_OTHER"}],
        }
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "has_saved_browser_auth", return_value=True
        ):
            with self.assertRaises(RuntimeError):
                service.remove_tracks_from_playlist("PL1234567890", ["abc123DEF45"])
        authenticated_client.remove_playlist_items.assert_not_called()

    def test_remove_tracks_from_playlist_rejects_non_owned_playlist(self):
        authenticated_client = Mock()
        # A saved/public playlist the account does not own: no ``owned`` flag
        # and no ``collaborators`` entry.
        authenticated_client.get_playlist.return_value = {
            "tracks": [{"videoId": "abc123DEF45", "setVideoId": "SET_ABC"}]
        }
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "has_saved_browser_auth", return_value=True
        ):
            with self.assertRaises(RuntimeError):
                service.remove_tracks_from_playlist("PL1234567890", ["abc123DEF45"])
        authenticated_client.remove_playlist_items.assert_not_called()

    def test_create_playlist_returns_new_id_for_empty_playlist(self):
        authenticated_client = Mock()
        authenticated_client.create_playlist.return_value = "PLNEW1234567"
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "has_saved_browser_auth", return_value=True
        ):
            new_id = service.create_playlist("Minha playlist")

        self.assertEqual(new_id, "PLNEW1234567")
        authenticated_client.create_playlist.assert_called_once_with(
            "Minha playlist", "", privacy_status="PRIVATE", video_ids=None
        )

    def test_create_playlist_seeds_and_dedupes_video_ids(self):
        authenticated_client = Mock()
        authenticated_client.create_playlist.return_value = "PLNEW1234567"
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "has_saved_browser_auth", return_value=True
        ):
            new_id = service.create_playlist(
                "Seleção",
                video_ids=["abc123DEF45", "abc123DEF45", "xyz987WVU54"],
            )

        self.assertEqual(new_id, "PLNEW1234567")
        authenticated_client.create_playlist.assert_called_once_with(
            "Seleção", "", privacy_status="PRIVATE", video_ids=["abc123DEF45", "xyz987WVU54"]
        )

    def test_create_playlist_forwards_chosen_privacy_status(self):
        authenticated_client = Mock()
        authenticated_client.create_playlist.return_value = "PLNEW1234567"
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "has_saved_browser_auth", return_value=True
        ):
            service.create_playlist("Pública", privacy_status="PUBLIC")

        authenticated_client.create_playlist.assert_called_once_with(
            "Pública", "", privacy_status="PUBLIC", video_ids=None
        )

    def test_create_playlist_falls_back_to_private_for_invalid_privacy(self):
        authenticated_client = Mock()
        authenticated_client.create_playlist.return_value = "PLNEW1234567"
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "has_saved_browser_auth", return_value=True
        ):
            service.create_playlist("Qualquer", privacy_status="BOGUS")

        authenticated_client.create_playlist.assert_called_once_with(
            "Qualquer", "", privacy_status="PRIVATE", video_ids=None
        )

    def test_create_playlist_raises_when_no_id_returned(self):
        authenticated_client = Mock()
        authenticated_client.create_playlist.return_value = {"error": "boom"}
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "has_saved_browser_auth", return_value=True
        ):
            with self.assertRaises(RuntimeError):
                service.create_playlist("Sem id")

    def test_delete_playlist_deletes_owned_playlist(self):
        authenticated_client = Mock()
        authenticated_client.get_playlist.return_value = {"owned": True, "tracks": []}
        authenticated_client.delete_playlist.return_value = "STATUS_SUCCEEDED"
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "has_saved_browser_auth", return_value=True
        ):
            deleted_id = service.delete_playlist("PL1234567890")

        self.assertEqual(deleted_id, "PL1234567890")
        authenticated_client.delete_playlist.assert_called_once_with("PL1234567890")

    def test_delete_playlist_rejects_non_owned_playlist(self):
        authenticated_client = Mock()
        # Saved/collaborator playlist: editable but not owned, so not deletable.
        authenticated_client.get_playlist.return_value = {"collaborators": [], "tracks": []}
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "has_saved_browser_auth", return_value=True
        ):
            with self.assertRaises(RuntimeError):
                service.delete_playlist("PL1234567890")
        authenticated_client.delete_playlist.assert_not_called()

    def test_delete_playlist_rejects_watch_mix_without_api_calls(self):
        authenticated_client = Mock()
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "has_saved_browser_auth", return_value=True
        ):
            with self.assertRaises(RuntimeError):
                service.delete_playlist("RDAMVM1234567")
        authenticated_client.get_playlist.assert_not_called()
        authenticated_client.delete_playlist.assert_not_called()

    def test_get_media_feedback_status_reads_current_track_from_watch_playlist(self):
        authenticated_client = Mock()
        authenticated_client.get_watch_playlist.return_value = {
            "tracks": [
                {"videoId": "other123456", "likeStatus": "INDIFFERENT"},
                {"videoId": "abc123DEF45", "likeStatus": "LIKE"},
            ]
        }
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "has_saved_browser_auth", return_value=True
        ):
            status = service.get_media_feedback_status("https://music.youtube.com/watch?v=abc123DEF45")

        self.assertEqual(status, "LIKE")
        authenticated_client.get_watch_playlist.assert_called_once_with(videoId="abc123DEF45", limit=1)
        fake_ytmusic_cls.assert_called_once_with(service.browser_auth_file_path)

    def test_get_media_feedback_status_reads_matching_counterpart(self):
        authenticated_client = Mock()
        authenticated_client.get_watch_playlist.return_value = {
            "tracks": [
                {
                    "videoId": "song1234567",
                    "likeStatus": "INDIFFERENT",
                    "counterpart": {"videoId": "abc123DEF45", "likeStatus": "LIKE"},
                }
            ]
        }
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(YTMusic=fake_ytmusic_cls)
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "has_saved_browser_auth", return_value=True
        ):
            status = service.get_media_feedback_status("https://music.youtube.com/watch?v=abc123DEF45")

        self.assertEqual(status, "LIKE")
        authenticated_client.get_watch_playlist.assert_called_once_with(videoId="abc123DEF45", limit=1)

    def test_get_media_feedback_status_uses_cache_until_forced_refresh(self):
        authenticated_client = Mock()
        authenticated_client.get_watch_playlist.side_effect = [
            {"tracks": [{"videoId": "abc123DEF45", "likeStatus": "LIKE"}]},
            {"tracks": [{"videoId": "abc123DEF45", "likeStatus": "INDIFFERENT"}]},
        ]
        fake_module = SimpleNamespace(YTMusic=Mock(return_value=authenticated_client))
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "has_saved_browser_auth", return_value=True
        ):
            first_status = service.get_media_feedback_status("https://music.youtube.com/watch?v=abc123DEF45")
            cached_status = service.get_media_feedback_status("https://music.youtube.com/watch?v=abc123DEF45")
            refreshed_status = service.get_media_feedback_status(
                "https://music.youtube.com/watch?v=abc123DEF45", force_refresh=True
            )

        self.assertEqual((first_status, cached_status, refreshed_status), ("LIKE", "LIKE", "INDIFFERENT"))
        self.assertEqual(authenticated_client.get_watch_playlist.call_count, 2)

    def test_rate_media_feedback_calls_rate_song_for_like(self):
        authenticated_client = Mock()
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(
            YTMusic=fake_ytmusic_cls,
            LikeStatus=SimpleNamespace(LIKE="LIKE", DISLIKE="DISLIKE", INDIFFERENT="INDIFFERENT"),
        )
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "get_client", return_value=authenticated_client
        ):
            message = service.rate_media_feedback("https://music.youtube.com/watch?v=abc123DEF45", "LIKE")

        self.assertEqual(message, "Mídia atual curtida no YouTube Music.")
        authenticated_client.rate_song.assert_called_once_with("abc123DEF45", "LIKE")
        authenticated_client.get_song.assert_not_called()


    def test_rate_media_feedback_names_youtube_for_a_plain_youtube_video(self):
        fake_client = Mock()
        fake_module = SimpleNamespace(
            YTMusic=Mock(return_value=fake_client),
            LikeStatus=SimpleNamespace(LIKE="LIKE", DISLIKE="DISLIKE", INDIFFERENT="INDIFFERENT"),
        )
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "get_client", return_value=fake_client
        ):
            message = service.rate_media_feedback("https://www.youtube.com/watch?v=abc123DEF45", "LIKE")

        self.assertEqual(message, "Mídia atual curtida no YouTube.")
        fake_client.rate_song.assert_called_once_with("abc123DEF45", "LIKE")

    def test_rate_media_feedback_calls_rate_song_for_dislike(self):
        authenticated_client = Mock()
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(
            YTMusic=fake_ytmusic_cls,
            LikeStatus=SimpleNamespace(LIKE="LIKE", DISLIKE="DISLIKE", INDIFFERENT="INDIFFERENT"),
        )
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "get_client", return_value=authenticated_client
        ):
            message = service.rate_media_feedback("https://music.youtube.com/watch?v=abc123DEF45", "DISLIKE")

        self.assertEqual(message, "Mídia atual marcada como não gostei no YouTube Music.")
        authenticated_client.rate_song.assert_called_once_with("abc123DEF45", "DISLIKE")
        authenticated_client.get_song.assert_not_called()


    def test_rate_media_feedback_rejects_invalid_rating_without_calling_api(self):
        authenticated_client = Mock()
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(
            YTMusic=fake_ytmusic_cls,
            LikeStatus=SimpleNamespace(LIKE="LIKE", DISLIKE="DISLIKE", INDIFFERENT="INDIFFERENT"),
        )
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "get_client", return_value=authenticated_client
        ):
            with self.assertRaises(RuntimeError):
                service.rate_media_feedback("https://music.youtube.com/watch?v=abc123DEF45", "FAVORITE")

        authenticated_client.rate_song.assert_not_called()

    def test_rate_media_feedback_returns_success_regardless_of_server_propagation_delay(self):
        # O YouTube Music propaga avaliações de forma assíncrona: o get_song()
        # imediatamente após rate_song() pode retornar o status anterior.
        # O player não deve fazer get_song() nem reportar falso alarme.
        authenticated_client = Mock()
        fake_ytmusic_cls = Mock(return_value=authenticated_client)
        fake_module = SimpleNamespace(
            YTMusic=fake_ytmusic_cls,
            LikeStatus=SimpleNamespace(LIKE="LIKE", DISLIKE="DISLIKE", INDIFFERENT="INDIFFERENT"),
        )
        service = YouTubeMusicService()

        with patch("player.youtube_music.service.import_ytmusicapi_module", return_value=fake_module), patch.object(
            service, "get_client", return_value=authenticated_client
        ):
            message = service.rate_media_feedback("https://music.youtube.com/watch?v=abc123DEF45", "LIKE")

        # Mesmo que o servidor ainda não reflita o novo status, a mensagem
        # deve ser a de sucesso (a avaliação foi enviada sem exceção).
        self.assertEqual(message, "Mídia atual curtida no YouTube Music.")
        authenticated_client.rate_song.assert_called_once_with("abc123DEF45", "LIKE")
        authenticated_client.get_song.assert_not_called()


if __name__ == "__main__":
    unittest.main()
