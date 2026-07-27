from __future__ import annotations

import threading

import wx

from ..i18n import _
from .service import (
    UpdateCancelledError,
    UpdateError,
    UpdateInfo,
    download_release_archive,
    format_byte_count,
    release_notes_to_plain_text,
)


class UpdateAvailableDialog(wx.Dialog):
    def __init__(self, parent, update_info: UpdateInfo, *, install_message: str = ""):
        super().__init__(
            parent,
            title=_("Atualização disponível"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.update_info = update_info
        panel = wx.Panel(self)
        root_sizer = wx.BoxSizer(wx.VERTICAL)

        size_label = (
            format_byte_count(update_info.archive_size_bytes)
            if update_info.archive_size_bytes > 0
            else _("tamanho não informado")
        )
        details_label = wx.StaticText(
            panel,
            label=_(
                "Nova versão disponível: {current} → {latest}.\n"
                "Arquivo: {file}.\n"
                "Tamanho do download: {size}."
            ).format(
                current=update_info.current_version,
                latest=update_info.latest_version,
                file=update_info.archive_name,
                size=size_label,
            ),
        )
        details_label.Wrap(560)
        details_label.SetName(_("Resumo da atualização"))

        notes_label = wx.StaticText(panel, label=_("O que mudou nesta versão:"))
        notes_label.SetName(_("Título das mudanças"))

        self.notes_ctrl = wx.TextCtrl(
            panel,
            value=self._format_release_notes(update_info.release_notes),
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_BESTWRAP,
        )
        self.notes_ctrl.SetMinSize((560, 240))
        self.notes_ctrl.SetName(_("Mudanças da atualização"))

        root_sizer.Add(details_label, 0, wx.ALL | wx.EXPAND, 10)
        root_sizer.Add(notes_label, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 10)
        root_sizer.Add(self.notes_ctrl, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

        if install_message:
            warning_label = wx.StaticText(panel, label=install_message)
            warning_label.Wrap(560)
            warning_label.SetName(_("Aviso sobre instalação"))
            root_sizer.Add(warning_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

        button_sizer = wx.StdDialogButtonSizer()
        self.download_button = wx.Button(panel, wx.ID_OK, _("&Baixar e instalar"))
        self.cancel_button = wx.Button(panel, wx.ID_CANCEL, _("A&gora não"))
        self.download_button.SetDefault()
        button_sizer.AddButton(self.download_button)
        button_sizer.AddButton(self.cancel_button)
        button_sizer.Realize()
        root_sizer.Add(button_sizer, 0, wx.ALL | wx.EXPAND, 10)

        panel.SetSizer(root_sizer)

        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizerAndFit(frame_sizer)
        self.SetMinSize((620, 460))
        self.SetEscapeId(wx.ID_CANCEL)
        self.CentreOnParent()

    def _format_release_notes(self, release_notes: str) -> str:
        normalized_notes = release_notes_to_plain_text(release_notes)
        if normalized_notes:
            return normalized_notes
        return _("As notas desta versão ainda não foram publicadas na release do GitHub.")


class UpdateDownloadDialog(wx.Dialog):
    def __init__(self, parent, update_info: UpdateInfo):
        super().__init__(
            parent,
            title=_("Baixando atualização"),
            style=wx.DEFAULT_DIALOG_STYLE,
        )

        self.update_info = update_info
        self.downloaded_file_path = None
        self.error_message = ""
        self.was_cancelled = False
        self._cancel_event = threading.Event()
        self._worker_thread = None
        self._finished = False
        self._cancel_requested = False

        panel = wx.Panel(self)
        root_sizer = wx.BoxSizer(wx.VERTICAL)

        self.status_label = wx.StaticText(
            panel,
            label=_("Preparando o download da versão {version}...").format(version=self.update_info.latest_version),
        )
        self.status_label.Wrap(420)
        self.status_label.SetName(_("Status do download"))

        self.progress_gauge = wx.Gauge(panel, range=1000, style=wx.GA_HORIZONTAL | wx.GA_SMOOTH)
        self.progress_gauge.SetName(_("Progresso do download"))

        self.detail_label = wx.StaticText(panel, label=_("Aguardando resposta do servidor..."))
        self.detail_label.Wrap(420)
        self.detail_label.SetName(_("Detalhes do download"))

        root_sizer.Add(self.status_label, 0, wx.ALL | wx.EXPAND, 10)
        root_sizer.Add(self.progress_gauge, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
        root_sizer.Add(self.detail_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

        button_sizer = wx.StdDialogButtonSizer()
        self.cancel_button = wx.Button(panel, wx.ID_CANCEL, _("&Cancelar"))
        button_sizer.AddButton(self.cancel_button)
        button_sizer.Realize()
        root_sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 10)

        panel.SetSizer(root_sizer)

        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizerAndFit(frame_sizer)
        self.SetMinSize((480, 220))
        # ESC must trigger a graceful cancel (waiting for the worker thread)
        # instead of letting wx end the modal directly via the Cancel button.
        self.SetEscapeId(wx.ID_NONE)
        self.CentreOnParent()

        self.cancel_button.Bind(wx.EVT_BUTTON, self.on_cancel)
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_key_down)
        wx.CallAfter(self._start_download)

    def _start_download(self):
        if self._worker_thread is not None:
            return

        self._worker_thread = threading.Thread(target=self._download_worker, daemon=True)
        self._worker_thread.start()

    def _download_worker(self):
        try:
            downloaded_file_path = download_release_archive(
                self.update_info,
                progress_callback=self._queue_progress_update,
                cancel_event=self._cancel_event,
            )
        except UpdateCancelledError:
            wx.CallAfter(self._finish_cancelled)
            return
        except UpdateError as exc:
            wx.CallAfter(self._finish_with_error, str(exc))
            return
        except Exception:
            wx.CallAfter(self._finish_with_error, _("Não foi possível baixar a atualização."))
            return

        wx.CallAfter(self._finish_successfully, str(downloaded_file_path))

    def _queue_progress_update(self, downloaded_bytes, total_bytes, status_message):
        wx.CallAfter(self._apply_progress_update, downloaded_bytes, total_bytes, status_message)

    def _apply_progress_update(self, downloaded_bytes, total_bytes, status_message):
        if status_message:
            self.status_label.SetLabel(status_message)

        downloaded_label = format_byte_count(downloaded_bytes)
        if total_bytes > 0:
            total_label = format_byte_count(total_bytes)
            progress = int(round((downloaded_bytes / total_bytes) * 1000)) if total_bytes else 0
            self.progress_gauge.SetValue(max(0, min(1000, progress)))
            percentage = int(round((downloaded_bytes / total_bytes) * 100)) if total_bytes else 0
            self.detail_label.SetLabel(
                _("{downloaded} de {total} baixados ({percent}%).").format(
                    downloaded=downloaded_label, total=total_label, percent=percentage
                )
            )
            return

        self.progress_gauge.Pulse()
        self.detail_label.SetLabel(_("{downloaded} baixados.").format(downloaded=downloaded_label))

    def _finish_successfully(self, downloaded_file_path: str):
        self._finished = True
        self.downloaded_file_path = downloaded_file_path
        self.progress_gauge.SetValue(1000)
        self.status_label.SetLabel(_("Download concluído."))
        if self.IsModal():
            self.EndModal(wx.ID_OK)

    def _finish_with_error(self, error_message: str):
        self._finished = True
        self.error_message = error_message
        if self.IsModal():
            self.EndModal(wx.ID_CANCEL)

    def _finish_cancelled(self):
        self._finished = True
        self.was_cancelled = True
        self.error_message = ""
        if self.IsModal():
            self.EndModal(wx.ID_CANCEL)

    def _request_cancel(self):
        if self._finished or self._cancel_requested:
            return

        self._cancel_requested = True
        self._cancel_event.set()
        self.cancel_button.Disable()
        self.status_label.SetLabel(_("Cancelando..."))
        self.detail_label.SetLabel(_("Aguarde um momento."))

    def on_cancel(self, _event):
        self._request_cancel()

    def on_key_down(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self._request_cancel()
            return
        event.Skip()

    def on_close(self, event):
        if self._finished:
            event.Skip()
            return

        self._request_cancel()
        event.Veto()
