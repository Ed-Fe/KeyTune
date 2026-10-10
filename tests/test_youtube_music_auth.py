from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.youtube_music.auth import (
    auth_headers_have_login_info,
    summarize_auth_input,
    build_browser_auth_cookie_file_content,
    create_temporary_browser_auth_cookie_file,
    export_cookies_from_browser,
    load_saved_playback_auth,
    prepare_browser_auth_input,
    sanitize_sensitive_text,
    write_browser_auth_cookie_file,
)


class YouTubeMusicAuthTests(unittest.TestCase):
    def test_export_cookies_filters_other_sites_and_keeps_http_only_cookies(self):
        cookie_lines = "\n".join(
            [
                "# Netscape HTTP Cookie File",
                "#HttpOnly_.youtube.com\tTRUE\t/\tTRUE\t0\tSID\tyoutube-secret",
                ".youtube.com\tTRUE\t/\tTRUE\t0\tSAPISID\tsapisid-secret",
                ".example.com\tTRUE\t/\tTRUE\t0\tSESSION\tother-site-secret",
                "",
            ]
        )

        def fake_run(command, **_kwargs):
            cookie_path = pathlib.Path(command[command.index("--cookies") + 1])
            self.assertFalse(cookie_path.exists())
            cookie_path.write_text(cookie_lines, encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = pathlib.Path(temp_dir) / "youtube-cookies.txt"
            with patch(
                "player.youtube_music.yt_dlp_runtime.find_yt_dlp_executable_path",
                return_value="C:/KeyTune/yt-dlp.exe",
            ), patch("player.youtube_music.auth.subprocess.run", side_effect=fake_run):
                exported_path = export_cookies_from_browser("firefox", str(output_path))

            self.assertEqual(exported_path, str(output_path))
            exported_content = output_path.read_text(encoding="utf-8")
            self.assertIn("#HttpOnly_.youtube.com", exported_content)
            self.assertIn("youtube-secret", exported_content)
            self.assertIn("sapisid-secret", exported_content)
            self.assertNotIn("example.com", exported_content)
            self.assertNotIn("other-site-secret", exported_content)
            prepared_auth = prepare_browser_auth_input(exported_content)
            self.assertIn("SID=youtube-secret", prepared_auth)
            self.assertIn("SAPISID=sapisid-secret", prepared_auth)
            self.assertEqual(
                [path.name for path in pathlib.Path(temp_dir).iterdir()],
                ["youtube-cookies.txt"],
            )

    def test_export_cookies_preserves_existing_output_when_yt_dlp_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = pathlib.Path(temp_dir) / "youtube-cookies.txt"
            output_path.write_text("autenticação anterior", encoding="utf-8")
            failed_result = SimpleNamespace(
                returncode=1,
                stdout="",
                stderr="ERROR: Could not copy Chrome cookie database: Permission denied",
            )

            with patch(
                "player.youtube_music.yt_dlp_runtime.find_yt_dlp_executable_path",
                return_value="C:/KeyTune/yt-dlp.exe",
            ), patch("player.youtube_music.auth.subprocess.run", return_value=failed_result):
                with self.assertRaisesRegex(RuntimeError, "Feche o chrome completamente"):
                    export_cookies_from_browser("chrome", str(output_path))

            self.assertEqual(output_path.read_text(encoding="utf-8"), "autenticação anterior")

    def test_export_cookies_rejects_unknown_browser_without_running_yt_dlp(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "player.youtube_music.auth.subprocess.run"
        ) as run_process:
            with self.assertRaisesRegex(RuntimeError, "Navegador não reconhecido"):
                export_cookies_from_browser("desconhecido", str(pathlib.Path(temp_dir) / "cookies.txt"))

        run_process.assert_not_called()

    def test_build_browser_auth_cookie_file_content_from_headers(self):
        raw_headers = "\n".join(
            [
                "Authorization: SAPISIDHASH teste",
                "Cookie: SID=abc; HSID=def; SAPISID=ghi",
                "X-Goog-AuthUser: 0",
                "x-origin: https://music.youtube.com",
            ]
        )

        cookie_file_content = build_browser_auth_cookie_file_content(raw_headers)

        self.assertIn("# Netscape HTTP Cookie File", cookie_file_content)
        self.assertIn("\tSID\tabc", cookie_file_content)
        self.assertIn("\tHSID\tdef", cookie_file_content)
        self.assertIn("\tSAPISID\tghi", cookie_file_content)

    def test_load_saved_playback_auth_creates_cookie_file_for_existing_browser_json(self):
        auth_json = """{
            "authorization": "SAPISIDHASH teste",
            "cookie": "SID=abc; HSID=def",
            "user-agent": "Mozilla/5.0 Teste",
            "x-goog-authuser": "0",
            "x-origin": "https://music.youtube.com"
        }"""

        with tempfile.TemporaryDirectory() as temp_dir:
            auth_file_path = pathlib.Path(temp_dir) / "ytmusic_browser.json"
            cookie_file_path = pathlib.Path(temp_dir) / "ytmusic_cookies.txt"
            auth_file_path.write_text(auth_json, encoding="utf-8")

            playback_auth = load_saved_playback_auth(
                str(auth_file_path),
                cookie_file_path=str(cookie_file_path),
            )

            self.assertEqual(playback_auth.cookie_header, "SID=abc; HSID=def")
            self.assertEqual(playback_auth.user_agent, "Mozilla/5.0 Teste")
            self.assertEqual(playback_auth.cookie_file_path, str(cookie_file_path))
            self.assertEqual(playback_auth.yt_dlp_http_headers, {"User-Agent": "Mozilla/5.0 Teste"})
            self.assertEqual(
                playback_auth.playback_http_headers,
                {
                    "Cookie": "SID=abc; HSID=def",
                    "User-Agent": "Mozilla/5.0 Teste",
                },
            )
            self.assertTrue(cookie_file_path.is_file())

    def test_write_browser_auth_cookie_file_removes_sidecar_when_no_cookies_exist(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cookie_file_path = pathlib.Path(temp_dir) / "ytmusic_cookies.txt"
            cookie_file_path.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")

            written_path = write_browser_auth_cookie_file("Authorization: sem-cookie", str(cookie_file_path))

            self.assertEqual(written_path, "")
            self.assertFalse(cookie_file_path.exists())

    def test_load_saved_playback_auth_regenerates_existing_empty_cookie_file(self):
        auth_json = """{
            "authorization": "SAPISIDHASH teste",
            "cookie": "SID=abc; HSID=def",
            "user-agent": "Mozilla/5.0 Teste",
            "x-goog-authuser": "0",
            "x-origin": "https://music.youtube.com"
        }"""

        with tempfile.TemporaryDirectory() as temp_dir:
            auth_file_path = pathlib.Path(temp_dir) / "ytmusic_browser.json"
            cookie_file_path = pathlib.Path(temp_dir) / "ytmusic_cookies.txt"
            auth_file_path.write_text(auth_json, encoding="utf-8")
            cookie_file_path.write_text("", encoding="utf-8")

            playback_auth = load_saved_playback_auth(
                str(auth_file_path),
                cookie_file_path=str(cookie_file_path),
            )

            self.assertEqual(playback_auth.cookie_file_path, str(cookie_file_path))
            self.assertIn("# Netscape HTTP Cookie File", cookie_file_path.read_text(encoding="utf-8"))
            self.assertIn("\tSID\tabc", cookie_file_path.read_text(encoding="utf-8"))

    def test_load_saved_playback_auth_does_not_persist_cookie_file_by_default(self):
        auth_json = """{
            "authorization": "SAPISIDHASH teste",
            "cookie": "SID=abc; HSID=def",
            "user-agent": "Mozilla/5.0 Teste",
            "x-goog-authuser": "0",
            "x-origin": "https://music.youtube.com"
        }"""

        with tempfile.TemporaryDirectory() as temp_dir:
            auth_file_path = pathlib.Path(temp_dir) / "ytmusic_browser.json"
            auth_file_path.write_text(auth_json, encoding="utf-8")

            playback_auth = load_saved_playback_auth(str(auth_file_path))

            self.assertEqual(playback_auth.cookie_header, "SID=abc; HSID=def")
            self.assertEqual(playback_auth.user_agent, "Mozilla/5.0 Teste")
            self.assertEqual(playback_auth.cookie_file_path, "")

    def test_create_temporary_browser_auth_cookie_file_generates_netscape_content(self):
        cookie_file_path = create_temporary_browser_auth_cookie_file("SID=abc; HSID=def")

        try:
            self.assertTrue(pathlib.Path(cookie_file_path).is_file())
            raw_content = pathlib.Path(cookie_file_path).read_text(encoding="utf-8")
            self.assertIn("# Netscape HTTP Cookie File", raw_content)
            self.assertIn("\tSID\tabc", raw_content)
            self.assertIn("\tHSID\tdef", raw_content)
        finally:
            if cookie_file_path:
                pathlib.Path(cookie_file_path).unlink(missing_ok=True)

    def _assert_ytmusicapi_reads(self, headers_raw, expected_sapisid):
        from ytmusicapi.auth.browser import setup_browser
        from ytmusicapi.helpers import sapisid_from_cookie
        import json

        headers = json.loads(setup_browser(headers_raw=headers_raw))
        self.assertEqual(sapisid_from_cookie(headers["cookie"]), expected_sapisid)
        return headers

    def test_cookie_outside_the_standard_does_not_hide_the_auth_cookie(self):
        for odd_cookie in ("PREF=a b", "NOME=joão", "ST[1]=v", "X=a\\b", "a(b)=1"):
            with self.subTest(odd_cookie=odd_cookie):
                headers_raw = prepare_browser_auth_input(f"Cookie: {odd_cookie}; SID=x; __Secure-3PAPISID=segredo")

                headers = self._assert_ytmusicapi_reads(headers_raw, "segredo")
                self.assertIn("SID=x", headers["cookie"])

    def test_sapisid_stands_in_for_a_missing_third_party_cookie(self):
        headers_raw = prepare_browser_auth_input("Cookie: SID=x; SAPISID=segredo")

        self._assert_ytmusicapi_reads(headers_raw, "segredo")

    def test_pasted_headers_get_the_fields_ytmusicapi_requires(self):
        headers_raw = prepare_browser_auth_input("Cookie: SID=x; __Secure-3PAPISID=segredo\nUser-Agent: Teste")

        headers = self._assert_ytmusicapi_reads(headers_raw, "segredo")
        self.assertEqual(headers["x-goog-authuser"], "0")

    def test_bare_cookie_value_is_accepted(self):
        headers_raw = prepare_browser_auth_input("SID=x; __Secure-3PAPISID=segredo")

        self._assert_ytmusicapi_reads(headers_raw, "segredo")
        self.assertIn(
            "\tSID\tx",
            build_browser_auth_cookie_file_content(headers_raw),
        )

    def test_netscape_cookies_pasted_with_spaces_instead_of_tabs(self):
        pasted = (
            "# Netscape HTTP Cookie File\n"
            ".youtube.com    TRUE    /    TRUE    0    __Secure-3PAPISID    segredo\n"
            "#HttpOnly_.youtube.com TRUE / TRUE 0 SID x\n"
        )

        self._assert_ytmusicapi_reads(prepare_browser_auth_input(pasted), "segredo")
        self.assertIn("#HttpOnly_.youtube.com\tTRUE\t/\tTRUE\t0\tSID\tx", build_browser_auth_cookie_file_content(pasted))

    def test_cookies_are_read_before_ytmusicapi_is_available(self):
        cookies_txt = "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSAPISID\tsegredo\n"

        # No build de release o ytmusicapi é baixado sob demanda.
        with patch.dict(sys.modules, {"ytmusicapi": None, "ytmusicapi.helpers": None}):
            headers_raw = prepare_browser_auth_input(cookies_txt)

        self.assertRegex(headers_raw, r"Authorization: SAPISIDHASH \d+_[0-9a-f]{40}\n")

    def test_login_info_is_found_in_every_accepted_input(self):
        cookies_txt = (
            "# Netscape HTTP Cookie File\n"
            ".youtube.com\tTRUE\t/\tTRUE\t0\tSAPISID\tsegredo\n"
            "#HttpOnly_.youtube.com\tTRUE\t/\tTRUE\t0\tLOGIN_INFO\tAFmmF2sw:QUQ3Mj==\n"
        )

        self.assertTrue(auth_headers_have_login_info(prepare_browser_auth_input(cookies_txt)))
        self.assertTrue(auth_headers_have_login_info({"Cookie": "SAPISID=segredo; LOGIN_INFO=a:b"}))
        self.assertFalse(auth_headers_have_login_info(prepare_browser_auth_input("SID=x; SAPISID=segredo")))

    def test_input_summary_for_the_log_has_names_and_counts_but_no_values(self):
        cookies_txt = (
            "# Netscape HTTP Cookie File\n"
            ".youtube.com\tTRUE\t/\tTRUE\t0\tSAPISID\tvalor-secreto\n"
            ".youtube.com\tTRUE\t/\tTRUE\t1\tSID\tvalor-vencido\n"
            ".google.com\tTRUE\t/\tTRUE\t0\tSID\tvalor-de-outro-site\n"
        )

        summary = summarize_auth_input(cookies_txt)

        self.assertIn("format=netscape other_sites=1 expired=1 youtube_cookies=1", summary)
        self.assertIn("present=SAPISID ", summary)
        self.assertIn("LOGIN_INFO", summary.split("missing=")[1])
        self.assertNotIn("valor", summary)

    def test_input_summary_names_each_accepted_format(self):
        inputs = {
            "format=headers": "Cookie: SID=x; SAPISID=segredo\nUser-Agent: Teste",
            "format=cookie-value": "SID=x; SAPISID=segredo",
            "format=json-cookies": '[{"name": "SAPISID", "value": "segredo", "domain": ".youtube.com"}]',
            "format=json-headers": '{"cookie": "SID=x; SAPISID=segredo"}',
            "format=unknown": "texto qualquer",
            "format=empty": "  ",
        }
        for expected, raw_input in inputs.items():
            with self.subTest(expected=expected):
                summary = summarize_auth_input(raw_input)
                self.assertTrue(summary.startswith(expected), summary)
                self.assertNotIn("segredo", summary)

    def test_text_without_cookies_is_left_for_ytmusicapi_to_reject(self):
        self.assertEqual(prepare_browser_auth_input("texto qualquer"), "texto qualquer")

    def test_sanitize_sensitive_text_redacts_cookie_and_tokens(self):
        raw_error = (
            "ERROR: Cookie: SID=abc123; HSID=def456; Authorization: Bearer xyz987 "
            "https://example.invalid/watch?v=123&token=secret"
        )

        sanitized_error = sanitize_sensitive_text(raw_error)

        self.assertNotIn("abc123", sanitized_error)
        self.assertNotIn("def456", sanitized_error)
        self.assertNotIn("xyz987", sanitized_error)
        self.assertNotIn("secret", sanitized_error)
        self.assertIn("[oculto]", sanitized_error)


if __name__ == "__main__":
    unittest.main()
