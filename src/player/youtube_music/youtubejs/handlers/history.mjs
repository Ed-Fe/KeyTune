// O histórico do YouTube da conta.

import { accountClientFor } from "../lib/clients.mjs";
import { feedVideoEntry } from "../lib/entries.mjs";
import { requireVideoId } from "../lib/text.mjs";
import { accountListing } from "../lib/listings.mjs";

// O que foi assistido, do mais recente para o mais antigo.
export function watchHistory(request) {
  return accountListing(request, "watch_history", (innertube) => innertube.getHistory(), (feed) => feed.videos, feedVideoEntry);
}

// Põe um vídeo no histórico da conta, como o YouTube faz quando ele começa a tocar.
export async function addToHistory(request) {
  const videoId = requireVideoId(request);
  const innertube = await accountClientFor(request);
  const info = await innertube.getInfo(videoId);
  const response = await info.addToWatchHistory();
  return { ok: response?.ok !== false };
}
