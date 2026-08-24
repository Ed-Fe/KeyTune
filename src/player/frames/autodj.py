"""Lifecycle integration for the shared local/online AutoDJ analyzer."""

from pathlib import Path

from ..autodj import AutoDJService
from ..session import get_app_storage_dir


class FrameAutoDJMixin:
    def _initialize_autodj_service(self):
        self.autodj_service = AutoDJService(
            Path(get_app_storage_dir()) / "autodj-analysis.db",
            remote_resolver=lambda media_path: self._get_youtube_music_service().resolve_stream_playback(media_path),
        )

    def _shutdown_autodj_service(self):
        self.autodj_service = None
