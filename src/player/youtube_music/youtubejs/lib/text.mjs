// Pequenos ajudantes de texto e de identificadores que os módulos do worker dividem.

export function textOf(value) {
  return value ? String(value.toString() || "").trim() : "";
}

export function videoIdFrom(value) {
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

// O identificador de vídeo de um pedido, ou o erro que o Python mostra.
export function requireVideoId(request) {
  const videoId = videoIdFrom(request.media_url);
  if (!videoId) {
    throw new Error("URL do YouTube sem identificador de vídeo.");
  }
  return videoId;
}

export function findBadgeText(node, depth = 0) {
  if (!node || typeof node !== "object" || depth > 6) {
    return "";
  }
  if (node.type === "ThumbnailBadgeView") {
    return textOf(node.text);
  }
  for (const value of Array.isArray(node) ? node : Object.values(node)) {
    const text = findBadgeText(value, depth + 1);
    if (text) {
      return text;
    }
  }
  return "";
}

// Quanto do vídeo a conta já assistiu (0 a 100): a barra vermelha sob a miniatura.
export function findWatchedPercent(node, depth = 0) {
  if (!node || typeof node !== "object" || depth > 6) {
    return 0;
  }
  if (node.type === "ThumbnailOverlayProgressBarView") {
    return Number(node.start_percent) || 0;
  }
  if (node.type === "ThumbnailOverlayResumePlayback") {
    return Number(node.percent_duration_watched) || 0;
  }
  for (const value of Array.isArray(node) ? node : Object.values(node)) {
    const percent = findWatchedPercent(value, depth + 1);
    if (percent) {
      return percent;
    }
  }
  return 0;
}

// O canal de um vídeo do feed vem só dentro dos comandos de toque do cartão.
export function findChannelId(node, depth = 0) {
  if (typeof node === "string") {
    return /^UC[\w-]{22}$/.test(node) ? node : "";
  }
  if (!node || typeof node !== "object" || depth > 12) {
    return "";
  }
  for (const value of Array.isArray(node) ? node : Object.values(node)) {
    const channelId = findChannelId(value, depth + 1);
    if (channelId) {
      return channelId;
    }
  }
  return "";
}

// O identificador de canal de um pedido, ou o erro que o Python mostra.
export function requireChannelId(request) {
  const channelId = String(request.channel_id || "").trim();
  if (!/^UC[\w-]{22}$/.test(channelId)) {
    throw new Error("Canal do YouTube sem identificador.");
  }
  return channelId;
}
