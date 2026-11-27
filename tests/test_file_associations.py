from __future__ import annotations

import importlib
import re
import sys
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import Mock, patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.constants import SUPPORTED_MEDIA_EXTENSIONS


class FileAssociationTests(unittest.TestCase):
    def setUp(self):
        self.keys = {}
        registry = Mock(HKEY_CURRENT_USER="HKCU", KEY_READ=1, KEY_WRITE=2, REG_SZ=1, REG_NONE=0)
        registry.CreateKeyEx.side_effect = self._create_key
        registry.OpenKeyEx.side_effect = self._open_key
        registry.SetValueEx.side_effect = self._set_value
        registry.QueryValueEx.side_effect = self._query_value
        registry.DeleteValue.side_effect = self._delete_value
        registry.EnumKey.side_effect = self._enum_key
        registry.DeleteKey.side_effect = self._delete_key

        try:
            self.associations = importlib.import_module("player.file_associations")
        except ModuleNotFoundError as exc:
            if exc.name != "winreg":
                raise
            with patch.dict(sys.modules, {"winreg": registry}):
                self.associations = importlib.import_module("player.file_associations")
        self.enterContext(patch.object(self.associations, "winreg", registry))
        self.enterContext(patch.object(self.associations, "_notify_shell"))
        self.enterContext(patch.object(sys, "frozen", True, create=True))
        self.portable = self.enterContext(patch.object(self.associations, "is_portable", return_value=False))
        self.enterContext(patch.object(sys, "executable", r"C:\Program Files\KeyTune\KeyTune.exe"))

    def _create_key(self, _root, subkey, *_args):
        parts = subkey.casefold().split("\\")
        for depth in range(1, len(parts) + 1):
            self.keys.setdefault("\\".join(parts[:depth]), {})
        return nullcontext(subkey.casefold())

    def _open_key(self, _root, subkey, *_args):
        if subkey.casefold() not in self.keys:
            raise FileNotFoundError(subkey)
        return nullcontext(subkey.casefold())

    def _set_value(self, key, name, _reserved, kind, data):
        self.keys[key][name.casefold()] = data, kind

    def _query_value(self, key, name):
        try:
            return self.keys[key][name.casefold()]
        except KeyError:
            raise FileNotFoundError(name) from None

    def _delete_value(self, key, name):
        self._query_value(key, name)
        del self.keys[key][name.casefold()]

    def _enum_key(self, key, index):
        prefix = key + "\\"
        children = [path[len(prefix):] for path in self.keys if path.startswith(prefix)]
        direct = [child for child in children if "\\" not in child]
        if index >= len(direct):
            raise OSError("no more keys")
        return direct[index]

    def _delete_key(self, _root, subkey):
        key = subkey.casefold()
        if any(path.startswith(key + "\\") for path in self.keys):
            raise OSError("has subkeys")
        del self.keys[key]

    def _values(self, key):
        return {name: data for name, (data, _) in self.keys[rf"Software\Classes\{key}".casefold()].items()}

    def test_portable_and_installed_progids_and_verbs_are_independent(self):
        self.assertTrue(self.associations.register_file_associations())
        with patch.object(sys, "executable", r"E:\KeyTune\KeyTune.exe"):
            self.portable.return_value = True
            self.assertFalse(self.associations.are_associations_registered())
            self.assertTrue(self.associations.register_file_associations())
            self.assertTrue(self.associations.are_associations_registered())
            self.assertEqual(self._values(r"KeyTune.Portable.MediaFile\shell\open\command")[""], f'"{sys.executable}" "%1"')
            self.assertEqual(set(self._values(r".mp3\OpenWithProgids")), {
                "keytune.mediafile", "keytune.portable.mediafile",
            })
            self.assertTrue(self.associations.unregister_file_associations())
            self.assertFalse(self.associations.are_associations_registered())
        self.portable.return_value = False
        self.assertTrue(self.associations.are_associations_registered())
        self.assertEqual(self._values(r"KeyTune.MediaFile\shell\open\command")[""], f'"{sys.executable}" "%1"')
        self.assertEqual(set(self._values(r".mp3\OpenWithProgids")), {"keytune.mediafile"})
        self.assertIn(r"software\classes\systemfileassociations\.mp3\shell\keytune.enqueue", self.keys)
        self.assertNotIn(r"software\classes\systemfileassociations\.mp3\shell\keytune.portable.enqueue", self.keys)

    def test_unregistration_checks_which_portable_copy_owns_the_commands(self):
        self.portable.return_value = True
        with patch.object(sys, "executable", r"E:\First\KeyTune.exe"):
            self.assertTrue(self.associations.register_file_associations())
        with patch.object(sys, "executable", r"F:\Second\KeyTune.exe"):
            self.assertTrue(self.associations.register_file_associations())
        with patch.object(sys, "executable", r"E:\First\KeyTune.exe"):
            self.assertFalse(self.associations.are_associations_registered())
            self.assertTrue(self.associations.unregister_file_associations())
        with patch.object(sys, "executable", r"f:\second\KEYTUNE.EXE"):
            self.assertTrue(self.associations.are_associations_registered())
            key = r"SystemFileAssociations\.mp3\shell\KeyTune.Portable.enqueue\command"
            self.assertEqual(self._values(key)[""], r'"F:\Second\KeyTune.exe" --enqueue "%1"')
            self.assertTrue(self.associations.unregister_file_associations())
            self.assertEqual(self._values(r".mp3\OpenWithProgids"), {})
            self.assertNotIn(rf"software\classes\{key}".casefold(), self.keys)

    def test_media_extensions_get_verb_and_playlists_keep_open_with(self):
        unrelated = r"Software\Classes\SystemFileAssociations\.mp3\shell\OtherPlayer.Convert"
        with self._create_key(None, unrelated) as key:
            self._set_value(key, "", 0, 1, "Convert")

        self.assertTrue(self.associations.register_file_associations())
        for ext in SUPPORTED_MEDIA_EXTENSIONS:
            verb = rf"SystemFileAssociations\{ext}\shell\KeyTune.enqueue"
            self.assertEqual(self._values(verb), {
                "": "Adicionar à playlist do KeyTune", "multiselectmodel": "Player",
            })
            self.assertEqual(self._values(verb + r"\command")[""], f'"{sys.executable}" --enqueue "%1"')
        self.assertEqual(self._values(r"KeyTune.MediaFile\shell\KeyTune.enqueue")["multiselectmodel"], "Player")
        for ext in (".m3u", ".m3u8"):
            self.assertIn("keytune.mediafile", self._values(rf"{ext}\OpenWithProgids"))
            self.assertNotIn(rf"software\classes\systemfileassociations\{ext}\shell\keytune.enqueue", self.keys)

        self.assertTrue(self.associations.unregister_file_associations())
        self.assertIn(unrelated.casefold(), self.keys)
        self.assertFalse(any("keytune.enqueue" in key for key in self.keys))


