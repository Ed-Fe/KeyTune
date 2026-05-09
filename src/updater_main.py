from __future__ import annotations

import argparse
import ctypes
import threading
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import datetime
from pathlib import Path

import wx


LOG_DIRECTORY = Path(tempfile.gettempdir()) / "KeyTuneUpdater"
LOG_FILE_PATH = LOG_DIRECTORY / "updater.log"
WAIT_OBJECT_0 = 0x00000000
WAIT_TIMEOUT = 0x00000102
WAIT_FAILED = 0xFFFFFFFF
SYNCHRONIZE = 0x00100000


class UpdateProgressDialog(wx.Dialog):
    def __init__(self, parent=None):
        super().__init__(
            parent,
            title="Atualizando KeyTune",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.succeeded = False
        self.error_message = ""
        self._finished = False
        self._allow_close = False
        self._pulse_timer = wx.Timer(self)

        self.Bind(wx.EVT_TIMER, self._on_pulse, self._pulse_timer)
        self.Bind(wx.EVT_CLOSE, self.on_close)

        panel = wx.Panel(self)
        root_sizer = wx.BoxSizer(wx.VERTICAL)

        self.status_label = wx.StaticText(panel, label="Preparando a atualização...")
        self.status_label.Wrap(460)
        self.status_label.SetName("Status da atualização")
        self.status_label.SetHelpText("Mostra a etapa atual do instalador da atualização.")

        self.detail_label = wx.StaticText(
            panel,
            label="Aguarde enquanto aplicamos a atualização.",
        )
        self.detail_label.Wrap(460)
        self.detail_label.SetName("Detalhes da atualização")
        self.detail_label.SetHelpText("Mostra detalhes sobre o passo atual da atualização.")

        self.progress_gauge = wx.Gauge(panel, range=100, style=wx.GA_HORIZONTAL | wx.GA_SMOOTH)
        self.progress_gauge.SetName("Progresso da atualização")
        self.progress_gauge.SetHelpText("Mostra que a atualização ainda está em andamento.")

        root_sizer.Add(self.status_label, 0, wx.ALL | wx.EXPAND, 10)
        root_sizer.Add(self.detail_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
        root_sizer.Add(self.progress_gauge, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

        button_sizer = wx.StdDialogButtonSizer()
        self.close_button = wx.Button(panel, wx.ID_CLOSE, "&Fechar")
        self.close_button.Disable()
        self.close_button.Bind(wx.EVT_BUTTON, self.on_close_button)
        button_sizer.AddButton(self.close_button)
        button_sizer.Realize()
        root_sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 10)

        panel.SetSizer(root_sizer)

        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizerAndFit(frame_sizer)
        self.SetMinSize((520, 220))
        self.CentreOnScreen()

        self._pulse_timer.Start(120)

    def _on_pulse(self, _event):
        if not self._finished:
            self.progress_gauge.Pulse()

    def update_status(self, title: str, detail: str = ""):
        self.status_label.SetLabel(title)
        self.detail_label.SetLabel(detail or " ")
        self.status_label.Wrap(460)
        self.detail_label.Wrap(460)
        self.Layout()

    def finish_successfully(self):
        if self._finished:
            return

        self._finished = True
        self.succeeded = True
        self._pulse_timer.Stop()
        self.progress_gauge.SetValue(self.progress_gauge.GetRange())
        self.update_status(
            "Atualização concluída.",
            "O aplicativo será aberto em instantes.",
        )
        self.close_button.Enable()
        wx.CallLater(900, self._close_after_success)

    def finish_with_error(self, error_message: str):
        if self._finished:
            return

        self._finished = True
        self.error_message = error_message
        self._allow_close = True
        self._pulse_timer.Stop()
        self.update_status(
            "Não deu para concluir a atualização.",
            error_message,
        )
        self.close_button.Enable()
        self.close_button.SetFocus()

    def _close_after_success(self):
        self._allow_close = True
        self.Close()

    def on_close_button(self, _event):
        self.Close()

    def on_close(self, event):
        if not self._allow_close:
            event.Veto()
            return

        event.Skip()


def main() -> int:
    args = parse_args()
    log_message("Iniciando atualizador externo.")
    log_message(f"Pasta do aplicativo: {args.app_dir}")
    log_message(f"Pacote recebido: {args.package}")

    try:
        return run_interactive_update(args)
    except Exception as exc:
        log_message(f"Falha ao iniciar a janela do atualizador: {exc}")

    try:
        run_update(args)
    except Exception as exc:
        log_message(f"Falha durante a atualização: {exc}")
        show_error_message(
            "Não foi possível atualizar agora."
        )
        return 1

    log_message("Atualização concluída com sucesso.")
    return 0


def run_interactive_update(args) -> int:
    app = wx.App(False)
    dialog = UpdateProgressDialog(None)

    worker_thread = threading.Thread(
        target=_update_worker,
        args=(args, dialog),
        daemon=True,
    )
    worker_thread.start()

    dialog.Show()
    app.MainLoop()

    if dialog.error_message:
        return 1
    return 0


def _update_worker(args, dialog: UpdateProgressDialog):
    try:
        run_update(
            args,
            status_callback=lambda title, detail="": wx.CallAfter(dialog.update_status, title, detail),
        )
    except Exception as exc:
        log_message(f"Falha durante a atualização: {exc}")
        wx.CallAfter(dialog.finish_with_error, str(exc))
        return

    log_message("Atualização concluída com sucesso.")
    wx.CallAfter(dialog.finish_successfully)


def parse_args():
    parser = argparse.ArgumentParser(description="Aplica uma atualização do KeyTune a partir de um arquivo ZIP.")
    parser.add_argument("--parent-pid", type=int, required=True)
    parser.add_argument("--app-dir", required=True)
    parser.add_argument("--package", required=True)
    parser.add_argument("--restart-executable", required=True)
    return parser.parse_args()


def run_update(args, *, status_callback=None):
    app_dir = Path(args.app_dir).resolve()
    package_path = Path(args.package).resolve()
    restart_executable = str(args.restart_executable).strip()
    if not app_dir.exists() or not app_dir.is_dir():
        raise FileNotFoundError(f"Pasta do aplicativo não encontrada: {app_dir}")
    if not package_path.exists() or not package_path.is_file():
        raise FileNotFoundError(f"Pacote de atualização não encontrado: {package_path}")

    _report_status(
        status_callback,
        "Aguardando o fechamento do player.",
        "",
    )
    wait_for_process_exit(args.parent_pid, timeout_seconds=120)

    working_directory = _create_working_directory(app_dir)
    extract_directory = working_directory / "extract"
    backup_directory = working_directory / "backup"

    _report_status(
        status_callback,
        "Preparando a atualização.",
        "",
    )
    extract_release_archive(package_path, extract_directory)
    payload_root = locate_payload_root(extract_directory)

    _report_status(
        status_callback,
        "Guardando a versão atual.",
        "",
    )
    backup_installation(app_dir, backup_directory)

    try:
        _report_status(
            status_callback,
            "Aplicando a atualização.",
            "",
        )
        replace_installation(app_dir, payload_root)
    except Exception:
        _report_status(
            status_callback,
            "Não deu para aplicar a atualização.",
            "",
        )
        restore_installation(app_dir, backup_directory)
        raise

    restart_path = app_dir / restart_executable
    _report_status(
        status_callback,
        "Pronto.",
        "",
    )
    restart_application(restart_path)


def wait_for_process_exit(process_id: int, *, timeout_seconds: int):
    kernel32 = ctypes.windll.kernel32
    process_handle = kernel32.OpenProcess(SYNCHRONIZE, False, int(process_id))
    if not process_handle:
        log_message("Processo principal já havia encerrado.")
        return

    try:
        wait_result = kernel32.WaitForSingleObject(process_handle, timeout_seconds * 1000)
        if wait_result == WAIT_OBJECT_0:
            return
        if wait_result == WAIT_TIMEOUT:
            raise TimeoutError("Tempo esgotado aguardando o encerramento do aplicativo.")
        if wait_result == WAIT_FAILED:
            raise OSError("Falha ao aguardar o encerramento do processo principal.")
        raise OSError(f"Resultado inesperado ao aguardar o processo principal: {wait_result}")
    finally:
        kernel32.CloseHandle(process_handle)


def extract_release_archive(package_path: Path, extract_directory: Path):
    extract_directory.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(package_path) as archive_file:
        safe_extract_all(archive_file, extract_directory)


def safe_extract_all(archive_file: zipfile.ZipFile, extract_directory: Path):
    target_root = extract_directory.resolve()
    for member in archive_file.infolist():
        target_path = (extract_directory / member.filename).resolve()
        try:
            target_path.relative_to(target_root)
        except ValueError as exc:
            raise ValueError("O pacote de atualização contém caminhos inválidos.")
        except Exception as exc:
            raise ValueError("Não foi possível validar os caminhos do pacote de atualização.") from exc
    archive_file.extractall(extract_directory)


def locate_payload_root(extract_directory: Path) -> Path:
    entries = [entry for entry in extract_directory.iterdir() if entry.name not in {"__MACOSX"}]
    if not entries:
        raise ValueError("O pacote de atualização foi extraído, mas não contém arquivos válidos.")
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return extract_directory


def backup_installation(source_directory: Path, backup_directory: Path):
    if backup_directory.exists():
        shutil.rmtree(backup_directory, ignore_errors=True)
    backup_directory.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source_directory), str(backup_directory))


