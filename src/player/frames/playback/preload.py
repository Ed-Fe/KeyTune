"""Pré-carregamento da próxima faixa para o crossfade.

Sem isto, a faixa seguinte só começa a ser aberta quando a transição já
começou: conectar, baixar o primeiro pedaço e abrir a saída de áudio do segundo
player acontecem todos no mesmo instante em que a faixa que sai está sendo
mixada. Numa saída Bluetooth isso pode soar como uma interrupção curta.

Aqui a faixa seguinte é carregada, parada e muda, no player livre, assim que a
atual terminou de ser baixada e faltam até ``PRELOAD_CACHED_LEAD_MS`` para o fim
dela (ou, no mais tardar, ``PRELOAD_LEAD_MS`` antes do fim). Na hora da transição o crossfade só dá o ``play``. Clipes (com vídeo
junto) entram do mesmo jeito: o MPV guarda o stream inteiro no cache.
O pré-carregamento é descartado se a faixa seguinte deixar de ser a mesma
(troca de playlist, fila, aleatório, repetição, parada, pulo).
"""

import contextlib
import time

from ...constants import REPEAT_ALL, REPEAT_ONE, REPEAT_STOP
from ...library import is_audio_playback_media
from ...log import get_logger

_logger = get_logger(__name__)

# A próxima faixa é carregada assim que a atual terminou de ser baixada (cache
# completo). Se o MPV não informar isso (arquivo local, por exemplo), é carregada
# no mais tardar quando faltar este tempo para o fim da atual.
PRELOAD_LEAD_MS = 60_000
# Tempo mínimo de reprodução da faixa atual antes de começar a baixar a próxima.
PRELOAD_MIN_ELAPSED_MS = 3_000
# Mesmo com a faixa atual toda baixada, a próxima só é carregada quando faltar
# no máximo isto: numa faixa longa, não deixa outro stream aberto e parado (e
# guardado na memória) por muitos minutos.
PRELOAD_CACHED_LEAD_MS = 300_000
# Folga mínima entre o fim do pré-carregamento e o começo da janela do crossfade.
PRELOAD_MIN_MARGIN_MS = 2_000
# Passado isto sem ficar pronto, o pré-carregamento é abandonado.
PRELOAD_READY_TIMEOUT_S = 20.0


def _format_diagnostics(diagnostics):
    if not diagnostics:
        return "{}"
    return ", ".join(f"{name}={value}" for name, value in diagnostics.items())


