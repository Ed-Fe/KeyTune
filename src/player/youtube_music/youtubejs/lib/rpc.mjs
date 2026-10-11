// O protocolo entre o KeyTune e um worker: uma linha JSON por pedido na entrada padrão e
// uma linha "KEYTUNE_YOUTUBEJS_RESULT=<json>" por resposta. Cada pedido traz um "id" e a
// resposta o devolve, então os pedidos andam juntos e uma resposta atrasada nunca é
// confundida com a de outro. Dentro de uma "pista", os pedidos seguem em fila (as listas
// paginadas dependem disso); pistas diferentes, e pedidos sem pista, não esperam uns pelos
// outros. Um pedido que demora para de segurar a pista, e o processo continua de pé.

import { createInterface } from "node:readline";

const RESULT_PREFIX = "KEYTUNE_YOUTUBEJS_RESULT=";
const HANDLER_TIMEOUT_MS = 25_000;

function withTimeout(promise, milliseconds) {
  let timer;
  const expired = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error("O YouTube.js demorou demais para responder.")), milliseconds);
  });
  return Promise.race([promise, expired]).finally(() => clearTimeout(timer));
}

function reply(id, payload) {
  let line;
  try {
    line = JSON.stringify({ ...payload, id });
  } catch (error) {
    line = JSON.stringify({ id, error: `Resposta inválida: ${error.message}` });
  }
  process.stdout.write(RESULT_PREFIX + line + "\n");
}

// Uma falha solta dentro da biblioteca não pode derrubar o processo (e a reprodução com ele).
function guardAgainstCrashes() {
  const report = (kind) => (error) =>
    process.stdout.write(`[youtubejs] ${kind}: ${error instanceof Error ? error.message : String(error)}\n`);
  process.on("unhandledRejection", report("unhandledRejection"));
  process.on("uncaughtException", report("uncaughtException"));
}

// *handlers* mapeia a ação ao tratador; *laneOf(ação)* devolve o nome da pista dela, ou
// nada para a ação que pode andar a qualquer hora. *defaultAction* vale quando o pedido
// não diz qual é; *timeoutMs* é quanto um tratador pode levar.
export async function serve({ handlers, laneOf = () => null, defaultAction = "", timeoutMs = HANDLER_TIMEOUT_MS }) {
  guardAgainstCrashes();
  const lanes = new Map();

  async function run(request) {
    const handler = handlers[request.action || defaultAction];
    if (!handler) {
      throw new Error(`Ação desconhecida: ${request.action}`);
    }
    return withTimeout(Promise.resolve().then(() => handler(request)), timeoutMs);
  }

  async function answer(request) {
    try {
      reply(request.id, await run(request));
    } catch (error) {
      reply(request.id, { error: error instanceof Error ? error.message : String(error) });
    }
  }

  const input = createInterface({ input: process.stdin, crlfDelay: Infinity });
  for await (const line of input) {
    let request;
    try {
      request = JSON.parse(line);
    } catch {
      continue;
    }
    const lane = laneOf(request.action || defaultAction);
    if (lane) {
      lanes.set(lane, (lanes.get(lane) || Promise.resolve()).then(() => answer(request)));
    } else {
      answer(request);
    }
  }
}
