// O que a conta acompanha: os vídeos novos das inscrições e os canais inscritos.

import { feedVideoEntry, searchEntry } from "../lib/entries.mjs";
import { accountListing } from "../lib/listings.mjs";

export function subscriptionVideos(request) {
  return accountListing(request, "subscription_videos", (innertube) => innertube.getSubscriptionsFeed(), (feed) => feed.videos, feedVideoEntry);
}

export function subscribedChannels(request) {
  return accountListing(request, "subscribed_channels", (innertube) => innertube.getChannelsFeed(), (feed) => feed.channels, searchEntry);
}
