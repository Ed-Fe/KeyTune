// O proxy local por onde o MPV lê o áudio: ele pede a faixa em blocos de 1 MB ao Google e
// entrega ao MPV com suporte a Range. Mora no worker de reprodução, sozinho: nenhuma outra
// ação do YouTube.js pode derrubar o processo que mantém a música tocando.

import { randomUUID } from "node:crypto";
import { createServer } from "node:http";

const UPSTREAM_TIMEOUT_MS = 30_000;
const MAX_STREAMS = 200;
const streamUrls = new Map();

function waitForDrain(response) {
  return new Promise((resolve, reject) => {
    if (response.destroyed || response.writableEnded) {
      reject(new Error("A conexão local de reprodução foi encerrada."));
      return;
    }
    const cleanup = () => {
      response.off("drain", onDrain);
      response.off("close", onClose);
      response.off("error", onError);
    };
    const onDrain = () => {
      cleanup();
      resolve();
    };
    const onClose = () => {
      cleanup();
      reject(new Error("A conexão local de reprodução foi encerrada."));
    };
    const onError = (error) => {
      cleanup();
      reject(error);
    };
    response.once("drain", onDrain);
    response.once("close", onClose);
    response.once("error", onError);
    if (response.destroyed || response.writableEnded) {
      cleanup();
      reject(new Error("A conexão local de reprodução foi encerrada."));
    }
  });
}

const proxyServer = createServer(async (request, response) => {
  try {
    if (request.method !== "GET" && request.method !== "HEAD") {
      response.writeHead(405, { allow: "GET, HEAD" }).end();
      return;
    }
    const token = new URL(request.url, "http://127.0.0.1").pathname.split("/").filter(Boolean)[1] || "";
    const stream = streamUrls.get(token);
    if (!stream) {
      response.writeHead(404).end();
      return;
    }

    const requestedRange = String(request.headers.range || "").trim();
    const parsedRange = /^bytes=(\d+)-(\d*)$/i.exec(requestedRange);
    if (requestedRange && !parsedRange) {
      response.writeHead(416).end();
      return;
    }
    const rangeStart = parsedRange ? Number(parsedRange[1]) : 0;
    const streamEnd = stream.contentLength - 1;
    const requestedEnd = parsedRange?.[2] ? Number(parsedRange[2]) : streamEnd;
    if (
      !Number.isSafeInteger(rangeStart) ||
      !Number.isSafeInteger(requestedEnd) ||
      rangeStart < 0 ||
      requestedEnd < rangeStart ||
      rangeStart > streamEnd
    ) {
      response.writeHead(416, { "content-range": `bytes */${stream.contentLength}` }).end();
      return;
    }
    const rangeEnd = Math.min(requestedEnd, streamEnd);
    const responseHeaders = {
      "accept-ranges": "bytes",
      "content-length": String(rangeEnd - rangeStart + 1),
      "content-type": stream.contentType,
    };
    if (parsedRange) {
      responseHeaders["content-range"] = `bytes ${rangeStart}-${rangeEnd}/${stream.contentLength}`;
    }
    response.writeHead(parsedRange ? 206 : 200, responseHeaders);
    if (request.method === "HEAD") {
      response.end();
      return;
    }

    for (let offset = rangeStart; offset <= rangeEnd; offset += 1024 * 1024) {
      if (response.destroyed) {
        return;
      }
      const chunkEnd = Math.min(offset + 1024 * 1024 - 1, rangeEnd);
      const upstream = await fetch(stream.url, {
        headers: { Range: `bytes=${offset}-${chunkEnd}` },
        signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
      });
      if (upstream.status !== 206 || !upstream.body) {
        throw new Error(`O Google recusou o bloco ${offset}-${chunkEnd}: HTTP ${upstream.status}.`);
      }
      for await (const chunk of upstream.body) {
        if (!response.write(chunk)) {
          await waitForDrain(response);
        }
      }
    }
    response.end();
  } catch {
    if (!response.headersSent) {
      response.writeHead(502).end();
      return;
    }
    // O cabeçalho já prometeu o tamanho: cortar a conexão mostra ao MPV que faltou um
    // pedaço, em vez de parecer o fim normal da faixa.
    response.destroy();
  }
});
const proxyReady = new Promise((resolve, reject) => {
  proxyServer.once("error", reject);
  proxyServer.listen(0, "127.0.0.1", resolve);
});


// Registra a URL direta e devolve o endereço local que o MPV deve abrir.
export async function registerStream({ url, contentLength, contentType }) {
  await proxyReady;
  const token = randomUUID();
  streamUrls.set(token, { url, contentLength, contentType });
  if (streamUrls.size > MAX_STREAMS) {
    streamUrls.delete(streamUrls.keys().next().value);
  }
  return `http://127.0.0.1:${proxyServer.address().port}/stream/${token}`;
}
