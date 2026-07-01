import os

import wx

from ...constants import PLAYLIST_WILDCARD
from ...library import (
    OPEN_MODE_FOLDER_BROWSER,
    OPEN_MODE_PLAYLIST,
    OPEN_SOURCE_DIALOG_TITLE,
    OpenSourceDialog,
    build_supported_media_wildcard,
    is_playlist_source,
    is_remote_media_path,
    is_supported_media,
    playlist_display_name,
    save_playlist,
)
from ...i18n import _
from ...playlists import ScreenTabState


class OpenCommandsMixin:
    def _split_selected_files(self, paths):
        media_paths = []
        playlist_paths = []

        for path in paths:
            normalized_path = self._normalize_path(path)
            if not normalized_path or not os.path.isfile(normalized_path):
                continue

            if is_playlist_source(normalized_path):
                playlist_paths.append(normalized_path)
                continue

            if is_supported_media(normalized_path):
                media_paths.append(normalized_path)

        return media_paths, playlist_paths

    def on_open(self, _event):
        with wx.FileDialog(
            self,
            _("Escolha um ou mais arquivos de mídia ou uma playlist"),
            defaultDir=self._default_dialog_directory(),
            wildcard=build_supported_media_wildcard(include_playlists=True),
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE,
        ) as dialog:
            if dialog.ShowModal() == wx.ID_CANCEL:
                return
            paths = dialog.GetPaths()

        if not paths:
            return

        self._open_selected_files(paths, dialog_title=_("Abrir arquivos"))

    def on_open_folder(self, _event):
        with wx.DirDialog(
            self,
            _("Escolha uma pasta para navegar"),
            defaultPath=self._default_dialog_directory(),
            style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST,
        ) as dialog:
            if dialog.ShowModal() == wx.ID_CANCEL:
                return
            folder_path = dialog.GetPath()

        self._open_folder_path(folder_path)

    def on_open_source(self, _event):
        self._show_open_source_dialog(initial_mode=OPEN_MODE_PLAYLIST)

    def on_copy_current_item_path(self, _event):
        if isinstance(self._get_tab_state(), ScreenTabState):
            return

        browser = self._get_browser_panel()
        selected_items = browser.get_selected_item_paths() if browser else []
        if not selected_items:
            self._announce(_("Nenhum item selecionado para copiar."))
            return

        if not self._copy_text_to_clipboard("\n".join(selected_items)):
            self._announce(_("Não foi possível acessar a área de transferência."))
            return

        if len(selected_items) == 1 and is_remote_media_path(selected_items[0]):
            self._announce(_("Link copiado."))
        elif len(selected_items) == 1:
            self._announce(_("Caminho copiado."))
        else:
            self._announce(_("{count} itens copiados.").format(count=len(selected_items)))

    def on_paste_open_from_clipboard(self, _event):
        if isinstance(self._get_tab_state(), ScreenTabState):
            return

        text = self._read_text_from_clipboard()
        if not text:
            self._announce(_("A área de transferência está vazia."))
            return

        self._open_from_clipboard_text(text, force_new_playlist=False)

    def on_paste_open_from_clipboard_new_playlist(self, _event):
        if isinstance(self._get_tab_state(), ScreenTabState):
            return

        text = self._read_text_from_clipboard()
        if not text:
            self._announce(_("A área de transferência está vazia."))
            return

        self._open_from_clipboard_text(text, force_new_playlist=True)

    def _copy_text_to_clipboard(self, text):
        if not text or not wx.TheClipboard.Open():
            return False
        try:
            wx.TheClipboard.SetData(wx.TextDataObject(text))
        finally:
            wx.TheClipboard.Close()
        return True

    def _read_text_from_clipboard(self):
        if not wx.TheClipboard.Open():
            return ""
        try:
            data = wx.TextDataObject()
            if not wx.TheClipboard.GetData(data):
                return ""
            return (data.GetText() or "").strip()
        finally:
            wx.TheClipboard.Close()

    def _open_from_clipboard_text(self, text, *, force_new_playlist=False):
        normalized_lines = [
            str(line or "").strip().strip('"').strip("'")
            for line in str(text or "").replace("\r", "\n").split("\n")
        ]
        normalized_sources = [line for line in normalized_lines if line]
        if not normalized_sources:
            self._announce(_("A área de transferência está vazia."))
            return

        if len(normalized_sources) > 1:
            media_sources = []
            for source in normalized_sources:
                if is_remote_media_path(source):
                    if is_playlist_source(source):
                        self._announce(_("A área de transferência contém playlists misturadas com múltiplos itens. Use apenas mídias ou links."))
                        return
                    media_sources.append(source)
                    continue

                normalized_local = self._normalize_path(source)
                if normalized_local and os.path.isfile(normalized_local):
                    if is_playlist_source(normalized_local):
                        self._announce(_("A área de transferência contém playlists misturadas com múltiplos itens. Use apenas mídias ou links."))
                        return
                    media_sources.append(normalized_local)
                    continue

                self._announce(_("A área de transferência contém itens não suportados para colagem em lote."))
                return

            open_media = self._open_media_paths if force_new_playlist else self._open_external_media_paths
            if not open_media(media_sources):
                self._announce(_("Não foi possível abrir a mídia da área de transferência."))
            return

        normalized_source = normalized_sources[0]

        if is_remote_media_path(normalized_source):
            if is_playlist_source(normalized_source):
                if not self._open_playlist_source(normalized_source):
                    self._announce(_("Não foi possível abrir a playlist da área de transferência."))
                return

            open_media = self._open_media_paths if force_new_playlist else self._open_external_media_paths
            if not open_media([normalized_source]):
                self._announce(_("Não foi possível abrir a mídia da área de transferência."))
            return

        normalized_local = self._normalize_path(normalized_source)
        if normalized_local:
            if os.path.isdir(normalized_local):
                if not self._open_folder_path(normalized_local):
                    self._announce(_("Não foi possível abrir a pasta da área de transferência."))
                return

            if os.path.isfile(normalized_local):
                if is_playlist_source(normalized_local):
                    if not self._open_playlist_source(normalized_local):
                        self._announce(_("Não foi possível abrir a playlist da área de transferência."))
                    return

                open_media = self._open_media_paths if force_new_playlist else self._open_external_media_paths
                if not open_media([normalized_local]):
                    self._announce(_("Não foi possível abrir a mídia da área de transferência."))
                return

        self._announce(_("Conteúdo da área de transferência não suportado."))

    def _show_open_source_dialog(self, initial_source="", initial_mode=OPEN_MODE_PLAYLIST):
        source_value = initial_source
        open_mode = initial_mode

        while True:
            dialog = OpenSourceDialog(
                self,
                default_dir=self._default_dialog_directory(),
                initial_source=source_value,
                initial_mode=open_mode,
            )
            try:
                if dialog.ShowModal() == wx.ID_CANCEL:
                    return
                source_value = dialog.get_source()
                open_mode = dialog.get_open_mode()
            finally:
                dialog.Destroy()

            if self._open_source_from_dialog(source_value, open_mode):
                return

    def _open_selected_files(self, paths, dialog_title=None):
        if dialog_title is None:
            dialog_title = _("Abrir arquivos")
        media_paths, playlist_paths = self._split_selected_files(paths)

        if playlist_paths and media_paths:
            wx.MessageBox(
                _("Selecione uma única playlist ou apenas arquivos de mídia."),
                dialog_title,
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return False

        if len(playlist_paths) > 1:
            wx.MessageBox(
                _("Selecione apenas uma playlist por vez."),
                dialog_title,
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return False

        if playlist_paths:
            return self._open_playlist_source(playlist_paths[0])

        if media_paths:
            return self._open_media_paths(media_paths)

        wx.MessageBox(
            _("Nenhum arquivo de mídia ou playlist compatível foi selecionado."),
            dialog_title,
            wx.OK | wx.ICON_WARNING,
            self,
        )
        return False

    def _open_external_files(self, paths):
        media_paths, playlist_paths = self._split_selected_files(paths)

        if playlist_paths and media_paths:
            self._announce(_("Arquivos externos mistos não foram abertos. Use apenas mídias ou uma playlist."))
            return False

        if len(playlist_paths) > 1:
            self._announce(_("A abertura externa aceita apenas uma playlist por vez."))
            return False

        if media_paths:
            return self._open_external_media_paths(media_paths)

        if playlist_paths:
            return self._open_playlist_source(playlist_paths[0])

        self._announce(_("Nenhum arquivo compatível foi recebido do Explorador."))
        return False

    def _open_source_from_dialog(self, source_value, open_mode):
        normalized_source = str(source_value or "").strip()
        if not normalized_source:
            wx.MessageBox(
                _("Informe um caminho local, uma pasta ou um link de mídia."),
                OPEN_SOURCE_DIALOG_TITLE,
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return False

        normalized_local_source = ""
        if not is_remote_media_path(normalized_source):
            normalized_local_source = self._normalize_path(normalized_source)

        if open_mode == OPEN_MODE_FOLDER_BROWSER:
            if normalized_local_source and self._open_folder_path(normalized_local_source):
                return True

            wx.MessageBox(
                _("Para abrir no navegador, informe uma pasta local válida."),
                OPEN_SOURCE_DIALOG_TITLE,
                wx.OK | wx.ICON_WARNING,
                self,
            )
            return False

        if normalized_local_source and os.path.isdir(normalized_local_source):
            if self._open_folder_as_playlist(normalized_local_source):
                return True

            wx.MessageBox(
                _("Não foi possível abrir a pasta selecionada como playlist."),
                OPEN_SOURCE_DIALOG_TITLE,
                wx.OK | wx.ICON_ERROR,
                self,
            )
            return False

        if is_playlist_source(normalized_source):
            if self._open_playlist_source(normalized_source):
                return True

            wx.MessageBox(
                _("Não foi possível abrir a playlist ou link informado."),
                OPEN_SOURCE_DIALOG_TITLE,
                wx.OK | wx.ICON_ERROR,
                self,
            )
            return False

        if (normalized_local_source and os.path.isfile(normalized_local_source)) or is_remote_media_path(normalized_source):
            if self._open_media_paths([normalized_source if is_remote_media_path(normalized_source) else normalized_local_source]):
                return True

            wx.MessageBox(
                _("Não foi possível abrir a mídia informada."),
                OPEN_SOURCE_DIALOG_TITLE,
                wx.OK | wx.ICON_ERROR,
                self,
            )
            return False

        message = (
            _("Não foi possível interpretar o link informado como mídia ou playlist.")
            if is_remote_media_path(normalized_source)
            else _("Informe uma pasta local, um arquivo existente, uma playlist .m3u/.m3u8 ou um link de mídia.")
        )
        wx.MessageBox(message, OPEN_SOURCE_DIALOG_TITLE, wx.OK | wx.ICON_WARNING, self)
        return False

    def on_save_playlist(self, _event):
        state = self._get_playlist_state()
        if not state or not state.items:
            self._announce(_("A playlist atual está vazia."))
            return

        default_name = os.path.basename(state.source_path) if state.source_path else f"{state.title}.m3u8"
        default_dir = os.path.dirname(state.source_path) if state.source_path else self._default_dialog_directory()

        with wx.FileDialog(
            self,
            _("Salvar playlist"),
            wildcard=PLAYLIST_WILDCARD,
            defaultDir=default_dir,
            defaultFile=default_name,
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dialog:
            if dialog.ShowModal() == wx.ID_CANCEL:
                return
            playlist_path = dialog.GetPath()

        if not os.path.splitext(playlist_path)[1]:
            playlist_path += ".m3u8"

        save_playlist(playlist_path, state.items)
        self._remember_directory(playlist_path)
        state.source_path = playlist_path
        state.title = playlist_display_name(playlist_path)
        active_index = self._get_active_playlist_index()
        if active_index != wx.NOT_FOUND:
            self.notebook.SetPageText(active_index, state.title)
        self._update_title()
        self._refresh_playlist_browser()
        self._add_recent_path("recent_playlists", playlist_path)
        self._announce(_("Playlist salva: {title}.").format(title=state.title))
        if hasattr(self, "_set_status_message"):
            self._set_status_message(_("Playlist salva em {path}").format(path=playlist_path))

    def on_recent_menu_action(self, event):
        action = self._recent_menu_actions.get(event.GetId())
        if not action:
            event.Skip()
            return

        action_kind, attribute_name, path = action
        if action_kind == "clear":
            announcements = {
                "recent_media_files": _("Arquivos recentes limpos."),
                "recent_folders": _("Pastas recentes limpas."),
                "recent_playlists": _("Playlists recentes limpas."),
            }
            self._clear_recent_paths(attribute_name, announcements.get(attribute_name, _("Itens recentes limpos.")))
            return

        if path and attribute_name == "recent_media_files":
            if self._open_media_paths([path]):
                return
        elif path and attribute_name == "recent_folders":
            if self._open_folder_path(path):
                return
        elif path and attribute_name == "recent_playlists":
            if self._open_playlist_path(path):
                return

        if path:
            self._remove_recent_path(attribute_name, path)
        self._announce(_("O item recente selecionado não está mais disponível."))
