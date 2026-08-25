from dataclasses import dataclass


FOLDER_ENTRY_PARENT = "parent"
FOLDER_ENTRY_DIRECTORY = "directory"
FOLDER_ENTRY_FILE = "file"

@dataclass(frozen=True)
class FolderBrowserEntry:
    path: str
    label: str
    entry_type: str
    modified_time: float = 0.0
    created_time: float = 0.0
    size: int = 0
    extension: str = ""

    @property
    def is_parent(self):
        return self.entry_type == FOLDER_ENTRY_PARENT

    @property
    def is_directory(self):
        return self.entry_type in {FOLDER_ENTRY_PARENT, FOLDER_ENTRY_DIRECTORY}

    @property
    def is_file(self):
        return self.entry_type == FOLDER_ENTRY_FILE
