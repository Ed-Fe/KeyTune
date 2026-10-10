"""As verificações do diagnóstico: cada uma devolve o que achou e o que fazer.

Sem wxPython. Nenhuma verificação altera o sistema, e uma que falhe por conta
própria vira um resultado em vez de interromper as outras.
"""

from __future__ import annotations

import platform
import sys
from dataclasses import dataclass

from ..constants import APP_VERSION
from ..i18n import _
from ..log import get_logger
from .mpv_library import MpvLibraryDiagnosis, diagnose_mpv_library, explain_mpv_library

_logger = get_logger(__name__)

OK = "ok"
WARNING = "warning"
PROBLEM = "problem"


@dataclass(frozen=True, slots=True)
class CheckResult:
    title: str
    status: str
    detail: str = ""
    advice: str = ""


def run_diagnostics(*, include_optional=True, youtube_service=None, youtubejs_enabled=True) -> list[CheckResult]:
    """Roda as verificações em ordem.

    *include_optional*: também o que não impede o player de abrir (yt-dlp,
    Node.js, YouTube.js, FFmpeg e, pela rede, a resolução de um vídeo público
    e a conta do YouTube).
    *youtubejs_enabled*: a preferência **Usar YouTube.js**; desligada, a falta
    do pacote não é um aviso.
    """
    results = [_system_result()]
    library = _guarded(_("Biblioteca do MPV"), diagnose_mpv_library)
    if isinstance(library, MpvLibraryDiagnosis):
        results.append(_mpv_library_result(library))
        results.extend(_vulkan_loader_results(library))
        if library.loaded or not sys.platform.startswith("win"):
            results.extend(_collect(_("Player"), _player_results))
    else:
        results.append(library)

    if include_optional:
        results.extend(_collect("yt-dlp", _yt_dlp_results))
        results.extend(_collect("Node.js", _node_results))
        results.extend(_collect("YouTube.js", lambda: _youtubejs_results(youtubejs_enabled)))
        results.extend(_collect(_("Vídeo do YouTube"), lambda: _youtube_resolution_results(youtubejs_enabled)))
        results.extend(_collect("FFmpeg", _ffmpeg_results))
        if youtube_service is not None:
            results.extend(_collect(_("Conta do YouTube"), lambda: _youtube_account_results(youtube_service)))
    return results


def _guarded(title, check):
    try:
        return check()
    except Exception as exc:
        _logger.exception("Diagnostic check failed: %s", title)
        return CheckResult(title, PROBLEM, _("A verificação falhou: {error}").format(error=exc))


def _collect(title, check) -> list[CheckResult]:
    outcome = _guarded(title, check)
    return [outcome] if isinstance(outcome, CheckResult) else list(outcome)


def _system_result() -> CheckResult:
    return CheckResult(
        _("Sistema"),
        OK,
        _("KeyTune {version}, {system} {release} ({build}), {bits}.").format(
            version=APP_VERSION,
            system=platform.system(),
            release=platform.release(),
            build=platform.version(),
            bits=platform.architecture()[0],
        ),
    )


def _mpv_library_result(diagnosis: MpvLibraryDiagnosis) -> CheckResult:
    title = _("Biblioteca do MPV")
    if diagnosis.loaded:
        return CheckResult(title, OK, _("Carregada de {path}.").format(path=diagnosis.dll_path))
    detail, advice = explain_mpv_library(diagnosis)
    return CheckResult(title, PROBLEM, detail, advice)


def _vulkan_loader_results(diagnosis: MpvLibraryDiagnosis) -> list[CheckResult]:
    if not diagnosis.loaded or not sys.platform.startswith("win") or not diagnosis.imports("vulkan-1.dll"):
        return []
    if (diagnosis.dll_path.parent / "vulkan-1.dll").is_file():
        detail = _("O MPV usa o vulkan-1.dll que vem com o KeyTune.")
    else:
        detail = _("O MPV usa o vulkan-1.dll do Windows, instalado pelo driver de vídeo.")
    return [CheckResult(_("Vulkan"), OK, detail)]


def _player_results() -> list[CheckResult]:
    from ..mpv_backend import create_player_instance

    title = _("Player")
    try:
        player = create_player_instance(video_output_enabled=False).media_player_new()
    except Exception as exc:
        return [
            CheckResult(
                title,
                PROBLEM,
                str(exc),
                _("Use Copiar relatório e envie o texto, junto com o arquivo de log, ao relatar o problema."),
            )
        ]

    try:
        devices = player.list_audio_output_devices()
    finally:
        player.release()

    results = [CheckResult(title, OK, _("O MPV iniciou."))]
    audio_title = _("Saída de áudio")
    if devices:
        results.append(
            CheckResult(audio_title, OK, _("Dispositivos de saída encontrados: {count}.").format(count=len(devices)))
        )
    else:
        results.append(
            CheckResult(
                audio_title,
                WARNING,
                _("O MPV não encontrou nenhum dispositivo de saída de áudio."),
                _("Conecte ou ative um dispositivo de som nas configurações do Windows."),
            )
        )
    return results


