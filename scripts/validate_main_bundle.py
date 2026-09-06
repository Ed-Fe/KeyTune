from __future__ import annotations

import argparse
from pathlib import Path


FORBIDDEN_OPTIONAL_MODULES = (
    "av",
    "librosa",
    "llvmlite",
    "numba",
    "numpy",
    "scipy",
)


def find_bundled_optional_dependencies(bundle_dir: Path) -> list[str]:
    internal_dir = bundle_dir / "_internal"
    if not internal_dir.is_dir():
        raise RuntimeError(f"Diretório interno do aplicativo não encontrado: {internal_dir}")

    found = []
    entries = tuple(internal_dir.iterdir())
    for module_name in FORBIDDEN_OPTIONAL_MODULES:
        normalized = module_name.casefold().replace("-", "_")
        if any(
            entry.name.casefold().replace("-", "_") == normalized
            or entry.name.casefold().replace("-", "_").startswith(f"{normalized}_")
            for entry in entries
        ):
            found.append(module_name)
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle_dir", type=Path)
    args = parser.parse_args()

    found = find_bundled_optional_dependencies(args.bundle_dir)
    if found:
        raise RuntimeError(
            "O executável principal contém dependências opcionais do AutoDJ: "
            + ", ".join(found)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
