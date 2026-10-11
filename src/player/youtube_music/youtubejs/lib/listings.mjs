// As listas paginadas: o YouTube entrega em lotes, e a janela pede por faixa (início e
// quantidade). Cada lista aberta fica guardada pela chave para a página seguinte continuar
// de onde a anterior parou.

import { accountClientFor, accountKey } from "./clients.mjs";

const MAX_LISTINGS = 12;

export const listings = new Map();

export function rememberListing(key, listing) {
  listings.delete(key);
  listings.set(key, listing);
  if (listings.size > MAX_LISTINGS) {
    listings.delete(listings.keys().next().value);
  }
  return listing;
}

export function forgetListings(predicate) {
  for (const key of [...listings.keys()]) {
    if (predicate(key)) {
      listings.delete(key);
    }
  }
}

export function pageBounds(request) {
  return {
    start: Math.max(0, Number(request.start) || 0),
    count: Math.max(1, Number(request.count) || 20),
  };
}

export function collectEntries(listing, nodes, toEntry) {
  for (const node of nodes || []) {
    const entry = toEntry(node);
    if (entry?.id && entry.title && !listing.seen.has(entry.id)) {
      listing.seen.add(entry.id);
      listing.entries.push(entry);
    }
  }
}

export function listingPage(listing, start, count, hasContinuation) {
  return {
    entries: listing.entries.slice(start, start + count),
    has_more: listing.entries.length > start + count || Boolean(hasContinuation),
  };
}

// Uma lista de vídeos ou canais lida de um feed com continuação. *openFeed* abre o feed;
// *nodesOf* diz onde estão os itens num lote dele; *toEntry* transforma cada item.
export async function pagedFeed(key, request, { openFeed, nodesOf, toEntry, extra = {} }) {
  const { start, count } = pageBounds(request);
  let listing = listings.get(key);
  if (!listing || start === 0) {
    listing = { entries: [], seen: new Set(), feed: await openFeed(), ...extra };
    collectEntries(listing, nodesOf(listing.feed), toEntry);
  }
  rememberListing(key, listing);
  while (listing.entries.length < start + count && listing.feed?.has_continuation) {
    listing.feed = await listing.feed.getContinuation();
    collectEntries(listing, nodesOf(listing.feed), toEntry);
  }
  return listingPage(listing, start, count, listing.feed?.has_continuation);
}

// Uma lista paginada que só a conta lê.
export function accountListing(request, name, openFeed, nodesOf, toEntry) {
  return pagedFeed(JSON.stringify([name, accountKey(request)]), request, {
    openFeed: async () => openFeed(await accountClientFor(request)),
    nodesOf,
    toEntry,
  });
}
