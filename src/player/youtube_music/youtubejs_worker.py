"""Um processo Node.js do YouTube.js e o diálogo com ele.

O KeyTune manda uma linha JSON por pedido na entrada do processo, com um ``id``, e
o processo responde com ``KEYTUNE_YOUTUBEJS_RESULT=<json>`` trazendo o mesmo ``id``.
Os pedidos andam juntos: cada um espera só a resposta dele, então um pedido lento
nunca segura os outros, e uma resposta atrasada nunca é confundida com a de outro.

O processo só é descartado quando ele morre ou deixa de responder a tudo (vários
pedidos seguidos sem nenhuma resposta). Um pedido que demora falha sozinho, sem
derrubar o processo e o que mais ele estiver fazendo.

Um pedido que **muda algo** no YouTube (comentar, enviar ao chat, votar, inscrever-se)
nunca é reenviado depois de ter chegado ao processo: sem resposta, não há como saber
se o YouTube o recebeu, e reenviar duplicaria a ação.
"""

from __future__ import annotations

from collections import deque
import itertools
import json
import queue
import subprocess
import threading

from ..i18n import _


RESULT_PREFIX = "KEYTUNE_YOUTUBEJS_RESULT="
# Quantos pedidos seguidos podem esgotar o tempo, sem uma única resposta no meio, antes
# de o processo ser tratado como travado e recomeçar.
HUNG_AFTER_TIMEOUTS = 3

_EXITED = object()


class _Connection:
    """Um processo em andamento: a entrada, os pedidos à espera e a thread que lê as respostas."""

    def __init__(self, process, name, sanitize):
        self.process = process
        self.name = name
        self._sanitize = sanitize
        self.pending: dict[int, queue.Queue] = {}
        self.lock = threading.Lock()
        self.write_lock = threading.Lock()
        self.diagnostics: deque[str] = deque(maxlen=20)
        self.timeouts_in_a_row = 0
        self.closed = False
        threading.Thread(target=self._read, daemon=True, name=f"youtubejs-{name}-reader").start()

    @property
    def alive(self):
        return not self.closed and self.process.poll() is None

    def diagnostic_text(self):
        with self.lock:
            return " | ".join(self.diagnostics)[-2000:]

    def expect(self, request_id):
        slot = queue.Queue(maxsize=1)
        with self.lock:
            self.pending[request_id] = slot
        return slot

    def forget(self, request_id):
        with self.lock:
            self.pending.pop(request_id, None)

    def send(self, request):
        line = json.dumps(request) + "\n"
        with self.write_lock:
            self.process.stdin.write(line)
            self.process.stdin.flush()

    def _read(self):
        try:
            while line := self.process.stdout.readline():
                if line.startswith(RESULT_PREFIX):
                    self._deliver(line)
                    continue
                text = " ".join(str(line or "").split())
                if text:
                    with self.lock:
                        self.diagnostics.append(self._sanitize(text))
        except Exception:
            pass
        finally:
            self._finish()

    def _deliver(self, line):
        try:
            response = json.loads(line[len(RESULT_PREFIX):])
        except json.JSONDecodeError:
            return
        if not isinstance(response, dict):
            return
        with self.lock:
            slot = self.pending.pop(response.get("id"), None)
            self.timeouts_in_a_row = 0
        if slot is not None:
            slot.put(response)

    def _finish(self):
        """O processo acabou: quem ainda espera resposta fica sabendo."""
        with self.lock:
            self.closed = True
            waiting = list(self.pending.values())
            self.pending.clear()
        for slot in waiting:
            slot.put(_EXITED)

    def discard(self):
        self.closed = True
        process = self.process
        if process.poll() is None:
            process.kill()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass


class NodeWorker:
    """Um processo do YouTube.js que o KeyTune sobe quando precisa e recomeça se ele morrer."""

    def __init__(self, name, spawn, *, sanitize=str):
        """*spawn* abre o processo (``subprocess.Popen``) e levanta ``RuntimeError`` se não der."""
        self.name = name
        self._spawn = spawn
        self._sanitize = sanitize
        self._lock = threading.RLock()
        self._connection: _Connection | None = None
        self._ids = itertools.count(1)

    def ensure_started(self):
        with self._lock:
            if self._connection is not None and self._connection.alive:
                return self._connection
            self._connection = _Connection(self._spawn(), self.name, self._sanitize)
            return self._connection

    def stop(self):
        with self._lock:
            connection, self._connection = self._connection, None
        if connection is not None:
            connection.discard()

    def _drop(self, connection):
        with self._lock:
            if self._connection is connection:
                self._connection = None
        connection.discard()

    def request(self, payload, *, timeout, replay_safe):
        """Manda *payload* e espera a resposta; devolve o dicionário que o Node respondeu.

        *replay_safe*: se, depois de o pedido ter chegado ao processo e ele morrer sem
        responder, vale mandar o pedido de novo a um processo novo. Só é seguro para
        leituras; um pedido que não chegou a ser entregue é sempre repetido.
        """
        for attempt in range(2):
            connection = self.ensure_started()
            request_id = next(self._ids)
            slot = connection.expect(request_id)
            try:
                connection.send({**payload, "id": request_id})
            except (BrokenPipeError, OSError, ValueError):
                # Não chegou ao processo: repetir não duplica nada.
                connection.forget(request_id)
                self._drop(connection)
                if attempt:
                    raise RuntimeError(_("O processo do YouTube.js não respondeu.")) from None
                continue
            try:
                outcome = slot.get(timeout=timeout)
            except queue.Empty:
                connection.forget(request_id)
                self._count_timeout(connection)
                raise RuntimeError(self._timeout_message(connection)) from None
            if outcome is _EXITED:
                self._drop(connection)
                if replay_safe and not attempt:
                    continue
                raise RuntimeError(self._exit_message(connection))
            return outcome
        raise RuntimeError(_("O processo do YouTube.js não respondeu."))

    def _count_timeout(self, connection):
        with connection.lock:
            connection.timeouts_in_a_row += 1
            hung = connection.timeouts_in_a_row >= HUNG_AFTER_TIMEOUTS
        if hung:
            self._drop(connection)

    @staticmethod
    def _with_detail(message, connection):
        detail = connection.diagnostic_text()
        if detail:
            message += " " + _("Detalhes: {detail}").format(detail=detail)
        return message

    def _timeout_message(self, connection):
        return self._with_detail(_("O YouTube.js demorou demais para responder."), connection)

    def _exit_message(self, connection):
        return self._with_detail(_("O processo do YouTube.js foi encerrado."), connection)
