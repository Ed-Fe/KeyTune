import { Innertube, UniversalCache } from "youtubei.js";
import { randomUUID } from "node:crypto";
import { createServer } from "node:http";
import { createInterface } from "node:readline";

const RESULT_PREFIX = "KEYTUNE_YOUTUBEJS_RESULT=";
const PROBE_TIMEOUT_MS = 15_000;
const UPSTREAM_TIMEOUT_MS = 30_000;
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
      response.writeHead(502);
    }
    response.end();
  }
});
const proxyReady = new Promise((resolve, reject) => {
  proxyServer.once("error", reject);
  proxyServer.listen(0, "127.0.0.1", resolve);
});

function videoIdFrom(value) {
  const normalized = String(value || "").trim();
  if (/^[A-Za-z0-9_-]{11}$/.test(normalized)) {
    return normalized;
  }

  const url = new URL(normalized);
  if (url.hostname === "youtu.be") {
    return url.pathname.split("/").filter(Boolean)[0] || "";
  }
  if (url.pathname.startsWith("/shorts/") || url.pathname.startsWith("/embed/")) {
    return url.pathname.split("/").filter(Boolean)[1] || "";
  }
  return url.searchParams.get("v") || "";
}

const innertubePromise = Innertube.create({
  cache: new UniversalCache(true, process.argv[2]),
  generate_session_locally: true,
});

async function resolve(request) {
  const videoId = videoIdFrom(request.media_url);
  if (!videoId) {
    throw new Error("URL do YouTube sem identificador de vídeo.");
  }

  const innertube = await innertubePromise;
  const profiles = [
    { client: "IOS", format: { type: "audio", quality: "best", format: "any" } },
    { client: "ANDROID", format: { itag: 18 } },
  ];
  let info;
  let format;
  let streamUrl = "";
  let lastError;
  for (const profile of profiles) {
    try {
      const candidateInfo = await innertube.getBasicInfo(videoId, { client: profile.client });
      const candidateFormat = candidateInfo.chooseFormat(profile.format);
      const candidateUrl = await candidateFormat.decipher(innertube.session.player);
      if (candidateUrl) {
        info = candidateInfo;
        format = candidateFormat;
        streamUrl = candidateUrl;
        break;
      }
    } catch (error) {
      lastError = error;
    }
  }
  if (!streamUrl) {
    const detail = lastError instanceof Error ? `: ${lastError.message}` : "";
    throw new Error(`O YouTube.js não retornou uma URL direta de mídia${detail}.`);
  }
  let contentLength = Number(format.content_length) || Number(new URL(streamUrl).searchParams.get("clen")) || 0;
  if (!contentLength) {
    const probe = await fetch(streamUrl, {
      headers: { Range: "bytes=0-0" },
      signal: AbortSignal.timeout(PROBE_TIMEOUT_MS),
    });
    if (probe.status !== 206) {
      await probe.body?.cancel();
      throw new Error(`O YouTube.js não conseguiu medir a mídia: HTTP ${probe.status}.`);
    }
    const contentRange = String(probe.headers.get("content-range") || "");
    contentLength = Number(contentRange.split("/").pop()) || 0;
    await probe.body?.cancel();
  }
  if (!contentLength) {
    throw new Error("O YouTube.js não informou o tamanho da mídia.");
  }

  await proxyReady;
  const token = randomUUID();
  streamUrls.set(token, {
    url: streamUrl,
    contentLength,
    contentType: String(format.mime_type || "audio/mp4").split(";", 1)[0],
  });
  if (streamUrls.size > 200) {
    streamUrls.delete(streamUrls.keys().next().value);
  }
  const proxyAddress = proxyServer.address();

  return {
    stream_url: `http://127.0.0.1:${proxyAddress.port}/stream/${token}`,
    title: info.basic_info?.title || "",
    artist: info.basic_info?.author || info.basic_info?.channel?.name || "",
  };
}

const input = createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of input) {
  try {
    const response = await resolve(JSON.parse(line));
    process.stdout.write(RESULT_PREFIX + JSON.stringify(response) + "\n");
  } catch (error) {
    process.stdout.write(RESULT_PREFIX + JSON.stringify({
      error: error instanceof Error ? error.message : String(error),
    }) + "\n");
  }
}
