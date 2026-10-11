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

export async function resolve(request) {
  const videoId = requireVideoId(request);
  const innertube = await clientFor();
  let info;
  let format;
  let streamUrl = "";
  let resolutionError;
  try {
    info = await innertube.getBasicInfo(videoId, { client: "ANDROID" });
    format = info.chooseFormat({ itag: 18 });
    streamUrl = await format.decipher(innertube.session.player);
  } catch (error) {
    resolutionError = error;
  }
  if (!streamUrl) {
    const detail = resolutionError instanceof Error ? `: ${resolutionError.message}` : "";
    throw new Error(`O YouTube.js não retornou uma URL direta de mídia${detail}.`);
  }
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
