from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib import error, request


DEFAULT_REPOSITORY_OWNER = "zhongfly"
DEFAULT_REPOSITORY_NAME = "mpv-winbuild"
DEFAULT_ASSET_PATTERN = r"^mpv-dev-x86_64-\d{8}-git-[0-9a-f]+\.7z$"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "mpv"
DOWNLOAD_TIMEOUT_SECONDS = 60
CHUNK_SIZE = 256 * 1024
RUNTIME_DLL_NAMES = ("libmpv-2.dll", "mpv-2.dll", "mpv-1.dll")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Baixa e extrai o runtime do MPV usado pelo KeyTune.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Diretório onde o runtime do MPV será gravado.",
    )
    parser.add_argument(
        "--source-path",
        default="",
        help="Pasta local com o runtime do MPV ou arquivo .7z para usar no lugar do download.",
    )
    parser.add_argument(
        "--source-archive",
        default="",
        help="Arquivo .7z local com o runtime do MPV para usar no lugar do download.",
    )
    parser.add_argument(
        "--repository-owner",
        default=DEFAULT_REPOSITORY_OWNER,
        help="Proprietário do repositório do mpv-winbuild.",
    )
    parser.add_argument(
        "--repository-name",
        default=DEFAULT_REPOSITORY_NAME,
        help="Nome do repositório do mpv-winbuild.",
    )
    parser.add_argument(
        "--asset-pattern",
        default=DEFAULT_ASSET_PATTERN,
        help="Expressão regular para localizar o asset da release do MPV.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).expanduser().resolve()
    source_path = Path(args.source_path).expanduser() if str(args.source_path).strip() else None
    source_archive = Path(args.source_archive).expanduser() if str(args.source_archive).strip() else None

    with tempfile.TemporaryDirectory(prefix="keytune-mpv-runtime-") as temp_root_name:
        temp_root = Path(temp_root_name)
        runtime_source_dir, source_label, release_version = resolve_runtime_source(
            temp_root=temp_root,
            source_path=source_path,
            source_archive=source_archive,
            repository_owner=str(args.repository_owner).strip(),
            repository_name=str(args.repository_name).strip(),
            asset_pattern=str(args.asset_pattern).strip(),
        )

        output_dir.parent.mkdir(parents=True, exist_ok=True)
        if output_dir.exists():
            if output_dir.is_dir():
                shutil.rmtree(output_dir)
            else:
                output_dir.unlink()

        shutil.copytree(runtime_source_dir, output_dir)

        print(f"Versão: {release_version}")
        print(f"Origem: {source_label}")
        print(f"Destino: {output_dir}")

    return 0


def resolve_runtime_source(
    *,
    temp_root: Path,
    source_path: Path | None,
    source_archive: Path | None,
    repository_owner: str,
    repository_name: str,
    asset_pattern: str,
) -> tuple[Path, str, str]:
    if source_path is not None:
        if not source_path.exists():
            raise RuntimeError(f"O caminho informado em --source-path não existe: {source_path}")

        if source_path.is_file():
            extracted_dir = temp_root / "source-archive"
            extract_7z_archive(source_path, extracted_dir)
            runtime_dir = locate_runtime_directory(extracted_dir)
            return runtime_dir, str(source_path), "local"

        runtime_dir = locate_runtime_directory(source_path)
        return runtime_dir, str(source_path), "local"

    if source_archive is not None:
        if not source_archive.exists():
            raise RuntimeError(f"O arquivo informado em --source-archive não existe: {source_archive}")

        extracted_dir = temp_root / "source-archive"
        extract_7z_archive(source_archive, extracted_dir)
        runtime_dir = locate_runtime_directory(extracted_dir)
        return runtime_dir, str(source_archive), "local"

    release_info = fetch_latest_release(
        repository_owner=repository_owner,
        repository_name=repository_name,
        asset_pattern=asset_pattern,
    )

    download_dir = temp_root / "download"
    download_dir.mkdir(parents=True, exist_ok=True)
    archive_path = download_dir / release_info["asset_name"]
    extracted_dir = download_dir / "extracted"

    download_file(release_info["asset_url"], archive_path)
    extract_7z_archive(archive_path, extracted_dir)

    runtime_dir = locate_runtime_directory(extracted_dir)
    return runtime_dir, release_info["asset_name"], release_info["version"]


def fetch_latest_release(*, repository_owner: str, repository_name: str, asset_pattern: str) -> dict[str, str]:
    api_url = f"https://api.github.com/repos/{repository_owner}/{repository_name}/releases/latest"
    payload = download_json(api_url)
    assets = payload.get("assets")
    if not isinstance(assets, list):
        raise RuntimeError("A release do MPV veio sem a lista de assets.")

    asset = find_asset(assets, asset_pattern)
    if asset is None:
        available_assets = ", ".join(str(item.get("name") or "") for item in assets if isinstance(item, dict))
        raise RuntimeError(
            "Não foi possível localizar um asset compatível na release mais recente do MPV. "
            f"Assets disponíveis: {available_assets}"
        )

    version_text = str(payload.get("tag_name") or payload.get("name") or "").strip()
    asset_url = str(asset.get("browser_download_url") or "").strip()
    asset_name = str(asset.get("name") or "").strip()
    if not version_text or not asset_url or not asset_name:
        raise RuntimeError("A release do MPV veio com metadados incompletos.")

    return {
        "version": version_text,
        "asset_url": asset_url,
        "asset_name": asset_name,
    }


def download_json(url: str) -> dict:
    try:
        with request.urlopen(
            request.Request(
                url,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "KeyTune-build/1.0",
                },
            ),
            timeout=DOWNLOAD_TIMEOUT_SECONDS,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.HTTPError, error.URLError, json.JSONDecodeError) as exc:
        raise RuntimeError("Não foi possível consultar a release do MPV.") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("A release do MPV veio em formato inválido.")
    return payload


