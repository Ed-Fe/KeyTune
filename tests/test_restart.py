from __future__ import annotations

import pathlib
import sys
import unittest
from unittest.mock import patch


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player import restart


class RestartTests(unittest.TestCase):
    def test_the_restart_is_only_asked_for_on_request(self):
        with patch.object(restart, "_requested", False):
            self.assertFalse(restart.restart_requested())
            restart.request_restart()
            self.assertTrue(restart.restart_requested())

    def test_the_source_checkout_reopens_through_main(self):
        with patch.object(restart.sys, "frozen", False, create=True):
            command = restart.restart_command()

        self.assertEqual(command[0], sys.executable)
        self.assertEqual(pathlib.Path(command[1]), SRC_ROOT / "main.py")

    def test_the_installed_player_reopens_its_own_executable(self):
        with patch.object(restart.sys, "frozen", True, create=True):
            self.assertEqual(restart.restart_command(), [sys.executable])

    def test_the_new_process_is_told_it_came_from_a_restart(self):
        with patch.object(restart.subprocess, "Popen") as popen:
            self.assertTrue(restart.relaunch())

        environment = popen.call_args.kwargs["env"]
        self.assertTrue(restart.started_by_restart(environment))
        # O aviso vale uma vez só: os processos filhos não o herdam.
        self.assertFalse(restart.started_by_restart(environment))

    def test_a_failed_reopen_is_reported_not_raised(self):
        with patch.object(restart.subprocess, "Popen", side_effect=OSError("sem permissão")):
            self.assertFalse(restart.relaunch())


if __name__ == "__main__":
    unittest.main()
