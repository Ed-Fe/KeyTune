import time

import wx

from ..constants import (
    SLEEP_TIMER_MAX_MINUTES,
    SLEEP_TIMER_MIN_MINUTES,
    SLEEP_TIMER_MODE_COUNTDOWN,
    SLEEP_TIMER_MODE_END_OF_TRACK,
    SLEEP_TIMER_MODE_OFF,
    SLEEP_TIMER_TICK_INTERVAL_MS,
    SLEEP_TIMER_WARNING_MINUTES,
)
from ..i18n import _, ngettext
from ..sleep_timer import SleepTimerDialog


class FrameSleepTimerMixin:
    """Temporizador de desligamento (contagem regressiva ou fim da faixa).

    A contagem usa um relógio monotônico com um tique de 1 s só para conferir o
    prazo, então mudanças de relógio do sistema e tiques atrasados não deslocam
    o horário combinado. Ao vencer, a reprodução é pausada (não parada) para
    preservar a posição da mídia.
    """

    def _initialize_sleep_timer_state(self):
        self._sleep_timer_mode = SLEEP_TIMER_MODE_OFF
        self._sleep_timer_deadline = None
        self._sleep_timer_total_minutes = None
        self._sleep_timer_last_warning_minutes = None

    def _sleep_timer_is_armed(self):
        return getattr(self, "_sleep_timer_mode", SLEEP_TIMER_MODE_OFF) != SLEEP_TIMER_MODE_OFF

    def _sleep_timer_remaining_seconds(self):
        deadline = getattr(self, "_sleep_timer_deadline", None)
        if deadline is None:
            return None
        return max(0, int(round(deadline - time.monotonic())))

    def _format_sleep_timer_remaining(self, remaining_seconds):
        # Abreviações invariáveis (min/s) evitam concordância artificial na frase
        # que carrega este trecho ("tempo restante {remaining}").
        minutes, seconds = divmod(int(max(0, remaining_seconds)), 60)
        if minutes and seconds:
            return _("{minutes} min e {seconds} s").format(minutes=minutes, seconds=seconds)
        if minutes:
            return _("{minutes} min").format(minutes=minutes)
        return _("{seconds} s").format(seconds=seconds)

    def _sleep_timer_status_sentence(self):
        """Frase curta com o estado do temporizador (ou vazia quando desligado)."""
        mode = getattr(self, "_sleep_timer_mode", SLEEP_TIMER_MODE_OFF)
        if mode == SLEEP_TIMER_MODE_END_OF_TRACK:
            return _("Temporizador de desligamento: ao fim da faixa atual.")
        if mode == SLEEP_TIMER_MODE_COUNTDOWN:
            remaining = self._sleep_timer_remaining_seconds()
            if remaining is not None:
                return _("Temporizador de desligamento: tempo restante {remaining}.").format(
                    remaining=self._format_sleep_timer_remaining(remaining)
                )
        return ""

    def _stop_sleep_timer_ticks(self):
        timer = getattr(self, "sleep_timer", None)
        if timer is not None and timer.IsRunning():
            timer.Stop()

    def _clear_sleep_timer(self, announce=False):
        was_armed = self._sleep_timer_is_armed()
        self._stop_sleep_timer_ticks()
        self._initialize_sleep_timer_state()

        if not announce:
            return was_armed

        if was_armed:
            self._announce(_("Temporizador de desligamento cancelado."))
            if hasattr(self, "_set_status_message"):
                self._set_status_message(_("Temporizador de desligamento cancelado."))
        else:
            self._announce(_("Nenhum temporizador de desligamento ativo."))
        return was_armed

    def _arm_sleep_timer_countdown(self, minutes):
        try:
            normalized_minutes = int(minutes)
        except (TypeError, ValueError):
            return False

        normalized_minutes = max(SLEEP_TIMER_MIN_MINUTES, min(SLEEP_TIMER_MAX_MINUTES, normalized_minutes))

        self._stop_sleep_timer_ticks()
        self._sleep_timer_mode = SLEEP_TIMER_MODE_COUNTDOWN
        self._sleep_timer_total_minutes = normalized_minutes
        self._sleep_timer_deadline = time.monotonic() + normalized_minutes * 60
        self._sleep_timer_last_warning_minutes = None

        timer = getattr(self, "sleep_timer", None)
        if timer is not None:
            timer.Start(SLEEP_TIMER_TICK_INTERVAL_MS)

        message = ngettext(
            "Temporizador de desligamento ligado: {minutes} minuto.",
            "Temporizador de desligamento ligado: {minutes} minutos.",
            normalized_minutes,
        ).format(minutes=normalized_minutes)
        self._announce(message)
        if hasattr(self, "_set_status_message"):
            self._set_status_message(message)
        self._refresh_sleep_timer_menu_state()
        return True

    def _arm_sleep_timer_end_of_track(self):
        self._stop_sleep_timer_ticks()
        self._sleep_timer_mode = SLEEP_TIMER_MODE_END_OF_TRACK
        self._sleep_timer_deadline = None
        self._sleep_timer_total_minutes = None
        self._sleep_timer_last_warning_minutes = None

        message = _("Temporizador de desligamento ligado: ao fim da faixa atual.")
        self._announce(message)
        if hasattr(self, "_set_status_message"):
            self._set_status_message(message)
        self._refresh_sleep_timer_menu_state()
        return True

    def _apply_sleep_timer_selection(self, mode, minutes=None):
        if mode == SLEEP_TIMER_MODE_COUNTDOWN:
            return self._arm_sleep_timer_countdown(minutes)
        if mode == SLEEP_TIMER_MODE_END_OF_TRACK:
            return self._arm_sleep_timer_end_of_track()
        self._clear_sleep_timer(announce=True)
        self._refresh_sleep_timer_menu_state()
        return True

    def _announce_sleep_timer_status(self):
        message = self._sleep_timer_status_sentence() or _("Nenhum temporizador de desligamento ativo.")
        self._announce(message)
        if hasattr(self, "_set_status_message"):
            self._set_status_message(message)

    def _open_sleep_timer_dialog(self):
        dialog = SleepTimerDialog(
            self,
            current_mode=getattr(self, "_sleep_timer_mode", SLEEP_TIMER_MODE_OFF),
            current_minutes=getattr(self, "_sleep_timer_total_minutes", None),
            status_label=self._sleep_timer_status_sentence(),
        )
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            mode, minutes = dialog.get_selection()
        finally:
            dialog.Destroy()

        self._apply_sleep_timer_selection(mode, minutes)

    def _pause_playback_for_sleep_timer(self):
        player = getattr(self, "player", None)
        if player is None or player.get_media() is None:
            return False
        if not player.is_playing():
            return False

        # Reusa o caminho normal de pausa para manter fade curto, SMTC, barra de
        # status e estado da playlist consistentes.
        self._toggle_play_pause()
        return True

    def _finish_sleep_timer(self):
        self._clear_sleep_timer()
        self._refresh_sleep_timer_menu_state()
        # Anuncia antes de pausar: a pausa faz um fade curto assíncrono, então o
        # aviso do temporizador chegaria depois do "Pausado." se viesse depois.
        was_playing = getattr(self, "player", None) is not None and self.player.is_playing()
        message = (
            _("Temporizador de desligamento concluído. Reprodução pausada.")
            if was_playing
            else _("Temporizador de desligamento concluído.")
        )
        self._announce(message)
        if hasattr(self, "_set_status_message"):
            self._set_status_message(message, auto_clear_ms=0)
        self._pause_playback_for_sleep_timer()

    def _sleep_timer_should_stop_at_media_end(self):
        return getattr(self, "_sleep_timer_mode", SLEEP_TIMER_MODE_OFF) == SLEEP_TIMER_MODE_END_OF_TRACK

    def _handle_sleep_timer_media_end(self):
        """Encerra a sessão no fim da faixa em vez de avançar na playlist."""
        self._clear_sleep_timer()
        self._refresh_sleep_timer_menu_state()
        message = _("Temporizador de desligamento: fim da faixa. Reprodução encerrada.")
        self._announce(message)
        if hasattr(self, "_set_status_message"):
            self._set_status_message(message, auto_clear_ms=0)

    def _maybe_warn_sleep_timer(self, remaining_seconds):
        remaining_minutes = int(remaining_seconds // 60) + (1 if remaining_seconds % 60 else 0)
        for warning_minutes in SLEEP_TIMER_WARNING_MINUTES:
            if remaining_minutes != warning_minutes:
                continue
            if self._sleep_timer_last_warning_minutes == warning_minutes:
                return
            self._sleep_timer_last_warning_minutes = warning_minutes
            self._announce(
                ngettext(
                    "Temporizador de desligamento: falta {minutes} minuto.",
                    "Temporizador de desligamento: faltam {minutes} minutos.",
                    warning_minutes,
                ).format(minutes=warning_minutes)
            )
            return

    def on_sleep_timer_tick(self, _event):
        if getattr(self, "_sleep_timer_mode", SLEEP_TIMER_MODE_OFF) != SLEEP_TIMER_MODE_COUNTDOWN:
            self._stop_sleep_timer_ticks()
            return

        remaining_seconds = self._sleep_timer_remaining_seconds()
        if remaining_seconds is None:
            self._stop_sleep_timer_ticks()
            return

        if remaining_seconds <= 0:
            self._finish_sleep_timer()
            return

        self._maybe_warn_sleep_timer(remaining_seconds)

    def _refresh_sleep_timer_menu_state(self):
        menu_item_id = getattr(self, "menu_sleep_timer_cancel_id", None)
        menu_bar = self.GetMenuBar() if hasattr(self, "GetMenuBar") else None
        if menu_item_id is None or menu_bar is None:
            return
        menu_item = menu_bar.FindItemById(int(menu_item_id))
        if menu_item is not None:
            menu_item.Enable(self._sleep_timer_is_armed())

    def on_open_sleep_timer(self, _event):
        self._open_sleep_timer_dialog()

    def on_sleep_timer_preset(self, event):
        minutes = getattr(self, "_sleep_timer_menu_presets", {}).get(event.GetId())
        if minutes is None:
            event.Skip()
            return
        self._arm_sleep_timer_countdown(minutes)

    def on_sleep_timer_end_of_track(self, _event):
        self._arm_sleep_timer_end_of_track()

    def on_sleep_timer_status(self, _event):
        self._announce_sleep_timer_status()

    def on_cancel_sleep_timer(self, _event):
        self._clear_sleep_timer(announce=True)
        self._refresh_sleep_timer_menu_state()
