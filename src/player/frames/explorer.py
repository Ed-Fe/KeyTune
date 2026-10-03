"""Explorador de pastas da janela principal.

Fica ao lado das abas e alimenta a playlist ativa: navega-se pelas pastas e, de
lá, toca-se, adiciona-se à playlist ou à fila, converte-se ou copia-se o que
estiver selecionado. Substitui o antigo modo em que uma aba inteira virava o
navegador de uma pasta.
"""

import os
import subprocess
import sys

import wx

from ..convert.options import media_kind
from ..folder_sort import (
    FOLDER_SORT_CREATED,
    FOLDER_SORT_MODIFIED,
    FOLDER_SORT_NAME,
    FOLDER_SORT_SIZE,
    FOLDER_SORT_TYPE,
)
from ..i18n import _, ngettext
from .background import run_in_background
from ..library import (
    EXPLORER_ROOT,
    ExplorerState,
    PlaylistBrowserPanel,
    collect_media_paths,
    explorer_display_name,
    explorer_parent_path,
    is_supported_media,
    scan_explorer_folder,
)
from ..log import get_logger
from ..playlists import PlaylistState, ScreenTabState


_logger = get_logger(__name__)


class FrameExplorerMixin:
    _EXPLORER_SORT_LABELS = {
        FOLDER_SORT_NAME: _("Nome"),
        FOLDER_SORT_MODIFIED: _("Data de modificação"),
        FOLDER_SORT_CREATED: _("Data de criação"),
        FOLDER_SORT_TYPE: _("Tipo"),
        FOLDER_SORT_SIZE: _("Tamanho"),
    }

    # -- Painel ---------------------------------------------------------------

    def _create_explorer_panel(self, parent):
        self._explorer_state = ExplorerState()
        self._focus_before_explorer = None
        panel = PlaylistBrowserPanel(
            parent,
            on_activate_item=self.on_explorer_activate_item,
            on_remove_item=lambda _indexes: None,
            on_go_back=self.on_explorer_go_back,
            on_toggle_navigation_mode=self.on_explorer_leave,
            on_tab=self.on_explorer_tab,
            on_show_context_menu=self.on_explorer_show_context_menu,
            folder_hint=_(
                "Enter entra na pasta ou toca o arquivo. Shift+Enter adiciona sem tocar. "
                "Ctrl+Shift+F põe na fila. Backspace volta. Shift+F10 abre ações. Tab vai para a playlist."
            ),
        )
        panel.SetName(_("Explorador de pastas"))
        panel.items_list.SetName(_("Explorador de pastas"))
        panel.items_list.SetToolTip(_("Enter abre ou toca. Shift+Enter adiciona sem tocar. Shift+F10 abre as ações."))
        panel.header_label.SetName(_("Pasta atual do explorador"))
        # Ligado depois do painel, este tratador vê a tecla antes dele.
        panel.items_list.Bind(wx.EVT_CHAR_HOOK, self._on_explorer_list_char_hook)
        panel.Hide()
        self.explorer_panel = panel
        return panel

    def _explorer_visible(self):
        panel = getattr(self, "explorer_panel", None)
        return bool(panel is not None and panel.IsShown())

    def _explorer_has_focus(self):
        return self._explorer_visible() and self.explorer_panel.is_item_navigation_active()

    def _refresh_explorer_panel(self):
        if not self._explorer_visible():
            return

        state = self._explorer_state
        self.explorer_panel.update_folder(
            title=_("Explorador"),
            current_path=state.current_path or explorer_display_name(EXPLORER_ROOT),
            entries=state.entries,
            selected_path=state.selected_path,
            current_media_path=None,
            entries_revision=state.entries_revision,
            loading=state.is_loading,
            entry_index_map=state.entry_index_map,
        )

    def on_toggle_explorer(self, _event=None):
        if self._explorer_has_focus():
            self._hide_explorer()
            return
        self._show_explorer()

    def _show_explorer(self, folder_path=None, *, focus=True, quiet=False):
        panel = getattr(self, "explorer_panel", None)
        if panel is None:
            return False

        was_visible = panel.IsShown()
        if focus and not panel.is_item_navigation_active():
            focused_window = wx.Window.FindFocus()
            self._focus_before_explorer = focused_window if isinstance(focused_window, wx.Window) else None

        if not was_visible:
            panel.Show()
            panel.GetParent().Layout()

        state = self._explorer_state
        target_path = state.current_path if folder_path is None else folder_path
        if not was_visible or folder_path is not None or not state.entries:
            self._explorer_navigate(target_path, selected_path=state.selected_path, quiet=quiet)

        if focus:
            panel.focus_current_item()
        return True

    def _hide_explorer(self, announce=True):
        panel = getattr(self, "explorer_panel", None)
        if panel is None or not panel.IsShown():
            return

        had_focus = panel.is_item_navigation_active()
        panel.Hide()
        panel.GetParent().Layout()
        if had_focus:
            self._leave_explorer_focus()
        if announce:
            self._announce(_("Explorador de pastas fechado."))

    def _leave_explorer_focus(self):
        """Devolve o foco para onde ele estava antes de o explorador ser aberto."""
        target = getattr(self, "_focus_before_explorer", None)
        self._focus_before_explorer = None
        panel = getattr(self, "explorer_panel", None)
        if (
            isinstance(target, wx.Window)
            and bool(target)
            and not self._window_is_descendant_of(target, panel)
            and target.IsShownOnScreen()
            and target.IsEnabled()
        ):
            target.SetFocus()
            return

        if isinstance(self._get_tab_state(), PlaylistState):
            self._focus_item_navigation(announce=False)
        else:
            self.notebook.SetFocus()

    def _focus_explorer_if_visible(self):
        if not self._explorer_visible():
            return False
        self.explorer_panel.focus_current_item()
        return True

    # -- Navegação ------------------------------------------------------------

    def _explorer_navigate(self, folder_path, *, selected_path=None, quiet=False):
        """Carrega *folder_path* sem tocar no disco pela thread da interface."""
        state = self._explorer_state
        normalized_path = self._normalize_path(folder_path) if folder_path else EXPLORER_ROOT
        previous_path = state.current_path
        state.current_path = normalized_path
        state.selected_path = selected_path
        state.is_loading = True
        state.request_serial += 1
        request_serial = state.request_serial
        sort_by = state.sort_by
        descending = state.sort_descending
        self._refresh_explorer_panel()

        def scan():
            try:
                return scan_explorer_folder(normalized_path, sort_by=sort_by, descending=descending), None
            except OSError as exc:
                _logger.warning("OS error loading explorer folder %r: %s", normalized_path, exc)
                return [], exc

        run_in_background(
            self,
            scan,
            lambda result: self._finish_explorer_navigation(request_serial, *result, previous_path, quiet),
        )
        return True

    def _finish_explorer_navigation(self, request_serial, entries, error, previous_path, quiet):
        state = self._explorer_state
        if request_serial != state.request_serial or getattr(self, "explorer_panel", None) is None:
            return

        if error is None:
            state.is_loading = False
            state.set_entries(entries)
            self._refresh_explorer_panel()
            return

        if not quiet:
            if isinstance(error, FileNotFoundError):
                self._announce(_("A pasta não está mais disponível."))
            else:
                self._announce(_("Não foi possível carregar a pasta selecionada: {error}.").format(error=error))

        failed_path = state.current_path
        if not failed_path:
            state.is_loading = False
            state.set_entries([])
            self._refresh_explorer_panel()
            return
        # Volta para onde se estava; se era a própria pasta que sumiu, para a raiz.
        fallback_path = previous_path if previous_path != failed_path else EXPLORER_ROOT
        self._explorer_navigate(fallback_path, selected_path=failed_path, quiet=True)

    def on_explorer_go_back(self):
        state = self._explorer_state
        parent_path = explorer_parent_path(state.current_path)
        if parent_path is None:
            self._announce(_("Você já está na pasta raiz."))
            return
        self._explorer_navigate(parent_path, selected_path=state.current_path)

    def on_explorer_activate_item(self, item_index):
        entries = self._explorer_state.entries
        if not 0 <= item_index < len(entries):
            return

        entry = entries[item_index]
        if entry.is_parent:
            self.on_explorer_go_back()
        elif entry.is_directory:
            self._explorer_navigate(entry.path)
        else:
            self._explorer_play_paths([entry.path])

    def on_explorer_leave(self):
        self._leave_explorer_focus()

    def on_explorer_tab(self, *, backward=False):
        self._focus_before_explorer = None
        if backward:
            self._focus_player_controls(announce=True)
        elif isinstance(self._get_tab_state(), ScreenTabState):
            self.notebook.SetFocus()
        else:
            self._focus_item_navigation(announce=True)
        return True

    def _open_folder_path(self, folder_path):
        """Mostra *folder_path* no explorador (menu, recentes, diálogo de abrir)."""
        normalized_folder_path = self._normalize_path(folder_path)
        if not normalized_folder_path or not os.path.isdir(normalized_folder_path):
            return False

        self._remember_directory(normalized_folder_path)
        self._add_recent_path("recent_folders", normalized_folder_path)
        auto_index_folder = getattr(self, "_auto_index_opened_folder", None)
        if callable(auto_index_folder):
            auto_index_folder(normalized_folder_path)
        return self._show_explorer(normalized_folder_path)

    # -- Seleção e ações ------------------------------------------------------

    def _explorer_selected_paths(self):
        if not self._explorer_visible():
            return []
        return list(self.explorer_panel.get_selected_item_paths())

    def _explorer_path_is_folder(self, path):
        """Se *path* é pasta, pelo que a listagem já sabe, sem consultar o disco."""
        entry = self._explorer_state.entry_for(path)
        if entry is not None:
            return bool(entry.is_directory)
        return not is_supported_media(path)

    def _explorer_with_media(self, paths, action):
        """Chama *action* com as mídias de *paths*, lendo subpastas fora da interface."""
        if not paths:
            self._announce(_("Nenhum item selecionado no explorador."))
            return

        def deliver(media_paths):
            if not media_paths:
                self._announce(_("Nenhuma mídia compatível foi encontrada na seleção."))
                return
            action(media_paths)

        folders = [path for path in paths if self._explorer_path_is_folder(path)]
        if not folders:
            deliver(list(paths))
            return
        if any(explorer_parent_path(folder) == EXPLORER_ROOT for folder in folders):
            self._announce(_("Uma unidade inteira não pode ser adicionada de uma vez. Entre nela e escolha uma pasta."))
            return

        self._announce(_("Lendo as pastas selecionadas..."))
        run_in_background(self, lambda: collect_media_paths(paths), deliver)

    def _explorer_play_paths(self, paths):
        if self._block_sensitive_action_during_youtube_music("track-selection"):
            return

        self._explorer_with_media(paths, self._play_media_paths_in_current_playlist)

    def _explorer_add_paths(self, paths):
        self._explorer_with_media(
            paths,
            lambda media_paths: self._add_media_paths_without_playing(media_paths, verified=True),
        )

    def _explorer_enqueue_paths(self, paths):
        self._explorer_with_media(paths, self._enqueue_media_paths)

    def _explorer_open_paths_in_new_playlist(self, paths):
        self._explorer_with_media(paths, lambda media_paths: self._open_media_paths(media_paths, verified=True))

    def _explorer_convert_paths(self, paths):
        self._explorer_with_media(paths, self._convert_media_paths)

    def _explorer_copy_selection(self, *, as_text=False):
        paths = self._explorer_selected_paths()
        if not paths:
            self._announce(_("Nenhum item selecionado para copiar."))
            return

        copied = self._copy_text_to_clipboard("\n".join(paths)) if as_text else self._copy_files_to_clipboard(paths)
        if not copied:
            self._announce(_("Não foi possível acessar a área de transferência."))
        elif as_text:
            self._announce(
                ngettext("Caminho copiado.", "{count} caminhos copiados.", len(paths)).format(count=len(paths))
            )
        else:
            self._announce(ngettext("Item copiado.", "{count} itens copiados.", len(paths)).format(count=len(paths)))

    def _explorer_reveal_in_file_manager(self, path):
        try:
            if path == self._explorer_state.current_path:
                os.startfile(path)
            else:
                subprocess.Popen(["explorer", f"/select,{path}"])
        except OSError:
            self._announce(_("Não foi possível abrir o Explorador de Arquivos do Windows."))

    def _explorer_refresh(self):
        selected_paths = self._explorer_selected_paths()
        self._explorer_navigate(
            self._explorer_state.current_path,
            selected_path=selected_paths[0] if selected_paths else None,
        )

    def _explorer_apply_sort(self, sort_by, descending):
        state = self._explorer_state
        state.sort_by = sort_by
        state.sort_descending = bool(descending)
        selected_paths = self._explorer_selected_paths()
        self._explorer_navigate(
            state.current_path,
            selected_path=selected_paths[0] if selected_paths else None,
        )
        self._announce(
            _("Pasta classificada por {criterion}, em ordem {direction}.").format(
                criterion=self._EXPLORER_SORT_LABELS.get(sort_by, self._EXPLORER_SORT_LABELS[FOLDER_SORT_NAME]),
                direction=_("decrescente") if descending else _("crescente"),
            )
        )

    def _append_explorer_sort_menu(self, menu):
        state = self._explorer_state
        criterion_menu = wx.Menu()
        direction_menu = wx.Menu()

        for sort_by, label in self._EXPLORER_SORT_LABELS.items():
            item = criterion_menu.AppendRadioItem(wx.ID_ANY, label)
            item.Check(sort_by == state.sort_by)
            criterion_menu.Bind(
                wx.EVT_MENU,
                lambda _event, value=sort_by: self._explorer_apply_sort(value, state.sort_descending),
                id=item.GetId(),
            )

        for descending, label in ((False, _("Crescente")), (True, _("Decrescente"))):
            item = direction_menu.AppendRadioItem(wx.ID_ANY, label)
            item.Check(descending == state.sort_descending)
            direction_menu.Bind(
                wx.EVT_MENU,
                lambda _event, value=descending: self._explorer_apply_sort(state.sort_by, value),
                id=item.GetId(),
            )

        menu.AppendSubMenu(criterion_menu, _("Classificar por"))
        menu.AppendSubMenu(direction_menu, _("Ordem"))

    def on_show_explorer_sort_menu(self):
        if not self._explorer_state.current_path:
            self._announce(_("A lista de unidades não pode ser classificada."))
            return

        menu = wx.Menu()
        self._append_explorer_sort_menu(menu)
        try:
            self.explorer_panel.items_list.PopupMenu(menu)
        finally:
            menu.Destroy()

    def on_explorer_show_context_menu(self, _panel=None, anchor_window=None):
        state = self._explorer_state
        paths = self._explorer_selected_paths()
        folders = [path for path in paths if self._explorer_path_is_folder(path)]
        has_selection = bool(paths)
        current_path = state.current_path
        menu = wx.Menu()

        def add(label, handler, enabled=True):
            item = menu.Append(wx.ID_ANY, label)
            item.Enable(bool(enabled))
            menu.Bind(wx.EVT_MENU, lambda _event: handler(), id=item.GetId())
            return item

        add(_("&Tocar agora"), lambda: self._explorer_play_paths(paths), has_selection)
        add(_("&Adicionar à playlist sem tocar\tShift+Enter"), lambda: self._explorer_add_paths(paths), has_selection)
        add(_("Adicionar à &fila de reprodução\tCtrl+Shift+F"), lambda: self._explorer_enqueue_paths(paths), has_selection)
        add(_("Abrir em &nova playlist"), lambda: self._explorer_open_paths_in_new_playlist(paths), has_selection)
        add(
            _("Adicionar a &pasta atual inteira à playlist"),
            lambda: self._explorer_add_paths([current_path]),
            bool(current_path),
        )
        menu.AppendSeparator()
        add(
            _("Con&verter seleção...\tCtrl+Shift+K"),
            lambda: self._explorer_convert_paths(paths),
            bool(folders) or any(media_kind(path) for path in paths),
        )
        add(
            _("&Indexar pasta na biblioteca"),
            lambda: self._index_folder_in_library(folders[0] if folders else current_path),
            bool(folders or current_path),
        )
        menu.AppendSeparator()
        add(_("&Copiar\tCtrl+C"), self._explorer_copy_selection, has_selection)
        add(_("Copiar ca&minho\tCtrl+Shift+C"), lambda: self._explorer_copy_selection(as_text=True), has_selection)
        if sys.platform.startswith("win"):
            reveal_path = paths[0] if paths else current_path
            add(
                _("Mostrar no &Explorador de Arquivos do Windows"),
                lambda: self._explorer_reveal_in_file_manager(reveal_path),
                bool(reveal_path),
            )
        menu.AppendSeparator()
        if current_path:
            self._append_explorer_sort_menu(menu)
        add(_("At&ualizar\tF5"), self._explorer_refresh)
        add(_("&Fechar explorador\tCtrl+E"), self._hide_explorer)

        popup_parent = anchor_window or self.explorer_panel.items_list
        try:
            popup_parent.PopupMenu(menu)
        finally:
            menu.Destroy()
        return True

    # -- Teclado --------------------------------------------------------------

    def _on_explorer_list_char_hook(self, event):
        key_code = event.GetKeyCode()
        if key_code == wx.WXK_F5 and not event.HasAnyModifiers():
            self._explorer_refresh()
            return
        if (
            key_code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER)
            and event.ShiftDown()
            and not event.ControlDown()
            and not event.AltDown()
        ):
            # Shift é "sem tocar", como em Ctrl+Shift+O e Ctrl+Shift+V.
            self._explorer_add_paths(self._explorer_selected_paths())
            return
        event.Skip()

    def _handle_explorer_key_down(self, event):
        """Atalhos com Ctrl enquanto o foco está no explorador; True se tratou a tecla."""
        if not event.ControlDown() or event.AltDown():
            return False

        key_code = event.GetKeyCode()
        shift = event.ShiftDown()
        paths = self._explorer_selected_paths()

        if not shift and key_code == wx.WXK_SPACE:
            self.on_show_explorer_sort_menu()
        elif shift and key_code in (ord("F"), ord("f")):
            self._explorer_enqueue_paths(paths)
        elif shift and key_code in (ord("K"), ord("k")):
            self._explorer_convert_paths(paths)
        elif key_code in (ord("C"), ord("c")):
            self._explorer_copy_selection(as_text=shift)
        else:
            return False
        return True

    # -- Sessão ---------------------------------------------------------------

    def _explorer_session_payload(self):
        return self._explorer_state.to_dict(visible=self._explorer_visible())

    def _restore_explorer_session(self, data, *, fallback_folder=None):
        state = self._explorer_state
        was_visible = state.restore(data)
        if not state.current_path and fallback_folder:
            # Sessão antiga, de quando a pasta era uma aba: reabre-a no explorador.
            state.current_path = fallback_folder
            was_visible = True
        if was_visible:
            self._show_explorer(focus=False, quiet=True)
