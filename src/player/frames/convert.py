"""Conversão de mídia entre áudio e vídeo (menu Arquivo > Converter).

Este módulo cuida só do lado da janela: validar o que será convertido (a mídia
aberta ou os arquivos selecionados na lista), escolher o modo, perguntar as
opções, oferecer o FFmpeg quando faltar e acompanhar a conversão em segundo
plano. Montar o comando e executar o FFmpeg ficam em ``player/convert``.
"""

import os
import threading
import time

import wx

from ..convert.dialog import ConvertDialog
from ..convert.options import (
    KIND_AUDIO,
    KIND_VIDEO,
    MODE_AUDIO_TO_AUDIO,
    MODE_AUDIO_TO_VIDEO,
    MODE_SOURCE_KIND,
    MODE_VIDEO_TO_AUDIO,
    MODE_VIDEO_TO_VIDEO,
    media_kind,
    mode_label,
)
from ..convert.plan import build_batch_requests, modes_for_sources
from ..convert.runner import ConversionCancelled, run_conversion
from ..download.ffmpeg import (
    FFMPEG_APPROXIMATE_DOWNLOAD_MB,
    FFmpegInstallCancelled,
    ffmpeg_install_supported,
    find_ffmpeg_directory,
    install_managed_ffmpeg,
)
from ..i18n import _
from ..library.playlist_io import is_remote_media_path
from ..log import get_logger
from ..process_control import CancelToken
from .selection import selected_list_entries
from .task_progress import TaskProgressMixin


_logger = get_logger(__name__)

# Modos que cada tipo de mídia aceita, na ordem em que o atalho os oferece.
_MODES_BY_SOURCE_KIND = {
    KIND_AUDIO: (MODE_AUDIO_TO_AUDIO, MODE_AUDIO_TO_VIDEO),
    KIND_VIDEO: (MODE_VIDEO_TO_AUDIO, MODE_VIDEO_TO_VIDEO),
}
_ALL_MODES_IN_ORDER = (MODE_AUDIO_TO_AUDIO, MODE_AUDIO_TO_VIDEO, MODE_VIDEO_TO_AUDIO, MODE_VIDEO_TO_VIDEO)
_STATUS_UPDATE_INTERVAL_SECONDS = 0.5


def _is_convertible_local_file(path) -> bool:
    return (
        bool(path)
        and not is_remote_media_path(path)
        and os.path.isfile(path)
        and bool(media_kind(path))
    )


