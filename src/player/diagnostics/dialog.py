"""Mostra o relatório do diagnóstico na caixa de leitura."""

import os

import wx

from ..i18n import _
from ..log import get_log_dir
from ..reading_dialog import show_reading_dialog
from .checks import run_diagnostics
from .report import format_report, startup_failure_intro


def _copy_to_clipboard(text):
    if not wx.TheClipboard.Open():
        return
    try:
        wx.TheClipboard.SetData(wx.TextDataObject(text))
        wx.TheClipboard.Flush()
    finally:
        wx.TheClipboard.Close()


def _open_log_folder():
    log_dir = get_log_dir()
    if os.path.isdir(log_dir) and hasattr(os, "startfile"):
        os.startfile(log_dir)


def show_player_startup_failure(parent, error):
    """O player não iniciou: roda as verificações do MPV e mostra o motivo."""
    with wx.BusyCursor():
        results = run_diagnostics(include_optional=False)
    return show_diagnostics_report(
        parent,
        results,
        title=_("O player não iniciou"),
        intro=startup_failure_intro(results, error),
    )


def show_diagnostics_report(parent, results, *, title=None, intro=""):
    """Abre o relatório; os botões copiam o texto ou abrem a pasta dos logs."""
    text = format_report(results, intro=intro)
    return show_reading_dialog(
        parent,
        title=title or _("Diagnóstico do KeyTune"),
        label=_("Relatório do diagnóstico"),
        text=text,
        actions=(
            (_("&Copiar relatório"), lambda: _copy_to_clipboard(text)),
            (_("Abrir pasta de &logs"), _open_log_folder),
        ),
    )
