// A caixa de notificações da conta: ler, marcar como lida e ocultar.

import { accountClientFor, accountKey } from "../lib/clients.mjs";
import { rememberBounded } from "../lib/bounded.mjs";
import { assertOk } from "../lib/results.mjs";
import { collectEntries, listingPage, listings, pageBounds, rememberListing } from "../lib/listings.mjs";
import { textOf } from "../lib/text.mjs";

const MAX_NOTIFICATIONS = 300;

// As notificações mostradas, pelo identificador: marcar como lida e ocultar agem nelas.
const notificationRecords = new Map();

function notificationEntry(node) {
  if (!node.notification_id) {
    return null;
  }
  rememberBounded(notificationRecords, String(node.notification_id), node, MAX_NOTIFICATIONS);
  const target = node.endpoint?.payload || {};
  // A notificação de um comentário ou de uma resposta aponta para ele no endereço do vídeo.
  const linked = /[?&]lc=([\w.-]+)/.exec(String(node.endpoint?.metadata?.url || ""));
  return {
    id: String(node.notification_id),
    title: textOf(node.short_message),
    published: textOf(node.sent_time),
    read: Boolean(node.read),
    video_id: /^[\w-]{11}$/.test(target.videoId || "") ? target.videoId : "",
    comment_id: linked ? linked[1] : "",
  };
}

// A caixa de notificações da conta. O menu do YouTube nem sempre tem página seguinte.
export async function notifications(request) {
  const { start, count } = pageBounds(request);
  const key = JSON.stringify(["notifications", accountKey(request)]);
  let listing = listings.get(key);
  if (!listing || start === 0) {
    const innertube = await accountClientFor(request);
    listing = { entries: [], seen: new Set(), menu: await innertube.getNotifications(), done: false };
    collectEntries(listing, listing.menu.contents, notificationEntry);
  }
  rememberListing(key, listing);
  while (listing.entries.length < start + count && !listing.done) {
    try {
      listing.menu = await listing.menu.getContinuation();
      collectEntries(listing, listing.menu.contents, notificationEntry);
    } catch {
      listing.done = true;
    }
  }
  return listingPage(listing, start, count, !listing.done && listing.entries.length > start + count);
}

// O YouTube recebe o que foi feito com a notificação num campo com outro nome que o do comando.
async function recordInteraction(innertube, endpoint, fallback) {
  const token = endpoint?.payload?.serializedInteractionsRequest;
  if (!token) {
    throw new Error(`${fallback}.`);
  }
  const response = await innertube.actions.execute("/notification/record_interactions", {
    serializedRecordNotificationInteractionsRequest: token,
  });
  assertOk(response, fallback);
}

export async function notificationAction(request) {
  const innertube = await accountClientFor(request);
  const notificationId = String(request.notification_id || "");
  if (!notificationRecords.has(notificationId)) {
    // O processo recomeçou desde que a lista foi mostrada: a notificação é buscada de novo.
    await notifications({ ...request, start: 0, count: 50 });
  }
  const node = notificationRecords.get(notificationId);
  if (!node) {
    throw new Error("Esta notificação não está mais na sua caixa.");
  }
  if (request.operation === "read") {
    await recordInteraction(innertube, node.record_click_endpoint, "O YouTube não marcou a notificação como lida");
    node.read = true;
    return { ok: true };
  }
  if (request.operation === "hide") {
    const item = (node.menu?.items || []).find((entry) => entry.icon_type === "VISIBILITY_OFF");
    await recordInteraction(innertube, item?.endpoint, "O YouTube não permite ocultar esta notificação");
    notificationRecords.delete(notificationId);
    return { ok: true };
  }
  throw new Error(`Ação de notificação desconhecida: ${request.operation}`);
}
