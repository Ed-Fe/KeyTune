from __future__ import annotations

import json
import pathlib
import queue
import sys
import threading
import time
import unittest
from types import SimpleNamespace


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.youtube_music import youtubejs_runtime
from player.youtube_music.youtubejs_worker import RESULT_PREFIX, NodeWorker


class FakeProcess:
    """Um processo Node de mentira: ``handler(pedido, responder)`` decide o que responder."""

    def __init__(self, handler):
        self._handler = handler
        self._lines = queue.Queue()
        self.returncode = None
        self.break_pipe = False
        self.requests = []
        self.stdin = SimpleNamespace(write=self._write, flush=lambda: None)
        self.stdout = SimpleNamespace(readline=self._lines.get)

    def _write(self, line):
        if self.break_pipe or self.returncode is not None:
            raise BrokenPipeError("o processo acabou")
        request = json.loads(line)
        self.requests.append(request)
        self._handler(request, lambda response: self.respond(request["id"], response))

    def respond(self, request_id, response):
        self._lines.put(RESULT_PREFIX + json.dumps({**response, "id": request_id}) + "\n")

    def say(self, text):
        self._lines.put(text + "\n")

    def die(self):
        self.returncode = 1
        self._lines.put("")

    def poll(self):
        return self.returncode

    def kill(self):
        self.die()

    def wait(self, timeout=None):
        return self.returncode


def echo(request, respond):
    respond({"echo": request.get("value")})


class Spawner:
    def __init__(self, *handlers):
        self.handlers = list(handlers)
        self.processes = []

    def __call__(self):
        handler = self.handlers[min(len(self.processes), len(self.handlers) - 1)]
        process = FakeProcess(handler)
        self.processes.append(process)
        return process


class NodeWorkerTests(unittest.TestCase):
    def worker(self, *handlers):
        spawner = Spawner(*handlers)
        worker = NodeWorker("teste", spawner)
        self.addCleanup(worker.stop)
        return worker, spawner

    def test_each_request_gets_its_own_answer_even_out_of_order(self):
        held = {}

        def handler(request, respond):
            if request["value"] == "lento":
                held["respond"] = lambda: respond({"echo": "lento"})
            else:
                respond({"echo": request["value"]})

        worker, _spawner = self.worker(handler)
        results = {}
        slow = threading.Thread(
            target=lambda: results.update(slow=worker.request({"value": "lento"}, timeout=5, replay_safe=True))
        )
        slow.start()
        while "respond" not in held:
            time.sleep(0.01)

        fast = worker.request({"value": "rapido"}, timeout=5, replay_safe=True)
        held["respond"]()
        slow.join(5)

        self.assertEqual(fast["echo"], "rapido")
        self.assertEqual(results["slow"]["echo"], "lento")

    def test_a_request_that_times_out_does_not_kill_the_process_or_the_others(self):
        def handler(request, respond):
            if request["value"] != "travado":
                respond({"echo": request["value"]})

        worker, spawner = self.worker(handler)
        with self.assertRaisesRegex(RuntimeError, "demorou demais"):
            worker.request({"value": "travado"}, timeout=0.1, replay_safe=True)
        answer = worker.request({"value": "outro"}, timeout=5, replay_safe=True)

        self.assertEqual(answer["echo"], "outro")
        self.assertEqual(len(spawner.processes), 1)
        self.assertIsNone(spawner.processes[0].returncode)

    def test_a_late_answer_to_a_request_that_gave_up_is_ignored(self):
        held = []

        def handler(request, respond):
            if request["value"] == "atrasado":
                held.append(lambda: respond({"echo": "tarde demais"}))
            else:
                respond({"echo": request["value"]})

        worker, _spawner = self.worker(handler)
        with self.assertRaises(RuntimeError):
            worker.request({"value": "atrasado"}, timeout=0.1, replay_safe=True)
        held[0]()

        self.assertEqual(worker.request({"value": "novo"}, timeout=5, replay_safe=True)["echo"], "novo")

    def test_a_process_that_answers_nothing_for_several_requests_is_restarted(self):
        def silent(request, respond):
            pass

        worker, spawner = self.worker(silent, echo)
        for _ in range(3):
            with self.assertRaises(RuntimeError):
                worker.request({"value": "x"}, timeout=0.05, replay_safe=True)

        self.assertEqual(worker.request({"value": "volta"}, timeout=5, replay_safe=True)["echo"], "volta")
        self.assertEqual(len(spawner.processes), 2)
        self.assertIsNotNone(spawner.processes[0].returncode)

    def test_a_read_is_repeated_when_the_process_dies_without_answering(self):
        def dies(request, respond):
            spawner.processes[0].die()

        worker, spawner = self.worker(dies, echo)

        self.assertEqual(worker.request({"value": "leitura"}, timeout=5, replay_safe=True)["echo"], "leitura")
        self.assertEqual(len(spawner.processes), 2)

    def test_a_write_is_never_repeated_once_it_reached_the_process(self):
        def dies(request, respond):
            spawner.processes[0].die()

        worker, spawner = self.worker(dies, echo)

        with self.assertRaisesRegex(RuntimeError, "encerrado"):
            worker.request({"action": "create_comment", "value": "oi"}, timeout=5, replay_safe=False)
        self.assertEqual(len(spawner.processes), 1)
        delivered = [request for process in spawner.processes for request in process.requests]
        self.assertEqual(len(delivered), 1)

    def test_a_request_that_never_reached_the_process_is_repeated_even_if_it_writes(self):
        worker, spawner = self.worker(echo)
        first = worker.ensure_started()
        spawner.processes[0].break_pipe = True  # parece vivo, mas a entrada já está fechada

        answer = worker.request({"action": "create_comment", "value": "oi"}, timeout=5, replay_safe=False)

        self.assertEqual(answer["echo"], "oi")
        self.assertIsNot(worker.ensure_started(), first)

    def test_lines_that_are_not_answers_become_error_details(self):
        def handler(request, respond):
            spawner.processes[0].say("Error: algo deu errado no Node")

        worker, spawner = self.worker(handler)
        with self.assertRaisesRegex(RuntimeError, "algo deu errado no Node"):
            worker.request({"value": "x"}, timeout=0.3, replay_safe=True)


