from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
from urllib import error, request

from ..constants import APP_TITLE, APP_VERSION, UPDATE_DOWNLOAD_CHUNK_SIZE, UPDATE_HTTP_TIMEOUT_SECONDS
from ..session import get_app_storage_dir
from ..i18n import _


YTDLP_EXECUTABLE_NAME = "yt-dlp.exe" if sys.platform.startswith("win") else "yt-dlp"
YTDLP_RELEASE_ASSET_NAME = YTDLP_EXECUTABLE_NAME
YTDLP_RELEASE_CHECKSUM_ASSET_NAME = "SHA2-256SUMS"
YTDLP_STABLE_REPOSITORY = ("yt-dlp", "yt-dlp")
YTDLP_NIGHTLY_REPOSITORY = ("yt-dlp", "yt-dlp-nightly-builds")
YTDLP_COMMAND_TIMEOUT_SECONDS = 30
YTDLP_UPDATE_TIMEOUT_SECONDS = 180
# Ordered by yt-dlp's own recommendation (see the yt-dlp EJS wiki): Deno is the
# recommended runtime and the only one enabled by default; Node is the next best
# alternative. Bun support is deprecated upstream (versions after 1.3.14 are
# unsupported and it may be dropped entirely), so it is tried last and only as a
# best-effort fallback when nothing better is installed.
SUPPORTED_JS_RUNTIME_EXECUTABLES = ("deno", "node", "bun")

_YTDLP_UPDATE_LOCK = threading.Lock()


@dataclass(frozen=True, slots=True)
class YtDlpJsonResponse:
    data: dict | list | None
    stdout_text: str = ""
    stderr_text: str = ""


@dataclass(frozen=True, slots=True)
class YtDlpReleaseInfo:
    version: str
    executable_url: str
    checksum_url: str


def find_available_javascript_runtime() -> str:
    for executable_name in SUPPORTED_JS_RUNTIME_EXECUTABLES:
        if shutil.which(executable_name):
            return executable_name
    return ""


def find_all_available_javascript_runtimes() -> dict[str, str]:
    discovered: dict[str, str] = {}
    for executable_name in SUPPORTED_JS_RUNTIME_EXECUTABLES:
        executable_path = shutil.which(executable_name)
        if executable_path:
            discovered[executable_name] = executable_path
    return discovered


def get_managed_yt_dlp_dir() -> Path:
    return Path(get_app_storage_dir()) / "resources" / "youtube_music" / "bin"


def get_managed_yt_dlp_executable_path() -> Path:
    return get_managed_yt_dlp_dir() / YTDLP_EXECUTABLE_NAME


def find_yt_dlp_executable_path() -> Path | None:
    candidates: list[Path] = [get_managed_yt_dlp_executable_path()]

    env_override = str(os.environ.get("KEYTUNE_YTDLP_PATH") or "").strip()
    if env_override:
        candidates.append(Path(env_override))

    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / YTDLP_EXECUTABLE_NAME)

    repo_root = Path(__file__).resolve().parents[3]
    candidates.append(repo_root / YTDLP_EXECUTABLE_NAME)
    candidates.append(Path.cwd() / YTDLP_EXECUTABLE_NAME)

    path_match = shutil.which(YTDLP_EXECUTABLE_NAME) or shutil.which("yt-dlp")
    if path_match:
        candidates.append(Path(path_match))

    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved_candidate = str(candidate.resolve())
        except OSError:
            resolved_candidate = str(candidate)
        if resolved_candidate in seen:
            continue
        seen.add(resolved_candidate)
        if candidate.is_file():
            return candidate
    return None


def yt_dlp_executable_available() -> bool:
    return find_yt_dlp_executable_path() is not None


def get_yt_dlp_version(*, executable_path: str | os.PathLike[str] | None = None) -> str:
    resolved_path = Path(executable_path) if executable_path else find_yt_dlp_executable_path()
    if resolved_path is None or not resolved_path.is_file():
        return ""

    command = [str(resolved_path), "--version"]
    try:
        completed_process = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(5, YTDLP_COMMAND_TIMEOUT_SECONDS),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""

    version_text = str(completed_process.stdout or completed_process.stderr or "").strip()
    return version_text.splitlines()[0].strip() if version_text else ""


