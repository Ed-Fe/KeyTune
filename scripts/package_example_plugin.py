"""Gera o pacote instalável do plugin de exemplo do KeyTune."""

from __future__ import annotations

from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = ROOT / "examples" / "plugins" / "now-playing"
OUTPUT = PLUGIN_DIR / "now-playing-example-1.1.0.ktplugin"
FILES = ("keytune-plugin.json", "plugin.py")


def main() -> None:
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            archive.write(PLUGIN_DIR / name, name)
    print(OUTPUT)


if __name__ == "__main__":
    main()
