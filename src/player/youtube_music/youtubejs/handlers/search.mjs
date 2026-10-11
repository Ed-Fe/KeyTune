// A busca do YouTube.

import { clientFor } from "../lib/clients.mjs";
import { searchEntry } from "../lib/entries.mjs";
import { pagedFeed } from "../lib/listings.mjs";

const SEARCH_TYPES = { videos: "video", channels: "channel", playlists: "playlist" };

export async function search(request) {
  const query = String(request.query || "").trim();
  const type = SEARCH_TYPES[request.kind] || SEARCH_TYPES.videos;
  if (!query) {
    return { entries: [], has_more: false };
  }
  const key = JSON.stringify(["search", request.lang, request.location, type, query]);
  return pagedFeed(key, request, {
    openFeed: async () => (await clientFor(request)).search(query, { type }),
    nodesOf: (feed) => feed.results,
    toEntry: searchEntry,
  });
}