def install_or_update_yt_dlp_executable(
    *,
    force: bool = False,
    include_prerelease: bool = False,
    timeout_seconds: int = YTDLP_UPDATE_TIMEOUT_SECONDS,
) -> str:
    target_dir = get_managed_yt_dlp_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = get_managed_yt_dlp_executable_path()

    with _YTDLP_UPDATE_LOCK:
        if not force and target_path.is_file():
            version_text = get_yt_dlp_version(executable_path=target_path)
            if version_text:
                return version_text

        release_info = _fetch_latest_release(include_prerelease=include_prerelease)
        download_dir = Path(tempfile.mkdtemp(prefix="keytune-ytdlp-"))
        download_path = download_dir / YTDLP_RELEASE_ASSET_NAME
        checksum_path = download_dir / YTDLP_RELEASE_CHECKSUM_ASSET_NAME
        temporary_target_path = target_dir / f"{YTDLP_EXECUTABLE_NAME}.tmp"

        try:
            _download_binary_file(release_info.executable_url, download_path, timeout_seconds=timeout_seconds)
            _download_binary_file(release_info.checksum_url, checksum_path, timeout_seconds=timeout_seconds)

            expected_checksum = _extract_expected_checksum(
                checksum_path.read_text(encoding="utf-8"),
                asset_name=YTDLP_RELEASE_ASSET_NAME,
            )
            actual_checksum = _calculate_sha256(download_path)
            if actual_checksum.casefold() != expected_checksum.casefold():
                raise RuntimeError(_("O executável yt-dlp baixado não passou na validação de integridade."))

            shutil.copyfile(download_path, temporary_target_path)
            os.replace(temporary_target_path, target_path)
            return get_yt_dlp_version(executable_path=target_path) or release_info.version
        finally:
            try:
                if temporary_target_path.exists():
                    temporary_target_path.unlink()
            except OSError:
                pass
            shutil.rmtree(download_dir, ignore_errors=True)


def extract_info(
    media_path: str,
    *,
    format_selector: str = "",
    cookie_file_path: str = "",
    http_headers: dict[str, str] | None = None,
    extractor_args: dict[str, dict[str, list[str] | tuple[str, ...] | str]] | None = None,
    js_runtimes: dict[str, str] | None = None,
    socket_timeout_seconds: int = 0,
    noplaylist: bool = False,
    extract_flat: str | bool | None = None,
    ignore_no_formats_error: bool = False,
    playlist_end: int | None = None,
    quiet: bool = True,
    no_warnings: bool = False,
) -> YtDlpJsonResponse:
    executable_path = find_yt_dlp_executable_path()
    if executable_path is None:
        raise RuntimeError(
            "O executável yt-dlp não está disponível. Ative os Recursos adicionais do YouTube Music "
            "ou use uma build do player que já inclua o yt-dlp."
        )

    normalized_media_path = str(media_path or "").strip()
    if not normalized_media_path:
        raise RuntimeError(_("Nenhuma mídia válida foi informada ao yt-dlp."))

    command = _build_yt_dlp_command(
        executable_path=executable_path,
        media_path=normalized_media_path,
        format_selector=format_selector,
        cookie_file_path=cookie_file_path,
        http_headers=http_headers,
        extractor_args=extractor_args,
        js_runtimes=js_runtimes,
        socket_timeout_seconds=socket_timeout_seconds,
        noplaylist=noplaylist,
        extract_flat=extract_flat,
        ignore_no_formats_error=ignore_no_formats_error,
        playlist_end=playlist_end,
        quiet=quiet,
        no_warnings=no_warnings,
    )

    try:
        completed_process = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(5, int(socket_timeout_seconds or 0) + 20),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except FileNotFoundError as exc:
        raise RuntimeError(_("Não foi possível iniciar o executável yt-dlp.")) from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(_("O yt-dlp demorou demais para responder e foi interrompido.")) from exc
    except OSError as exc:
        raise RuntimeError(_("O executável yt-dlp falhou ao iniciar.")) from exc

    stdout_text = str(completed_process.stdout or "").strip()
    stderr_text = str(completed_process.stderr or "").strip()
    parsed_data = _parse_yt_dlp_json(stdout_text)
    if parsed_data is not None:
        return YtDlpJsonResponse(
            data=parsed_data,
            stdout_text=stdout_text,
            stderr_text=stderr_text,
        )

    error_message = stderr_text or stdout_text or "O yt-dlp não retornou dados válidos."
    raise RuntimeError(error_message)


