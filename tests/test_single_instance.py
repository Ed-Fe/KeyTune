from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch


SRC_ROOT = pathlib.Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player import single_instance


@unittest.skipIf(sys.platform.startswith("win"), "usa um socket Unix no lugar do pipe nomeado")
class SingleInstanceHandshakeTests(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        address = os.path.join(self._directory.name, "keytune.sock")
        patcher = patch.object(single_instance, "_PIPE_ADDRESS", address)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._directory.cleanup)

    def _start_server(self, callback):
        server = single_instance.SingleInstanceServer(callback)
        self.addCleanup(server.shutdown)
        return server

    def test_no_instance_listening_lets_the_caller_start(self):
        self.assertFalse(single_instance.try_send_to_existing_instance([]))

    def test_handled_launch_is_confirmed(self):
        received = []
        self._start_server(lambda message: received.append(message) or True)

        self.assertTrue(single_instance.try_send_to_existing_instance(["a.mp3"]))
        self.assertEqual(received, [{"action": "open", "paths": ["a.mp3"]}])

    def test_stalled_instance_is_terminated_and_caller_starts(self):
        self._start_server(lambda message: False)

        with patch.object(single_instance, "_terminate_stalled_instance") as terminate:
            self.assertFalse(single_instance.try_send_to_existing_instance([]))

        terminate.assert_called_once_with(os.getpid())

    def test_terminate_ignores_the_current_process(self):
        with patch.object(single_instance.os, "kill") as kill:
            single_instance._terminate_stalled_instance(os.getpid())
        kill.assert_not_called()


if __name__ == "__main__":
    unittest.main()
