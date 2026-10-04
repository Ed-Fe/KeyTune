import { Innertube, UniversalCache } from "youtubei.js";
import { createHash, randomUUID } from "node:crypto";
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

const MAX_CLIENTS = 3;
const MAX_LISTINGS = 12;
const clients = new Map();
const listings = new Map();

// Um cliente anônimo por idioma e região. A reprodução usa sempre o padrão
// (sem idioma nem região), para não mudar com as preferências de conteúdo.
function clientFor(request = {}) {
  const lang = String(request.lang || "").trim() || "en";
  const location = String(request.location || "").trim().toUpperCase();
  const key = `${lang}|${location}`;
  if (!clients.has(key)) {
    if (clients.size >= MAX_CLIENTS) {
      clients.delete(clients.keys().next().value);
    }
    const options = {
      cache: new UniversalCache(true, process.argv[2]),
      // A reprodução gera a sessão aqui, como sempre fez; as listas pedem a sessão ao YouTube.
      generate_session_locally: !request.lang,
      lang,
    };
    if (location) {
      options.location = location;
    }
    const client = Innertube.create(options);
    client.catch(() => clients.delete(key));
    clients.set(key, client);
  }
  return clients.get(key);
}
clientFor();

// O cliente da conta: os mesmos cookies do YouTube Music. Fica separado dos anônimos
// porque, com os cookies, o YouTube recusa a reprodução pelos clientes que o KeyTune usa.
let accountClient = { key: "", client: null };

function accountKey(request) {
  const cookie = String(request.cookie || "").trim();
  if (!cookie) {
    throw new Error("A conta do YouTube não está conectada.");
  }
  return [createHash("sha256").update(cookie).digest("hex"), request.lang, request.location].join("|");
}

function accountClientFor(request) {
  const key = accountKey(request);
  if (accountClient.key !== key) {
    const options = { cookie: String(request.cookie).trim(), lang: String(request.lang || "").trim() || "en" };
    const location = String(request.location || "").trim().toUpperCase();
    if (location) {
      options.location = location;
    }
    const client = Innertube.create(options);
    client.catch(() => {
      accountClient = { key: "", client: null };
    });
    accountClient = { key, client };
  }
  return accountClient.client;
}

