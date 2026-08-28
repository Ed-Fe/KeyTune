from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
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
# Ordered by yt-dlp's priority (see the yt-dlp EJS wiki). Bun support is
# deprecated upstream and restricted to a narrow version range.
SUPPORTED_JS_RUNTIME_EXECUTABLES = ("deno", "node", "qjs", "bun")

_YTDLP_UPDATE_LOCK = threading.Lock()


@dataclass(frozen=True, slots=True)
class JavascriptRuntimeInfo:
    runtime_name: str
    executable_name: str
    executable_path: str
    version: str
    supported: bool


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


_JAVASCRIPT_RUNTIME_SPECS = (
    ("deno", "deno", ("--version",), r"^deno\s+(\S+)", (2, 3, 0), None),
    ("node", "node", ("--version",), r"^v(\S+)", (22, 0, 0), None),
    ("quickjs", "qjs", ("--help",), r"^QuickJS(?:-ng)?\s+version\s+(\S+)", (2023, 12, 9), None),
    ("bun", "bun", ("--version",), r"^(\S+)", (1, 2, 11), (1, 3, 14)),
)


def find_available_javascript_runtime() -> str:
    available_runtimes = find_all_available_javascript_runtimes()
    for runtime_name, *_unused in _JAVASCRIPT_RUNTIME_SPECS:
        if runtime_name in available_runtimes:
            return runtime_name
    return ""


def find_all_available_javascript_runtimes() -> dict[str, str]:
    return {
        runtime.runtime_name: runtime.executable_path
        for runtime in inspect_javascript_runtimes()
        if runtime.supported
    }


def find_incompatible_javascript_runtimes() -> dict[str, str]:
    return {
        runtime.runtime_name: runtime.version
        for runtime in inspect_javascript_runtimes()
        if not runtime.supported
    }


def inspect_javascript_runtimes() -> tuple[JavascriptRuntimeInfo, ...]:
    discovered: list[JavascriptRuntimeInfo] = []
    for runtime_name, executable_name, version_args, version_pattern, minimum_version, maximum_version in (
        _JAVASCRIPT_RUNTIME_SPECS
    ):
        executable_path = _find_javascript_runtime_executable(executable_name)
        if not executable_path:
            continue
        version_output = _get_executable_version_output(executable_path, version_args)
        version_match = re.search(version_pattern, version_output, flags=re.MULTILINE)
        version = version_match.group(1) if version_match else ""
        version_tuple = _parse_version_tuple(version)
        is_quickjs_ng = runtime_name == "quickjs" and "QuickJS-ng" in version_output
        supported = bool(version_tuple) and (
            is_quickjs_ng
            or (
                version_tuple >= minimum_version
                and (maximum_version is None or version_tuple <= maximum_version)
            )
        )
        discovered.append(
            JavascriptRuntimeInfo(
                runtime_name=runtime_name,
                executable_name=executable_name,
                executable_path=executable_path,
                version=version,
                supported=supported,
            )
        )
    return tuple(discovered)


def _find_javascript_runtime_executable(executable_name: str) -> str:
    candidate_names = [executable_name]
    if sys.platform.startswith("win"):
        candidate_names.insert(0, f"{executable_name}.exe")

    candidates: list[Path] = []
    path_match = shutil.which(executable_name)
    if path_match:
        candidates.append(Path(path_match))

    yt_dlp_path = find_yt_dlp_executable_path()
    if yt_dlp_path is not None:
        candidates.extend(yt_dlp_path.parent / candidate_name for candidate_name in candidate_names)

    if getattr(sys, "frozen", False):
        executable_dir = Path(sys.executable).resolve().parent
        candidates.extend(executable_dir / candidate_name for candidate_name in candidate_names)

    candidates.extend(Path.cwd() / candidate_name for candidate_name in candidate_names)

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
            return resolved_candidate
    return ""


