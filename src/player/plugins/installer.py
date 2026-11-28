"""Transactional, checksum-verified installation of .ktplugin archives."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import stat
from urllib.request import Request, urlopen
import zipfile

from ..i18n import _
from .manifest import PLUGIN_ID_RE, PluginManifest

MANIFEST_NAME = "keytune-plugin.json"
MAX_ARCHIVE_BYTES = 50 * 1024 * 1024
MAX_EXTRACTED_BYTES = 200 * 1024 * 1024
MAX_FILES = 2000
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL", *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


class InstallationError(RuntimeError):
    pass


def _safe_members(archive: zipfile.ZipFile):
    infos = archive.infolist()
    if len(infos) > MAX_FILES or sum(item.file_size for item in infos) > MAX_EXTRACTED_BYTES:
        raise InstallationError(_("O pacote excede os limites de segurança."))
    seen = set()
    for info in infos:
        path = Path(info.filename)
        normalized = path.as_posix().rstrip("/")
        collision_key = normalized.casefold()
        components = [part for part in path.parts if part not in {"", "."}]
        unix_mode = info.external_attr >> 16
        is_link = stat.S_ISLNK(unix_mode)
        if (
            not normalized
            or path.is_absolute()
            or ".." in path.parts
            or "\\" in info.filename
            or "\x00" in info.filename
            or any(
                ":" in part or part.rstrip(" .").split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES
                for part in components
            )
            or any(part != part.rstrip(" .") for part in components)
            or collision_key in seen
            or is_link
            or bool(info.flag_bits & 0x1)
        ):
            raise InstallationError(_("O pacote contém caminhos inseguros."))
        seen.add(collision_key)
        yield info


def inspect_archive(path: str | Path) -> PluginManifest:
    try:
        with zipfile.ZipFile(path) as archive:
            names = {item.filename for item in _safe_members(archive)}
            if MANIFEST_NAME not in names:
                raise InstallationError(_("O pacote não contém {name} na raiz.").format(name=MANIFEST_NAME))
            manifest = PluginManifest.from_dict(json.loads(archive.read(MANIFEST_NAME)))
            module_name = manifest.entrypoint.split(":", 1)[0]
            module_path = module_name.replace(".", "/")
            if f"{module_path}.py" not in names and f"{module_path}/__init__.py" not in names:
                raise InstallationError(_("O entrypoint declarado não existe no pacote."))
            return manifest
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        if isinstance(exc, InstallationError):
            raise
        raise InstallationError(_("Pacote de plugin inválido: {error}").format(error=exc)) from exc


def install_archive(
    path: str | Path,
    plugins_dir: str | Path,
    *,
    expected_sha256: str | None = None,
    expected_plugin_id: str | None = None,
    expected_version: str | None = None,
) -> PluginManifest:
    source = Path(path)
    if source.stat().st_size > MAX_ARCHIVE_BYTES:
        raise InstallationError(_("O pacote excede o limite de 50 MB."))
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if expected_sha256 and digest.lower() != expected_sha256.lower():
        raise InstallationError(_("O SHA-256 do pacote não corresponde ao catálogo."))
    manifest = inspect_archive(source)
    if expected_plugin_id and manifest.id != expected_plugin_id:
        raise InstallationError(_("O id do pacote não corresponde à entrada selecionada no catálogo."))
    if expected_version and manifest.version != expected_version:
        raise InstallationError(_("A versão do pacote não corresponde à entrada selecionada no catálogo."))
    destination_root = Path(plugins_dir)
    destination_root.mkdir(parents=True, exist_ok=True)
    destination = destination_root / manifest.id
    with tempfile.TemporaryDirectory(prefix=f".{manifest.id}-", dir=destination_root) as temporary:
        staging = Path(temporary)
        with zipfile.ZipFile(source) as archive:
            archive.extractall(staging, members=_safe_members(archive))
        backup = destination_root / f".{manifest.id}.backup"
        if backup.exists():
            shutil.rmtree(backup)
        if destination.exists():
            destination.replace(backup)
        try:
            shutil.copytree(staging, destination)
        except Exception:
            if backup.exists():
                if destination.exists():
                    shutil.rmtree(destination, ignore_errors=True)
                backup.replace(destination)
            raise
        finally:
            shutil.rmtree(backup, ignore_errors=True)
    return manifest


def download_package(url: str, output: str | Path, *, timeout: int = 30) -> Path:
    if not str(url).startswith("https://"):
        raise InstallationError(_("Downloads de plugins devem usar HTTPS."))
    request = Request(url, headers={"User-Agent": "KeyTune/2 plugin-marketplace"})
    target = Path(output)
    total = 0
    with urlopen(request, timeout=timeout) as response, target.open("wb") as stream:
        if not str(response.geturl()).startswith("https://"):
            raise InstallationError(_("O download foi redirecionado para uma conexão não segura."))
        while chunk := response.read(256 * 1024):
            total += len(chunk)
            if total > MAX_ARCHIVE_BYTES:
                raise InstallationError(_("O download excede o limite de 50 MB."))
            stream.write(chunk)
    return target


def uninstall_plugin(plugin_id: str, plugins_dir: str | Path) -> bool:
    if not PLUGIN_ID_RE.fullmatch(str(plugin_id)):
        raise InstallationError(_("Id de plugin inválido."))
    target = Path(plugins_dir) / plugin_id
    if not target.is_dir():
        return False
    shutil.rmtree(target)
    return True
