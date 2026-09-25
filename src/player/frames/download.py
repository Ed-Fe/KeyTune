"""Download de mídia do YouTube pelo yt-dlp (Ctrl+Shift+B).

Este módulo cuida só do lado da janela: validar o que será baixado, perguntar o
formato, oferecer o FFmpeg quando preciso e acompanhar o download em segundo
plano, seja uma faixa, uma seleção da lista ou a playlist inteira. Montar o
comando, executar o yt-dlp e instalar o FFmpeg ficam em ``player/download``.
"""

import dataclasses
import os
import threading
import time

import wx

from ..download.dialog import DownloadDialog
from ..download.ffmpeg import (
    FFMPEG_APPROXIMATE_DOWNLOAD_MB,
    FFmpegInstallCancelled,
    ffmpeg_install_supported,
    find_ffmpeg_directory,
    install_managed_ffmpeg,
)
from ..download.options import DOWNLOAD_KIND_VIDEO, resolve_download_directory
from ..download.plan import (
    MAX_BATCH_ITEMS,
    DownloadChoice,
    build_download_plan,
    describe_quality_difference,
    download_file_stem,
    download_source_url,
    requires_ffmpeg,
    safe_folder_name,
    select_download_items,
    unique_file_stem,
)
from ..download.runner import DownloadCancelled, DownloadCancelToken, run_download
from ..i18n import _
from ..library.playlist_io import is_remote_media_path
from ..log import get_logger
from ..task_failures_dialog import offer_task_failures
from .playback.live import is_live_media
from .selection import selected_list_entries
from .task_progress import TaskProgressMixin


_logger = get_logger(__name__)

# Intervalo mínimo entre atualizações da barra de status, para o progresso não
# disparar um redesenho a cada bloco baixado.
_STATUS_UPDATE_INTERVAL_SECONDS = 0.5