class RuntimeRoutingTests(unittest.TestCase):
    def setUp(self):
        self.playback = Spawner(lambda request, respond: respond({"stream_url": "http://127.0.0.1/stream/1"}))
        self.actions = Spawner(echo)
        self.originals = (youtubejs_runtime._playback_worker, youtubejs_runtime._actions_worker)
        youtubejs_runtime._playback_worker = NodeWorker("playback", self.playback)
        youtubejs_runtime._actions_worker = NodeWorker("actions", self.actions)
        self.addCleanup(self.restore)

    def restore(self):
        youtubejs_runtime._stop_worker()
        youtubejs_runtime._playback_worker, youtubejs_runtime._actions_worker = self.originals

    def test_playback_and_actions_run_in_separate_processes(self):
        youtubejs_runtime._request_worker({"media_url": "https://www.youtube.com/watch?v=abc123DEF45"})
        youtubejs_runtime._request_worker({"action": "notifications", "value": "x"})

        self.assertEqual(len(self.playback.processes), 1)
        self.assertEqual(len(self.actions.processes), 1)
        self.assertEqual(self.playback.processes[0].requests[0].get("action"), None)
        self.assertEqual(self.actions.processes[0].requests[0]["action"], "notifications")

    def test_the_actions_process_dying_leaves_playback_alone(self):
        youtubejs_runtime._request_worker({"media_url": "abc123DEF45"})
        youtubejs_runtime._request_worker({"action": "notifications", "value": "x"})

        youtubejs_runtime._actions_worker.stop()

        self.assertIsNone(self.playback.processes[0].returncode)
        self.assertIsNotNone(self.actions.processes[0].returncode)

    def test_writes_are_not_replayed_but_reads_are(self):
        self.assertNotIn("search", youtubejs_runtime._WRITE_ACTIONS)
        for action in ("create_comment", "comment_action", "live_chat_send", "post_vote", "channel_action"):
            self.assertIn(action, youtubejs_runtime._WRITE_ACTIONS)


if __name__ == "__main__":
    unittest.main()
