import { Innertube, UniversalCache } from "youtubei.js";
import { randomUUID } from "node:crypto";
import { createServer } from "node:http";
import { createInterface } from "node:readline";

const RESULT_PREFIX = "KEYTUNE_YOUTUBEJS_RESULT=";
const streamUrls = new Map();
const proxyServer = createServer(async (request, response) => {
  try {
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
    if (rangeStart > streamEnd) {
      response.writeHead(416, { "content-range": `bytes */${stream.contentLength}` }).end();
      return;
    }
    const requestedEnd = parsedRange?.[2] ? Number(parsedRange[2]) : streamEnd;
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
      const chunkEnd = Math.min(offset + 1024 * 1024 - 1, rangeEnd);
      const upstream = await fetch(stream.url, {
        headers: { Range: `bytes=${offset}-${chunkEnd}` },
      });
      if (!upstream.ok || !upstream.body) {
        throw new Error(`O Google recusou o bloco ${offset}-${chunkEnd}: HTTP ${upstream.status}.`);
      }
      for await (const chunk of upstream.body) {
        response.write(chunk);
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
  const info = await innertube.getBasicInfo(videoId, { client: "ANDROID" });
  const format = info.chooseFormat({ itag: 18 });
  const streamUrl = await format.decipher(innertube.session.player);
  if (!streamUrl) {
    throw new Error("O YouTube.js não retornou uma URL direta de mídia.");
  }
  let contentLength = Number(format.content_length) || Number(new URL(streamUrl).searchParams.get("clen")) || 0;
  if (!contentLength) {
    const probe = await fetch(streamUrl, { headers: { Range: "bytes=0-0" } });
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
    contentType: String(format.mime_type || "video/mp4").split(";", 1)[0],
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
