"""Criação, desligamento e estado compartilhado da biblioteca inteligente.

O serviço é opcional: se a preferência estiver desligada ou o banco não puder
ser aberto, `_smart_library()` devolve None e todos os comandos avisam o
usuário em vez de falhar. A reprodução nunca depende dele.
"""

import os

import wx

from ...i18n import _
from ...library import is_remote_media_path
from ...smart_library import (
    SOURCE_FOLDER,
    SOURCE_LOCAL,
    SOURCE_REMOTE,
    SOURCE_YOUTUBE_MUSIC,
    SmartLibraryService,
)


class SmartLibraryLifecycleMixin:
    def _initialize_smart_library_state(self):
        self._smart_library_service = None
        self._smart_library_search_query = ""
        self._smart_library_playback_tracking = {}
        self._smart_library_next_resume_save_ms = 0
        self._smart_library_indexing = False
        self._initialize_library_marks_state()
        self._initialize_smart_playlist_state()

    def _create_smart_library_service(self):
        """Abre o serviço quando a preferência permite. Idempotente."""
        if getattr(self, "_smart_library_service", None) is not None:
            return self._smart_library_service

        if not getattr(self.settings, "smart_library_enabled", True):
            return None

        service = SmartLibraryService(dispatch=wx.CallAfter)
        if not service.is_available:
            service.close()
            return None

        self._smart_library_service = service
        return service

    def _smart_library(self):
        return getattr(self, "_smart_library_service", None)

    def _begin_smart_library_shutdown(self):
        service = self._smart_library()
        if service is not None:
            service.begin_shutdown()

    def _finish_smart_library_shutdown(self):
        service = self._smart_library()
        if service is None:
            return
        service.finish_shutdown()
        self._smart_library_service = None

    def _handle_smart_library_preferences_change(self, previous_settings):
        """Liga ou desliga o serviço quando a preferência muda."""
        was_enabled = bool(getattr(previous_settings, "smart_library_enabled", True))
        is_enabled = bool(getattr(self.settings, "smart_library_enabled", True))
        if was_enabled == is_enabled:
            return

        if is_enabled:
            if self._create_smart_library_service() is not None:
                self._announce(_("Biblioteca inteligente ativada."))
            else:
                self._announce(_("Não foi possível ativar a biblioteca inteligente."))
            return

        self._begin_smart_library_shutdown()
        self._finish_smart_library_shutdown()
        self._announce(_("Biblioteca inteligente desativada."))

    def _announce_smart_library_unavailable(self):
        if not getattr(self.settings, "smart_library_enabled", True):
            self._announce(
                _("A biblioteca inteligente está desligada. Ative em Preferências, aba Biblioteca.")
            )
            return
        self._announce(_("A biblioteca inteligente não está disponível agora."))

    # ------------------------------------------------------------------
    # Ajuda compartilhada pelos outros sub-mixins
    # ------------------------------------------------------------------
    def _smart_library_media_source(self, media_path):
        normalized_path = str(media_path or "").strip()
        if not normalized_path:
            return SOURCE_LOCAL

        if is_remote_media_path(normalized_path):
            if "youtube" in normalized_path.casefold():
                return SOURCE_YOUTUBE_MUSIC
            return SOURCE_REMOTE

        state = self._get_active_playlist_state()
        if state is not None and getattr(state, "is_folder_tab", False):
            return SOURCE_FOLDER

        return SOURCE_LOCAL

    def _smart_library_selected_media_paths(self):
        """Itens da lista ou, se nada estiver selecionado, a mídia em reprodução."""
        browser = self._get_browser_panel()
        paths = list(browser.get_selected_item_paths()) if browser is not None else []
        if paths:
            return paths

        state = self._get_active_playlist_state()
        current_media_path = getattr(state, "current_media_path", None) if state else None
        return [current_media_path] if current_media_path else []

    def _smart_library_label_for(self, media_path):
        label_provider = getattr(self, "_media_label", None)
        if callable(label_provider):
            return label_provider(media_path)
        normalized_path = str(media_path or "").rstrip("\\/")
        return os.path.basename(normalized_path) or normalized_path

    def _smart_library_summary_text(self):
        service = self._smart_library()
        if service is None:
            return _("A biblioteca inteligente não está disponível agora.")

        statistics = service.statistics()
        return _(
            "{media} mídias indexadas em {folders} pastas, {favorites} favoritas, "
            "{history} reproduções no histórico."
        ).format(
            media=statistics["media"],
            folders=statistics["folders"],
            favorites=statistics["favorites"],
            history=statistics["history"],
        )
