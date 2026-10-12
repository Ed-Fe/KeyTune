// O que se sabe de um vídeo: as faixas de áudio (vídeos dublados) e os detalhes.

import { accountClientFor, clientFor } from "../lib/clients.mjs";
import { feedVideoEntry } from "../lib/entries.mjs";
import { requireVideoId, textOf } from "../lib/text.mjs";

async function audioTrackFormats(innertube, videoId) {
  const info = await innertube.getBasicInfo(videoId, { client: "IOS" });
  const formats = new Map();
  for (const format of info.streaming_data?.adaptive_formats || []) {
    if (format.has_audio && !format.has_video && format.audio_track?.id && !formats.has(format.audio_track.id)) {
      formats.set(format.audio_track.id, format);
    }
  }
  return formats;
}

// As faixas de áudio de um vídeo dublado. O YouTube.js só as lista: a URL que ele
// consegue para uma faixa que não é a padrão para de responder depois do começo.
export async function audioTracks(request) {
  const videoId = requireVideoId(request);
  // O que é "padrão" vale para o cliente que toca; os nomes vêm no idioma do conteúdo.
  const [formats, named] = await Promise.all([
    audioTrackFormats(await clientFor(), videoId),
    request.names
      ? clientFor(request).then((innertube) => audioTrackFormats(innertube, videoId)).catch(() => new Map())
      : new Map(),
  ]);
  return {
    tracks: [...formats.values()].map((format) => ({
      id: format.audio_track.id,
      name: named.get(format.audio_track.id)?.audio_track.display_name || format.audio_track.display_name || "",
      language: format.language || "",
      default: Boolean(format.audio_track.audio_is_default),
      original: Boolean(format.is_original),
      descriptive: Boolean(format.is_descriptive),
    })),
  };
}

// Os detalhes de um vídeo ou música: descrição, canal, visualizações, curtidas e data.
export async function details(request) {
  const videoId = requireVideoId(request);
  const innertube = await clientFor(request);
  const info = await innertube.getInfo(videoId);
  const basic = info.basic_info || {};
  const primary = info.primary_info;
  const owner = info.secondary_info?.owner;
  return {
    title: basic.title || textOf(primary?.title),
    channel: basic.author || textOf(owner?.author?.name) || basic.channel?.name || "",
    channel_id: basic.channel_id || basic.channel?.id || owner?.author?.id || "",
    subscribers: textOf(owner?.subscriber_count),
    description: basic.short_description || textOf(info.secondary_info?.description),
    duration: Number(basic.duration) || 0,
    is_live: Boolean(basic.is_live),
    view_count: Number(basic.view_count) || 0,
    view_count_text: textOf(primary?.view_count?.view_count) || textOf(primary?.view_count?.original_view_count),
    like_count: Number(basic.like_count) || 0,
    published: textOf(primary?.published),
    relative_date: textOf(primary?.relative_date),
    category: basic.category || "",
  };
}

// Os vídeos que o YouTube sugere depois deste (a coluna "A seguir"). Com a conta, vêm
// personalizados; sem ela, o que o YouTube mostra para qualquer visitante.
export async function relatedVideos(request) {
  const videoId = requireVideoId(request);
  const innertube = request.cookie ? await accountClientFor(request) : await clientFor(request);
  const info = await innertube.getInfo(videoId);
  const entries = [];
  const seen = new Set([videoId]);
  for (const node of info.watch_next_feed || []) {
    const entry = feedVideoEntry(node);
    if (entry?.id && entry.title && !seen.has(entry.id)) {
      seen.add(entry.id);
      entries.push(entry);
    }
  }
  return { entries };
}
