// O que o YouTube recomenda e as playlists da conta que o yt-dlp não alcança:
// o início, Assistir mais tarde, os vídeos curtidos e os Shorts.

import { accountClientFor, accountKey } from "../lib/clients.mjs";
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
  const response = await innertube.playlist.addVideos(playlistId, [videoId]);
  return { ok: response?.action_result !== undefined };
}

// Tira um vídeo de uma playlist da conta.
export async function playlistRemoveVideo(request) {
  const videoId = requireVideoId(request);
  const playlistId = requirePlaylistId(request);
  const innertube = await accountClientFor(request);
  const response = await innertube.playlist.removeVideos(playlistId, [videoId]);
  return { ok: response?.action_result !== undefined };
}

// Os Shorts: o YouTube não tem uma lista para abrir, só uma sequência a partir de um
// short. O primeiro vem do início da conta (ou da busca, sem conta).
async function firstShortId(request) {
  const home = await (await accountClientFor(request)).getHomeFeed();
  for (const node of home.videos) {
    const id = node.type === "ReelItem" ? node.id : node.type === "ShortsLockupView" ? node.on_tap_endpoint?.payload?.videoId : "";
    if (id) {
      return id;
    }
  }
  return "";
}

export function shorts(request) {
  return pagedFeed(JSON.stringify(["shorts", accountKey(request)]), request, {
    openFeed: async () => {
      const seed = await firstShortId(request);
      if (!seed) {
        throw new Error("O YouTube não trouxe nenhum short agora.");
      }
      const innertube = await accountClientFor(request);
      const info = await innertube.getShortsVideoInfo(seed);
      // A sequência só traz o endereço de cada short: título e canal vêm de uma leitura
      // por short, feitas juntas e só para os primeiros.
      const ids = [seed];
      for (const node of info.watch_next_feed || []) {
        const id = node.payload?.videoId || node.payload?.reelWatchEndpoint?.videoId;
        if (id && !ids.includes(id)) {
          ids.push(id);
        }
      }
      const found = await Promise.all(
        ids.slice(0, SHORTS_LIMIT).map(async (id) => {
          try {
            const basic = (await innertube.getBasicInfo(id)).basic_info;
            return basic?.title
              ? { id, title: basic.title, channel: basic.author || "", duration: Number(basic.duration) || 60, view_count_number_text: basic.view_count ? String(basic.view_count) : "" }
              : null;
          } catch {
            return null;
          }
        }),
      );
      return { items: found.filter(Boolean), has_continuation: false };
    },
    nodesOf: (feed) => feed.items,
    toEntry: (node) => node,
  });
}
