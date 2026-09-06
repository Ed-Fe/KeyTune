from __future__ import annotations

import hashlib
import json
import os
import platform
from pathlib import Path
import shutil
import uuid
import zipfile
from urllib import error, request

from .constants import (
    APP_TITLE,
    APP_VERSION,
    GITHUB_REPOSITORY_NAME,
    GITHUB_REPOSITORY_OWNER,
    UPDATE_DOWNLOAD_CHUNK_SIZE,
    UPDATE_HTTP_TIMEOUT_SECONDS,
)
from .i18n import _
from .session import get_app_storage_dir


RESOURCE_MANIFEST_NAME = "keytune-resource.json"
RESOURCE_REVISIONS = {
    "node": 1,
    "youtube": 1,
    "youtubejs": 1,
    "autodj": 1,
}
# These resources predate resource revisions and are safe to reuse across
# KeyTune updates. AutoDJ is intentionally omitted so affected installations
# replace the previously published, incompatible scientific stack once.
LEGACY_CROSS_VERSION_RESOURCES = frozenset({"node", "youtube", "youtubejs"})
UPDATE_REPOSITORY_OWNER_ENV = "MEDIA_PLAYER_UPDATE_REPOSITORY_OWNER"
UPDATE_REPOSITORY_NAME_ENV = "MEDIA_PLAYER_UPDATE_REPOSITORY_NAME"


class OptionalResourceError(RuntimeError):
    pass


def resource_asset_name(resource_name: str) -> str:
    architecture = platform.machine().strip().lower()
    architecture_label = "arm64" if architecture in {"arm64", "aarch64"} else "x64"
    labels = {
        "node": "NodeJS",
        "youtube": "YouTubePython",
        "youtubejs": "YouTubeJS",
        "autodj": "AutoDJ",
    }
    try:
        label = labels[resource_name]
    except KeyError as exc:
        raise ValueError(f"Recurso adicional desconhecido: {resource_name}") from exc
    return f"KeyTune-{label}-win-{architecture_label}.zip"


def get_optional_resource_dir(resource_name: str) -> Path:
    if resource_name in {"node", "youtube"}:
        resource_dir = Path(get_app_storage_dir()) / "resources" / "youtube_music" / resource_name
    else:
        resource_dir = Path(get_app_storage_dir()) / "resources" / resource_name
    if _resource_dir_is_accessible(resource_dir):
        return resource_dir
    return resource_dir.with_name(f"{resource_dir.name}.repaired")


def _resource_dir_is_accessible(resource_dir: Path) -> bool:
    if not resource_dir.exists():
        return True
    try:
        with os.scandir(resource_dir):
            pass
    except OSError:
        return False
    return True


def read_optional_resource_manifest(resource_name: str) -> dict:
    manifest_path = get_optional_resource_dir(resource_name) / RESOURCE_MANIFEST_NAME
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict) or payload.get("resource") != resource_name:
        return {}
    return payload


def optional_resource_installed(resource_name: str) -> bool:
    manifest = read_optional_resource_manifest(resource_name)
    if not manifest:
        return False
    revision = manifest.get("resource_revision")
    expected_revision = RESOURCE_REVISIONS.get(resource_name)
    if revision is None:
        compatible = resource_name in LEGACY_CROSS_VERSION_RESOURCES
    else:
        compatible = revision == expected_revision
    if not compatible:
        return False
    required_paths = manifest.get("required_paths")
    if not isinstance(required_paths, list) or not required_paths:
        return False
    resource_dir = get_optional_resource_dir(resource_name)
    return all((resource_dir / str(relative_path)).exists() for relative_path in required_paths)


def install_optional_resource(resource_name: str, *, progress_callback=None) -> dict:
    asset_name = resource_asset_name(resource_name)
    checksum_name = f"{asset_name}.sha256"
    release_payload = _fetch_release_payload()
    assets = release_payload.get("assets")
    if not isinstance(assets, list):
        raise OptionalResourceError(_("A release do KeyTune não informou seus recursos adicionais."))

    archive_asset = _find_asset(assets, asset_name)
    checksum_asset = _find_asset(assets, checksum_name)
    if archive_asset is None or checksum_asset is None:
        raise OptionalResourceError(
            _("A release instalada do KeyTune não publicou o pacote opcional {name}.").format(name=asset_name)
        )

    resource_parent = get_optional_resource_dir(resource_name).parent
    resource_parent.mkdir(parents=True, exist_ok=True)
    archive_size = max(0, int(archive_asset.get("size") or 0))
    required_free_space = max(100 * 1024 * 1024, archive_size * 4)
    if shutil.disk_usage(resource_parent).free < required_free_space:
        raise OptionalResourceError(
            _("Não há espaço livre suficiente para instalar o recurso {name}.").format(name=asset_name)
        )
    download_dir = _create_download_dir(resource_parent, resource_name)
    archive_path = download_dir / asset_name
    checksum_path = download_dir / checksum_name
    staging_dir = download_dir / "content"
    try:
        _report_progress(progress_callback, _("Baixando {name}...").format(name=asset_name))
        _download_file(str(archive_asset.get("browser_download_url") or ""), archive_path)
        _download_file(str(checksum_asset.get("browser_download_url") or ""), checksum_path)
        expected_checksum = _read_expected_checksum(checksum_path, asset_name)
        if _calculate_sha256(archive_path).casefold() != expected_checksum.casefold():
            raise OptionalResourceError(
                _("O pacote {name} não passou na validação de integridade.").format(name=asset_name)
            )

        _report_progress(progress_callback, _("Instalando {name}...").format(name=asset_name))
        _extract_archive(archive_path, staging_dir)
        manifest = _validate_staged_resource(resource_name, staging_dir)
        _replace_resource_dir(resource_name, staging_dir)
        return manifest
    finally:
        shutil.rmtree(download_dir, ignore_errors=True)