def _build_yt_dlp_command(
    *,
    executable_path: Path,
    media_path: str,
    format_selector: str,
    cookie_file_path: str,
    http_headers: dict[str, str] | None,
    extractor_args: dict[str, dict[str, list[str] | tuple[str, ...] | str]] | None,
    js_runtimes: dict[str, str] | None,
    socket_timeout_seconds: int,
    noplaylist: bool,
    extract_flat: str | bool | None,
    ignore_no_formats_error: bool,
    playlist_end: int | None,
    quiet: bool,
    no_warnings: bool,
) -> list[str]:
    command = [
        str(executable_path),
        "--ignore-config",
        "--encoding",
        "utf-8",
        "--skip-download",
        "--dump-single-json",
        "--no-call-home",
    ]

    if quiet:
        command.append("--quiet")
    if no_warnings:
        command.append("--no-warnings")
    if noplaylist:
        command.append("--no-playlist")
    if extract_flat:
        command.append("--flat-playlist")
    if ignore_no_formats_error:
        command.append("--ignore-no-formats-error")
    if socket_timeout_seconds:
        command.extend(("--socket-timeout", str(max(1, int(socket_timeout_seconds)))))
    if playlist_end is not None:
        command.extend(("--playlist-end", str(max(1, int(playlist_end)))))

    normalized_format_selector = str(format_selector or "").strip()
    if normalized_format_selector:
        command.extend(("--format", normalized_format_selector))

    normalized_cookie_file_path = str(cookie_file_path or "").strip()
    if normalized_cookie_file_path:
        command.extend(("--cookies", normalized_cookie_file_path))

    for header_name, header_value in sorted((http_headers or {}).items()):
        normalized_header_name = str(header_name or "").strip()
        normalized_header_value = str(header_value or "").strip()
        if not normalized_header_name or not normalized_header_value:
            continue
        command.extend(("--add-header", f"{normalized_header_name}:{normalized_header_value}"))

    if extractor_args:
        for extractor_name, raw_args in sorted(extractor_args.items()):
            normalized_argument = _normalize_extractor_argument(extractor_name, raw_args)
            if normalized_argument:
                command.extend(("--extractor-args", normalized_argument))

    for runtime_name, runtime_path in sorted((js_runtimes or {}).items()):
        normalized_runtime_name = str(runtime_name or "").strip()
        normalized_runtime_path = str(runtime_path or "").strip()
        if not normalized_runtime_name:
            continue
        runtime_argument = normalized_runtime_name
        if normalized_runtime_path:
            runtime_argument = f"{runtime_argument}:{normalized_runtime_path}"
        command.extend(("--js-runtimes", runtime_argument))

    command.append(media_path)
    return command


def _normalize_extractor_argument(
    extractor_name: str,
    raw_args: dict[str, list[str] | tuple[str, ...] | str] | None,
) -> str:
    normalized_extractor_name = str(extractor_name or "").strip()
    if not normalized_extractor_name or not isinstance(raw_args, dict):
        return ""

    argument_parts: list[str] = []
    for argument_name, raw_value in sorted(raw_args.items()):
        normalized_argument_name = str(argument_name or "").strip().replace("_", "-")
        if not normalized_argument_name:
            continue

        if isinstance(raw_value, (list, tuple)):
            normalized_values = [str(item or "").strip() for item in raw_value]
            normalized_values = [item for item in normalized_values if item]
            if not normalized_values:
                continue
            argument_parts.append(f"{normalized_argument_name}={','.join(normalized_values)}")
            continue

        normalized_value = str(raw_value or "").strip()
        if not normalized_value:
            continue
        argument_parts.append(f"{normalized_argument_name}={normalized_value}")

    if not argument_parts:
        return ""
    return f"{normalized_extractor_name}:{';'.join(argument_parts)}"


