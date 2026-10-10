"""Resolve um vídeo público de verdade pelo YouTube.js e pelo yt-dlp.

Os outros testes dizem se os componentes abrem; este diz se o YouTube ainda
responde a eles. Sem a conta: nenhum cookie é enviado. Chama o YouTube.js e o
yt-dlp direto, e não o caminho da reprodução, porque aquele instala e atualiza
componentes quando falha e o diagnóstico não altera nada.
"""

from __future__ import annotations

import time

from ..i18n import _
from .checks import OK, PROBLEM, WARNING, CheckResult

TEST_VIDEO_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
_ANONYMOUS_PLAYER_CLIENT = "visionos"
_SOCKET_TIMEOUT_SECONDS = 20


def youtube_resolution_results(*, youtubejs_enabled=True) -> list[CheckResult]:
    """Um resultado por resolvedor instalado; nenhum se não houver o que testar."""
    attempts = []
    if youtubejs_enabled and _youtubejs_installed():
        attempts.append((_("Vídeo pelo YouTube.js"), _resolve_with_youtubejs))
    if _yt_dlp_ready():
        attempts.append((_("Vídeo pelo yt-dlp"), _resolve_with_yt_dlp))

    outcomes = [(title, *_timed(resolve)) for title, resolve in attempts]
    any_worked = any(error is None for _title, _seconds, error in outcomes)
    results = []
    for title, seconds, error in outcomes:
        if error is None:
            results.append(
                CheckResult(title, OK, _("Resolveu um vídeo público em {seconds} s.").format(seconds=f"{seconds:.1f}"))
            )
        elif any_worked:
            results.append(
                CheckResult(
                    title,
                    WARNING,
                    str(error),
                    _("O outro resolvedor funcionou, então o YouTube toca. Atualize em Preferências > Recursos adicionais."),
                )
            )
        else:
            results.append(
                CheckResult(
                    title,
                    PROBLEM,
                    str(error),
                    _(
                        "Verifique a conexão com a internet. Se ela estiver normal, atualize os componentes em "
                        "Preferências > Recursos adicionais; a versão nightly do yt-dlp costuma receber as correções antes."
                    ),
                )
            )
    return results


def _timed(resolve):
    started_at = time.monotonic()
    try:
        resolve()
    except Exception as exc:
        return time.monotonic() - started_at, exc
    return time.monotonic() - started_at, None


def _youtubejs_installed() -> bool:
    from ..youtube_music.youtubejs_runtime import youtubejs_dependencies_available

    return youtubejs_dependencies_available()


def _yt_dlp_ready() -> bool:
    from ..youtube_music.yt_dlp_runtime import find_all_available_javascript_runtimes, yt_dlp_executable_available

    return yt_dlp_executable_available() and bool(find_all_available_javascript_runtimes())


def _resolve_with_youtubejs() -> None:
    from ..youtube_music.youtubejs_runtime import resolve_stream

    resolve_stream(TEST_VIDEO_URL)


def _resolve_with_yt_dlp() -> None:
    from ..youtube_music.yt_dlp_runtime import extract_info, find_all_available_javascript_runtimes

    response = extract_info(
        TEST_VIDEO_URL,
        format_selector="bestaudio/best",
        extractor_args={"youtube": {"player_client": [_ANONYMOUS_PLAYER_CLIENT]}},
        js_runtimes=dict(find_all_available_javascript_runtimes()),
        socket_timeout_seconds=_SOCKET_TIMEOUT_SECONDS,
        noplaylist=True,
        extract_flat=False,
        ignore_no_formats_error=True,
    )
    info = response.data if isinstance(response.data, dict) else {}
    formats = [info, *(info.get("requested_formats") or []), *(info.get("formats") or [])]
    if not any(isinstance(fmt, dict) and str(fmt.get("url") or "").strip() for fmt in formats):
        raise RuntimeError(_("O yt-dlp abriu o vídeo, mas o YouTube não entregou nenhum formato reproduzível."))
