// O que o YouTube recomenda e as playlists da conta que o yt-dlp não alcança:
// o início, Assistir mais tarde, os vídeos curtidos e os Shorts.

import { accountClientFor, accountKey, clientFor } from "../lib/clients.mjs";
import { feedVideoEntry } from "../lib/entries.mjs";
import { accountListing, pagedFeed } from "../lib/listings.mjs";
import { requireVideoId } from "../lib/text.mjs";

const SHORTS_LIMIT = 15;

function requirePlaylistId(request) {
  const playlistId = String(request.playlist_id || "").trim();
  if (!playlistId) {
    throw new Error("Playlist sem identificador.");
  }
  return playlistId;
}

// O início do YouTube: o que a conta vê ao abrir o site.
export function homeFeed(request) {
  return accountListing(request, "home_feed", (innertube) => innertube.getHomeFeed(), (feed) => feed.videos, feedVideoEntry);
}

// Uma playlist que só a conta lê (Assistir mais tarde, vídeos curtidos, as privadas).
export function accountPlaylist(request) {
  const playlistId = requirePlaylistId(request);
  return accountListing(
    request,
    `playlist:${playlistId}`,
    (innertube) => innertube.getPlaylist(playlistId),
    (feed) => feed.items,
    feedVideoEntry,
  );
}

// Põe um vídeo numa playlist da conta (a de Assistir mais tarde é "WL").
export async function playlistAddVideo(request) {
  const videoId = requireVideoId(request);
  const playlistId = requirePlaylistId(request);
  const innertube = await accountClientFor(request);
  const response = await innertube.actions.execute("/browse/edit_playlist", {
    playlistId,
    actions: [{ action: "ACTION_ADD_VIDEO", addedVideoId: videoId }],
  });
  return { ok: response?.success !== false && response?.data?.status !== "STATUS_FAILED" };
}

// Tira um vídeo de uma playlist da conta.
export async function playlistRemoveVideo(request) {
  const videoId = requireVideoId(request);
  const playlistId = requirePlaylistId(request);
  const innertube = await accountClientFor(request);
  // A biblioteca levanta erro quando o vídeo não está na playlist ou o YouTube recusa.
  await innertube.playlist.removeVideos(playlistId, [videoId]);
  return { ok: true };
}

// Os Shorts abrem como a aba Shorts do site: sem um short de partida, o YouTube escolhe
// o primeiro para a conta e devolve a continuação da sequência.
const SEEDLESS_SHORTS_PARAMS = "CA8%3D";

function isShortsAd(node) {
  // Os anúncios vêm na sequência como shorts; só eles trazem "adClientParams".
  return Boolean(node.payload?.adClientParams);
}

function shortIdOf(node) {
  return node.payload?.videoId || node.payload?.reelWatchEndpoint?.videoId || "";
}

function collectShortIds(ids, nodes) {
  for (const node of nodes || []) {
    const id = isShortsAd(node) ? "" : shortIdOf(node);
    if (id && !ids.includes(id)) {
      ids.push(id);
    }
  }
  return ids;
}

async function seedlessShortIds(request) {
  const account = await accountClientFor(request);
  const first = await account.actions.execute("/reel/reel_item_watch", {
    disablePlayerResponse: true,
    params: SEEDLESS_SHORTS_PARAMS,
    inputType: "REEL_WATCH_INPUT_TYPE_SEEDLESS",
  });
  const seed = first.data?.replacementEndpoint?.reelWatchEndpoint?.videoId || "";
  const ids = seed ? [seed] : [];
  const continuation = first.data?.sequenceContinuation;
  if (continuation) {
    const sequence = await account.actions.execute("/reel/reel_watch_sequence", {
      sequenceParams: continuation,
      parse: true,
    });
    collectShortIds(ids, sequence.entries);
  }
  return ids;
}

// A sequência que o YouTube sugere depois de *seed* (pela conta: são as recomendações dela).
async function shortIdsAfter(request, seed) {
  const info = await (await accountClientFor(request)).getShortsVideoInfo(seed);
  return collectShortIds([seed], info.watch_next_feed);
}

// O título e o canal de cada short. A sequência só traz o endereço: o resto são dados
// públicos, lidos pelo cliente anônimo para não disparar uma rajada de consultas com os cookies.
async function describeShorts(request, ids) {
  const innertube = await clientFor(request);
  const found = await Promise.all(
    ids.map(async (id) => {
      try {
        const basic = (await innertube.getBasicInfo(id)).basic_info;
        return basic?.title
          ? {
              id,
              title: basic.title,
              channel: basic.author || "",
              duration: Number(basic.duration) || 60,
              view_count_number_text: basic.view_count ? String(basic.view_count) : "",
            }
          : null;
      } catch {
        return null;
      }
    }),
  );
  return found.filter(Boolean);
}

export function shorts(request) {
  return pagedFeed(JSON.stringify(["shorts", accountKey(request)]), request, {
    openFeed: async () => {
      const ids = await seedlessShortIds(request);
      if (!ids.length) {
        throw new Error("O YouTube não trouxe nenhum short agora.");
      }
      return { items: await describeShorts(request, ids.slice(0, SHORTS_LIMIT)), has_continuation: false };
    },
    nodesOf: (feed) => feed.items,
    toEntry: (node) => node,
  });
}

// Mais shorts a partir do último que a conta viu: a sequência continua de onde parou.
export async function shortsAfter(request) {
  const seed = requireVideoId(request);
  const ids = (await shortIdsAfter(request, seed)).filter((id) => id !== seed);
  const entries = await describeShorts(request, ids.slice(0, SHORTS_LIMIT));
  return { entries };
}
