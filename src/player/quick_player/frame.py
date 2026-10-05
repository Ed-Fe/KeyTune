"""Janela pequena que toca um arquivo aberto pelo Windows sem subir o KeyTune completo.

As teclas e os anúncios seguem os do player da janela principal
(``frames/playback/controls.py``): o que lá é silencioso, aqui também é.
"""

import os

import wx

from ..accessibility import ScreenReaderAnnouncer
from ..audio_output import is_selectable_audio_output_device_id, normalize_audio_output_device_id
from ..constants import APP_TITLE, LARGE_SEEK_STEP_MS, PROGRESS_GAUGE_RANGE, PROGRESS_TIMER_INTERVAL_MS
from ..i18n import _
from ..log import get_logger
from ..mpv_backend import PlayerEventType, create_player_instance
from ..playback_handover import AdoptedPlayback
from ..session import load_session
from .launch import format_time_ms, initial_volume, quick_player_paths
from .panel import QuickPlayerPanel

_logger = get_logger(__name__)

# Os mesmos limites de frames/playback/controls.py.
PLAYBACK_RATE_STEP = 0.25
PLAYBACK_RATE_MIN = 0.25
PLAYBACK_RATE_MAX = 3.0


class QuickPlayerFrame(wx.Frame):
    """Toca os arquivos recebidos, um de cada vez, e mais nada.

    *on_continue* recebe ``(paths, new_playlist=..., adopted_playback=...)``
    quando o pedido passa a ser do KeyTune completo. Com *adopted_playback*, o
    MPV daqui segue tocando e passa a ser da janela principal; sem ele, a
    reprodução daqui já foi encerrada.
    """

    def __init__(self, paths, *, settings, on_continue):
        style = wx.DEFAULT_FRAME_STYLE & ~(wx.RESIZE_BORDER | wx.MAXIMIZE_BOX)
        super().__init__(None, title=APP_TITLE, style=style)

        self.settings = settings
        self._on_continue = on_continue
        self._paths = list(paths)
        self._index = 0
        self._volume = initial_volume(settings, load_session())
        self._playback_rate = 1.0
        self._instance = None
        self._player = None
        self._paused = False
        self._ended = False
        self._length_ms = -1
        self._play_serial = 0
        self.announcer = ScreenReaderAnnouncer()

        self.panel = QuickPlayerPanel(self, on_toggle_play=self._toggle_play_pause, on_continue=self._continue_in_full)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.panel, 1, wx.EXPAND)
        self.SetSizer(sizer)
        best_size = self.panel.GetBestSize()
        self.SetClientSize((max(best_size.width, self.FromDIP(480)), best_size.height))

        self.progress_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_progress_timer, self.progress_timer)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        self.Bind(wx.EVT_CLOSE, self._on_close)

        self._show_current_media()
        self.Centre()
        self.Show()
        self.panel.play_button.SetFocus()
        # A janela aparece antes de o MPV subir, para o Enter responder na hora.
        wx.CallAfter(self._start_playback)

    # --- pedidos vindos de fora -------------------------------------------

    def receive_external_files(self, paths):
        """Toca o que outra abertura pelo Windows mandou, no lugar do que tocava."""
        if not paths:
            return
        media_paths = quick_player_paths(paths, self.settings)
        if not media_paths:
            self._hand_over(list(paths), new_playlist=False)
            return

        self._paths = media_paths
        self._index = 0
        self._show_current_media()
        self._play_current()

    def focus_from_relaunch(self):
        """Abrir o KeyTune de novo, sem arquivo, é pedir a janela principal."""
        self._continue_in_full()

    # --- reprodução ---------------------------------------------------------

    def _start_playback(self):
        if not self or self._player is not None:
            return
        try:
            self._instance = create_player_instance(
                video_output_enabled=False,
                audio_output_device_id=self._configured_audio_output_device_id(),
            )
            player = self._instance.media_player_new()
        except Exception as exc:
            _logger.error("Quick player could not start MPV: %s", exc)
            wx.MessageBox(str(exc), APP_TITLE, wx.OK | wx.ICON_ERROR, self)
            self.Close()
            return

        self._player = player
        self._use_default_audio_output_if_configured_is_missing()
        event_manager = player.event_manager()
        event_manager.event_attach(PlayerEventType.MEDIA_PLAYER_END_REACHED, self._post, self._on_media_end)
        event_manager.event_attach(PlayerEventType.MEDIA_PLAYER_ERROR, self._post, self._on_media_error)
        player.audio_set_volume(self._volume)
        self.progress_timer.Start(PROGRESS_TIMER_INTERVAL_MS)
        self._play_current()

    def _configured_audio_output_device_id(self):
        device_id = normalize_audio_output_device_id(getattr(self.settings, "audio_output_device_id", ""))
        return device_id if is_selectable_audio_output_device_id(device_id) else ""

    def _use_default_audio_output_if_configured_is_missing(self):
        # A saída escolhida pode estar desconectada (fone Bluetooth); sem isto o
        # MPV cairia na saída nula e o arquivo tocaria em silêncio.
        device_id = self._configured_audio_output_device_id()
        if not device_id:
            return
        try:
            available_ids = {
                normalize_audio_output_device_id(device.device_id)
                for device in self._player.list_audio_output_devices()
            }
            if device_id not in available_ids:
                self._player.set_audio_output_device("")
        except Exception:
            pass

    def _post(self, event, handler):
        # Os eventos do MPV chegam na thread dele.
        wx.CallAfter(self._deliver, handler, event, self._play_serial)

    def _deliver(self, handler, event, play_serial):
        # Um evento da mídia anterior não pode encerrar a que acabou de entrar.
        if self and self._player is not None and play_serial == self._play_serial:
            handler(event)

    def _current_path(self):
        if 0 <= self._index < len(self._paths):
            return self._paths[self._index]
        return ""

    def _current_name(self):
        path = self._current_path()
        return os.path.basename(path) or path

    def _show_current_media(self):
        name = self._current_name()
        self.SetTitle(f"{APP_TITLE} — {name}" if name else APP_TITLE)
        self.panel.set_title(name)

    def _play_current(self, *, start_ms=0):
        path = self._current_path()
        if self._player is None or not path:
            return
        self._play_serial += 1
        self._ended = False
        self._paused = False
        self._length_ms = -1
        self._player.set_media(self._instance.media_new(path))
        self._player.play(start_seconds=start_ms / 1000.0 if start_ms > 0 else None)
        self.panel.set_playing(True)
        self._update_time()

    def _on_media_end(self, _event):
        if self._index + 1 < len(self._paths):
            self._index += 1
            self._show_current_media()
            self._play_current()
            return
        self._ended = True
        self.panel.set_playing(False)

    def _on_media_error(self, event):
        detail = str(getattr(event, "detail", "") or "").strip()
        if detail:
            message = _("Não foi possível reproduzir a mídia: {detail}.").format(detail=detail)
        else:
            message = _("Não foi possível reproduzir a mídia.")
        self._ended = True
        self.panel.set_playing(False)
        self.panel.set_time(message, 0)
        self._announce(message)

    def _toggle_play_pause(self):
        if self._player is None:
            return
        if self._ended:
            self._play_current()
            self._announce(_("Reprodução retomada."))
            return
        if self._paused:
            self._player.play()
            self._paused = False
            self._announce(_("Reprodução retomada."))
        else:
            self._player.pause()
            self._paused = True
            self._announce(_("Pausado."))
        self.panel.set_playing(not self._paused)

    def _seek_relative(self, delta_ms):
        if self._player is None:
            return
        if self._ended:
            # No fim, o MPV já soltou o arquivo: voltar é recarregar perto do fim.
            if delta_ms < 0 and self._length_ms > 0:
                self._play_current(start_ms=max(0, self._length_ms + delta_ms))
            return
        current_ms = self._player.get_time()
        if current_ms < 0:
            return
        target_ms = max(0, current_ms + delta_ms)
        if self._length_ms > 0:
            target_ms = min(target_ms, self._length_ms)
        self._player.set_time(target_ms)
        self._update_time()

    def _seek_to_start(self):
        if self._player is None:
            return
        if self._ended:
            self._play_current()
        else:
            self._player.set_time(0)
            self._update_time()
        self._announce(_("Início do arquivo."))

    def _seek_to_end(self):
        if self._player is None or self._ended:
            return
        if self._length_ms > 0:
            self._player.set_time(max(0, self._length_ms - 1000))
        else:
            self._player.set_position(0.99)
        self._update_time()
        self._announce(_("Fim do arquivo."))

    def _change_volume(self, delta):
        self._volume = max(0, min(100, self._volume + delta))
        if self._player is not None:
            self._player.audio_set_volume(self._volume)

    def _set_playback_rate(self, rate):
        self._playback_rate = max(PLAYBACK_RATE_MIN, min(PLAYBACK_RATE_MAX, round(rate, 2)))
        if self._player is not None:
            self._player.set_rate(self._playback_rate)
        self._announce(_("Velocidade de reprodução: {rate}.").format(rate=f"{self._playback_rate:g}x"))

    def _playback_position(self):
        """``(posição, duração)`` em milissegundos; a duração é ``-1`` enquanto desconhecida."""
        if self._player is None:
            return 0, -1
        length_ms = self._player.get_length()
        if length_ms > 0:
            self._length_ms = length_ms
        if self._ended and self._length_ms > 0:
            return self._length_ms, self._length_ms
        return max(0, self._player.get_time()), self._length_ms

    def _update_time(self):
        if self._player is None or self._player.get_media() is None:
            return
        current_ms, length_ms = self._playback_position()
        if length_ms <= 0:
            self.panel.set_time(
                _("Tempo: {current} / duração desconhecida").format(current=format_time_ms(current_ms)), 0
            )
            return
        current_ms = min(current_ms, length_ms)
        self.panel.set_time(
            _("Tempo: {current} / {total} ({percent}%)").format(
                current=format_time_ms(current_ms),
                total=format_time_ms(length_ms),
                percent=round(current_ms / length_ms * 100),
            ),
            round(current_ms / length_ms * PROGRESS_GAUGE_RANGE),
        )

    def _on_progress_timer(self, _event):
        self._update_time()

    # --- anúncios -----------------------------------------------------------

    def _announce(self, message):
        if self.settings.announcements_enabled:
            self.announcer.speak(message)

    def _announce_volume(self):
        self._announce(f"{self._volume}%.")

    def _announce_time(self):
        current_ms, length_ms = self._playback_position()
        if length_ms <= 0:
            self._announce(f"{format_time_ms(current_ms)}.")
            return
        current_ms = min(current_ms, length_ms)
        self._announce(
            _("{current} de {total}. {percent}%.").format(
                current=format_time_ms(current_ms),
                total=format_time_ms(length_ms),
                percent=round(current_ms / length_ms * 100),
            )
        )

    def _announce_status(self):
        # A mesma ordem do status da janela principal; a velocidade só entra fora de 1x.
        playback_state = _("pausado") if self._paused or self._ended else _("tocando")
        status_parts = [_("{name}, {state}.").format(name=self._current_name(), state=playback_state)]
        current_ms, length_ms = self._playback_position()
        if length_ms > 0:
            current_ms = min(current_ms, length_ms)
            status_parts.append(
                _("{current} de {total}. {percent}%.").format(
                    current=format_time_ms(current_ms),
                    total=format_time_ms(length_ms),
                    percent=round(current_ms / length_ms * 100),
                )
            )
        else:
            status_parts.append(f"{format_time_ms(current_ms)}.")
        if len(self._paths) > 1:
            status_parts.append(
                _("Item {current} de {total}.").format(current=self._index + 1, total=len(self._paths))
            )
        status_parts.append(_("Volume {volume}%.").format(volume=self._volume))
        if self._playback_rate != 1.0:
            status_parts.append(_("Velocidade {rate}.").format(rate=f"{self._playback_rate:g}x"))
        self._announce(" ".join(status_parts))

    # --- teclado e encerramento ---------------------------------------------

    def _on_char_hook(self, event):
        key_code = event.GetKeyCode()
        if event.AltDown():
            event.Skip()
            return

        if event.ControlDown():
            if key_code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
                self._continue_in_full()
            else:
                event.Skip()
            return

        if key_code == wx.WXK_ESCAPE:
            self.Close()
        elif key_code == wx.WXK_SPACE:
            if wx.Window.FindFocus() is self.panel.continue_button:
                event.Skip()
            else:
                self._toggle_play_pause()
        elif key_code == wx.WXK_LEFT:
            self._seek_relative(-(LARGE_SEEK_STEP_MS if event.ShiftDown() else self.settings.seek_step_ms))
        elif key_code == wx.WXK_RIGHT:
            self._seek_relative(LARGE_SEEK_STEP_MS if event.ShiftDown() else self.settings.seek_step_ms)
        elif key_code == wx.WXK_UP:
            self._change_volume(self.settings.volume_step)
        elif key_code == wx.WXK_DOWN:
            self._change_volume(-self.settings.volume_step)
        elif key_code == wx.WXK_HOME:
            self._seek_to_start()
        elif key_code == wx.WXK_END:
            self._seek_to_end()
        elif key_code in (ord("T"), ord("t")):
            self._announce_time()
        elif key_code in (ord("V"), ord("v")):
            self._announce_volume()
        elif key_code in (ord("S"), ord("s")):
            self._announce_status()
        elif not event.ShiftDown() and key_code == ord("]"):
            self._set_playback_rate(self._playback_rate + PLAYBACK_RATE_STEP)
        elif not event.ShiftDown() and key_code == ord("["):
            self._set_playback_rate(self._playback_rate - PLAYBACK_RATE_STEP)
        elif not event.ShiftDown() and key_code == ord("\\"):
            self._set_playback_rate(1.0)
        else:
            event.Skip()

    def _continue_in_full(self):
        paths = self._paths[self._index :]
        if self._player is None or self._ended:
            self._hand_over(paths, new_playlist=True)
            return

        # A mídia segue tocando: o MPV muda de dono em vez de ser encerrado.
        adopted = AdoptedPlayback(
            player=self._player,
            instance=self._instance,
            paths=paths,
            volume=self._volume,
            playback_rate=self._playback_rate,
            paused=self._paused,
        )
        self._shutdown_playback(release_player=False)
        self._on_continue(paths, new_playlist=True, adopted_playback=adopted)
        self.Destroy()

    def _hand_over(self, paths, *, new_playlist):
        self._shutdown_playback()
        self._on_continue(paths, new_playlist=new_playlist)
        self.Destroy()

    def _shutdown_playback(self, *, release_player=True):
        if self.progress_timer.IsRunning():
            self.progress_timer.Stop()
        self.announcer.request_close()
        player, self._player = self._player, None
        if player is not None and release_player:
            try:
                player.release()
            except Exception:
                pass

    def _on_close(self, event):
        self._shutdown_playback()
        event.Skip()
