// Os resultados do YouTube.js no formato da listagem do yt-dlp, para o KeyTune tratar
// as duas fontes igual.

import { findBadgeText, findChannelId, findWatchedPercent, textOf } from "./text.mjs";

export function searchEntry(node) {
  if (node.type === "Video") {
    return {
      id: node.video_id,
      title: textOf(node.title),
      channel: textOf(node.author?.name),
      channel_id: /^UC[\w-]{22}$/.test(node.author?.id || "") ? node.author.id : "",
      duration: Number(node.duration?.seconds) || 0,
      view_count_text: textOf(node.short_view_count) || textOf(node.view_count),
      published: textOf(node.published),
      live_status: node.is_live ? "is_live" : "",
      watched_percent: findWatchedPercent(node.thumbnail_overlays),
    };
  }
  if (node.type === "Channel") {
    // O YouTube pôs o @ do canal onde ficavam os inscritos; os inscritos vêm no outro campo.
    const counts = [textOf(node.subscriber_count), textOf(node.video_count)];
    return {
      id: node.id,
      title: textOf(node.author?.name),
      url: `https://www.youtube.com/channel/${node.id}`,
      channel_id: node.id,
      detail_text: counts.find((text) => text && !text.startsWith("@")) || "",
    };
  }
  if (node.type === "LockupView" && ["PLAYLIST", "SHOW", "PODCAST"].includes(node.content_type)) {
    const owner = node.metadata?.metadata?.metadata_rows?.[0]?.metadata_parts?.[0]?.text;
    return {
      id: node.content_id,
      title: textOf(node.metadata?.title),
      url: `https://www.youtube.com/playlist?list=${node.content_id}`,
      channel: textOf(owner),
    };
  }
  return null;
}

export function feedVideoEntry(node) {
  if (node.type === "Video") {
    return searchEntry(node);
  }
  if (node.type === "PlaylistVideo") {
    return {
      id: node.id,
      title: textOf(node.title),
      channel: textOf(node.author?.name),
      channel_id: /^UC[\w-]{22}$/.test(node.author?.id || "") ? node.author.id : "",
      duration: Number(node.duration?.seconds) || 0,
      view_count_text: textOf(node.video_info),
      live_status: node.is_live ? "is_live" : "",
      watched_percent: findWatchedPercent(node.thumbnail_overlays),
    };
  }
  if (node.type === "CompactVideo" || node.type === "GridVideo") {
    // Os cartões de antes do LockupView: o YouTube ainda os serve em algumas sessões.
    const seconds = Number(node.duration?.seconds) || 0;
    return {
      id: node.video_id,
      title: textOf(node.title),
      channel: textOf(node.author?.name),
      channel_id: /^UC[\w-]{22}$/.test(node.author?.id || "") ? node.author.id : "",
      duration: seconds,
      duration_text: seconds ? "" : textOf(node.duration?.text ?? node.duration),
      view_count_text: textOf(node.short_view_count) || textOf(node.view_count) || textOf(node.views),
      published: textOf(node.published),
      live_status: node.is_live ? "is_live" : "",
      watched_percent: findWatchedPercent(node.thumbnail_overlays),
    };
  }
  if (node.type !== "LockupView" || node.content_type !== "VIDEO") {
    return null;
  }
  const parts = (node.metadata?.metadata?.metadata_rows || []).flatMap((row) =>
    (row.metadata_parts || []).map((part) => textOf(part.text)),
  );
  // A linha de baixo traz o canal (ou os canais), depois as visualizações e a data;
  // a duração vem no selo da miniatura.
  const tail = parts.length >= 3 ? 2 : Math.max(0, parts.length - 1);
  const details = parts.slice(parts.length - tail);
  return {
    id: node.content_id,
    title: textOf(node.metadata?.title),
    channel: parts.slice(0, parts.length - tail).join(" "),
    channel_id: findChannelId(node.metadata),
    duration_text: findBadgeText(node.content_image),
    watched_percent: findWatchedPercent(node.content_image),
    view_count_number_text: details.length > 1 ? details[0] : "",
    published: details[details.length - 1] || "",
  };
}