def _get_executable_version_output(executable_path: str, version_args: tuple[str, ...]) -> str:
    try:
        completed_process = subprocess.run(
            [executable_path, *version_args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return "\n".join(
        part.strip()
        for part in (completed_process.stdout, completed_process.stderr)
        if str(part or "").strip()
    )


def _parse_version_tuple(version: str) -> tuple[int, ...]:
    version_parts = re.findall(r"\d+", str(version or ""))
    if not version_parts:
        return ()
    return tuple(int(part) for part in version_parts[:3])


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
            _("O executável yt-dlp não está disponível. Ative os Recursos adicionais do YouTube Music "
              "ou use uma build do player que já inclua o yt-dlp.")
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

    error_message = stderr_text or stdout_text or _("O yt-dlp não retornou dados válidos.")
    raise RuntimeError(error_message)


def download_media(
    media_path: str,
    *,
    destination_directory: str,
    format_selector: str = "best[ext=mp4]/best",
    filename_template: str = "%(title).200B [%(id)s].%(ext)s",
    playlist: bool = False,
    playlist_limit: int = 100,
    cookie_file_path: str = "",
    http_headers: dict[str, str] | None = None,
    js_runtimes: dict[str, str] | None = None,
    timeout_seconds: int = 60 * 60,
) -> list[str]:
    """Download media with the same managed yt-dlp runtime used by KeyTune.

    This intentionally exposes a small, stable option set instead of arbitrary
    command-line arguments.  Plugins cannot smuggle output paths through the
    filename template and receive only the final paths printed by yt-dlp.
    """
    executable_path = find_yt_dlp_executable_path()
    if executable_path is None:
        raise RuntimeError(_("O executável yt-dlp não está disponível."))

    normalized_media_path = str(media_path or "").strip()
    if not normalized_media_path:
        raise RuntimeError(_("Nenhuma mídia válida foi informada ao yt-dlp."))

    raw_destination_directory = str(destination_directory or "").strip()
    if not raw_destination_directory:
        raise RuntimeError(_("Escolha uma pasta de destino para o download."))
    output_directory = Path(raw_destination_directory).expanduser()
    output_directory.mkdir(parents=True, exist_ok=True)
    output_directory = output_directory.resolve()

    normalized_template = str(filename_template or "").strip() or "%(title).200B [%(id)s].%(ext)s"
    if (
        Path(normalized_template).name != normalized_template
        or ".." in normalized_template
        or "/" in normalized_template
        or "\\" in normalized_template
    ):
        raise RuntimeError(_("O modelo do nome do arquivo não pode conter pastas."))

    command = [
        str(executable_path),
        "--ignore-config",
        "--encoding", "utf-8",
        "--no-call-home",
        "--newline",
        "--print", "after_move:filepath",
        "--paths", str(output_directory),
        "--output", normalized_template,
        "--format", str(format_selector or "best[ext=mp4]/best").strip(),
        "--playlist-end", str(max(1, min(500, int(playlist_limit)))),
    ]
    command.append("--yes-playlist" if playlist else "--no-playlist")

    normalized_cookie_file_path = str(cookie_file_path or "").strip()
    if normalized_cookie_file_path:
        command.extend(("--cookies", normalized_cookie_file_path))
    for header_name, header_value in sorted((http_headers or {}).items()):
        if str(header_name).strip() and str(header_value).strip():
            command.extend(("--add-header", f"{str(header_name).strip()}:{str(header_value).strip()}"))
    for runtime_name, runtime_path in sorted((js_runtimes or {}).items()):
        runtime_argument = str(runtime_name).strip()
        if runtime_argument:
            if str(runtime_path).strip():
                runtime_argument += f":{str(runtime_path).strip()}"
            command.extend(("--js-runtimes", runtime_argument))
    command.extend(("--", normalized_media_path))

    try:
        completed_process = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(30, int(timeout_seconds)),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(_("O download pelo yt-dlp excedeu o tempo limite.")) from exc
    except OSError as exc:
        raise RuntimeError(_("Não foi possível iniciar o download pelo yt-dlp.")) from exc

    if completed_process.returncode != 0:
        detail = str(completed_process.stderr or completed_process.stdout or "").strip()
        raise RuntimeError(detail or _("O yt-dlp não conseguiu baixar a mídia."))

    downloaded_paths = []
    for line in str(completed_process.stdout or "").splitlines():
        candidate = Path(line.strip())
        if not candidate.is_absolute():
            candidate = output_directory / candidate
        try:
            resolved_candidate = candidate.resolve()
            resolved_candidate.relative_to(output_directory)
        except (OSError, ValueError):
            continue
        if resolved_candidate.is_file():
            downloaded_paths.append(str(resolved_candidate))
    return downloaded_paths


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
