// O histórico do YouTube da conta: a lista, o registro de um vídeo e até onde ele foi visto.

import { accountClientFor, accountKey } from "../lib/clients.mjs";
import { rememberBounded } from "../lib/bounded.mjs";
import { feedVideoEntry } from "../lib/entries.mjs";
import { requireVideoId } from "../lib/text.mjs";
import { accountListing } from "../lib/listings.mjs";

const MAX_WATCH_SESSIONS = 5;
// Um salto maior que este entre dois avisos é uma busca na linha do tempo, não tempo assistido.
const LONGEST_WATCHED_STRETCH_SECONDS = 120;

// Cada vídeo que a conta está assistindo: os endereços de registro dele (com a identidade
// desta reprodução) e até onde o YouTube já sabe que ela foi.
const watchSessions = new Map();

// O que foi assistido, do mais recente para o mais antigo.
export function watchHistory(request) {
  return accountListing(request, "watch_history", (innertube) => innertube.getHistory(), (feed) => feed.videos, feedVideoEntry);
}

async function watchSession(request, videoId, { fresh = false } = {}) {
  const key = `${accountKey(request)}|${videoId}`;
  let session = fresh ? null : watchSessions.get(key);
  if (!session) {
    const innertube = await accountClientFor(request);
    session = { info: await innertube.getInfo(videoId), position: 0 };
  }
  rememberBounded(watchSessions, key, session, MAX_WATCH_SESSIONS);
  return session;
}

// Põe um vídeo no histórico da conta, como o YouTube faz quando ele começa a tocar.
export async function addToHistory(request) {
  const videoId = requireVideoId(request);
  const session = await watchSession(request, videoId, { fresh: true });
  const response = await session.info.addToWatchHistory();
  return { ok: response?.ok !== false };
}

// Diz ao YouTube até onde (*position*, em segundos) a conta assistiu o vídeo: é o que faz a
// barra de progresso dele andar e deixa continuar de onde parou em outro aparelho.
export async function updateWatchTime(request) {
  const videoId = requireVideoId(request);
  const position = Math.max(0, Number(request.position) || 0);
  const session = await watchSession(request, videoId);
  const { info } = session;
  const watchtimeUrl = String(info.page?.[0]?.playback_tracking?.videostats_watchtime_url || "");
  let response;
  if (watchtimeUrl) {
    // O trecho assistido desde o último aviso; depois de uma busca, só o ponto atual.
    const stretch = position - session.position;
    const from = stretch > 0 && stretch <= LONGEST_WATCHED_STRETCH_SECONDS ? session.position : position;
    const client = info.actions.session.context.client;
    response = await info.actions.stats(
      watchtimeUrl.replace("https://s.", "https://www."),
      { client_name: client.clientName, client_version: client.clientVersion },
      { cpn: info.cpn, st: from.toFixed(3), et: position.toFixed(3), cmt: position.toFixed(3), final: "1" },
    );
  } else {
    response = await info.updateWatchTime(position);
  }
  session.position = position;
  return { ok: response?.ok !== false };
}
