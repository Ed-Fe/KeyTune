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

// Os clientes que entregam só o áudio (itag 140, AAC) com URL direta, do mais leve ao
// mais pesado. O ANDROID com o vídeo 360p (itag 18) fica por último, como reserva.
const ATTEMPTS = [
  { client: "YTMUSIC", pick: audioOnly },
  { client: "MWEB", pick: audioOnly },
  { client: "ANDROID", pick: (info) => info.chooseFormat({ itag: 18 }) },
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

async function directFormat(innertube, videoId) {
  const failures = [];
  for (const { client, pick } of ATTEMPTS) {
    try {
      const info = await innertube.getBasicInfo(videoId, { client });
      const format = pick(info);
      const streamUrl = await format.decipher(innertube.session.player);
      if (streamUrl) {
        return { info, format, streamUrl };
      }
      failures.push(`${client}: sem URL`);
    } catch (error) {
      failures.push(`${client}: ${error instanceof Error ? error.message : error}`);
    }
  }
  throw new Error(`O YouTube.js não retornou uma URL direta de mídia: ${failures.join("; ")}.`);
}

export async function resolve(request) {
  const videoId = requireVideoId(request);
  const innertube = await clientFor();
  const { info, format, streamUrl } = await directFormat(innertube, videoId);
  const contentLength = await measuredLength(format, streamUrl);
  if (!contentLength) {
    throw new Error("O YouTube.js não informou o tamanho da mídia.");
  }

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