def _parse_yt_dlp_json(stdout_text: str) -> dict | list | None:
    normalized_stdout_text = str(stdout_text or "").strip()
    if not normalized_stdout_text:
        return None

    try:
        parsed_data = json.loads(normalized_stdout_text)
    except json.JSONDecodeError:
        parsed_data = None
    if isinstance(parsed_data, (dict, list)):
        return parsed_data

    for candidate_line in reversed(normalized_stdout_text.splitlines()):
        stripped_line = candidate_line.strip()
        if not stripped_line:
            continue
        try:
            parsed_data = json.loads(stripped_line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed_data, (dict, list)):
            return parsed_data

    return None


def _fetch_latest_release(*, include_prerelease: bool) -> YtDlpReleaseInfo:
    repository_owner, repository_name = (
        YTDLP_NIGHTLY_REPOSITORY if include_prerelease else YTDLP_STABLE_REPOSITORY
    )
    api_url = f"https://api.github.com/repos/{repository_owner}/{repository_name}/releases/latest"
    payload = _download_json(api_url)
    assets = payload.get("assets")
    if not isinstance(assets, list):
        raise RuntimeError(_("Não foi possível ler os arquivos da release do yt-dlp."))

    executable_asset = _find_release_asset(assets, YTDLP_RELEASE_ASSET_NAME)
    checksum_asset = _find_release_asset(assets, YTDLP_RELEASE_CHECKSUM_ASSET_NAME)
    if executable_asset is None or checksum_asset is None:
        raise RuntimeError(_("A release do yt-dlp não publicou todos os arquivos necessários."))

    executable_url = str(executable_asset.get("browser_download_url") or "").strip()
    checksum_url = str(checksum_asset.get("browser_download_url") or "").strip()
    version_text = str(payload.get("tag_name") or payload.get("name") or "").strip()
    if not executable_url or not checksum_url or not version_text:
        raise RuntimeError(_("A release do yt-dlp veio com metadados incompletos."))

    return YtDlpReleaseInfo(
        version=version_text,
        executable_url=executable_url,
        checksum_url=checksum_url,
    )


def _download_json(url: str) -> dict:
    request_headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{APP_TITLE}/{APP_VERSION}",
    }
    release_request = request.Request(url, headers=request_headers)
    try:
        with request.urlopen(release_request, timeout=UPDATE_HTTP_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.HTTPError, error.URLError, json.JSONDecodeError) as exc:
        raise RuntimeError(_("Não foi possível consultar a release mais recente do yt-dlp.")) from exc

    if not isinstance(payload, dict):
        raise RuntimeError(_("A resposta da release do yt-dlp veio em formato inválido."))
    return payload


def _find_release_asset(assets: list[dict], asset_name: str) -> dict | None:
    expected_name = str(asset_name or "").casefold()
    for asset in assets:
        normalized_name = str(asset.get("name") or "").casefold()
        if normalized_name == expected_name:
            return asset
    return None


def _download_binary_file(url: str, destination_path: Path, *, timeout_seconds: int) -> None:
    download_request = request.Request(
        url,
        headers={
            "Accept": "application/octet-stream",
            "User-Agent": f"{APP_TITLE}/{APP_VERSION}",
        },
    )
    try:
        with request.urlopen(download_request, timeout=max(10, int(timeout_seconds or 0))) as response:
            with open(destination_path, "wb") as target_file:
                shutil.copyfileobj(response, target_file, length=UPDATE_DOWNLOAD_CHUNK_SIZE)
    except (error.HTTPError, error.URLError, OSError) as exc:
        raise RuntimeError(_("Não foi possível baixar os arquivos oficiais do yt-dlp.")) from exc


def _extract_expected_checksum(checksum_text: str, *, asset_name: str) -> str:
    normalized_asset_name = str(asset_name or "").strip()
    for line in str(checksum_text or "").splitlines():
        normalized_line = line.strip()
        if not normalized_line or normalized_asset_name not in normalized_line:
            continue
        checksum_value = normalized_line.split()[0].strip()
        if len(checksum_value) == 64:
            return checksum_value
    raise RuntimeError(_("Não foi possível localizar o checksum oficial do yt-dlp baixado."))


def _calculate_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with open(file_path, "rb") as source_file:
        while True:
            chunk = source_file.read(UPDATE_DOWNLOAD_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()