class PreloadMixin:
    # Estado do pré-carregamento atual (ou None).
    _preload = None
    # (faixa atual, próxima faixa) cujo pré-carregamento falhou: não tenta de novo.
    _preload_blocked = None

    def _player_diagnostics(self, player_key):
        """Propriedades do MPV úteis para achar cortes de áudio; nunca levanta erro."""
        try:
            player = self._managed_player(player_key)
            read = getattr(player, "get_diagnostics", None)
            if player is None or not callable(read):
                return {}
            return read()
        except Exception:
            return {}

    def _preload_next_target(self):
        """Faixa seguinte que vale pré-carregar, como ``(caminho, aba)``, ou None."""
        if self._crossfade_duration_ms() <= 0 or getattr(self, "_crossfade_state", None) is not None:
            return None
        settings = getattr(self, "settings", None)
        if bool(getattr(settings, "autodj_enabled", False)):
            return None
        state = self._get_active_playlist_state()
        if not state or state.is_folder_tab or not state.current_media_path or state.autodj_session:
            return None
        if state.repeat_mode in (REPEAT_ONE, REPEAT_STOP) or self._autoplay_next_is_off(state):
            return None

        next_path = state.peek_in_playback_order(1, wrap=state.repeat_mode == REPEAT_ALL)
        if not next_path or self._media_paths_match(state.current_media_path, next_path):
            return None
        if not is_audio_playback_media(state.current_media_path) or not is_audio_playback_media(next_path):
            return None
        chapter_pending = getattr(self, "_youtube_chapter_start_pending", None)
        if callable(chapter_pending) and chapter_pending(next_path):
            return None
        if self._youtube_music_media_is_disliked(next_path):
            return None
        return next_path, self._get_active_playlist_index()

    def _preload_time_window_is_open(self):
        if self._media_start_is_pending():
            return False
        player = self.player
        if player.get_media() is None or not player.is_playing():
            return False
        current_time = player.get_time()
        total_time = player.get_length()
        if current_time is None or current_time < 0 or total_time is None or total_time <= 0:
            return False
        remaining_ms = total_time - current_time
        crossfade_window_ms = self._crossfade_duration_ms() + self._crossfade_startup_headroom_ms()
        if remaining_ms <= crossfade_window_ms + PRELOAD_MIN_MARGIN_MS:
            # Tarde demais: a transição começa antes de dar tempo de carregar.
            return False
        if remaining_ms <= PRELOAD_LEAD_MS:
            return True
        # A faixa atual já está toda no dispositivo: a rede está livre para a próxima.
        # Espera um instante do começo dela para não disputar o primeiro buffer.
        if remaining_ms > PRELOAD_CACHED_LEAD_MS:
            return False
        is_fully_cached = getattr(player, "is_fully_cached", None)
        return current_time >= PRELOAD_MIN_ELAPSED_MS and callable(is_fully_cached) and bool(is_fully_cached())

    def _maybe_preload_next_track(self):
        """Chamado pelo temporizador de progresso: carrega a faixa seguinte quando chega a hora."""
        try:
            self._run_preload_check()
        except Exception:
            _logger.debug("Preload check failed.", exc_info=True)

    def _run_preload_check(self):
        preload = self._preload
        target = self._preload_next_target()
        player_has_media = self.player.get_media() is not None

        if preload is not None:
            if not player_has_media:
                self._discard_preload("nada tocando")
            elif target is None or target[0] != preload["media_path"] or target[1] != preload["tab_index"]:
                self._discard_preload("a faixa seguinte mudou")
            elif not preload["ready"] and time.monotonic() - preload["requested_at"] > PRELOAD_READY_TIMEOUT_S:
                self._preload_blocked = (self._preload_current_path(), preload["media_path"])
                self._discard_preload("não ficou pronto a tempo", level="warning")
            return

        if target is None or not self._preload_time_window_is_open():
            return
        if self._preload_blocked == (self._preload_current_path(), target[0]):
            return
        self._start_preload(*target)

    def _preload_current_path(self):
        state = self._get_active_playlist_state()
        return getattr(state, "current_media_path", None)

    def _start_preload(self, media_path, tab_index):
        slot = self._inactive_player_key()
        if not slot:
            return
        self._stop_player(slot, unload=True)
        # Sem incrementar o número da requisição: o que tocar de novo (qualquer
        # ação do usuário) já a torna antiga, e nenhuma requisição em andamento
        # é invalidada por causa do pré-carregamento.
        request = {
            "kind": "play",
            "serial": self._playback_request_serial,
            "media_path": media_path,
            "tab_index": tab_index,
            "video_output_handle": None,
            "announce_message": "",
            "restore_position_ms": 0,
            "pause_after_start": True,
            "player_key": slot,
            "initial_volume": 0,
            "crossfade": True,
            "start_position_ms": 0,
            "expect_live": False,
            "live_reconnect": False,
            "revert_snapshot": None,
            "preload": True,
        }
        self._preload = {
            "request": request,
            "serial": request["serial"],
            "media_path": media_path,
            "tab_index": tab_index,
            "slot": slot,
            "ready": False,
            "requested_at": time.monotonic(),
            "resolved_display_title": "",
            "resolved_display_artist": "",
        }
        try:
            current_time = self.player.get_time()
            total_time = self.player.get_length()
            remaining_ms = total_time - current_time
        except Exception:
            remaining_ms = None
        _logger.debug(
            "Preload requested: %r into slot %r with %sms left on the current track.",
            media_path,
            slot,
            remaining_ms,
        )
        self._playback_queue.put(request)

    def _finish_preload(self, request, success, error_message):
        """Resultado do carregamento pedido por ``_start_preload`` (thread da interface)."""
        slot = request.get("player_key")
        preload = self._preload
        if preload is None or preload.get("request") is not request:
            # Descartado enquanto carregava: só desocupa o player se ninguém mais o usa.
            crossfade_state = getattr(self, "_crossfade_state", None)
            in_use = (preload is not None and preload.get("slot") == slot) or (
                crossfade_state is not None and crossfade_state.get("incoming_key") == slot
            )
            if success and not in_use:
                self._stop_player(slot, unload=True)
            return

        if not success:
            self._preload_blocked = (self._preload_current_path(), request.get("media_path"))
            _logger.warning("Preload failed for %r: %s", request.get("media_path"), error_message)
            self._preload = None
            self._stop_player(slot, unload=True)
            return

        state = self._get_playlist_state(preload["tab_index"])
        self._apply_equalizer_state_to_player(self._managed_player(slot), state)
        self._apply_volume_to_player(slot, 0)
        preload["resolved_display_title"] = str(request.get("resolved_display_title", "") or "").strip()
        preload["resolved_display_artist"] = str(request.get("resolved_display_artist", "") or "").strip()
        preload["ready"] = True
        preload["ready_at"] = time.monotonic()
        _logger.debug(
            "Preload ready: %r in slot %r after %dms; slot: %s",
            preload["media_path"],
            slot,
            int((preload["ready_at"] - preload["requested_at"]) * 1000),
            _format_diagnostics(self._player_diagnostics(slot)),
        )

    def _handle_preload_player_error(self, player_key, error_detail=""):
        """Erro no player que só guarda a faixa pré-carregada: descarta e segue sem aviso.

        A faixa tocando agora não é afetada, e o crossfade, sem pré-carregamento,
        abre a faixa pelo caminho de sempre. Devolve True quando tratou o erro.
        """
        preload = self._preload
        if preload is None or preload.get("slot") != player_key:
            return False
        crossfade_state = getattr(self, "_crossfade_state", None)
        if crossfade_state is not None and crossfade_state.get("incoming_key") == player_key:
            return False
        self._preload_blocked = (self._preload_current_path(), preload.get("media_path"))
        self._discard_preload(f"erro do MPV: {error_detail or 'sem detalhe'}", level="warning")
        return True

    def _discard_preload(self, reason, level="debug"):
        preload = self._preload
        self._preload = None
        if preload is None:
            return
        slot = preload.get("slot")
        crossfade_state = getattr(self, "_crossfade_state", None)
        if crossfade_state is not None and crossfade_state.get("incoming_key") == slot:
            return
        getattr(_logger, level)("Preload discarded (%s): %r.", reason, preload.get("media_path"))
        lock = getattr(self, "_playback_backend_lock", None)
        with lock if lock is not None else contextlib.nullcontext():
            self._stop_player(slot, unload=True)

    def _take_preloaded_incoming(self, media_path, tab_index, incoming_key):
        """Entrega o pré-carregamento se ele é exatamente o que o crossfade vai tocar.

        Devolve o dicionário do pré-carregamento (e o tira da fila) ou None; neste
        caso o player livre já foi esvaziado e o crossfade segue o caminho normal.
        """
        preload = self._preload
        if preload is None:
            return None
        player = self._managed_player(incoming_key)
        valid = (
            preload.get("ready")
            and preload.get("slot") == incoming_key
            and preload.get("tab_index") == tab_index
            and preload.get("media_path") == media_path
            and player is not None
            and player.get_media() is not None
            and self._player_loaded_media_path(incoming_key) == media_path
        )
        if valid:
            self._preload = None
            return preload
        reason = "ainda carregando" if not preload.get("ready") else "não é a faixa que vai tocar"
        self._discard_preload(reason)
        return None
