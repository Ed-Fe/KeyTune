from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
from urllib import error, request


ASSET_NAME = "yt-dlp.exe"
CHECKSUM_ASSET_NAME = "SHA2-256SUMS"
REPOSITORIES = {
    "stable": ("yt-dlp", "yt-dlp"),
    "nightly": ("yt-dlp", "yt-dlp-nightly-builds"),
}
DOWNLOAD_TIMEOUT_SECONDS = 60
CHUNK_SIZE = 256 * 1024


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Baixa o binário oficial do yt-dlp para empacotamento.")
    parser.add_argument(
        "--channel",
        choices=sorted(REPOSITORIES.keys()),
        default="stable",
        help="Canal do yt-dlp a baixar.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Diretório onde o yt-dlp.exe será gravado.",
    )
    parser.add_argument(
        "--output-name",
        default=ASSET_NAME,
        help="Nome final do executável no diretório de saída.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / str(args.output_name or ASSET_NAME).strip()
    if not output_path.name:
        raise RuntimeError("O nome de saída do yt-dlp é inválido.")

    release_info = fetch_latest_release(channel=args.channel)
    download_dir = Path(tempfile.mkdtemp(prefix="keytune-ytdlp-build-"))
    executable_path = download_dir / ASSET_NAME
    checksum_path = download_dir / CHECKSUM_ASSET_NAME
    temporary_output_path = output_path.with_suffix(f"{output_path.suffix}.tmp")

    try:
        download_file(release_info["asset_url"], executable_path)
        download_file(release_info["checksum_url"], checksum_path)

        expected_checksum = extract_expected_checksum(
            checksum_path.read_text(encoding="utf-8"),
            asset_name=ASSET_NAME,
        )
        actual_checksum = calculate_sha256(executable_path)
        if actual_checksum.casefold() != expected_checksum.casefold():
            raise RuntimeError("O executável yt-dlp baixado não passou na validação de integridade.")

        shutil.copyfile(executable_path, temporary_output_path)
        temporary_output_path.replace(output_path)
    finally:
        try:
            if temporary_output_path.exists():
                temporary_output_path.unlink()
        except OSError:
            pass
        shutil.rmtree(download_dir, ignore_errors=True)

    print(f"Canal: {args.channel}")
    print(f"Versão: {release_info['version']}")
    print(f"Destino: {output_path}")
    return 0


def fetch_latest_release(*, channel: str) -> dict[str, str]:
    repository_owner, repository_name = REPOSITORIES[channel]
    api_url = f"https://api.github.com/repos/{repository_owner}/{repository_name}/releases/latest"
    payload = download_json(api_url)
    assets = payload.get("assets")
    if not isinstance(assets, list):
        raise RuntimeError("A release do yt-dlp veio sem a lista de assets.")

    asset = find_asset(assets, ASSET_NAME)
    checksum_asset = find_asset(assets, CHECKSUM_ASSET_NAME)
    if asset is None or checksum_asset is None:
        raise RuntimeError("A release do yt-dlp não publicou os assets esperados.")

    version_text = str(payload.get("tag_name") or payload.get("name") or "").strip()
    asset_url = str(asset.get("browser_download_url") or "").strip()
    checksum_url = str(checksum_asset.get("browser_download_url") or "").strip()
    if not version_text or not asset_url or not checksum_url:
        raise RuntimeError("A release do yt-dlp veio com metadados incompletos.")

    return {
        "version": version_text,
        "asset_url": asset_url,
        "checksum_url": checksum_url,
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
        raise RuntimeError("Não foi possível consultar a release do yt-dlp.") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("A release do yt-dlp veio em formato inválido.")
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
        raise RuntimeError("Não foi possível baixar os arquivos oficiais do yt-dlp.") from exc


def find_asset(assets: list[dict], asset_name: str) -> dict | None:
    expected_name = str(asset_name or "").casefold()
    for asset in assets:
        normalized_name = str(asset.get("name") or "").casefold()
        if normalized_name == expected_name:
            return asset
    return None


def extract_expected_checksum(checksum_text: str, *, asset_name: str) -> str:
    normalized_asset_name = str(asset_name or "").strip()
    for line in str(checksum_text or "").splitlines():
        normalized_line = line.strip()
        if not normalized_line or normalized_asset_name not in normalized_line:
            continue
        checksum_value = normalized_line.split()[0].strip()
        if len(checksum_value) == 64:
            return checksum_value
    raise RuntimeError("Não foi possível localizar o checksum oficial do yt-dlp baixado.")


def calculate_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with open(file_path, "rb") as source_file:
        while True:
            chunk = source_file.read(CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
