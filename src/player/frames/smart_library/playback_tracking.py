"""Amostragem periódica da reprodução para histórico e retomada.

`_record_playback_state_snapshot` é o gancho que o temporizador de progresso já
chamava (a cada 500 ms). Ele lê o tempo atual uma única vez e reparte a
informação entre o histórico e a retomada, para que nenhuma das duas precise
consultar o backend por conta própria.
"""

from ...constants import SMART_LIBRARY_RESUME_SAVE_INTERVAL_MS


class SmartLibraryPlaybackTrackingMixin:
    def _prepare_smart_library_tracking(self, media_path):
        """Reinicia o acompanhamento quando uma nova mídia começa a tocar."""
        normalized_media_path = str(media_path or "").strip()
        if not normalized_media_path:
            self._clear_smart_library_tracking()
            return False

        self._smart_library_playback_tracking = {
            "media_path": normalized_media_path,
            "history_recorded": False,
            "resume_saved": False,
        }
        self._smart_library_next_resume_save_ms = 0
        return True

    def _clear_smart_library_tracking(self):
        self._smart_library_playback_tracking = {}
        self._smart_library_next_resume_save_ms = 0

    def _record_playback_state_snapshot(self):
        tracking_state = getattr(self, "_smart_library_playback_tracking", None)
        if not tracking_state:
            return False

        if self._smart_library() is None:
            return False

        media_path = str(tracking_state.get("media_path") or "")
        if not media_path or not self._media_paths_match(media_path, self._player_loaded_media_path()):
            return False

        player = getattr(self, "player", None)
        if player is None or player.get_media() is None:
            return False

        try:
            position_ms = player.get_time()
            duration_ms = player.get_length()
            is_playing = bool(player.is_playing())
        except Exception:
            return False

        if position_ms is None or position_ms < 0:
            return False
        if not is_playing:
            return False

        normalized_duration_ms = int(duration_ms or 0)
        self._maybe_record_library_history(media_path, int(position_ms), normalized_duration_ms)

        # Gravar a posição a cada tique do temporizador seria uma escrita por
        # meio segundo; o intervalo mantém o disco quieto sem perder mais do que
        # alguns segundos se o app fechar de forma abrupta.
        if int(position_ms) < int(getattr(self, "_smart_library_next_resume_save_ms", 0) or 0):
            return True

        self._smart_library_next_resume_save_ms = int(position_ms) + SMART_LIBRARY_RESUME_SAVE_INTERVAL_MS
        self._maybe_save_resume_position(media_path, int(position_ms), normalized_duration_ms)
        return True

    def _flush_smart_library_playback_state(self):
        """Grava a posição atual antes de trocar de faixa ou fechar o app."""
        tracking_state = getattr(self, "_smart_library_playback_tracking", None)
        if not tracking_state or self._smart_library() is None:
            return False

        media_path = str(tracking_state.get("media_path") or "")
        player = getattr(self, "player", None)
        if not media_path or player is None or player.get_media() is None:
            return False

        try:
            position_ms = player.get_time()
            duration_ms = player.get_length()
        except Exception:
            return False

        if position_ms is None or position_ms < 0:
            return False

        return self._maybe_save_resume_position(media_path, int(position_ms), int(duration_ms or 0))
