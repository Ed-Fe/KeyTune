// Resolve um vídeo do YouTube em uma URL direta, que o proxy local entrega ao MPV.

import { clientFor } from "../lib/clients.mjs";
import { requireVideoId } from "../lib/text.mjs";
import { registerStream } from "./stream_proxy.mjs";

const PROBE_TIMEOUT_MS = 15_000;

async function measuredLength(format, streamUrl) {
  let contentLength = Number(format.content_length) || Number(new URL(streamUrl).searchParams.get("clen")) || 0;
  if (contentLength) {
    return contentLength;
  }
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
  return contentLength;
}

// Do que já sabemos que toca inteiro para o que ainda é uma aposta: o ANDROID com o vídeo
// 360p (itag 18) vem primeiro; o áudio puro do YTMUSIC e do MWEB só entra se ele falhar.
// Esses clientes costumam exigir um PO token e o YouTube corta o arquivo depois dos
// primeiros blocos, por isso cada candidato é conferido antes de ser aceito.
const ATTEMPTS = [
  { client: "ANDROID", pick: (info) => info.chooseFormat({ itag: 18 }) },
  { client: "YTMUSIC", pick: audioOnly },
  { client: "MWEB", pick: audioOnly },
];

function audioOnly(info) {
  const formats = (info.streaming_data?.adaptive_formats || []).filter((f) => f.has_audio && !f.has_video);
  const aac = formats.filter((f) => String(f.mime_type || "").startsWith("audio/mp4"));
  const best = (list) => list.sort((a, b) => (b.bitrate || 0) - (a.bitrate || 0))[0];
  const format = best(aac) || best(formats);
  if (!format) {
    throw new Error("sem formato de áudio");
  }
  return format;
}

// Pede um trecho do meio e um do fim do arquivo, onde o corte por falta de PO token aparece.
async function playsThrough(streamUrl, contentLength) {
  const spots = [Math.min(3 * 1024 * 1024, contentLength - 1), contentLength - 1];
  for (const spot of new Set(spots)) {
    const probe = await fetch(streamUrl, {
      headers: { Range: `bytes=${spot}-${spot}` },
      signal: AbortSignal.timeout(PROBE_TIMEOUT_MS),
    });
    await probe.body?.cancel();
    if (probe.status !== 206) {
      return false;
    }
  }
  return true;
}

async function directFormat(innertube, videoId) {
  const failures = [];
  for (const { client, pick } of ATTEMPTS) {
    try {
      const info = await innertube.getBasicInfo(videoId, { client });
      const format = pick(info);
      const streamUrl = await format.decipher(innertube.session.player);
      if (!streamUrl) {
        failures.push(`${client}: sem URL`);
        continue;
      }
      const contentLength = await measuredLength(format, streamUrl);
      if (!contentLength) {
        failures.push(`${client}: sem tamanho`);
        continue;
      }
      if (!(await playsThrough(streamUrl, contentLength))) {
        failures.push(`${client}: o YouTube cortou o arquivo`);
        continue;
      }
      return { info, format, streamUrl, contentLength };
    } catch (error) {
      failures.push(`${client}: ${error instanceof Error ? error.message : error}`);
    }
  }
  throw new Error(`O YouTube.js não retornou uma URL direta de mídia: ${failures.join("; ")}.`);
}

export async function resolve(request) {
  const videoId = requireVideoId(request);
  const innertube = await clientFor();
  const { info, format, streamUrl, contentLength } = await directFormat(innertube, videoId);

  return {
    stream_url: await registerStream({
      url: streamUrl,
      contentLength,
      contentType: String(format.mime_type || "audio/mp4").split(";", 1)[0],
    }),
    title: info.basic_info?.title || "",
    artist: info.basic_info?.author || info.basic_info?.channel?.name || "",
  };
}
