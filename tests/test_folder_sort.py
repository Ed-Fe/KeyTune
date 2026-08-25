from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.library import (
    FOLDER_ENTRY_DIRECTORY,
    FOLDER_ENTRY_FILE,
    FOLDER_ENTRY_PARENT,
    FOLDER_SORT_CREATED,
    FOLDER_SORT_MODIFIED,
    FOLDER_SORT_SIZE,
    FOLDER_SORT_TYPE,
    FolderBrowserEntry,
    scan_folder_contents,
    sort_folder_entries,
)
from player.playlists import PlaylistState


def _entry(
    label,
    entry_type=FOLDER_ENTRY_FILE,
    *,
    modified=0,
    created=0,
    size=0,
    extension="mp3",
):
    return FolderBrowserEntry(
        path=f"C:\\Músicas\\{label}",
        label=label,
        entry_type=entry_type,
        modified_time=modified,
        created_time=created,
        size=size,
        extension=extension,
    )


class FolderEntrySortTests(unittest.TestCase):
    def setUp(self):
        self.parent = _entry("[..] Pasta acima", FOLDER_ENTRY_PARENT)
        self.directory_10 = _entry("Álbum 10", FOLDER_ENTRY_DIRECTORY, modified=30, created=10)
        self.directory_2 = _entry("Album 2", FOLDER_ENTRY_DIRECTORY, modified=20, created=20)
        self.flac = _entry("Faixa 10.flac", modified=10, created=30, size=100, extension="flac")
        self.mp3 = _entry("Faixa 2.mp3", modified=40, created=40, size=50, extension="mp3")
        self.entries = [self.mp3, self.directory_10, self.parent, self.flac, self.directory_2]

    def labels(self, **kwargs):
        return [entry.label for entry in sort_folder_entries(self.entries, **kwargs)]

    def test_name_sort_keeps_parent_directories_and_files_grouped(self):
        self.assertEqual(
            self.labels(),
            ["[..] Pasta acima", "Album 2", "Álbum 10", "Faixa 10.flac", "Faixa 2.mp3"],
        )

    def test_descending_reverses_each_group_but_keeps_parent_at_the_top(self):
        self.assertEqual(
            self.labels(descending=True),
            ["[..] Pasta acima", "Álbum 10", "Album 2", "Faixa 2.mp3", "Faixa 10.flac"],
        )

    def test_metadata_sort_options(self):
        self.assertEqual(
            self.labels(sort_by=FOLDER_SORT_MODIFIED)[1:],
            ["Album 2", "Álbum 10", "Faixa 10.flac", "Faixa 2.mp3"],
        )
        self.assertEqual(
            self.labels(sort_by=FOLDER_SORT_CREATED)[1:],
            ["Álbum 10", "Album 2", "Faixa 10.flac", "Faixa 2.mp3"],
        )
        self.assertEqual(
            self.labels(sort_by=FOLDER_SORT_TYPE)[3:],
            ["Faixa 10.flac", "Faixa 2.mp3"],
        )
        self.assertEqual(
            self.labels(sort_by=FOLDER_SORT_SIZE)[3:],
            ["Faixa 2.mp3", "Faixa 10.flac"],
        )

    def test_folder_scan_collects_file_metadata_and_applies_size_sort(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = pathlib.Path(temp_dir)
            (folder / "maior.mp3").write_bytes(b"12345")
            (folder / "menor.flac").write_bytes(b"1")

            entries, media_files = scan_folder_contents(folder, sort_by=FOLDER_SORT_SIZE)

            file_entries = [entry for entry in entries if entry.is_file]
            self.assertEqual([entry.label for entry in file_entries], ["menor.flac", "maior.mp3"])
            self.assertEqual([entry.size for entry in file_entries], [1, 5])
            self.assertEqual([pathlib.Path(path).name for path in media_files], ["menor.flac", "maior.mp3"])


class FolderSortStateTests(unittest.TestCase):
    def test_sort_preference_survives_session_round_trip(self):
        state = PlaylistState(title="Pasta", tab_type="folder")
        state.folder_sort_by = FOLDER_SORT_MODIFIED
        state.folder_sort_descending = True

        restored = PlaylistState.from_dict(state.to_dict())

        self.assertEqual(restored.folder_sort_by, FOLDER_SORT_MODIFIED)
        self.assertTrue(restored.folder_sort_descending)

    def test_reordering_preserves_current_media_and_shuffle_paths(self):
        state = PlaylistState(title="Pasta", tab_type="folder")
        state.set_items(["a.mp3", "b.mp3", "c.mp3"])
        state.select_index(1)
        state.shuffle_enabled = True
        state.playback_order = [1, 2, 0]
        state.playback_order_position = 0

        state.reorder_items(["c.mp3", "b.mp3", "a.mp3"])

        self.assertEqual(state.current_media_path, "b.mp3")
        self.assertEqual(state.current_index, 1)
        self.assertEqual(
            [state.items[index] for index in state.playback_order],
            ["b.mp3", "c.mp3", "a.mp3"],
        )


if __name__ == "__main__":
    unittest.main()