function findBadgeText(node, depth = 0) {
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

function feedVideoEntry(node) {
  if (node.type === "Video") {
    return searchEntry(node);
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
    duration_text: findBadgeText(node.content_image),
    view_count_number_text: details.length > 1 ? details[0] : "",
    published: details[details.length - 1] || "",
  };
}

async function accountListing(request, name, fetchFeed, nodesOf, toEntry) {
  const { start, count } = pageBounds(request);
  const key = JSON.stringify([name, accountKey(request)]);
  let listing = listings.get(key);
  if (!listing || start === 0) {
    listing = { entries: [], seen: new Set(), feed: await fetchFeed(await accountClientFor(request)) };
    collectEntries(listing, nodesOf(listing.feed), toEntry);
  }
  rememberListing(key, listing);
  while (listing.entries.length < start + count && listing.feed?.has_continuation) {
    listing.feed = await listing.feed.getContinuation();
    collectEntries(listing, nodesOf(listing.feed), toEntry);
  }
  return listingPage(listing, start, count, listing.feed?.has_continuation);
}

function subscriptionVideos(request) {
  return accountListing(request, "subscription_videos", (innertube) => innertube.getSubscriptionsFeed(), (feed) => feed.videos, feedVideoEntry);
}

function subscribedChannels(request) {
  return accountListing(request, "subscribed_channels", (innertube) => innertube.getChannelsFeed(), (feed) => feed.channels, searchEntry);
}

function rememberListing(key, listing) {
  listings.delete(key);
  listings.set(key, listing);
  if (listings.size > MAX_LISTINGS) {
    listings.delete(listings.keys().next().value);
  }
  return listing;
}

function pageBounds(request) {
  return {
    start: Math.max(0, Number(request.start) || 0),
    count: Math.max(1, Number(request.count) || 20),
  };
}

function textOf(value) {
  return value ? String(value.toString() || "").trim() : "";
}

const SEARCH_TYPES = { videos: "video", channels: "channel", playlists: "playlist" };

// As entradas saem no formato da listagem do yt-dlp, para o KeyTune tratar as duas fontes igual.
function searchEntry(node) {
  if (node.type === "Video") {
    return {
      id: node.video_id,
      title: textOf(node.title),
      channel: textOf(node.author?.name),
      duration: Number(node.duration?.seconds) || 0,
      view_count_text: textOf(node.short_view_count) || textOf(node.view_count),
      live_status: node.is_live ? "is_live" : "",
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

function collectEntries(listing, nodes, toEntry) {
  for (const node of nodes || []) {
    const entry = toEntry(node);
    if (entry?.id && entry.title && !listing.seen.has(entry.id)) {
      listing.seen.add(entry.id);
      listing.entries.push(entry);
    }
  }
}

function listingPage(listing, start, count, hasContinuation) {
  return {
    entries: listing.entries.slice(start, start + count),
    has_more: listing.entries.length > start + count || Boolean(hasContinuation),
  };
}

async function search(request) {
  const query = String(request.query || "").trim();
  const type = SEARCH_TYPES[request.kind] || SEARCH_TYPES.videos;
  const { start, count } = pageBounds(request);
  if (!query) {
    return { entries: [], has_more: false };
  }

  const key = JSON.stringify(["search", request.lang, request.location, type, query]);
  let listing = listings.get(key);
  if (!listing || start === 0) {
    const innertube = await clientFor(request);
    listing = { entries: [], seen: new Set(), feed: await innertube.search(query, { type }) };
    collectEntries(listing, listing.feed.results, searchEntry);
  }
  rememberListing(key, listing);
  while (listing.entries.length < start + count && listing.feed?.has_continuation) {
    listing.feed = await listing.feed.getContinuation();
    collectEntries(listing, listing.feed.results, searchEntry);
  }
  return listingPage(listing, start, count, listing.feed?.has_continuation);
}

function commentEntry(thread, listing) {
  const comment = thread.comment || thread;
  if (!comment?.comment_id) {
    return null;
  }
  listing.threads?.set(comment.comment_id, thread);
  return {
    id: comment.comment_id,
    author: textOf(comment.author?.name),
    text: textOf(comment.content),
    likes: textOf(comment.like_count),
    published: textOf(comment.published_time),
    reply_count: textOf(comment.reply_count),
    // Só os comentários principais guardam a conversa de onde saem as respostas.
    has_replies: Boolean(listing.threads && thread.has_replies),
    pinned: Boolean(comment.is_pinned),
    title: "-",
  };
}

async function comments(request) {
  const videoId = videoIdFrom(request.media_url);
  if (!videoId) {
    throw new Error("URL do YouTube sem identificador de vídeo.");
  }
  const { start, count } = pageBounds(request);
  const key = JSON.stringify(["comments", request.lang, request.location, videoId]);
  let listing = listings.get(key);
  if (!listing || start === 0) {
    const innertube = await clientFor(request);
    listing = { entries: [], seen: new Set(), threads: new Map(), feed: null };
    try {
      listing.feed = await innertube.getComments(videoId);
    } catch (error) {
      // É assim que a biblioteca avisa que o vídeo está com os comentários desativados.
      if (!String(error?.message).includes("did not have any content")) {
        throw error;
      }
    }
    collectEntries(listing, listing.feed?.contents, (thread) => commentEntry(thread, listing));
  }
  rememberListing(key, listing);
  while (listing.entries.length < start + count && listing.feed?.has_continuation) {
    listing.feed = await listing.feed.getContinuation();
    collectEntries(listing, listing.feed.contents, (thread) => commentEntry(thread, listing));
  }
  return listingPage(listing, start, count, listing.feed?.has_continuation);
}

async function commentReplies(request) {
  const videoId = videoIdFrom(request.media_url);
  const commentId = String(request.comment_id || "");
  const { start, count } = pageBounds(request);
  const key = JSON.stringify(["replies", request.lang, request.location, videoId, commentId]);
  let listing = listings.get(key);
  if (!listing || start === 0) {
    const parent = listings.get(JSON.stringify(["comments", request.lang, request.location, videoId]));
    const thread = parent?.threads.get(commentId);
    if (!thread) {
      throw new Error("Os comentários deste vídeo precisam ser abertos de novo.");
    }
    listing = { entries: [], seen: new Set(), innertube: await clientFor(request), next: null };
    // O YouTube manda as respostas em dois formatos, conforme a sessão; os dois chegam aqui.
    const replyData = thread.comment_replies_data;
    takeReplyNodes(listing, [...(replyData?.sub_threads || []), ...(replyData?.contents || [])]);
  }
  rememberListing(key, listing);
  while (listing.entries.length < start + count && listing.next) {
    const endpoint = listing.next.button?.endpoint || listing.next.endpoint;
    listing.next = null;
    const response = await endpoint.call(listing.innertube.actions, { parse: true });
    for (const action of response.on_response_received_endpoints || []) {
      takeReplyNodes(listing, [...(action.contents || [])]);
    }
  }
  return listingPage(listing, start, count, listing.next);
}

function takeReplyNodes(listing, nodes) {
  collectEntries(listing, nodes.filter((node) => node.type !== "ContinuationItem"), (reply) => commentEntry(reply, listing));
  listing.next = nodes.find((node) => node.type === "ContinuationItem") || listing.next;
}

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
async function audioTracks(request) {
  const videoId = videoIdFrom(request.media_url);
  if (!videoId) {
    throw new Error("URL do YouTube sem identificador de vídeo.");
  }
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

async function resolve(request) {
  const videoId = videoIdFrom(request.media_url);
  if (!videoId) {
    throw new Error("URL do YouTube sem identificador de vídeo.");
  }

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

const HANDLERS = {
  resolve,
  search,
  comments,
  comment_replies: commentReplies,
  audio_tracks: audioTracks,
  subscription_videos: subscriptionVideos,
  subscribed_channels: subscribedChannels,
};

const input = createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of input) {
  try {
    const request = JSON.parse(line);
    const handler = HANDLERS[request.action || "resolve"];
    if (!handler) {
      throw new Error(`Ação desconhecida: ${request.action}`);
    }
    const response = await handler(request);
    process.stdout.write(RESULT_PREFIX + JSON.stringify(response) + "\n");
  } catch (error) {
    process.stdout.write(RESULT_PREFIX + JSON.stringify({
      error: error instanceof Error ? error.message : String(error),
    }) + "\n");
  }
}
