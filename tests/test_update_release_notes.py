import pathlib
import sys
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.update.service import release_notes_to_plain_text


class ReleaseNotesFormattingTests(unittest.TestCase):
    def test_converts_changelog_markdown_to_plain_text(self):
        release_notes = """## [1.2.1] - 2026-07-27

### Corrigido
- **Reprodução automática de playlists**: volta a iniciar corretamente.
- Use `yt-dlp` ou consulte a [documentação](https://example.com).
"""

        self.assertEqual(
            release_notes_to_plain_text(release_notes),
            """1.2.1 - 2026-07-27

Corrigido
- Reprodução automática de playlists: volta a iniciar corretamente.
- Use yt-dlp ou consulte a documentação (https://example.com).""",
        )

    def test_preserves_empty_release_notes(self):
        self.assertEqual(release_notes_to_plain_text(""), "")


if __name__ == "__main__":
    unittest.main()