class FrameConvertMixin(TaskProgressMixin):
    def _initialize_convert_state(self):
        self._convert_token = None
        self._convert_percent = None
        self._convert_last_status_at = 0.0
        self._convert_batch_index = 1
        self._convert_batch_total = 1
        # Última pasta escolhida em «Outra pasta», oferecida de novo no próximo diálogo.
        self._convert_other_directory = ""

    def _convert_in_progress(self):
        return getattr(self, "_convert_token", None) is not None

    def _shutdown_convert(self):
        token = getattr(self, "_convert_token", None)
        if token is not None:
            token.cancel()

    # -- Comandos de menu e atalho ---------------------------------------------

    def on_convert_audio_to_video(self, _event=None):
        self._begin_conversion(MODE_AUDIO_TO_VIDEO)

    def on_convert_video_to_audio(self, _event=None):
        self._begin_conversion(MODE_VIDEO_TO_AUDIO)

    def on_convert_audio_to_audio(self, _event=None):
        self._begin_conversion(MODE_AUDIO_TO_AUDIO)

    def on_convert_video_to_video(self, _event=None):
        self._begin_conversion(MODE_VIDEO_TO_VIDEO)

    def on_convert_current_media(self, _event=None):
        """Atalho: oferece só os modos que servem ao tipo da mídia aberta."""
        if self._convert_in_progress():
            self._offer_to_cancel_conversion()
            return

        source_path = self._validated_convert_source()
        if not source_path:
            return

        modes = _MODES_BY_SOURCE_KIND[media_kind(source_path)]
        mode = self._choose_convert_mode(modes, [mode_label(item) for item in modes])
        if mode:
            self._begin_conversion(mode, source_path=source_path)

    def on_convert_selection(self, _event=None):
        """Converte os arquivos de áudio e vídeo selecionados na lista da aba atual."""
        if self._convert_in_progress():
            self._offer_to_cancel_conversion()
            return

        paths = [path for path, _title in selected_list_entries(self) if _is_convertible_local_file(path)]
        if not paths:
            self._announce(_("Nenhum arquivo de áudio ou vídeo do computador está selecionado."))
            return

        counts = modes_for_sources(paths)
        modes = [mode for mode in _ALL_MODES_IN_ORDER if mode in counts]
        if len(paths) == 1:
            labels = [mode_label(mode) for mode in modes]
        else:
            labels = [
                _("{mode} (arquivos: {count})").format(mode=mode_label(mode), count=counts[mode]) for mode in modes
            ]
        mode = self._choose_convert_mode(modes, labels)
        if not mode:
            return

        if len(paths) == 1:
            self._begin_conversion(mode, source_path=paths[0])
        else:
            matching = [path for path in paths if media_kind(path) == MODE_SOURCE_KIND[mode]]
            self._begin_batch_conversion(mode, matching, total_selected=len(paths))

    def _choose_convert_mode(self, modes, labels):
        with wx.SingleChoiceDialog(
            self,
            _("O que você quer fazer com esta mídia?"),
            _("Converter mídia"),
            list(labels),
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return None
            return modes[dialog.GetSelection()]

    # -- Fluxo -----------------------------------------------------------------

    def _current_convert_media_path(self):
        state = self._get_active_playlist_state()
        return str(getattr(state, "current_media_path", "") or "").strip() if state else ""

    def _validated_convert_source(self):
        """Caminho da mídia aberta se ela puder ser convertida; vazio (com aviso) se não."""
        media_path = self._current_convert_media_path()
        if not media_path:
            self._announce(_("Nenhuma mídia está aberta para converter."))
            return ""
        if is_remote_media_path(media_path):
            self._announce(
                _("A conversão funciona com arquivos do computador. Para mídias do YouTube, use Baixar (Ctrl+Shift+B).")
            )
            return ""
        if not os.path.isfile(media_path):
            self._announce(_("O arquivo da mídia atual não foi encontrado."))
            return ""
        if not media_kind(media_path):
            self._announce(_("Este tipo de arquivo não pode ser convertido."))
            return ""
        return media_path

    def _begin_conversion(self, mode, *, source_path=None):
        if self._convert_in_progress():
            self._offer_to_cancel_conversion()
            return

        source_path = source_path or self._validated_convert_source()
        if not source_path:
            return

        if media_kind(source_path) != MODE_SOURCE_KIND[mode]:
            if media_kind(source_path) == KIND_AUDIO:
                self._announce(_("Esta opção converte vídeo, mas a mídia atual é um áudio. Use as opções de áudio."))
            else:
                self._announce(_("Esta opção converte áudio, mas a mídia atual é um vídeo. Use as opções de vídeo."))
            return

        request = self._ask_conversion_options(mode, source_path)
        if request is None:
            return

        install_ffmpeg = self._confirm_convert_ffmpeg()
        if install_ffmpeg is None:
            return
        self._start_conversion((request,), install_ffmpeg=install_ffmpeg)

    def _begin_batch_conversion(self, mode, source_paths, *, total_selected):
        if self._convert_in_progress():
            self._offer_to_cancel_conversion()
            return

        dialog = ConvertDialog(
            self,
            mode,
            source_paths[0],
            other_directory=self._convert_other_directory,
            item_count=len(source_paths),
        )
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            template = dialog.get_request()
            same_folder = dialog.saves_in_same_folder()
            self._convert_other_directory = dialog.other_directory() or self._convert_other_directory
        finally:
            dialog.Destroy()

        requests, skipped = build_batch_requests(template, source_paths, same_folder=same_folder)
        # Os de outro tipo (numa seleção mista) também não entram nesta conversão.
        skipped += total_selected - len(source_paths)
        if not requests:
            self._announce(_("Nenhum dos arquivos selecionados precisa desta conversão."))
            return

        install_ffmpeg = self._confirm_convert_ffmpeg()
        if install_ffmpeg is None:
            return
        self._start_conversion(requests, install_ffmpeg=install_ffmpeg, skipped=skipped)

    def _ask_conversion_options(self, mode, source_path):
        dialog = ConvertDialog(self, mode, source_path, other_directory=self._convert_other_directory)
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return None
            request = dialog.get_request()
            self._convert_other_directory = dialog.other_directory() or self._convert_other_directory
            return request
        finally:
            dialog.Destroy()

    def _confirm_convert_ffmpeg(self):
        """True para instalar o FFmpeg antes de converter, False se já existe e
        None para desistir: sem ele não há conversão."""
        if find_ffmpeg_directory() is not None:
            return False

        if not ffmpeg_install_supported():
            self._announce(_("A conversão precisa do FFmpeg, que não foi encontrado. Instale-o e tente de novo."))
            return None

        response = wx.MessageBox(
            _(
                "Para converter, o KeyTune precisa do FFmpeg, que não foi encontrado. "
                "Ele será baixado das versões oficiais (cerca de {size} MB) e guardado na pasta de recursos do KeyTune.\n\n"
                "Deseja instalar o FFmpeg e converter agora?"
            ).format(size=FFMPEG_APPROXIMATE_DOWNLOAD_MB),
            _("FFmpeg necessário"),
            wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION,
            self,
        )
        return True if response == wx.YES else None

    def _start_conversion(self, requests, *, install_ffmpeg, skipped=0):
        token = CancelToken()
        self._convert_token = token
        self._convert_percent = None
        self._convert_last_status_at = 0.0
        self._convert_batch_index = 1
        self._convert_batch_total = len(requests)

        if len(requests) > 1:
            self._announce(_("Iniciando a conversão de {count} arquivos.").format(count=len(requests)))
        else:
            self._announce(_("Iniciando a conversão."))
        self._set_status_message(_("Convertendo..."), auto_clear_ms=0)
        self._set_task_progress("convert", None)

        threading.Thread(
            target=self._convert_worker,
            args=(tuple(requests), token, install_ffmpeg, skipped),
            name="keytune-convert",
            daemon=True,
        ).start()

    def _convert_worker(self, requests, token, install_ffmpeg, skipped):
        try:
            if install_ffmpeg:
                wx.CallAfter(self._set_convert_status, _("Instalando o FFmpeg..."))
                install_managed_ffmpeg(cancel_event=token.event)
                wx.CallAfter(self._set_convert_status, _("Convertendo..."))

            ffmpeg_directory = find_ffmpeg_directory()
            if ffmpeg_directory is None:
                raise RuntimeError(_("O FFmpeg não foi encontrado."))

            results = []
            failures = []
            cancelled = False
            for position, request in enumerate(requests, start=1):
                if token.cancelled:
                    cancelled = True
                    break
                wx.CallAfter(self._on_convert_item_started, token, position)
                try:
                    results.append(
                        run_conversion(
                            request,
                            ffmpeg_directory=ffmpeg_directory,
                            progress_callback=self._on_convert_progress,
                            cancel_token=token,
                        )
                    )
                except ConversionCancelled:
                    cancelled = True
                    break
                except Exception as exc:
                    _logger.warning("Conversion failed: %s", exc)
                    failures.append((os.path.basename(request.source_path), str(exc)))
        except FFmpegInstallCancelled:
            wx.CallAfter(self._on_conversion_cancelled, token)
        except Exception as exc:
            _logger.warning("Conversion failed: %s", exc)
            wx.CallAfter(self._on_conversion_failed, token, str(exc))
        else:
            wx.CallAfter(
                self._dispatch_conversion_outcome, token, tuple(results), tuple(failures), len(requests), skipped, cancelled
            )

    def _dispatch_conversion_outcome(self, token, results, failures, total, skipped, cancelled):
        if cancelled:
            self._on_conversion_cancelled(token, done=len(results), total=total)
        elif total == 1 and results:
            self._on_conversion_finished(token, results[0])
        elif total == 1:
            self._on_conversion_failed(token, failures[0][1] if failures else "")
        else:
            self._on_batch_conversion_finished(token, results, failures, total, skipped)

    # -- Chamadas vindas da thread de conversão (sempre via wx.CallAfter) ------

    def _on_convert_progress(self, percent):
        now = time.monotonic()
        self._convert_percent = percent
        if now - self._convert_last_status_at < _STATUS_UPDATE_INTERVAL_SECONDS:
            return
        self._convert_last_status_at = now
        wx.CallAfter(self._update_convert_progress, percent)

    def _update_convert_progress(self, percent):
        """Texto da barra de status e barra de progresso, na thread da interface."""
        if not self._convert_in_progress():
            return
        if self._convert_batch_total > 1:
            text = _("Convertendo {index} de {total}... {percent}%").format(
                index=self._convert_batch_index, total=self._convert_batch_total, percent=percent
            )
        else:
            text = _("Convertendo... {percent}%").format(percent=percent)
        self._set_status_message(text, auto_clear_ms=0)
        self._set_task_progress("convert", self._convert_overall_percent(percent))

    def _convert_overall_percent(self, item_percent):
        # Numa fila, cada arquivo vale uma fatia igual da barra.
        total = max(1, self._convert_batch_total)
        return ((self._convert_batch_index - 1) * 100 + item_percent) / total

    def _on_convert_item_started(self, token, position):
        if self._convert_token is not token:
            return
        self._convert_batch_index = position
        self._convert_percent = None
        self._set_task_progress("convert", self._convert_overall_percent(0) if position > 1 else None)
        if self._convert_batch_total > 1:
            self._set_status_message(
                _("Convertendo {index} de {total}...").format(index=position, total=self._convert_batch_total),
                auto_clear_ms=0,
            )

    def _set_convert_status(self, message):
        if self._convert_in_progress():
            self._set_status_message(message, auto_clear_ms=0)

    def _finish_convert_state(self, token):
        if self._convert_token is not token:
            return False
        self._convert_token = None
        self._convert_percent = None
        self._convert_batch_index = 1
        self._convert_batch_total = 1
        self._clear_task_progress("convert")
        return True

    def _on_conversion_finished(self, token, result):
        if not self._finish_convert_state(token):
            return
        message = _("Conversão concluída: {name}.").format(name=os.path.basename(result.path))
        _logger.info("Conversion finished: %s", os.path.basename(result.path))
        self._set_status_message(message)
        self._announce(message)

    def _on_batch_conversion_finished(self, token, results, failures, total, skipped):
        if not self._finish_convert_state(token):
            return

        done = len(results)
        if done == 0:
            reason = failures[0][1] if failures else ""
            message = _("Não foi possível converter nenhum dos {total} arquivos: {reason}").format(
                total=total, reason=reason
            )
        elif failures:
            message = _("Conversão concluída: {done} de {total} arquivos. {failed} falharam.").format(
                done=done, total=total, failed=len(failures)
            )
        else:
            message = _("Conversão concluída: {done} arquivos.").format(done=done)
        if skipped:
            message += " " + _("{count} arquivos foram ignorados.").format(count=skipped)
        for name, reason in failures:
            _logger.warning("Batch conversion item failed (%s): %s", name, reason)
        self._set_status_message(message)
        self._announce(message)

    def _on_conversion_failed(self, token, reason):
        if not self._finish_convert_state(token):
            return
        message = _("Não foi possível converter a mídia: {reason}").format(reason=reason)
        self._set_status_message(message)
        self._announce(message)

    def _on_conversion_cancelled(self, token, done=0, total=1):
        if not self._finish_convert_state(token):
            return
        if total > 1 and done:
            message = _("Conversão cancelada. {done} de {total} arquivos já foram convertidos.").format(
                done=done, total=total
            )
        else:
            message = _("Conversão cancelada.")
        self._set_status_message(message)
        self._announce(message)

    def _offer_to_cancel_conversion(self):
        percent = self._convert_percent
        if self._convert_batch_total > 1:
            state_text = _("Conversão em andamento: arquivo {index} de {total}.").format(
                index=self._convert_batch_index, total=self._convert_batch_total
            )
        elif percent is not None:
            state_text = _("Conversão em andamento: {percent}%.").format(percent=percent)
        else:
            state_text = _("Conversão em andamento.")
        response = wx.MessageBox(
            state_text + "\n\n" + _("Deseja cancelar a conversão?"),
            _("Converter mídia"),
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
            self,
        )
        if response == wx.YES and self._convert_token is not None:
            self._convert_token.cancel()
