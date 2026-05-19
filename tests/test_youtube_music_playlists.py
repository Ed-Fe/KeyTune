from __future__ import annotations

import pathlib
import sys
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.youtube_music.playlists import extract_personalized_mix_summaries


class YouTubeMusicPlaylistHelperTests(unittest.TestCase):
    def test_extract_personalized_mix_summaries_includes_watch_mix_from_home(self):
        home_rows = [
            {
                "title": "Para você",
                "contents": [
                    {
                        "playlistId": "RDCLAK5uy_testmix",
                        "title": "Supermix",
                        "description": "Atualizada para você",
                        "count": "50+ faixas",
                    }
                ],
            }
        ]

        results = extract_personalized_mix_summaries(home_rows)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].playlist_id, "RDCLAK5uy_testmix")
        self.assertEqual(results[0].source_badge, "mix personalizada")

    def test_extract_personalized_mix_summaries_ignores_non_watch_playlist_even_if_title_mentions_mix(self):
        home_rows = [
            {
                "title": "Made for you",
                "contents": [
                    {
                        "playlistId": "PL1234567890abcdef",
                        "title": "Mix de treino",
                        "description": "Playlist comum",
                        "count": "20 faixas",
                    }
                ],
            }
        ]

        results = extract_personalized_mix_summaries(home_rows)

        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
