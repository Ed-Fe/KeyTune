// O que a conta faz com um canal (inscrição e sino) e o que se lê dele: a página "Sobre" e
// a busca nos vídeos dele.

import { accountClientFor, clientFor } from "../lib/clients.mjs";
import { feedVideoEntry } from "../lib/entries.mjs";
import { forgetListings, pagedFeed } from "../lib/listings.mjs";
import { assertOk } from "../lib/results.mjs";
import { requireChannelId, textOf } from "../lib/text.mjs";

const BELL_STATES = {
  SUBSCRIPTION_NOTIFICATION_STATE_ALL: "all",
  SUBSCRIPTION_NOTIFICATION_STATE_OCCASIONAL: "personalized",
  SUBSCRIPTION_NOTIFICATION_STATE_OFF: "none",
};
const BELL_PREFERENCES = { notify_all: "ALL", notify_personalized: "PERSONALIZED", notify_none: "NONE" };

// Se a conta está inscrita no canal e o que o sino dele avisa.
export async function channelState(request) {
  const channelId = requireChannelId(request);
  const innertube = await accountClientFor(request);
  const response = await innertube.actions.execute("/browse", { browseId: channelId });
  const state = { subscribed: false, notifications: "" };
  for (const mutation of response.data?.frameworkUpdates?.entityBatchUpdate?.mutations || []) {
    const payload = mutation.payload || {};
    if (payload.subscriptionStateEntity) {
      state.subscribed = Boolean(payload.subscriptionStateEntity.subscribed);
    }
    if (payload.subscriptionNotificationStateEntity) {
      state.notifications = BELL_STATES[payload.subscriptionNotificationStateEntity.state] || "";
    }
  }
  if (!state.subscribed) {
    state.notifications = "";
  }
  return state;
}

export async function channelAction(request) {
  const channelId = requireChannelId(request);
  const innertube = await accountClientFor(request);
  const operation = String(request.operation || "");
  if (operation === "subscribe") {
    assertOk(await innertube.interact.subscribe(channelId), "O YouTube recusou a inscrição");
  } else if (operation === "unsubscribe") {
    assertOk(await innertube.interact.unsubscribe(channelId), "O YouTube recusou cancelar a inscrição");
  } else if (BELL_PREFERENCES[operation]) {
    assertOk(
      await innertube.interact.setNotificationPreferences(channelId, BELL_PREFERENCES[operation]),
      "O YouTube recusou mudar as notificações do canal",
    );
  } else {
    throw new Error(`Ação de canal desconhecida: ${operation}`);
  }
  // As listas de inscrições em cache já não valem.
  forgetListings((key) => key.includes("subscribed_channels") || key.includes("subscription_videos"));
  return { ok: true };
}

// A página "Sobre" do canal: descrição, inscritos, vídeos, visualizações, país e data de entrada.
export async function channelAbout(request) {
  const channelId = requireChannelId(request);
  const innertube = await clientFor(request);
  const channel = await innertube.getChannel(channelId);
  const about = await channel.getAbout();
  const view = about?.metadata || about || {};
  return {
    title: textOf(channel.metadata?.title) || textOf(view.name),
    description: textOf(view.description) || textOf(channel.metadata?.description),
    subscribers: textOf(view.subscriber_count),
    video_count: textOf(view.video_count),
    view_count: textOf(view.view_count),
    joined: textOf(view.joined_date),
    country: textOf(view.country),
    url: view.canonical_channel_url || `https://www.youtube.com/channel/${channelId}`,
    links: (view.links || view.primary_links || [])
      .map((link) => [textOf(link.title), textOf(link.link)].filter(Boolean).join(": "))
      .filter(Boolean),
  };
}

// O que a busca de dentro de um canal acha nos vídeos dele.
export async function channelSearch(request) {
  const channelId = requireChannelId(request);
  const query = String(request.query || "").trim();
  if (!query) {
    return { entries: [], has_more: false };
  }
  const key = JSON.stringify(["channel_search", request.lang, request.location, channelId, query]);
  return pagedFeed(key, request, {
    openFeed: async () => (await (await clientFor(request)).getChannel(channelId)).search(query),
    nodesOf: (feed) => feed.videos,
    toEntry: feedVideoEntry,
  });
}
