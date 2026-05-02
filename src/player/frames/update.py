from __future__ import annotations

import threading

import wx

from ..constants import STARTUP_UPDATE_CHECK_DELAY_MS
from ..update import (
    UpdateAvailableDialog,
    UpdateDownloadDialog,
    UpdateError,
    can_self_update,
    check_for_update,
    format_byte_count,
    launch_external_updater,
    unsupported_install_message,
)


class FrameUpdateMixin:
    def _schedule_startup_update_check(self):
        if self._startup_update_check_scheduled or not can_self_update():
            return

        self._startup_update_check_scheduled = True
        wx.CallLater(STARTUP_UPDATE_CHECK_DELAY_MS, self._start_update_check, False)

    def on_check_for_updates(self, _event):
        self._on_manual_check_for_additional_updates()
        self._start_update_check(manual=True)

    def _on_manual_check_for_additional_updates(self):
        return None

    def _start_update_check(self, manual=False):
        if self._update_check_in_progress:
            if manual:
                wx.MessageBox(
                    "A verificação já está em andamento.",
                    "Atualizações",
                    wx.OK | wx.ICON_INFORMATION,
                    self,
                )
            return

        self._update_check_in_progress = True
        worker_thread = threading.Thread(target=self._update_check_worker, args=(manual,), daemon=True)
        worker_thread.start()

    def _update_check_worker(self, manual):
        try:
            update_info = check_for_update()
        except UpdateError as exc:
            wx.CallAfter(self._finish_update_check, manual, None, str(exc))
            return
        except Exception:
            wx.CallAfter(self._finish_update_check, manual, None, "Não foi possível verificar as atualizações.")
            return

        wx.CallAfter(self._finish_update_check, manual, update_info, "")

    def _finish_update_check(self, manual, update_info, error_message):
        self._update_check_in_progress = False

        if error_message:
            if manual:
                wx.MessageBox(error_message, "Atualizações", wx.OK | wx.ICON_ERROR, self)
            return

        if update_info is None:
            if manual:
                wx.MessageBox(
                    "Você já está na versão mais recente.",
                    "Atualizações",
                    wx.OK | wx.ICON_INFORMATION,
                    self,
                )
            return

        self._prompt_for_update(update_info, manual=manual)

    def _prompt_for_update(self, update_info, *, manual):
        install_message = ""
        if not can_self_update():
            install_message = unsupported_install_message()

        with UpdateAvailableDialog(self, update_info, install_message=install_message) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return

        if not can_self_update():
            wx.MessageBox(
                unsupported_install_message(),
                "Atualizações",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return

        self._download_and_install_update(update_info)

    def _download_and_install_update(self, update_info):
        dialog = UpdateDownloadDialog(self, update_info)
        try:
            dialog_result = dialog.ShowModal()
            downloaded_file_path = dialog.downloaded_file_path
            error_message = dialog.error_message
            was_cancelled = dialog.was_cancelled
        finally:
            dialog.Destroy()

        if dialog_result != wx.ID_OK:
            if error_message:
                wx.MessageBox(error_message, "Atualizações", wx.OK | wx.ICON_ERROR, self)
            elif was_cancelled:
                self._announce("Download da atualização cancelado.")
            return

        try:
            self._save_settings()
            self._save_session()
            launch_external_updater(downloaded_file_path)
        except UpdateError as exc:
            wx.MessageBox(str(exc), "Atualizações", wx.OK | wx.ICON_ERROR, self)
            return

        self._update_restart_pending = True
        self._announce("Atualização baixada. O player será reiniciado para concluir a instalação.")
        self.Close()
