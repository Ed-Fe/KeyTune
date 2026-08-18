"""Indexação de pastas e playlists na biblioteca inteligente.

A varredura roda na thread do serviço; aqui só disparamos o pedido e narramos o
resultado. Abrir uma pasta ou uma playlist também registra seus itens, para que
a busca global encontre o que o usuário realmente usa sem exigir configuração.
"""

import os

import wx

from ...i18n import _, ngettext


class SmartLibraryIndexingMixin:
    def _register_media_paths_in_library(self, media_paths, labels=None):
        """Registra em segundo plano os itens abertos em uma aba."""
        service = self._smart_library()
        if service is None:
            return False

        normalized_paths = [str(path or "").strip() for path in (media_paths or [])]
        normalized_paths = [path for path in normalized_paths if path]
        if not normalized_paths:
            return False

        normalized_labels = list(labels or [])
        entries = []
        for index, media_path in enumerate(normalized_paths):
            label = normalized_labels[index] if index < len(normalized_labels) else ""
            entries.append((media_path, label))

        return service.register_media_batch(entries)

    def _remember_indexed_folder(self, folder_path):
        normalized_path = str(folder_path or "").strip()
        if not normalized_path:
            return

        normalized_path = os.path.abspath(os.path.normpath(normalized_path))
        folder_key = os.path.normcase(normalized_path)
        existing = [
            path
            for path in getattr(self.settings, "smart_library_indexed_folders", [])
            if os.path.normcase(os.path.abspath(os.path.normpath(str(path or "")))) != folder_key
        ]
        self.settings.smart_library_indexed_folders = [normalized_path] + existing
        self._save_settings()

    def _index_folder_in_library(self, folder_path, *, announce=True, remember=True):
        service = self._smart_library()
        if service is None:
            if announce:
                self._announce_smart_library_unavailable()
            return False

        normalized_path = str(folder_path or "").strip()
        if not normalized_path or not os.path.isdir(normalized_path):
            if announce:
                self._announce(_("Pasta indisponível para indexar."))
            return False

        if remember:
            self._remember_indexed_folder(normalized_path)

        self._smart_library_indexing = True
        if announce:
            self._announce(
                _("Indexando {name} na biblioteca. Isso continua em segundo plano.").format(
                    name=os.path.basename(normalized_path.rstrip("\\/")) or normalized_path
                )
            )

        started = service.index_folder(
            normalized_path,
            recursive=True,
            on_finished=lambda summary: self._finish_library_indexing(summary, announce),
        )
        if not started:
            self._smart_library_indexing = False
            if announce:
                self._announce(_("Não foi possível iniciar a indexação."))
        return started

    def _finish_library_indexing(self, summary, announce=True):
        self._smart_library_indexing = False
        if not announce:
            return

        if summary is None or summary.failed:
            self._announce(_("A indexação não pôde ser concluída."))
            return

        message = ngettext(
            "Indexação concluída: {count} mídia adicionada à biblioteca.",
            "Indexação concluída: {count} mídias adicionadas à biblioteca.",
            summary.indexed_files,
        ).format(count=summary.indexed_files)
        self._announce(message)
        if hasattr(self, "_set_status_message"):
            self._set_status_message(message)

    def _auto_index_opened_folder(self, folder_path):
        """Indexa uma pasta recém-aberta quando a preferência permite."""
        if not getattr(self.settings, "smart_library_index_opened_folders", True):
            return False
        if self._smart_library() is None:
            return False

        return self._index_folder_in_library(folder_path, announce=False, remember=True)

    def _prompt_index_folder(self):
        service = self._smart_library()
        if service is None:
            self._announce_smart_library_unavailable()
            return

        default_directory = ""
        if hasattr(self, "_default_dialog_directory"):
            default_directory = self._default_dialog_directory()

        with wx.DirDialog(
            self,
            _("Escolha uma pasta para indexar na biblioteca"),
            defaultPath=default_directory,
            style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            selected_path = dialog.GetPath()

        self._index_folder_in_library(selected_path)

    def _reindex_known_folders(self):
        service = self._smart_library()
        if service is None:
            self._announce_smart_library_unavailable()
            return

        folders = [
            path
            for path in getattr(self.settings, "smart_library_indexed_folders", [])
            if os.path.isdir(str(path or ""))
        ]
        if not folders:
            self._announce(_("Nenhuma pasta indexada ainda. Use Biblioteca, Indexar pasta."))
            return

        service.forget_missing_media()
        for folder_path in folders:
            self._index_folder_in_library(folder_path, announce=False, remember=False)

        self._announce(
            ngettext(
                "Atualizando {count} pasta indexada em segundo plano.",
                "Atualizando {count} pastas indexadas em segundo plano.",
                len(folders),
            ).format(count=len(folders))
        )

    def _clear_library_index(self):
        service = self._smart_library()
        if service is None:
            self._announce_smart_library_unavailable()
            return

        with wx.MessageDialog(
            self,
            _(
                "Isso apaga o índice, os favoritos, as avaliações, o histórico e as posições de retomada. Continuar?"
            ),
            _("Limpar biblioteca"),
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
        ) as confirmation:
            if confirmation.ShowModal() != wx.ID_YES:
                return

        if not service.clear_everything():
            self._announce(_("Não foi possível limpar a biblioteca."))
            return

        self.settings.smart_library_indexed_folders = []
        self._save_settings()
        self._announce(_("Biblioteca limpa."))

    def _announce_library_statistics(self):
        if self._smart_library() is None:
            self._announce_smart_library_unavailable()
            return

        summary = self._smart_library_summary_text()
        self._announce(summary)
        if hasattr(self, "_set_status_message"):
            self._set_status_message(summary)

    def on_index_library_folder(self, _event):
        self._prompt_index_folder()

    def on_refresh_library_index(self, _event):
        self._reindex_known_folders()

    def on_clear_library_index(self, _event):
        self._clear_library_index()

    def on_library_statistics(self, _event):
        self._announce_library_statistics()