class FrameDownloadMixin(TaskProgressMixin):
    def _initialize_download_state(self):
        self._download_token = None
        self._download_percent = None
        self._download_title = ""
        self._download_last_status_at = 0.0
        self._download_batch_index = 1
        self._download_batch_total = 1

    def _download_in_progress(self):
        return getattr(self, "_download_token", None) is not None

    def _shutdown_download(self):
        token = getattr(self, "_download_token", None)
        if token is not None:
            token.cancel()

    # -- Pontos de entrada -------------------------------------------------------

    def on_download_current_media(self, _event=None):
        if self._download_in_progress():
            self._offer_to_cancel_download()
            return

        media_path = self._current_download_media_path()
        if not media_path:
            self._announce(_("Nenhuma mídia está tocando no momento."))
            return

        player = getattr(self, "player", None)
        if player is not None and is_live_media(player.get_media()):
            self._announce(_("Não é possível baixar uma transmissão ao vivo."))
            return

        if not download_source_url(media_path):
            if is_remote_media_path(media_path):
                self._announce(_("O download só está disponível para mídias do YouTube e do YouTube Music."))
            else:
                self._announce(_("Esta mídia já está no seu computador."))
            return

        self._begin_download([(media_path, self._current_download_media_title())])

    def on_download_selection(self, _event=None):
        """Baixa os itens selecionados na lista da aba atual."""
        entries = selected_list_entries(self)
        if not entries:
            self._announce(_("Nenhum item selecionado para baixar."))
            return
        self._begin_download(entries)

    def on_download_playlist(self, _event=None):
        """Baixa todos os itens da playlist da aba atual, numa pasta com o nome dela."""
        state = self._get_playlist_state()
        if state is None or getattr(state, "is_folder_tab", False) or not getattr(state, "items", None):
            self._announce(_("Esta aba não tem uma playlist para baixar."))
            return

        labels = list(getattr(state, "browser_item_labels", None) or [])
        entries = [
            (path, labels[index] if index < len(labels) else "")
            for index, path in enumerate(state.items)
        ]
        self._begin_download(entries, folder_name=safe_folder_name(state.title))

    def download_media_entries(self, entries, *, folder_name=""):
        """Baixa ``(caminho ou URL, título)`` vindos de outras telas, como a busca do YouTube."""
        self._begin_download(list(entries), folder_name=folder_name)

    # -- Fluxo -------------------------------------------------------------------

    def _begin_download(self, entries, *, folder_name=""):
        if self._download_in_progress():
            self._offer_to_cancel_download()
            return

        selection = select_download_items(entries)
        if not selection.items:
            self._announce(_("Nada para baixar: só mídias do YouTube e do YouTube Music podem ser baixadas."))
            return

        count = len(selection.items)
        title = selection.items[0].title if count == 1 else ""
        choice = self._choose_download_options(title, count)
        if choice is None:
            return

        if count > 1 and not self._confirm_batch_download(selection, choice, folder_name):
            return

        install_ffmpeg = self._confirm_ffmpeg_installation(choice)
        if install_ffmpeg is None:
            return

        self._start_download(selection.items, choice, install_ffmpeg=install_ffmpeg, folder_name=folder_name)

    def _current_download_media_path(self):
        state = self._get_active_playlist_state()
        return str(getattr(state, "current_media_path", "") or "").strip() if state else ""

    def _current_download_media_title(self):
        # O mesmo nome que a janela mostra para a mídia atual.
        media_label = getattr(self, "_media_label", None)
        media_path = self._current_download_media_path()
        if callable(media_label) and media_path:
            label = str(media_label(media_path) or "").strip()
            if label:
                return label

        state = self._get_active_playlist_state()
        if state is None:
            return ""
        labels = getattr(state, "browser_item_labels", None) or []
        index = getattr(state, "current_index", -1)
        if 0 <= index < len(labels):
            return str(labels[index] or "").strip()
        return ""

    def _choose_download_options(self, media_title, item_count=1):
        """Devolve o :class:`DownloadChoice` a baixar, ou None se o usuário desistir."""
        settings = self.settings
        if not settings.download_always_ask:
            return DownloadChoice(
                kind=settings.download_kind,
                audio_quality=settings.download_audio_quality,
                video_quality=settings.download_video_quality,
                sample_rate=settings.download_sample_rate,
                directory=resolve_download_directory(settings.download_directory),
            )

        dialog = DownloadDialog(self, settings, media_title=media_title, item_count=item_count)
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return None
            choice = dialog.get_choice()
            self._remember_download_choice(choice, dialog.get_directory_setting(), dialog.always_ask())
        finally:
            dialog.Destroy()
        return choice

    def _remember_download_choice(self, choice, directory_setting, always_ask):
        # A última escolha vira o padrão das Preferências, então o próximo
        # diálogo já abre como o usuário deixou.
        settings = self.settings
        settings.download_kind = choice.kind
        settings.download_audio_quality = choice.audio_quality
        settings.download_video_quality = choice.video_quality
        settings.download_sample_rate = choice.sample_rate
        settings.download_directory = directory_setting
        settings.download_always_ask = always_ask
        self._save_settings()

    def _confirm_batch_download(self, selection, choice, folder_name):
        """Pede confirmação antes de uma fila: ela pode ser longa e ocupar disco."""
        destination = os.path.join(choice.directory, folder_name) if folder_name else choice.directory
        lines = [
            _("Baixar {count} itens do YouTube para a pasta:").format(count=len(selection.items)),
            destination,
        ]
        if selection.skipped:
            lines.append("")
            lines.append(
                _("{count} itens que não são do YouTube serão ignorados.").format(count=selection.skipped)
            )
        if selection.truncated:
            lines.append("")
            lines.append(
                _("Só os primeiros {limit} itens serão baixados; {count} ficarão de fora.").format(
                    limit=MAX_BATCH_ITEMS, count=selection.truncated
                )
            )
        response = wx.MessageBox(
            "\n".join(lines),
            _("Baixar mídia"),
            wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION,
            self,
        )
        return response == wx.YES

    def _confirm_ffmpeg_installation(self, choice):
        """True para instalar o FFmpeg antes de baixar, False para seguir sem
        ele (qualidade original) e None para cancelar o download."""
        if not requires_ffmpeg(choice) or find_ffmpeg_directory() is not None:
            return False

        if not ffmpeg_install_supported():
            self._announce(
                _("O FFmpeg não foi encontrado. O download seguirá na qualidade original, sem conversão.")
            )
            return False

        what = (
            _("unir o vídeo e o áudio")
            if choice.kind == DOWNLOAD_KIND_VIDEO
            else _("converter o áudio")
        )
        message = _(
            "Para {what} o KeyTune precisa do FFmpeg, que não foi encontrado. "
            "Ele será baixado das versões oficiais (cerca de {size} MB) e guardado na pasta de recursos do KeyTune.\n\n"
            "Sim: instalar o FFmpeg e baixar.\n"
            "Não: baixar agora na qualidade original, sem conversão.\n"
            "Cancelar: não baixar."
        ).format(what=what, size=FFMPEG_APPROXIMATE_DOWNLOAD_MB)
        response = wx.MessageBox(
            message,
            _("FFmpeg necessário"),
            wx.YES_NO | wx.CANCEL | wx.YES_DEFAULT | wx.ICON_QUESTION,
            self,
        )
        if response == wx.YES:
            return True
        if response == wx.NO:
            return False
        return None

    def _start_download(self, items, choice, *, install_ffmpeg, folder_name=""):
        token = DownloadCancelToken()
        self._download_token = token
        self._download_percent = None
        self._download_title = items[0].title if len(items) == 1 else ""
        self._download_last_status_at = 0.0
        self._download_batch_index = 1
        self._download_batch_total = len(items)

        if len(items) > 1:
            self._announce(_("Iniciando o download de {count} itens.").format(count=len(items)))
        else:
            self._announce(_("Iniciando o download."))
        self._set_status_message(_("Baixando..."), auto_clear_ms=0)
        self._set_task_progress("download", None)

        worker = threading.Thread(
            target=self._download_worker,
            args=(tuple(items), choice, token, install_ffmpeg, folder_name),
            name="keytune-download",
            daemon=True,
        )
        worker.start()

    def _download_worker(self, items, choice, token, install_ffmpeg, folder_name):
        cookie_file_path = ""
        try:
            from ..youtube_music.auth import (
                create_temporary_browser_auth_cookie_file,
                load_saved_playback_auth,
            )
            from ..youtube_music.dependencies import ensure_yt_dlp_executable_available
            from ..youtube_music.yt_dlp_runtime import find_all_available_javascript_runtimes

            ensure_yt_dlp_executable_available()

            if install_ffmpeg:
                wx.CallAfter(self._set_download_status, _("Instalando o FFmpeg..."))
                install_managed_ffmpeg(
                    progress_callback=self._make_ffmpeg_progress_callback(),
                    cancel_event=token.event,
                )
                wx.CallAfter(self._set_download_status, _("Baixando..."))

            ffmpeg_directory = find_ffmpeg_directory()
            plan = build_download_plan(choice, ffmpeg_available=ffmpeg_directory is not None)

            playback_auth = load_saved_playback_auth()
            if playback_auth.cookie_header:
                cookie_file_path = create_temporary_browser_auth_cookie_file(playback_auth.cookie_header)

            item_choice = choice
            if folder_name:
                item_choice = dataclasses.replace(choice, directory=os.path.join(choice.directory, folder_name))
            js_runtimes = find_all_available_javascript_runtimes()

            results = []
            failures = []
            cancelled = False
            used_stems = set()
            for position, item in enumerate(items, start=1):
                if token.cancelled:
                    cancelled = True
                    break
                wx.CallAfter(self._on_download_item_started, token, position)
                try:
                    result = run_download(
                        item.url,
                        item_choice,
                        plan,
                        ffmpeg_directory=str(ffmpeg_directory or ""),
                        cookie_file_path=cookie_file_path,
                        http_headers=playback_auth.yt_dlp_http_headers,
                        js_runtimes=js_runtimes,
                        # O arquivo leva o mesmo nome que o KeyTune mostra para o item.
                        file_stem=unique_file_stem(download_file_stem(item.title), used_stems),
                        progress_callback=self._on_download_progress,
                        processing_callback=lambda: wx.CallAfter(self._on_download_processing),
                        cancel_token=token,
                    )
                except DownloadCancelled:
                    cancelled = True
                    break
                except Exception as exc:
                    _logger.warning("Download failed: %s", exc)
                    failures.append((item.title, str(exc)))
                else:
                    results.append(result)
        except FFmpegInstallCancelled:
            wx.CallAfter(self._on_download_cancelled, token)
        except Exception as exc:
            _logger.warning("Download failed: %s", exc)
            wx.CallAfter(self._on_download_failed, token, str(exc))
        else:
            wx.CallAfter(
                self._dispatch_download_outcome, token, choice, plan, tuple(results), tuple(failures), len(items), cancelled
            )
        finally:
            if cookie_file_path:
                try:
                    os.remove(cookie_file_path)
                except OSError:
                    pass

    def _dispatch_download_outcome(self, token, choice, plan, results, failures, total, cancelled):
        if cancelled:
            self._on_download_cancelled(token, done=len(results), total=total)
        elif total == 1 and results:
            self._on_download_finished(token, choice, plan, results[0])
        elif total == 1:
            self._on_download_failed(token, failures[0][1] if failures else "")
        else:
            self._on_batch_download_finished(token, plan, results, failures, total)

    def _make_ffmpeg_progress_callback(self):
        def report(downloaded, total):
            if total:
                self._on_download_progress_percent(int(downloaded * 100 / total))

        return report

    # -- Chamadas vindas da thread de download (sempre via wx.CallAfter) --------

    def _on_download_progress(self, progress):
        percent = progress.percent
        if percent is not None:
            self._on_download_progress_percent(percent)

    def _on_download_progress_percent(self, percent):
        now = time.monotonic()
        # Lida na thread de download; a barra só é atualizada de tempos em tempos.
        self._download_percent = percent
        if now - self._download_last_status_at < _STATUS_UPDATE_INTERVAL_SECONDS:
            return
        self._download_last_status_at = now
        wx.CallAfter(self._update_download_progress, percent)

    def _download_status_text(self, percent):
        if self._download_batch_total > 1:
            return _("Baixando {index} de {total}... {percent}%").format(
                index=self._download_batch_index, total=self._download_batch_total, percent=percent
            )
        return _("Baixando... {percent}%").format(percent=percent)

    def _update_download_progress(self, percent):
        """Texto da barra de status e barra de progresso, na thread da interface."""
        if not self._download_in_progress():
            return
        self._set_status_message(self._download_status_text(percent), auto_clear_ms=0)
        self._set_task_progress("download", self._download_overall_percent(percent))

    def _download_overall_percent(self, item_percent):
        # Numa fila, cada item vale uma fatia igual da barra.
        total = max(1, self._download_batch_total)
        return ((self._download_batch_index - 1) * 100 + item_percent) / total

    def _on_download_processing(self):
        if not self._download_in_progress():
            return
        self._set_status_message(_("Processando o arquivo..."), auto_clear_ms=0)
        self._set_task_progress("download", self._download_overall_percent(100))

    def _on_download_item_started(self, token, position):
        if self._download_token is not token:
            return
        self._download_batch_index = position
        self._download_percent = None
        self._set_task_progress("download", self._download_overall_percent(0) if position > 1 else None)
        if self._download_batch_total > 1:
            self._set_status_message(
                _("Baixando {index} de {total}...").format(index=position, total=self._download_batch_total),
                auto_clear_ms=0,
            )

    def _set_download_status(self, message):
        if self._download_in_progress():
            self._set_status_message(message, auto_clear_ms=0)

    def _finish_download_state(self, token):
        if self._download_token is not token:
            return False
        self._download_token = None
        self._download_percent = None
        self._download_batch_index = 1
        self._download_batch_total = 1
        self._clear_task_progress("download")
        return True

    def _on_download_finished(self, token, choice, plan, result):
        if not self._finish_download_state(token):
            return

        file_name = os.path.basename(result.paths[0]) if result.paths else ""
        parts = [_("Download concluído: {name}.").format(name=file_name)]
        if plan.reduced_without_ffmpeg:
            parts.append(_("Sem o FFmpeg, o arquivo foi baixado na qualidade original, sem conversão."))
        difference = describe_quality_difference(choice, result.height)
        if difference:
            parts.append(difference)
        message = " ".join(parts)
        _logger.info("Download finished: %s", file_name)
        self._set_status_message(message)
        self._announce(message)

    def _on_batch_download_finished(self, token, plan, results, failures, total):
        if not self._finish_download_state(token):
            return

        done = len(results)
        if done == 0:
            reason = failures[0][1] if failures else ""
            message = _("Não foi possível baixar nenhum dos {total} itens: {reason}").format(
                total=total, reason=reason
            )
        else:
            folder = os.path.dirname(results[0].paths[0]) if results[0].paths else ""
            if failures:
                message = _("Download concluído: {done} de {total} itens em {folder}. {failed} falharam.").format(
                    done=done, total=total, folder=folder, failed=len(failures)
                )
            else:
                message = _("Download concluído: {done} itens em {folder}.").format(done=done, folder=folder)
        parts = [message]
        if done and plan.reduced_without_ffmpeg:
            parts.append(_("Sem o FFmpeg, os arquivos foram baixados na qualidade original, sem conversão."))
        message = " ".join(parts)
        for title, reason in failures:
            _logger.warning("Batch download item failed (%s): %s", title, reason)
        self._set_status_message(message)
        self._announce(message)
        if failures and done:
            wx.CallAfter(offer_task_failures, self, _("Falhas no download"), failures)

    def _on_download_failed(self, token, reason):
        if not self._finish_download_state(token):
            return
        message = _("Não foi possível baixar a mídia: {reason}").format(reason=reason)
        self._set_status_message(message)
        self._announce(message)

    def _on_download_cancelled(self, token, done=0, total=1):
        if not self._finish_download_state(token):
            return
        if total > 1 and done:
            message = _("Download cancelado. {done} de {total} itens já foram baixados.").format(
                done=done, total=total
            )
        else:
            message = _("Download cancelado.")
        self._set_status_message(message)
        self._announce(message)

    def _offer_to_cancel_download(self):
        percent = self._download_percent
        if self._download_batch_total > 1:
            state_text = _("Download em andamento: item {index} de {total}.").format(
                index=self._download_batch_index, total=self._download_batch_total
            )
        elif percent is not None:
            state_text = _("Download em andamento: {percent}%.").format(percent=percent)
        else:
            state_text = _("Download em andamento.")
        response = wx.MessageBox(
            state_text + "\n\n" + _("Deseja cancelar o download?"),
            _("Baixar mídia"),
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
            self,
        )
        if response == wx.YES and self._download_token is not None:
            self._download_token.cancel()
