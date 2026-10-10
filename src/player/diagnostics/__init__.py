"""Diagnóstico do player: o que impede o KeyTune de tocar e o que fazer.

``checks`` roda as verificações, ``mpv_library`` explica por que a DLL do MPV
não carregou, ``youtube_resolution`` resolve um vídeo público de verdade, ``report`` monta o texto e ``dialog`` (o único módulo com
wxPython, importado só por quem mostra o relatório) abre a caixa de leitura.
"""

from .checks import OK, PROBLEM, WARNING, CheckResult, run_diagnostics
from .report import format_report, has_findings, startup_failure_intro, summarize

__all__ = [
    "OK",
    "PROBLEM",
    "WARNING",
    "CheckResult",
    "format_report",
    "has_findings",
    "run_diagnostics",
    "startup_failure_intro",
    "summarize",
]
