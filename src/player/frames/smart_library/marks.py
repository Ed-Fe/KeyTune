"""Marcadores de favorito e avaliação exibidos na lista de itens.

Sem isto, favorito e avaliação só existiriam sob demanda: quem percorre uma
playlist com leitor de tela não teria como distinguir uma faixa de cinco
estrelas de uma sem avaliação. O sufixo entra apenas na exibição — a busca
(Ctrl+F), a sessão salva e os rótulos das abas continuam vendo o texto puro.

A consulta ao banco é cara demais para rodar a cada atualização do navegador
(que acontece a cada troca de faixa), então o resultado fica em cache e só é
recalculado quando os itens da aba mudam ou quando um marcador é alterado.
"""

from ...i18n import _, ngettext
from ...smart_library import media_path_key


class SmartLibraryMarksMixin:
    def _initialize_library_marks_state(self):
        self._library_marks_signature = None
        self._library_marks_generation = 0

    def _invalidate_library_marks(self):
        """Força o recálculo dos marcadores na próxima atualização da lista."""
        self._library_marks_generation = getattr(self, "_library_marks_generation", 0) + 1
        self._library_marks_signature = None

    def _format_library_marks(self, record):
        if record is None:
            return ""

        parts = []
        if record.favorite:
            parts.append(_("favorito"))
        if record.rating > 0:
            parts.append(
                ngettext("{count} estrela", "{count} estrelas", record.rating).format(count=record.rating)
            )
        return ", ".join(parts)

    def _library_marked_paths_for_state(self, state):
        """Caminhos visíveis na aba, sejam itens de playlist ou de pasta."""
        if state is None:
            return []

        if getattr(state, "is_folder_tab", False):
            return [
                entry.path
                for entry in getattr(state, "folder_entries", [])
                if getattr(entry, "is_file", False) and getattr(entry, "path", "")
            ]

        return list(getattr(state, "items", []))

    def _library_marks_state_signature(self, state):
        if state is None:
            return None

        if getattr(state, "is_folder_tab", False):
            revision = getattr(state, "folder_entries_revision", 0)
        else:
            revision = getattr(state, "items_revision", 0)

        return (id(state), revision, getattr(self, "_library_marks_generation", 0))

    def _refresh_library_marks(self, browser=None, state=None):
        """Recalcula e aplica os marcadores da aba atual, se algo mudou."""
        if browser is None:
            browser = self._get_browser_panel()
        if browser is None or not hasattr(browser, "set_library_marks"):
            return False

        if state is None:
            state = self._get_playlist_state()

        service = self._smart_library()
        if service is None:
            # Serviço desligado: limpa os marcadores uma vez e não volta a
            # consultar até ele ser reativado.
            if self._library_marks_signature != "unavailable":
                self._library_marks_signature = "unavailable"
                browser.set_library_marks({})
            return False

        signature = self._library_marks_state_signature(state)
        if signature is None:
            return False
        if signature == self._library_marks_signature:
            return False

        self._library_marks_signature = signature

        media_paths = self._library_marked_paths_for_state(state)
        if not media_paths:
            browser.set_library_marks({})
            return True

        records_by_key = service.get_records(media_paths)
        marks_by_path = {}
        for media_path in media_paths:
            record = records_by_key.get(media_path_key(media_path))
            marks = self._format_library_marks(record)
            if marks:
                marks_by_path[media_path] = marks

        browser.set_library_marks(marks_by_path)
        return True
