from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


SRC_ROOT = pathlib.Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player import single_instance
from player.portable import PORTABLE_DIR_ENV


class PipeIdentityTests(unittest.TestCase):
    def test_installed_and_development_addresses_are_compatible(self):
        with patch("player.portable.is_portable", return_value=False):
            self.assertEqual(single_instance.build_pipe_address(dev_mode=False), r"\\.\pipe\KeyTune_SingleInstance")
            self.assertEqual(single_instance.build_pipe_address(dev_mode=True), r"\\.\pipe\KeyTune_SingleInstance_Dev")

    def test_portable_directories_get_separate_addresses(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            first, second = root / "Portable", root / "Second"
            first.mkdir()
            second.mkdir()
            with patch.dict(os.environ, {PORTABLE_DIR_ENV: str(first)}):
                address = single_instance.build_pipe_address(dev_mode=False)
            with patch.dict(os.environ, {PORTABLE_DIR_ENV: str(second / ".." / first.name)}):
                self.assertEqual(single_instance.build_pipe_address(dev_mode=False), address)
            with patch("player.portable.application_dir", return_value=pathlib.Path(str(first).upper())), patch(
                "player.portable.is_portable", return_value=True
            ):
                self.assertEqual(single_instance.build_pipe_address(dev_mode=False), address)
            with patch.dict(os.environ, {PORTABLE_DIR_ENV: str(second)}):
                self.assertNotEqual(single_instance.build_pipe_address(dev_mode=False), address)
        self.assertRegex(address, r"_Portable_[0-9a-f]{16}$")

    def test_client_and_listener_use_the_same_portable_address(self):
        connection = Mock()
        connection.recv.return_value = {"handled": True}
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {PORTABLE_DIR_ENV: directory}):
            address = single_instance.build_pipe_address(dev_mode=False)
            with (
                patch.object(single_instance, "_PIPE_ADDRESS", address),
                patch.object(single_instance, "Listener") as listener,
                patch.object(single_instance, "Client", return_value=connection) as client,
                patch.object(single_instance.threading, "Thread"),
            ):
                server = single_instance.SingleInstanceServer(Mock())
                self.addCleanup(server.shutdown)
                self.assertTrue(single_instance.try_send_to_existing_instance(["a.mp3"], enqueue=True))

        client.assert_called_once_with(address, authkey=single_instance._PIPE_AUTH_KEY)
        listener.assert_called_once_with(address, authkey=single_instance._PIPE_AUTH_KEY)


class InstanceMessageTests(unittest.TestCase):
    def test_enqueue_message_carries_the_paths(self):
        self.assertEqual(
            single_instance.build_instance_message(["a.mp3", "b.mp3"], enqueue=True),
            {"action": single_instance.ACTION_ENQUEUE, "paths": ["a.mp3", "b.mp3"]},
        )

    def test_enqueue_without_paths_asks_for_focus(self):
        self.assertEqual(
            single_instance.build_instance_message([], enqueue=True),
            {"action": "focus"},
        )

    def test_open_message_stays_the_same(self):
        self.assertEqual(
            single_instance.build_instance_message(["a.mp3"]),
            {"action": "open", "paths": ["a.mp3"]},
        )

    def test_try_send_forwards_the_enqueue_message(self):
        connection = unittest.mock.Mock()
        connection.poll.return_value = True
        connection.recv.return_value = {"handled": True}

        with patch.object(single_instance, "Client", return_value=connection):
            delivered = single_instance.try_send_to_existing_instance(["a.mp3", "b.mp3"], enqueue=True)

        self.assertTrue(delivered)
        connection.send.assert_called_once_with(
            {"action": "enqueue", "paths": ["a.mp3", "b.mp3"]}
        )

    def test_dispatch_enqueue_calls_only_the_enqueue_handler(self):
        target = unittest.mock.Mock()

        delivered = single_instance.dispatch_instance_message(
            target, {"action": "enqueue", "paths": ["a.mp3", "b.mp3"]}
        )

        self.assertTrue(delivered)
        target.receive_external_enqueue.assert_called_once_with(["a.mp3", "b.mp3"])
        target.receive_external_files.assert_not_called()
        target.focus_from_relaunch.assert_not_called()

    def test_dispatch_open_and_focus_stay_on_their_handlers(self):
        target = unittest.mock.Mock()

        self.assertTrue(
            single_instance.dispatch_instance_message(target, {"action": "open", "paths": ["a.mp3"]})
        )
        self.assertTrue(single_instance.dispatch_instance_message(target, {"action": "focus"}))
        self.assertFalse(single_instance.dispatch_instance_message(None, {"action": "enqueue"}))
        self.assertFalse(single_instance.dispatch_instance_message(target, {"action": "nope"}))

        target.receive_external_files.assert_called_once_with(["a.mp3"])
        target.focus_from_relaunch.assert_called_once_with()
        target.receive_external_enqueue.assert_not_called()


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

    def test_enqueue_launch_is_confirmed(self):
        received = []
        self._start_server(lambda message: received.append(message) or True)

        self.assertTrue(
            single_instance.try_send_to_existing_instance(["a.mp3", "b.mp3"], enqueue=True)
        )
        self.assertEqual(received, [{"action": "enqueue", "paths": ["a.mp3", "b.mp3"]}])

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
