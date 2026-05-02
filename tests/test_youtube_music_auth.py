from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.youtube_music.auth import (
    build_browser_auth_cookie_file_content,
    create_temporary_browser_auth_cookie_file,
    load_saved_playback_auth,
    sanitize_sensitive_text,
    write_browser_auth_cookie_file,
)


class YouTubeMusicAuthTests(unittest.TestCase):
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