def download_file(url: str, destination_path: Path) -> None:
    try:
        with request.urlopen(
            request.Request(
                url,
                headers={
                    "Accept": "application/octet-stream",
                    "User-Agent": "KeyTune-build/1.0",
                },
            ),
            timeout=DOWNLOAD_TIMEOUT_SECONDS,
        ) as response:
            with open(destination_path, "wb") as target_file:
                shutil.copyfileobj(response, target_file, length=CHUNK_SIZE)
    except (error.HTTPError, error.URLError, OSError) as exc:
        raise RuntimeError("Não foi possível baixar o runtime oficial do MPV.") from exc


def find_asset(assets: list[dict], asset_pattern: str) -> dict | None:
    pattern = re.compile(asset_pattern, re.IGNORECASE)
    matching_assets = []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        asset_name = str(asset.get("name") or "").strip()
        if asset_name and pattern.fullmatch(asset_name):
            matching_assets.append(asset)

    if not matching_assets:
        return None

    matching_assets.sort(key=lambda item: str(item.get("name") or "").casefold(), reverse=True)
    return matching_assets[0]


def extract_7z_archive(archive_path: Path, destination_dir: Path) -> None:
    seven_zip_executable = resolve_7z_command()
    destination_dir.mkdir(parents=True, exist_ok=True)

    completed = subprocess.run(
        [seven_zip_executable, "x", str(archive_path), f"-o{destination_dir}", "-y"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if completed.returncode != 0:
        details = completed.stdout.strip()
        if details:
            details = f" Detalhes: {details}"
        raise RuntimeError(f"Falha ao extrair o runtime do MPV com 7-Zip.{details}")


def resolve_7z_command() -> str:
    command = shutil.which("7z")
    if command:
        return command

    default_path = Path(r"C:\Program Files\7-Zip\7z.exe")
    if default_path.is_file():
        return str(default_path)

    raise RuntimeError("7-Zip (7z) não encontrado. Instale o 7-Zip ou deixe o comando 7z disponível no PATH.")


def locate_runtime_directory(search_root: Path) -> Path:
    if _is_valid_runtime_dir(search_root):
        return search_root

    for dll_name in RUNTIME_DLL_NAMES:
        for dll_path in search_root.rglob(dll_name):
            if dll_path.is_file():
                return dll_path.parent

    raise RuntimeError(
        "Não foi possível localizar um runtime válido do MPV no conteúdo baixado. "
        "O diretório precisa conter libmpv-2.dll, mpv-2.dll ou mpv-1.dll."
    )


def _is_valid_runtime_dir(directory: Path) -> bool:
    return any((directory / dll_name).is_file() for dll_name in RUNTIME_DLL_NAMES)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)