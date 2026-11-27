"""Atualizador externo da versão portátil.

Empacotado como ``KeyTuneUpdater.exe``. O player copia este executável para
uma pasta temporária e o inicia de lá: a pasta do programa, inclusive este
arquivo, será substituída pelo zip.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import sys
import threading
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    app_dir = Path(args.app_dir)
    _activate_language(app_dir)
    announcer = _create_announcer()
    try:
        result = _run_interactive(args, announcer)
        if result is not None:
            return result

        try:
            _run_headless(args)
        except Exception as exc:
            _note(app_dir, f"Falha durante a atualização: {exc}")
            message = f'{_("Não foi possível concluir a atualização.")}\n\n{exc}'
            _announce(announcer, message)
            _show_error_message(message)
            return 1
        _announce(announcer, _("Atualização concluída."))
        return 0
    finally:
        if announcer is not None:
            announcer.close()


def parse_args(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Aplica uma atualização portátil do KeyTune a partir de um zip.")
    parser.add_argument("--parent-pid", type=int, required=True)
    parser.add_argument("--app-dir", required=True)
    parser.add_argument("--package", required=True)
    parser.add_argument("--restart-executable", required=True)
    return parser.parse_args(argv)


def _run_headless(args) -> None:
    from player.portable_update import apply_portable_update

    apply_portable_update(
        args.app_dir,
        args.package,
        restart_executable=args.restart_executable,
        parent_pid=args.parent_pid,
    )


def _run_interactive(args, announcer) -> int | None:
    from player.portable_update import apply_portable_update

    try:
        import wx

        app = wx.App(False)
        dialog = _ProgressDialog(None, announcer=announcer)
        dialog.dialog.Show()
    except Exception as exc:
        _note(Path(args.app_dir), f"Falha ao abrir a janela do atualizador: {exc}")
        return None

    def worker() -> None:
        try:
            apply_portable_update(
                args.app_dir,
                args.package,
                restart_executable=args.restart_executable,
                parent_pid=args.parent_pid,
                status_callback=lambda title, detail="": wx.CallAfter(dialog.update_status, title, detail),
            )
        except Exception as exc:
            wx.CallAfter(dialog.finish_with_error, str(exc))
            return
        wx.CallAfter(dialog.finish_successfully)

    threading.Thread(target=worker, daemon=True).start()
    app.MainLoop()
    if dialog.error_message:
        return 1
    return 0


class _ProgressDialog:
    """Janela pequena enquanto os arquivos são trocados. Criada só com wx carregado."""

    def __init__(self, parent, *, announcer=None):
        import wx
        from player.accessibility import attach_named_accessible
        from player.reading_dialog import add_reading_field

        self._wx = wx
        self._announcer = announcer
        self.error_message = ""
        self._finished = False
        self._allow_close = False
        dialog = wx.Dialog(
            parent,
            title=_("Atualizando KeyTune"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.dialog = dialog
        border = dialog.FromDIP(10)

        panel = wx.Panel(dialog)
        root = wx.BoxSizer(wx.VERTICAL)
        self.status_label = wx.StaticText(panel, label=_("Preparando a atualização portátil."))
        root.Add(self.status_label, 0, wx.ALL | wx.EXPAND, border)
        self.details = add_reading_field(
            panel, root, _("Detalhes da atualização"), _("Aguarde enquanto a atualização é aplicada."), border=border
        )
        self.progress_gauge = wx.Gauge(panel, range=100, style=wx.GA_HORIZONTAL | wx.GA_SMOOTH)
        attach_named_accessible(
            self.progress_gauge, name=_("Progresso da atualização"), role=wx.ROLE_SYSTEM_PROGRESSBAR
        )
        root.Add(self.progress_gauge, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, border)

        buttons = wx.StdDialogButtonSizer()
        self.close_button = wx.Button(panel, wx.ID_CLOSE, _("&Fechar"))
        self.close_button.Disable()
        self.close_button.Bind(wx.EVT_BUTTON, lambda _event: dialog.Close())
        dialog.SetEscapeId(wx.ID_CLOSE)
        buttons.AddButton(self.close_button)
        buttons.Realize()
        root.Add(buttons, 0, wx.ALL | wx.ALIGN_RIGHT, border)
        panel.SetSizer(root)

        frame = wx.BoxSizer(wx.VERTICAL)
        frame.Add(panel, 1, wx.EXPAND)
        dialog.SetSizerAndFit(frame)
        dialog.SetMinSize(dialog.FromDIP((520, 240)))
        dialog.SetSize(dialog.GetMinSize())
        dialog.CentreOnScreen()
        self._pulse_timer = wx.Timer(dialog)
        dialog.Bind(wx.EVT_TIMER, self._on_pulse, self._pulse_timer)
        dialog.Bind(wx.EVT_CLOSE, self._on_close)
        dialog.Bind(wx.EVT_SHOW, self._on_show)

    def _on_show(self, event) -> None:
        if event.IsShown() and not self._finished:
            self._pulse_timer.Start(120)
        event.Skip()

    def _on_pulse(self, _event) -> None:
        if not self._finished:
            self.progress_gauge.Pulse()

    def update_status(self, title: str, detail: str = "") -> None:
        self.status_label.SetLabel(title)
        if detail and self.details.GetValue() != detail:
            self.details.ChangeValue(detail)
            self.details.SetInsertionPoint(0)
        self.dialog.Layout()

    def finish_successfully(self) -> None:
        if self._finished:
            return
        self._finished = True
        self._pulse_timer.Stop()
        self.progress_gauge.SetValue(self.progress_gauge.GetRange())
        title = _("Atualização concluída.")
        detail = _("O KeyTune será aberto em instantes.")
        self.update_status(title, detail)
        _announce(self._announcer, f"{title} {detail}")
        self.close_button.Enable()
        self._wx.CallLater(900, self._close_after_success)

    def finish_with_error(self, error_message: str) -> None:
        if self._finished:
            return
        self._finished = True
        self.error_message = error_message
        self._allow_close = True
        self._pulse_timer.Stop()
        title = _("Não foi possível concluir a atualização.")
        self.update_status(title, error_message)
        _announce(self._announcer, f"{title} {error_message}")
        self.close_button.Enable()

    def _close_after_success(self) -> None:
        self._allow_close = True
        self.dialog.Close()

    def _on_close(self, event) -> None:
        if not self._allow_close:
            event.Veto()
            return
        self.dialog.Destroy()


def _create_announcer():
    try:
        from player.accessibility import ScreenReaderAnnouncer
        # A static import lets PyInstaller's hook collect the backend and DLLs.
        from accessible_output2.outputs import auto  # noqa: F401
        return ScreenReaderAnnouncer()
    except Exception:
        return None


def _announce(announcer, message: str) -> None:
    if announcer is not None:
        announcer.speak(message, interrupt=False)


def _activate_language(app_dir: Path) -> None:
    import player.i18n as i18n

    extra = app_dir / "locale"
    original = i18n.locale_directories

    def _directories():
        found = original()
        if extra.is_dir():
            return [extra, *found]
        return found

    i18n.locale_directories = _directories
    i18n.setup_translation(_read_language(app_dir) or None)


def _read_language(app_dir: Path) -> str:
    settings = app_dir / "data" / "settings.json"
    try:
        payload = json.loads(settings.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return ""
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("language") or "").strip()


def _note(app_dir: Path, message: str) -> None:
    try:
        from player.portable_update import PORTABLE_UPDATE_LOG_NAME
        from player.portable import PORTABLE_DATA_DIR_NAME

        data_dir = app_dir / PORTABLE_DATA_DIR_NAME
        data_dir.mkdir(parents=True, exist_ok=True)
        with (data_dir / PORTABLE_UPDATE_LOG_NAME).open("a", encoding="utf-8") as handle:
            handle.write(message + "\n")
    except OSError:
        return


def _show_error_message(message: str) -> None:
    if sys.platform.startswith("win"):
        try:
            ctypes.windll.user32.MessageBoxW(0, message, _("Atualização do KeyTune"), 0x10)
            return
        except Exception:
            pass
    print(message, file=sys.stderr)


def _(message: str) -> str:
    """Traduz quando o catálogo já foi ativado; senão devolve o português."""

    try:
        from player.i18n import gettext
    except Exception:
        return message
    return gettext(message)


if __name__ == "__main__":
    raise SystemExit(main())
