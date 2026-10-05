"""Assume um player que já está tocando, vindo do player rápido, sem recarregar a mídia."""

from ...i18n import _
from ...playback_handover import AdoptedPlayback
from ...playlists import build_playlist_title

__all__ = ["AdoptedPlayback", "PlaybackAdoptionMixin"]


class PlaybackAdoptionMixin:
    def _pending_adoption(self):
        return getattr(self, "_pending_adopted_playback", None)

    def _adopt_pending_playback(self):
        """Liga o player herdado a uma playlist nova; devolve se a mídia seguiu tocando.

        Roda depois de a sessão ser restaurada, que nesse caso não mexe no
        player. Daqui em diante a mídia é a da aba ativa como qualquer outra.
        """
        adopted = self._pending_adoption()
        self._pending_adopted_playback = None
        if adopted is None:
            return False

        paths = [self._normalize_path(path) for path in adopted.paths]
        paths = [path for path in paths if path]
        if not paths:
            return False
        if adopted.ended:
            # Não há o que continuar: abre como uma mídia nova qualquer.
            return self._open_media_paths(paths, verified=True)

        self._remember_directory(paths[0])
        state, tab_index = self._resolve_target_playlist_tab()
        state.title = build_playlist_title(paths)
        state.set_items(paths, start_index=0)
        state.source_path = None
        state.was_playing = not adopted.paused
        state.playback_gain_db = 0.0
        current_time = adopted.player.get_time()
        state.last_position_ms = max(0, current_time) if current_time is not None else 0

        register_in_library = getattr(self, "_register_media_paths_in_library", None)
        if callable(register_in_library):
            register_in_library(state.items, state.browser_item_labels)

        # Marcado antes de a aba ser selecionada: assim ela encontra a mídia já
        # carregada e não manda o player carregá-la de novo.
        player_key = self._active_player_key
        self._set_player_loaded_media_path(player_key, state.current_media_path)
        self.active_playlist_index = tab_index
        self.notebook.SetPageText(tab_index, state.title)
        # Sem `_select_tab`: ele gravaria a posição do player herdado na aba
        # que estava selecionada, como se a mídia fosse dela.
        self.notebook.ChangeSelection(tab_index)
        self._activate_tab(tab_index, announce=False)
        self._refresh_playlist_browser()

        # O mesmo fechamento de um início normal (título, status, controles de
        # mídia do Windows, histórico, letras), só que sem ter carregado nada.
        # O número de série novo invalida qualquer pedido de início anterior.
        request = {
            "kind": "play",
            "serial": self._next_playback_request_serial(),
            "media_path": state.current_media_path,
            "tab_index": tab_index,
            "player_key": player_key,
            "announce_message": "",
        }
        self._player_playback_request_serials[player_key] = request["serial"]
        self._finish_media_start(request, True, "")
        if adopted.paused and hasattr(self, "_set_status_message"):
            self._set_status_message(
                _("Pausado: {name}").format(name=self._media_label(state.current_media_path)),
                auto_clear_ms=0,
            )
        refresh_smtc = getattr(self, "_refresh_smtc_state", None)
        if callable(refresh_smtc):
            # Um início normal atualiza os controles de mídia do Windows pelo
            # evento "tocando" do MPV, que aqui já passou.
            refresh_smtc()
        self._add_recent_media_paths(paths)
        return True
