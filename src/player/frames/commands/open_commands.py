import os

import wx

from ...constants import PLAYLIST_WILDCARD
from ...library import (
    build_supported_media_wildcard,
    collect_media_paths,
    is_playlist_source,
    is_remote_media_path,
    is_supported_media,
    playlist_display_name,
    save_playlist,
)
from ..background import run_in_background
from ...i18n import _
from ...playlists import ScreenTabState
from ...youtube_music import extract_playlist_id_from_text


class OpenCommandsMixin:
    def _split_selected_files(self, paths):
        """Separa mídias e playlists existentes; consulta o disco, então roda fora da interface."""
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
        self.on_toggle_explorer()

    def on_add_files_without_playing(self, _event=None):
        with wx.FileDialog(
            self,
            _("Escolha os arquivos para abrir sem tocar"),
            defaultDir=self._default_dialog_directory(),
            wildcard=build_supported_media_wildcard(include_playlists=False),
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE,
        ) as dialog:
            if dialog.ShowModal() == wx.ID_CANCEL:
                return
            paths = dialog.GetPaths()

        def finish(split):
            media_paths, _playlist_paths = split
            if not media_paths:
                self._announce(_("Nenhuma mídia compatível para adicionar."))
                return
            self._add_media_paths_without_playing(media_paths, verified=True)

        run_in_background(self, lambda: self._split_selected_files(paths), finish)

    def _selected_item_paths_to_copy(self):
        if isinstance(self._get_tab_state(), ScreenTabState):
            return None

        browser = self._get_browser_panel()
        selected_items = browser.get_selected_item_paths() if browser else []
        if not selected_items:
            self._announce(_("Nenhum item selecionado para copiar."))
            return None
        return selected_items

    def on_copy_current_item_path(self, _event):
        selected_items = self._selected_item_paths_to_copy()
        if not selected_items:
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

    def on_copy_current_item(self, _event=None):
        selected_items = self._selected_item_paths_to_copy()
        if not selected_items:
            return

        if not self._copy_items_to_clipboard(selected_items):
            self._announce(_("Não foi possível acessar a área de transferência."))
            return

        if len(selected_items) == 1:
            self._announce(_("Item copiado."))
        else:
            self._announce(_("{count} itens copiados.").format(count=len(selected_items)))

    def on_copy_playing_media_path(self, _event=None):
        state = self._get_active_playlist_state()
        media_path = str(getattr(state, "current_media_path", "") or "").strip() if state else ""
        if not media_path:
            self._announce(_("Nenhuma mídia está sendo reproduzida no momento."))
            return False

        if not self._copy_text_to_clipboard(media_path):
            self._announce(_("Não foi possível acessar a área de transferência."))
            return False

        if is_remote_media_path(media_path):
            self._announce(_("Link da mídia atual copiado."))
        else:
            self._announce(_("Caminho da mídia atual copiado."))
        return True

    def on_paste_open_from_clipboard(self, _event):
        self._open_clipboard_sources(self._read_clipboard_sources())

    def on_paste_without_playing(self, _event=None):
        self._open_clipboard_sources(self._read_clipboard_sources(), play=False)

    def _copy_text_to_clipboard(self, text):
        if not text or not wx.TheClipboard.Open():
            return False
        try:
            wx.TheClipboard.SetData(wx.TextDataObject(text))
        finally:
            wx.TheClipboard.Close()
        return True

    def _copy_files_to_clipboard(self, paths):
        normalized_paths = [str(path or "").strip() for path in paths]
        normalized_paths = [path for path in normalized_paths if path]
        if not normalized_paths:
            return False

        data = wx.FileDataObject()
        for path in normalized_paths:
            data.AddFile(path)

        if not wx.TheClipboard.Open():
            return False
        try:
            return bool(wx.TheClipboard.SetData(data))
        finally:
            wx.TheClipboard.Close()

    def _copy_items_to_clipboard(self, paths):
        """Copia os itens como texto e, quando são arquivos, também como arquivos.

        Assim a mesma cópia serve para colar no KeyTune, em um campo de texto ou
        no Explorador de Arquivos do Windows.
        """
        normalized_paths = [str(path or "").strip() for path in paths]
        normalized_paths = [path for path in normalized_paths if path]
        if not normalized_paths:
            return False

        data = wx.DataObjectComposite()
        data.Add(wx.TextDataObject("\n".join(normalized_paths)), True)
        local_files = [path for path in normalized_paths if not is_remote_media_path(path) and os.path.exists(path)]
        if local_files:
            file_data = wx.FileDataObject()
            for path in local_files:
                file_data.AddFile(path)
            data.Add(file_data)

        if not wx.TheClipboard.Open():
            return False
        try:
            return bool(wx.TheClipboard.SetData(data))
        finally:
            wx.TheClipboard.Close()

    def _read_clipboard_sources(self):
        """Arquivos ou pastas copiados (como no Explorador do Windows) ou linhas de texto."""
        if not wx.TheClipboard.Open():
            return []
        try:
            file_data = wx.FileDataObject()
            if wx.TheClipboard.IsSupported(wx.DataFormat(wx.DF_FILENAME)) and wx.TheClipboard.GetData(file_data):
                filenames = [str(path) for path in file_data.GetFilenames() if path]
                if filenames:
                    return filenames

            text_data = wx.TextDataObject()
            if not wx.TheClipboard.GetData(text_data):
                return []
            return self._clipboard_text_sources(text_data.GetText())
        finally:
            wx.TheClipboard.Close()

    def _clipboard_text_sources(self, text):
        normalized_lines = [
            str(line or "").strip().strip('"').strip("'")
            for line in str(text or "").replace("\r", "\n").split("\n")
        ]
        return [line for line in normalized_lines if line]

    def _open_from_clipboard_text(self, text):
        self._open_clipboard_sources(self._clipboard_text_sources(text))

    def _open_remote_clipboard_playlist(self, source):
        """Abre *source* se for um link de playlist; devolve se a colagem terminou aqui."""
        youtube_music_playlist_id = extract_playlist_id_from_text(source)
        open_youtube_music_playlist = getattr(self, "_load_youtube_music_playlist_by_id", None)
        if youtube_music_playlist_id and callable(open_youtube_music_playlist):
            open_youtube_music_playlist(
                youtube_music_playlist_id,
                fallback_title=_("Playlist do YouTube Music"),
            )
            return True
        if not is_playlist_source(source):
            return False
        self._open_clipboard_playlist(source)
        return True

    def _open_clipboard_playlist(self, playlist_source):
        if not self._open_playlist_source(playlist_source):
            self._announce(_("Não foi possível abrir a playlist da área de transferência."))

    def _classify_clipboard_sources(self, sources):
        """Diz o que é cada item colado: ``(itens, erro)``, com itens ``(caminho, tipo)``.

        Consulta o disco para os caminhos locais, então roda fora da interface.
        """
        mixed_playlist_message = _(
            "A área de transferência contém playlists misturadas com múltiplos itens. Use apenas mídias ou links."
        )
        pasted = []
        for source in sources:
            if is_remote_media_path(source):
                if is_playlist_source(source):
                    return [], mixed_playlist_message
                pasted.append((source, "media"))
                continue

            normalized_local = self._normalize_path(source)
            if normalized_local and os.path.isdir(normalized_local):
                pasted.append((normalized_local, "folder"))
                continue

            if normalized_local and os.path.isfile(normalized_local):
                if not is_playlist_source(normalized_local):
                    pasted.append((normalized_local, "media"))
                    continue
                if len(sources) > 1:
                    return [], mixed_playlist_message
                pasted.append((normalized_local, "playlist"))
                continue

            if len(sources) == 1:
                return [], _("Conteúdo da área de transferência não suportado.")
            return [], _("A área de transferência contém itens não suportados para colagem em lote.")
        return pasted, ""

    def _open_clipboard_sources(self, sources, *, play=True):
        """Abre o que foi colado: links, arquivos e pastas (com as subpastas)."""
        sources = [str(source or "").strip() for source in sources or ()]
        sources = [source for source in sources if source]
        if not sources:
            self._announce(_("A área de transferência está vazia."))
            return

        all_remote = all(is_remote_media_path(source) for source in sources)
        if len(sources) == 1 and all_remote and self._open_remote_clipboard_playlist(sources[0]):
            return

        def finish(classified):
            self._open_classified_clipboard_sources(*classified, play=play)

        if all_remote:
            finish(self._classify_clipboard_sources(sources))
        else:
            run_in_background(self, lambda: self._classify_clipboard_sources(sources), finish)

    def _open_classified_clipboard_sources(self, pasted, error_message, *, play):
        if error_message:
            self._announce(error_message)
            return
        if pasted[0][1] == "playlist":
            self._open_clipboard_playlist(pasted[0][0])
            return

        def expand():
            media_sources = []
            for path, kind in pasted:
                media_sources.extend(collect_media_paths([path]) if kind == "folder" else [path])
            return media_sources

        def finish(media_sources):
            self._finish_clipboard_paste(media_sources, play=play)

        if any(kind == "folder" for _path, kind in pasted):
            self._announce(_("Lendo as pastas coladas..."))
            run_in_background(self, expand, finish)
        else:
            finish(expand())

    def _finish_clipboard_paste(self, media_sources, *, play):
        if not media_sources:
            self._announce(_("Nenhuma mídia compatível foi encontrada no conteúdo colado."))
            return

        if not play:
            self._add_media_paths_without_playing(media_sources, verified=True)
        elif not self._play_media_paths_in_current_playlist(media_sources):
            self._announce(_("Não foi possível abrir a mídia da área de transferência."))

    def _play_media_paths_in_current_playlist(self, paths):
        """Põe *paths* na playlist atual e toca o primeiro novo.

        Abrir (Ctrl+O), colar (Ctrl+V) e o Enter do explorador chegam aqui, para
        que os três se comportem do mesmo jeito.
        """
        state = self._get_playlist_state()
        if state is not None and getattr(state, "autodj_session", False):
            self._add_media_to_autodj_session(paths)
            return True
        if not self._open_external_media_paths(paths, verified=True):
            return False
        # Não é uma abertura avulsa vinda de fora: a playlist segue adiante.
        self._suppress_next_auto_advance = False
        return True

    def _open_selected_files(self, paths, dialog_title=None):
        if dialog_title is None:
            dialog_title = _("Abrir arquivos")
        run_in_background(
            self,
            lambda: self._split_selected_files(paths),
            lambda split: self._open_split_selected_files(*split, dialog_title),
        )

    def _open_split_selected_files(self, media_paths, playlist_paths, dialog_title):
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
            return self._play_media_paths_in_current_playlist(media_paths)

        wx.MessageBox(
            _("Nenhum arquivo de mídia ou playlist compatível foi selecionado."),
            dialog_title,
            wx.OK | wx.ICON_WARNING,
            self,
        )
        return False

    def _open_external_files(self, paths):
        run_in_background(
            self,
            lambda: self._split_selected_files(paths),
            lambda split: self._open_split_external_files(*split),
        )

    def _open_split_external_files(self, media_paths, playlist_paths):
        if playlist_paths and media_paths:
            self._announce(_("Arquivos externos mistos não foram abertos. Use apenas mídias ou uma playlist."))
            return False

        if len(playlist_paths) > 1:
            self._announce(_("A abertura externa aceita apenas uma playlist por vez."))
            return False

        if media_paths:
            return self._open_external_media_paths(media_paths, verified=True)

        if playlist_paths:
            return self._open_playlist_source(playlist_paths[0])

        self._announce(_("Nenhum arquivo compatível foi recebido do Explorador."))
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
            # Um arquivo recente entra como qualquer arquivo aberto: na playlist atual, tocando.
            is_available = is_remote_media_path(path) or os.path.isfile(path)
            if is_available and self._play_media_paths_in_current_playlist([path]):
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
