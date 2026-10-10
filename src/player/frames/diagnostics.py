"""Diagnóstico pela janela: a pedido em Ajuda e sozinho quando o player não inicia."""

from ..diagnostics import run_diagnostics, summarize
from ..diagnostics.dialog import show_diagnostics_report, show_player_startup_failure
from ..i18n import _
from ..log import get_logger
from .background import run_in_background

_logger = get_logger(__name__)


class FrameDiagnosticsMixin:
    def on_run_diagnostics(self, _event):
        if getattr(self, "_diagnostics_running", False):
            self._announce(_("O diagnóstico já está em andamento."))
            return
        self._diagnostics_running = True
        self._announce(_("Executando o diagnóstico..."))
        youtube_service = self._get_youtube_music_service()
        youtubejs_enabled = bool(getattr(self.settings, "youtube_music_use_youtubejs", False))
        run_in_background(
            self,
            lambda: run_diagnostics(youtube_service=youtube_service, youtubejs_enabled=youtubejs_enabled),
            self._on_diagnostics_finished,
        )

    def _on_diagnostics_finished(self, results):
        self._diagnostics_running = False
        self._announce(summarize(results))
        show_diagnostics_report(self, results)

    def _handle_player_startup_failure(self, error):
        """O MPV não iniciou: diz por quê e fecha, porque nada na janela funciona sem ele."""
        _logger.error("Playback backend could not be created: %s", error, exc_info=error)
        self._announce(_("O player não iniciou."))
        show_player_startup_failure(self, error)
        self.Destroy()