def _yt_dlp_results() -> list[CheckResult]:
    from ..youtube_music.yt_dlp_runtime import find_yt_dlp_executable_path, get_yt_dlp_version

    install_advice = _("Instale ou atualize em Preferências > Recursos adicionais.")
    executable_path = find_yt_dlp_executable_path()
    if executable_path is None:
        return [
            CheckResult(
                "yt-dlp",
                WARNING,
                _("O yt-dlp não está instalado. Sem ele o YouTube não toca e os downloads não funcionam."),
                install_advice,
            )
        ]
    version = get_yt_dlp_version(executable_path=executable_path)
    if not version:
        return [
            CheckResult(
                "yt-dlp",
                PROBLEM,
                _("O yt-dlp está em {path}, mas não respondeu.").format(path=executable_path),
                _("Veja se o antivírus bloqueou o arquivo.") + " " + install_advice,
            )
        ]
    return [CheckResult("yt-dlp", OK, _("Versão {version}.").format(version=version))]


def _node_results() -> list[CheckResult]:
    from ..youtube_music.yt_dlp_runtime import inspect_javascript_runtimes

    install_advice = _("Instale ou atualize em Preferências > Recursos adicionais.")
    node = next((runtime for runtime in inspect_javascript_runtimes() if runtime.runtime_name == "node"), None)
    if node is None:
        return [
            CheckResult(
                "Node.js",
                WARNING,
                _("O Node.js não foi encontrado. O yt-dlp e o YouTube.js precisam dele para resolver vídeos do YouTube."),
                install_advice,
            )
        ]
    if not node.supported:
        return [
            CheckResult(
                "Node.js",
                WARNING,
                _("O Node.js em {path} é da versão {version}, que o KeyTune não aceita.").format(
                    path=node.executable_path, version=node.version or "?"
                ),
                install_advice,
            )
        ]
    return [CheckResult("Node.js", OK, _("Versão {version}.").format(version=node.version))]


def _youtubejs_results(enabled) -> list[CheckResult]:
    from ..youtube_music.youtubejs_runtime import (
        validate_youtubejs_dependencies,
        youtubejs_dependencies_available,
        youtubejs_dependency_versions,
    )

    install_advice = _("Instale ou atualize em Preferências > Recursos adicionais.")
    if not youtubejs_dependencies_available():
        if not enabled:
            return [CheckResult("YouTube.js", OK, _("Desativado nas preferências; o KeyTune usa o yt-dlp."))]
        return [
            CheckResult(
                "YouTube.js",
                WARNING,
                _("O YouTube.js está ativado, mas o pacote ou o Node.js não está instalado. O KeyTune usa o yt-dlp no lugar."),
                install_advice,
            )
        ]
    try:
        validate_youtubejs_dependencies()
    except Exception as exc:
        return [
            CheckResult(
                "YouTube.js",
                PROBLEM,
                str(exc),
                _("Veja se o antivírus bloqueou o arquivo.") + " " + install_advice,
            )
        ]
    version = str(youtubejs_dependency_versions().get("YouTube.js") or "").strip()
    detail = _("Versão {version}.").format(version=version) if version else _("Instalado e respondendo.")
    if not enabled:
        detail += " " + _("Está desativado nas preferências.")
    return [CheckResult("YouTube.js", OK, detail)]


def _youtube_resolution_results(youtubejs_enabled) -> list[CheckResult]:
    from .youtube_resolution import youtube_resolution_results

    return youtube_resolution_results(youtubejs_enabled=youtubejs_enabled)


def _ffmpeg_results() -> list[CheckResult]:
    from ..download.ffmpeg import find_ffmpeg_directory

    directory = find_ffmpeg_directory()
    if directory is None:
        return [
            CheckResult(
                "FFmpeg",
                WARNING,
                _("O FFmpeg não foi encontrado. Ele é usado para converter mídias e em alguns downloads."),
                _("O KeyTune oferece a instalação na primeira conversão ou download que precisar dele."),
            )
        ]
    return [CheckResult("FFmpeg", OK, _("Encontrado em {path}.").format(path=directory))]


def _youtube_account_results(service) -> list[CheckResult]:
    title = _("Conta do YouTube")
    if not service.has_saved_browser_auth():
        return [CheckResult(title, OK, _("Nenhuma conta conectada."))]
    try:
        account_name = service.get_connected_account_name()
    except Exception as exc:
        if bool(getattr(exc, "should_disconnect", True)):
            return [
                CheckResult(title, PROBLEM, str(exc), _("Use o botão Atualizar acesso, na aba KeyTube, para conectar a conta de novo."))
            ]
        return [CheckResult(title, WARNING, str(exc), _("Verifique a conexão com a internet e tente de novo."))]
    return [CheckResult(title, OK, _("Conectada como {name}.").format(name=account_name))]
