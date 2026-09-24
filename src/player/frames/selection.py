"""Itens selecionados na lista da aba atual, para download e conversão em lote."""

import os


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