class InstallerAssociationTests(unittest.TestCase):
    def test_extension_verbs_follow_the_same_tasks_as_open_with(self):
        script = (PROJECT_ROOT / "installer" / "keytune.iss").read_text(encoding="utf-8")
        tasks = dict(re.findall(r'Name: "(assoc(?:audio|video)\\\w+)"; Description: "(\.\w+)"', script))
        self.assertEqual(set(tasks.values()), SUPPORTED_MEDIA_EXTENSIONS)
        verbs = [line for line in script.splitlines() if "\\SystemFileAssociations\\" in line]
        self.assertEqual(len(verbs), 3 * len(tasks))
        for task, ext in tasks.items():
            with self.subTest(ext=ext):
                key = rf'Subkey: "Software\Classes\SystemFileAssociations\{ext}\shell\{{#EnqueueVerb}}'
                rows = [line for line in verbs if key in line]
                self.assertEqual(len(rows), 3)
                self.assertTrue(all(line.startswith("Root: HKA;") and line.endswith(f"; Tasks: {task}") for line in rows))
                self.assertTrue(any('ValueData: "{cm:EnqueueWithApp}"; Flags: uninsdeletekey' in line for line in rows))
                self.assertTrue(any('ValueName: "MultiSelectModel"; ValueData: "Player"' in line for line in rows))
                self.assertTrue(any(r'\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" --enqueue ""%1"""' in line for line in rows))
