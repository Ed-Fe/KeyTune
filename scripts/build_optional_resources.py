from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESOURCE_LABELS = {
    "node": "NodeJS",
    "youtube": "YouTubePython",
    "youtubejs": "YouTubeJS",
    "autodj": "AutoDJ",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Gera os pacotes opcionais do KeyTune.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--app-version", required=True)
    parser.add_argument("--python-exe", default=sys.executable)
    parser.add_argument("--node-executable", default="node")
    parser.add_argument("--architecture", default="x64", choices=("x64", "arm64"))
    parser.add_argument(
        "--resource",
        action="append",
        choices=tuple(RESOURCE_LABELS),
        help="Gera somente o recurso informado; pode ser repetido.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    selected_resources = set(args.resource or RESOURCE_LABELS)
    if "node" in selected_resources:
        _build_node(output_dir, args)
    if "youtube" in selected_resources:
        _build_youtube(output_dir, args)
    if "youtubejs" in selected_resources:
        _build_youtubejs(output_dir, args)
    if "autodj" in selected_resources:
        _build_autodj(output_dir, args)
    return 0


def _build_node(output_dir, args):
    node_path = Path(shutil.which(args.node_executable) or args.node_executable).resolve()
    if not node_path.is_file():
        raise RuntimeError(f"Node.js não encontrado: {node_path}")
    with tempfile.TemporaryDirectory(prefix="keytune-node-resource-", dir=output_dir.parent) as temporary:
        content = Path(temporary) / "content"
        content.mkdir()
        shutil.copy2(node_path, content / "node.exe")
        version = _command_output([str(node_path), "--version"]).lstrip("v")
        _write_manifest(content, "node", args.app_version, ["node.exe"], {"Node.js": version})
        _archive_resource(output_dir, "node", content, args.architecture)


def _build_youtubejs(output_dir, args):
    source_dir = PROJECT_ROOT / "src" / "player" / "youtube_music" / "youtubejs"
    with tempfile.TemporaryDirectory(prefix="keytune-youtubejs-resource-", dir=output_dir.parent) as temporary:
        content = Path(temporary) / "content"
        content.mkdir()
        for filename in ("resolve.mjs", "package.json", "package-lock.json"):
            shutil.copy2(source_dir / filename, content / filename)
        node_path = Path(shutil.which(args.node_executable) or args.node_executable).resolve()
        npm_cli = node_path.parent / "node_modules" / "npm" / "bin" / "npm-cli.js"
        npm_path = shutil.which("npm")
        if npm_cli.is_file():
            command = [str(node_path), str(npm_cli), "ci", "--omit=dev"]
        elif npm_path:
            command = [npm_path, "ci", "--omit=dev"]
        else:
            raise RuntimeError("npm não encontrado. Instale o Node.js com npm para gerar o recurso YouTube.js.")
        subprocess.run(command, cwd=content, check=True)
        package = json.loads((content / "node_modules" / "youtubei.js" / "package.json").read_text(encoding="utf-8"))
        _write_manifest(
            content,
            "youtubejs",
            args.app_version,
            ["resolve.mjs", "node_modules/youtubei.js"],
            {"YouTube.js": str(package.get("version") or "")},
        )
        _archive_resource(output_dir, "youtubejs", content, args.architecture)


def _build_youtube(output_dir, args):
    with tempfile.TemporaryDirectory(prefix="keytune-youtube-resource-", dir=output_dir.parent) as temporary:
        content = Path(temporary) / "content"
        site_packages = content / "site-packages"
        pip_temp_dir = Path(temporary) / "pip-temp"
        pip_temp_dir.mkdir()
        pip_environment = os.environ.copy()
        pip_environment.update({"TMP": str(pip_temp_dir), "TEMP": str(pip_temp_dir)})
        subprocess.run(
            [
                args.python_exe,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-cache-dir",
                "--only-binary=:all:",
                "--target",
                str(site_packages),
                "-r",
                str(PROJECT_ROOT / "requirements-youtube.txt"),
            ],
            check=True,
            env=pip_environment,
        )
        for cache_dir in site_packages.rglob("__pycache__"):
            shutil.rmtree(cache_dir, ignore_errors=True)
        versions = _distribution_versions(site_packages, ("ytmusicapi", "requests"))
        _write_manifest(
            content,
            "youtube",
            args.app_version,
            ["site-packages/ytmusicapi", "site-packages/requests"],
            versions,
        )
        _archive_resource(output_dir, "youtube", content, args.architecture)


def _build_autodj(output_dir, args):
    with tempfile.TemporaryDirectory(prefix="keytune-autodj-resource-", dir=output_dir.parent) as temporary:
        content = Path(temporary) / "content"
        site_packages = content / "site-packages"
        pip_temp_dir = Path(temporary) / "pip-temp"
        pip_temp_dir.mkdir()
        pip_environment = os.environ.copy()
        pip_environment.update({"TMP": str(pip_temp_dir), "TEMP": str(pip_temp_dir)})
        subprocess.run(
            [
                args.python_exe,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-cache-dir",
                "--only-binary=:all:",
                "--target",
                str(site_packages),
                "-r",
                str(PROJECT_ROOT / "requirements-autodj.txt"),
            ],
            check=True,
            env=pip_environment,
        )
        for cache_dir in site_packages.rglob("__pycache__"):
            shutil.rmtree(cache_dir, ignore_errors=True)
        versions = _distribution_versions(site_packages, ("librosa", "numpy", "scipy", "numba", "av"))
        _write_manifest(
            content,
            "autodj",
            args.app_version,
            ["site-packages/librosa", "site-packages/numpy", "site-packages/av"],
            versions,
        )
        _archive_resource(output_dir, "autodj", content, args.architecture)


def _distribution_versions(site_packages, names):
    versions = {}
    for name in names:
        normalized = name.replace("-", "_").casefold()
        candidates = sorted(site_packages.glob(f"{normalized}-*.dist-info"))
        if candidates:
            stem = candidates[-1].name[: -len(".dist-info")]
            versions[name] = stem.rsplit("-", 1)[-1]
    return versions


def _write_manifest(content, resource, app_version, required_paths, versions):
    manifest = {
        "resource": resource,
        "app_version": app_version,
        "required_paths": required_paths,
        "versions": versions,
    }
    (content / "keytune-resource.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _archive_resource(output_dir, resource, content, architecture):
    asset_name = f"KeyTune-{RESOURCE_LABELS[resource]}-win-{architecture}.zip"
    archive_path = output_dir / asset_name
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(content.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(content))
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    (output_dir / f"{asset_name}.sha256").write_text(f"{digest}  {asset_name}\n", encoding="ascii")


def _command_output(command):
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout.strip()


if __name__ == "__main__":
    raise SystemExit(main())
