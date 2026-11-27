import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from player.library.playlist_io import (  # noqa: E402
    _parse_extinf_title,
    load_playlist,
    load_playlist_entries,
    save_playlist,
)


class PlaylistTitlesTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.directory = self._tmp.name
        self.local_track = os.path.join(self.directory, "song.mp3")
        with open(self.local_track, "wb") as handle:
            handle.write(b"")
        self.playlist_path = os.path.join(self.directory, "list.m3u8")

    def test_saved_youtube_items_keep_their_titles(self):
        items = [
            "https://www.youtube.com/watch?v=YYiChSh_ktU",
            self.local_track,
            "https://www.youtube.com/watch?v=abc",
        ]
        labels = ["Artista - Canção", "song.mp3", "Outra,  com vírgula\nquebrada"]

        save_playlist(self.playlist_path, items, labels)
        entries = load_playlist_entries(self.playlist_path)

        self.assertEqual([item for item, _ in entries], items)
        self.assertEqual(
            [title for _, title in entries],
            ["Artista - Canção", None, "Outra, com vírgula quebrada"],
        )
        with open(self.playlist_path, encoding="utf-8") as handle:
            text = handle.read()
        # O nome do arquivo local já é o rótulo padrão: não ganha #EXTINF.
        self.assertEqual(text.count("#EXTINF"), 2)

    def test_save_without_labels_still_writes_plain_entries(self):
        save_playlist(self.playlist_path, [self.local_track])
        self.assertEqual(load_playlist(self.playlist_path), [self.local_track])
        self.assertEqual(load_playlist_entries(self.playlist_path), [(self.local_track, None)])

    def test_extinf_title_is_not_carried_over_a_missing_entry(self):
        with open(self.playlist_path, "w", encoding="utf-8") as handle:
            handle.write("#EXTM3U\n#EXTINF:-1,Sumiu\nmissing.mp3\nsong.mp3\n")
        self.assertEqual(load_playlist_entries(self.playlist_path), [(self.local_track, None)])

    def test_extinf_with_quoted_attributes(self):
        self.assertEqual(_parse_extinf_title('#EXTINF:-1 tvg-name="a,b",Rádio Boa'), "Rádio Boa")
        self.assertEqual(_parse_extinf_title("#EXTINF:123,"), None)
        self.assertEqual(_parse_extinf_title("#EXTINF:123"), None)


if __name__ == "__main__":
    unittest.main()
