"""Itens selecionados na lista da aba atual, para download e conversão em lote."""

import os

import wx


SCOPE_PLAYLIST = "playlist"
SCOPE_EXPLORER = "explorer"
SCOPE_SEARCH = "search"


def _window_has_focus(window):
    current_window = wx.Window.FindFocus()
    while isinstance(current_window, wx.Window):
        if current_window is window:
            return True
        current_window = current_window.GetParent()
    return False


def focused_list_scope(frame):
    """Lista que está com o foco: explorador, busca do YouTube ou playlist; vazio fora de uma lista.

    Converter (Ctrl+Shift+K) e baixar (Ctrl+Shift+B) seguem a mesma regra: com o
    foco numa lista agem na seleção dela; fora de uma lista, na mídia atual.
    """
    explorer_has_focus = getattr(frame, "_explorer_has_focus", None)
    if callable(explorer_has_focus) and explorer_has_focus():
        return SCOPE_EXPLORER

    get_youtube_music_panel = getattr(frame, "_get_youtube_music_panel", None)
    panel = get_youtube_music_panel() if callable(get_youtube_music_panel) else None
    search_results_list = getattr(panel, "search_results_list", None)
    if search_results_list is not None and _window_has_focus(search_results_list):
        return SCOPE_SEARCH

    browser = frame._get_browser_panel()
    if browser is not None and browser.is_item_navigation_active():
        return SCOPE_PLAYLIST
    return ""


def selected_list_entries(frame):
    """``(caminho, título)`` de cada item selecionado na lista da aba atual.

    Em playlists o título vem do rótulo exibido na lista; em pastas, do nome do
    arquivo. Sem lista ou sem seleção, devolve uma lista vazia.
    """
    browser = frame._get_browser_panel()
    if browser is None:
        return []

    state = frame._get_playlist_state()
    labels = list(getattr(state, "browser_item_labels", None) or []) if state is not None else []
    index_of_item = getattr(state, "index_of_item", None) if state is not None else None
    is_folder_tab = bool(getattr(state, "is_folder_tab", False))

    entries = []
    for path in browser.get_selected_item_paths():
        title = os.path.basename(str(path))
        if not is_folder_tab and callable(index_of_item):
            index = index_of_item(path)
            if index is not None and 0 <= index < len(labels) and labels[index]:
                title = labels[index]
        entries.append((path, str(title).strip()))
    return entries
