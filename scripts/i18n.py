#!/usr/bin/env python3
"""Translation tooling for KeyTune (no external gettext binaries required).

Two self-contained subcommands keep the localization workflow reproducible on
any machine that has Python, including the CI runner:

    python scripts/i18n.py extract
        Scan ``src/`` for ``_( ... )`` / ``ngettext( ... )`` calls and (re)write
        ``locale/keytune.pot`` — the template translators start from.

    python scripts/i18n.py compile
        Compile every ``locale/<lang>/LC_MESSAGES/keytune.po`` into the matching
        ``.mo`` binary the application loads at runtime.

The ``.po`` parser and ``.mo`` writer implement just the subset of the GNU
gettext formats KeyTune uses (singular + plural messages, no contexts), so the
project never depends on ``xgettext``/``msgfmt`` being installed.
"""

from __future__ import annotations

import argparse
import ast
import struct
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = REPO_ROOT / "src"
LOCALE_DIR = REPO_ROOT / "locale"
DOMAIN = "keytune"
POT_PATH = LOCALE_DIR / f"{DOMAIN}.pot"

# Names that mark a translatable string when called as ``NAME("...")``.
TRANSLATION_FUNCTIONS = {"_", "gettext", "ngettext"}


# --------------------------------------------------------------------------- #
# Extraction
# --------------------------------------------------------------------------- #
def _string_arg(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    # Allow implicitly concatenated literals: _("a" "b").
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _string_arg(node.left)
        right = _string_arg(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def extract_from_source(source_text: str) -> list[tuple[str, str | None]]:
    """Return ``(singular, plural-or-None)`` pairs found in *source_text*."""

    tree = ast.parse(source_text)
    messages: list[tuple[str, str | None]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        if name not in TRANSLATION_FUNCTIONS:
            continue

        singular = _string_arg(node.args[0])
        if singular is None:
            continue

        plural = None
        if name == "ngettext" and len(node.args) >= 2:
            plural = _string_arg(node.args[1])

        messages.append((singular, plural))

    return messages


def _po_escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )


def build_pot(messages: dict[str, tuple[str | None, list[str]]]) -> str:
    lines = [
        'msgid ""',
        'msgstr ""',
        '"Project-Id-Version: KeyTune\\n"',
        '"Content-Type: text/plain; charset=UTF-8\\n"',
        '"Content-Transfer-Encoding: 8bit\\n"',
        '"Plural-Forms: nplurals=2; plural=(n != 1);\\n"',
        "",
    ]

    for singular in sorted(messages):
        plural, references = messages[singular]
        for reference in sorted(set(references)):
            lines.append(f"#: {reference}")
        lines.append(f'msgid "{_po_escape(singular)}"')
        if plural is not None:
            lines.append(f'msgid_plural "{_po_escape(plural)}"')
            lines.append('msgstr[0] ""')
            lines.append('msgstr[1] ""')
        else:
            lines.append('msgstr ""')
        lines.append("")

    return "\n".join(lines)


def run_extract() -> int:
    messages: dict[str, tuple[str | None, list[str]]] = {}

    for path in sorted(SOURCE_DIR.rglob("*.py")):
        try:
            source_text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            found = extract_from_source(source_text)
        except SyntaxError:
            continue

        relative = path.relative_to(REPO_ROOT).as_posix()
        for singular, plural in found:
            existing_plural, references = messages.get(singular, (None, []))
            references = list(references)
            references.append(relative)
            messages[singular] = (plural or existing_plural, references)

    LOCALE_DIR.mkdir(parents=True, exist_ok=True)
    POT_PATH.write_text(build_pot(messages), encoding="utf-8")
    print(f"Extracted {len(messages)} message(s) -> {POT_PATH.relative_to(REPO_ROOT)}")
    return 0


# --------------------------------------------------------------------------- #
# Compilation (.po -> .mo)
# --------------------------------------------------------------------------- #
def _parse_po(text: str) -> dict[str, str]:
    """Parse a ``.po`` file into a ``{key: translation}`` mapping.

    Plural messages are encoded the way Python's ``gettext`` expects: the key is
    ``singular + "\\x00" + plural`` and the value joins the plural forms with
    ``\\x00``.
    """

    entries: dict[str, str] = {}

    msgid: list[str] = []
    msgid_plural: list[str] = []
    msgstrs: dict[int, list[str]] = {}
    current: list[str] | None = None
    current_index = 0
    # ``fuzzy`` is the flag for the entry currently being assembled; ``pending``
    # collects the flag from a ``#, fuzzy`` comment, which precedes the *next*
    # entry's msgid, and is promoted to ``fuzzy`` when that msgid is reached.
    fuzzy = False
    pending_fuzzy = False

    def flush() -> None:
        if not msgid and 0 not in msgstrs and not msgid_plural:
            return
        key = "".join(msgid)
        if msgid_plural:
            key = key + "\x00" + "".join(msgid_plural)
            value = "\x00".join("".join(msgstrs.get(i, [])) for i in sorted(msgstrs))
        else:
            value = "".join(msgstrs.get(0, []))
        # Keep the header (empty msgid) and skip fuzzy/empty translations so the
        # runtime falls back to the source string instead of showing blanks.
        if key == "" or (value and not fuzzy):
            entries[key] = value

    def unquote(segment: str) -> str:
        segment = segment.strip()
        if len(segment) >= 2 and segment[0] == '"' and segment[-1] == '"':
            segment = segment[1:-1]
        return (
            segment.replace("\\n", "\n")
            .replace("\\t", "\t")
            .replace('\\"', '"')
            .replace("\\\\", "\\")
        )

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            if line.startswith("#,") and "fuzzy" in line:
                pending_fuzzy = True
            continue
        if line.startswith("msgid_plural"):
            current = msgid_plural
            current.append(unquote(line[len("msgid_plural"):]))
            continue
        if line.startswith("msgid"):
            flush()
            fuzzy = pending_fuzzy
            pending_fuzzy = False
            msgid = [unquote(line[len("msgid"):])]
            msgid_plural = []
            msgstrs = {}
            current = msgid
            continue
        if line.startswith("msgstr["):
            closing = line.index("]")
            current_index = int(line[len("msgstr["):closing])
            current = msgstrs.setdefault(current_index, [])
            current.append(unquote(line[closing + 1:]))
            continue
        if line.startswith("msgstr"):
            current = msgstrs.setdefault(0, [])
            current.append(unquote(line[len("msgstr"):]))
            continue
        if line.startswith('"') and current is not None:
            current.append(unquote(line))

    flush()
    return entries


def _compile_mo(entries: dict[str, str]) -> bytes:
    keys = sorted(entries.keys())
    offsets: list[tuple[int, int, int, int]] = []
    ids = b""
    strs = b""

    for key in keys:
        encoded_key = key.encode("utf-8")
        encoded_value = entries[key].encode("utf-8")
        offsets.append((len(ids), len(encoded_key), len(strs), len(encoded_value)))
        ids += encoded_key + b"\x00"
        strs += encoded_value + b"\x00"

    count = len(keys)
    key_table_offset = 7 * 4
    value_table_offset = key_table_offset + count * 8
    ids_start = value_table_offset + count * 8

    key_table = b""
    value_table = b""
    for id_offset, id_length, str_offset, str_length in offsets:
        key_table += struct.pack("<II", id_length, ids_start + id_offset)
        value_table += struct.pack("<II", str_length, ids_start + len(ids) + str_offset)

    output = struct.pack(
        "<7I",
        0x950412DE,  # magic
        0,            # version
        count,
        key_table_offset,
        value_table_offset,
        0,            # hash table size
        0,            # hash table offset
    )
    return output + key_table + value_table + ids + strs


def run_compile() -> int:
    if not LOCALE_DIR.is_dir():
        print(f"No locale directory at {LOCALE_DIR}; nothing to compile.")
        return 0

    compiled = 0
    for po_path in sorted(LOCALE_DIR.rglob(f"{DOMAIN}.po")):
        entries = _parse_po(po_path.read_text(encoding="utf-8"))
        mo_path = po_path.with_suffix(".mo")
        mo_path.write_bytes(_compile_mo(entries))
        print(f"Compiled {po_path.relative_to(REPO_ROOT)} -> {mo_path.relative_to(REPO_ROOT)}")
        compiled += 1

    if not compiled:
        print("No .po catalogs found to compile.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="KeyTune translation tooling.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("extract", help="Rebuild locale/keytune.pot from the source tree.")
    subparsers.add_parser("compile", help="Compile every locale/**/keytune.po into a .mo file.")
    args = parser.parse_args()

    if args.command == "extract":
        return run_extract()
    if args.command == "compile":
        return run_compile()
    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
