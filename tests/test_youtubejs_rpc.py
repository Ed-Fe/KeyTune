"""O protocolo do worker Node de verdade (lib/rpc.mjs): ids, pistas e tempo de cada pedido."""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import threading
import time
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
PROBE = PROJECT_ROOT / "tests" / "fixtures" / "rpc_probe.mjs"
RESULT_PREFIX = "KEYTUNE_YOUTUBEJS_RESULT="


@unittest.skipUnless(shutil.which("node"), "precisa do Node.js")
class RpcProtocolTests(unittest.TestCase):
    def setUp(self):
        self.process = subprocess.Popen(
            [shutil.which("node"), str(PROBE)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
        )
        self.answers = []
        self.lines = []
        self.started = time.monotonic()
        threading.Thread(target=self._read, daemon=True).start()
        self.addCleanup(self._stop)

    def _stop(self):
        self.process.kill()
        self.process.wait()
        self.process.stdin.close()
        self.process.stdout.close()

    def _read(self):
        for line in self.process.stdout:
            if line.startswith(RESULT_PREFIX):
                answer = json.loads(line[len(RESULT_PREFIX):])
                answer["at"] = time.monotonic() - self.started
                self.answers.append(answer)
            else:
                self.lines.append(line.strip())

    def send(self, request_id, action, **fields):
        self.process.stdin.write(json.dumps({"id": request_id, "action": action, **fields}) + "\n")
        self.process.stdin.flush()

    def wait_for(self, count, timeout=5):
        deadline = time.monotonic() + timeout
        while len(self.answers) < count and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertGreaterEqual(len(self.answers), count, self.lines)
        return {answer["id"]: answer for answer in self.answers}

    def test_every_answer_carries_the_id_of_its_request(self):
        self.send(7, "fast", value="a")
        self.send(8, "boom")

        answers = self.wait_for(2)

        self.assertEqual(answers[7]["value"], "a")
        self.assertIn("falhou de propósito", answers[8]["error"])

    def test_an_unknown_action_is_an_error_not_a_crash(self):
        self.send(1, "nao_existe")
        self.send(2, "fast", value="ainda vivo")

        answers = self.wait_for(2)

        self.assertIn("Ação desconhecida", answers[1]["error"])
        self.assertEqual(answers[2]["value"], "ainda vivo")

    def test_a_request_without_a_lane_does_not_wait_for_a_slow_one(self):
        self.send(1, "slow", value="lento")
        self.send(2, "stray")

        answers = self.wait_for(2)

        self.assertLess(answers[2]["at"], answers[1]["at"])

    def test_requests_in_one_lane_keep_their_order(self):
        self.send(1, "slow", value="primeiro")
        self.send(2, "fast", value="segundo")

        answers = self.wait_for(2)

        self.assertLess(answers[1]["at"], answers[2]["at"])

    def test_a_handler_that_never_answers_gives_up_and_frees_its_lane(self):
        self.send(1, "hang")
        self.send(2, "fast", value="depois")

        answers = self.wait_for(2, timeout=5)

        self.assertIn("demorou demais", answers[1]["error"])
        self.assertEqual(answers[2]["value"], "depois")

    def test_a_stray_rejection_does_not_take_the_process_down(self):
        self.send(1, "stray")
        answers = self.wait_for(1)
        self.send(2, "fast", value="vivo")
        answers = self.wait_for(2)

        self.assertEqual(answers[1]["value"], "continua de pé")
        self.assertEqual(answers[2]["value"], "vivo")
        self.assertIsNone(self.process.poll())


if __name__ == "__main__":
    unittest.main()