def _fetch_release_payload() -> dict:
    owner = str(os.environ.get(UPDATE_REPOSITORY_OWNER_ENV) or GITHUB_REPOSITORY_OWNER).strip()
    repository = str(os.environ.get(UPDATE_REPOSITORY_NAME_ENV) or GITHUB_REPOSITORY_NAME).strip()
    tag = f"v{APP_VERSION}"
    api_url = f"https://api.github.com/repos/{owner}/{repository}/releases/tags/{tag}"
    try:
        with request.urlopen(
            request.Request(
                api_url,
                headers={"Accept": "application/vnd.github+json", "User-Agent": f"{APP_TITLE}/{APP_VERSION}"},
            ),
            timeout=UPDATE_HTTP_TIMEOUT_SECONDS,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.HTTPError, error.URLError, json.JSONDecodeError) as exc:
        raise OptionalResourceError(_("Não foi possível consultar os recursos adicionais do KeyTune.")) from exc
    if not isinstance(payload, dict):
        raise OptionalResourceError(_("A resposta dos recursos adicionais veio em formato inválido."))
    return payload


def _find_asset(assets: list[dict], asset_name: str) -> dict | None:
    expected_name = asset_name.casefold()
    for asset in assets:
        if isinstance(asset, dict) and str(asset.get("name") or "").casefold() == expected_name:
            return asset
    return None


def _download_file(url: str, destination: Path) -> None:
    if not url:
        raise OptionalResourceError(_("O endereço de download do recurso adicional está vazio."))
    try:
        with request.urlopen(
            request.Request(url, headers={"Accept": "application/octet-stream", "User-Agent": f"{APP_TITLE}/{APP_VERSION}"}),
            timeout=max(30, UPDATE_HTTP_TIMEOUT_SECONDS),
        ) as response:
            with open(destination, "wb") as output_file:
                shutil.copyfileobj(response, output_file, length=UPDATE_DOWNLOAD_CHUNK_SIZE)
    except (error.HTTPError, error.URLError, OSError) as exc:
        raise OptionalResourceError(_("Não foi possível baixar um recurso adicional do KeyTune.")) from exc


def _read_expected_checksum(checksum_path: Path, asset_name: str) -> str:
    try:
        lines = checksum_path.read_text(encoding="ascii").splitlines()
    except OSError as exc:
        raise OptionalResourceError(_("Não foi possível ler o checksum do recurso adicional.")) from exc
    expected_asset = asset_name.casefold()
    for line in lines:
        parts = line.strip().split()
        if len(parts) >= 2 and parts[-1].lstrip("*").casefold() == expected_asset and len(parts[0]) == 64:
            return parts[0]
    raise OptionalResourceError(_("O checksum do recurso adicional é inválido."))


def _calculate_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with open(file_path, "rb") as source_file:
        while chunk := source_file.read(UPDATE_DOWNLOAD_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _create_download_dir(resource_parent: Path, resource_name: str) -> Path:
    """Create an update workspace that inherits the resource directory ACL.

    ``tempfile.mkdtemp`` creates a Windows directory with an explicit private
    ACL.  Moving its extracted content into the resource directory preserves
    that ACL, which can make the resource inaccessible after an elevated app
    update.  A normal child directory inherits the per-user resource ACL.
    """
    download_dir = resource_parent / f".keytune-{resource_name}-{uuid.uuid4().hex}"
    download_dir.mkdir()
    return download_dir


def _extract_archive(archive_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                normalized = member.filename.replace("\\", "/")
                if normalized.startswith("/") or ".." in normalized.split("/"):
                    raise OptionalResourceError(_("O pacote do recurso adicional contém caminhos inválidos."))
            archive.extractall(destination)
    except zipfile.BadZipFile as exc:
        raise OptionalResourceError(_("O pacote do recurso adicional está corrompido.")) from exc


def _validate_staged_resource(resource_name: str, staging_dir: Path) -> dict:
    manifest_path = staging_dir / RESOURCE_MANIFEST_NAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OptionalResourceError(_("O pacote do recurso adicional não possui um manifesto válido.")) from exc
    if not isinstance(manifest, dict) or manifest.get("resource") != resource_name:
        raise OptionalResourceError(_("O pacote baixado não corresponde ao recurso solicitado."))
    if str(manifest.get("app_version") or "") != APP_VERSION:
        raise OptionalResourceError(_("O pacote baixado não é compatível com esta versão do KeyTune."))
    if manifest.get("resource_revision") != RESOURCE_REVISIONS.get(resource_name):
        raise OptionalResourceError(_("O pacote baixado não é compatível com esta versão do KeyTune."))
    required_paths = manifest.get("required_paths")
    if not isinstance(required_paths, list) or not required_paths:
        raise OptionalResourceError(_("O manifesto do recurso adicional está incompleto."))
    if not all((staging_dir / str(relative_path)).exists() for relative_path in required_paths):
        raise OptionalResourceError(_("O pacote do recurso adicional está incompleto."))
    return manifest


def _replace_resource_dir(resource_name: str, staging_dir: Path) -> None:
    target_dir = get_optional_resource_dir(resource_name)
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    backup_dir = target_dir.with_name(f"{target_dir.name}.previous")
    if backup_dir.exists():
        shutil.rmtree(backup_dir, ignore_errors=True)
    if target_dir.exists():
        target_dir.replace(backup_dir)
    try:
        staging_dir.replace(target_dir)
    except Exception:
        if backup_dir.exists() and not target_dir.exists():
            backup_dir.replace(target_dir)
        raise
    shutil.rmtree(backup_dir, ignore_errors=True)


def _report_progress(callback, message: str) -> None:
    if callable(callback):
        callback(message)