def replace_installation(target_directory: Path, payload_root: Path):
    remove_path(target_directory)
    shutil.move(str(payload_root), str(target_directory))


def restore_installation(target_directory: Path, backup_directory: Path):
    remove_path(target_directory)
    shutil.move(str(backup_directory), str(target_directory))


def remove_path(path: Path):
    if not path.exists():
        return

    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path, ignore_errors=False)
        return

    path.unlink(missing_ok=True)


def _create_working_directory(app_dir: Path) -> Path:
    preferred_parent = app_dir.parent
    try:
        return Path(tempfile.mkdtemp(prefix="keytune-updater-job-", dir=str(preferred_parent)))
    except OSError as exc:
        log_message(
            f"Não foi possível criar a área temporária ao lado da instalação: {exc}. Usando a pasta temporária do sistema."
        )
        return Path(tempfile.mkdtemp(prefix="keytune-updater-job-"))


def restart_application(executable_path: Path):
    if not executable_path.exists():
        raise FileNotFoundError(f"Executável principal não encontrado após a atualização: {executable_path}")

    creation_flags = 0
    creation_flags |= getattr(subprocess, "DETACHED_PROCESS", 0)
    creation_flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    creation_flags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)

    subprocess.Popen(
        [str(executable_path)],
        cwd=str(executable_path.parent),
        close_fds=True,
        creationflags=creation_flags,
    )


def log_message(message: str):
    LOG_DIRECTORY.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE_PATH, "a", encoding="utf-8") as log_file:
        log_file.write(f"[{timestamp}] {message}\n")


def show_error_message(message: str):
    try:
        ctypes.windll.user32.MessageBoxW(0, message, "Atualização do KeyTune", 0x10)
    except Exception:
        print(message, file=sys.stderr)
        time.sleep(5)


def _report_status(status_callback, title: str, detail: str = ""):
    message = title if not detail else f"{title} {detail}"
    log_message(message)
    if status_callback is not None:
        status_callback(title, detail)


if __name__ == "__main__":
    raise SystemExit(main())
