"""O relatório do diagnóstico em texto corrido, para ler linha a linha e copiar."""

from __future__ import annotations

from ..i18n import _
from ..log import get_log_dir
from .checks import OK, PROBLEM, WARNING, CheckResult

_STATUS_ORDER = (PROBLEM, WARNING, OK)


def has_findings(results: list[CheckResult]) -> bool:
    return any(result.status != OK for result in results)


def summarize(results: list[CheckResult]) -> str:
    problems = sum(result.status == PROBLEM for result in results)
    warnings = sum(result.status == WARNING for result in results)
    if not problems and not warnings:
        return _("Nenhum problema encontrado.")
    return _("Problemas: {problems}. Avisos: {warnings}.").format(problems=problems, warnings=warnings)


def startup_failure_intro(results: list[CheckResult], error) -> str:
    """A primeira linha do relatório que abre sozinho quando o player não inicia."""
    if has_findings(results):
        return _("O KeyTune não conseguiu iniciar o player e vai fechar. O diagnóstico encontrou o motivo abaixo.")
    return _(
        "O KeyTune não conseguiu iniciar o player e vai fechar. O diagnóstico não encontrou a causa. Erro: {error}"
    ).format(error=error)


def format_report(results: list[CheckResult], *, intro="") -> str:
    """Resumo primeiro, depois os problemas, os avisos e o que está em ordem."""
    status_labels = {PROBLEM: _("Problema"), WARNING: _("Aviso"), OK: _("Em ordem")}
    blocks = [intro.strip()] if intro.strip() else []
    blocks.append(summarize(results))
    for status in _STATUS_ORDER:
        for result in results:
            if result.status != status:
                continue
            lines = [f"{status_labels[status]}: {result.title}"]
            if result.detail:
                lines.append(result.detail)
            if result.advice:
                lines.append(_("O que fazer: {advice}").format(advice=result.advice))
            blocks.append("\n".join(lines))
    blocks.append(_("Arquivos de log: {path}").format(path=get_log_dir()))
    return "\n\n".join(blocks)
