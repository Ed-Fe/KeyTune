// O que a conta do YouTube acompanha nos canais: as notificações, a inscrição e o
// sino de cada canal, os posts e a página "Sobre". O resolve.mjs entrega os clientes
// e os ajudantes de listagem.

const MAX_NOTIFICATIONS = 300;
const MAX_POSTS = 500;

// As notificações mostradas, pelo identificador: marcar como lida e ocultar agem nelas.
const notificationRecords = new Map();
// Os posts mostrados pela conta, pelo identificador: é neles que se vota na enquete.
const postRecords = new Map();

const BELL_STATES = {
  SUBSCRIPTION_NOTIFICATION_STATE_ALL: "all",
  SUBSCRIPTION_NOTIFICATION_STATE_OCCASIONAL: "personalized",
  SUBSCRIPTION_NOTIFICATION_STATE_OFF: "none",
};
const BELL_PREFERENCES = { notify_all: "ALL", notify_personalized: "PERSONALIZED", notify_none: "NONE" };

// O fetch do cliente da conta. Depois de uma mudança (inscrição, sino, notificação lida)
// o YouTube devolve um token de consistência; sem mandá-lo de volta, as leituras seguintes
// podem vir com o estado antigo por até dez minutos. *onResponse* recebe cada resposta JSON.
export function createAccountFetch(onResponse) {
  let jar = { token: "", expires: 0 };

  function withConsistencyToken(init) {
    if (!jar.token || Date.now() > jar.expires || typeof init?.body !== "string") {
      return init;
    }
    try {
      const body = JSON.parse(init.body);
      if (!body?.context) {
        return init;
      }
      body.context.request = {
        ...(body.context.request || {}),
        consistencyTokenJars: [{ encryptedTokenJarContents: jar.token }],
      };
      return { ...init, body: JSON.stringify(body) };
    } catch {
      return init;
    }
  }

  return async function accountFetch(input, init) {
    const response = await fetch(input, withConsistencyToken(init));
    const url = String(input?.url || input || "");
    if (response.ok && url.includes("/youtubei/v1/")) {
      try {
        const data = await response.clone().json();
        const tokenJar = data?.responseContext?.consistencyTokenJar;
        if (tokenJar?.encryptedTokenJarContents) {
          jar = {
            token: tokenJar.encryptedTokenJarContents,
            expires: Date.now() + (Number(tokenJar.expirationSeconds) || 600) * 1000,
          };
        }
        onResponse?.(data);
      } catch {
        // Uma resposta que não é JSON só não traz o que guardar.
      }
    }
    return response;
  };
}

function assertOk(response, fallback) {
  if (response?.success === false) {
    throw new Error(`${fallback} (HTTP ${response.status_code})`);
  }
}

export function createAccountHandlers({
  clientFor,
  accountClientFor,
  accountKey,
  accountListing,
  feedVideoEntry,
  listings,
  rememberListing,
  pageBounds,
  collectEntries,
  listingPage,
  textOf,
  videoIdFrom,
}) {
  function channelIdOf(request) {
    const channelId = String(request.channel_id || "").trim();
    if (!/^UC[\w-]{22}$/.test(channelId)) {
      throw new Error("Canal do YouTube sem identificador.");
    }
    return channelId;
  }

  function notificationEntry(node) {
    if (!node.notification_id) {
      return null;
    }
    rememberNotification(node);
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

  function rememberNotification(node) {
    notificationRecords.delete(String(node.notification_id));
    notificationRecords.set(String(node.notification_id), node);
    if (notificationRecords.size > MAX_NOTIFICATIONS) {
      notificationRecords.delete(notificationRecords.keys().next().value);
    }
  }

  // A caixa de notificações da conta. O menu do YouTube nem sempre tem página seguinte.
  async function notifications(request) {
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

  async function notificationAction(request) {
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

  // Se a conta está inscrita no canal e o que o sino dele avisa.
  async function channelState(request) {
    const channelId = channelIdOf(request);
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

  async function channelAction(request) {
    const channelId = channelIdOf(request);
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
    for (const key of [...listings.keys()]) {
      if (key.includes("subscribed_channels") || key.includes("subscription_videos")) {
        listings.delete(key);
      }
    }
    return { ok: true };
  }

  function attachmentText(attachment) {
    if (!attachment) {
      return { text: "", video_id: "" };
    }
    if (attachment.type === "Video" || attachment.type === "VideoCard") {
      return { text: textOf(attachment.title), video_id: attachment.video_id || attachment.id || "" };
    }
    if (attachment.type === "Poll") {
      const choices = (attachment.choices || []).map((choice) => textOf(choice.text));
      return { text: choices.filter(Boolean).join(" / "), video_id: "", poll: true, choices };
    }
    if (attachment.type === "BackstageImage" || attachment.type === "PostMultiImage") {
      return { text: "", video_id: "", image: true };
    }
    return { text: "", video_id: "" };
  }

  function postEntry(node, channelId, listing) {
    const post = node.type === "SharedPost" ? node.original_post || node : node;
    const id = node.id || post.id;
    if (!id) {
      return null;
    }
    const attachment = attachmentText(post.attachment);
    const canVote = Boolean(
      listing.account && attachment.poll && (post.attachment.choices || []).every((choice) => choice.select_endpoint),
    );
    if (canVote) {
      postRecords.delete(id);
      postRecords.set(id, { poll: post.attachment, innertube: listing.innertube });
      if (postRecords.size > MAX_POSTS) {
        postRecords.delete(postRecords.keys().next().value);
      }
    }
    return {
      id,
      channel_id: channelId,
      author: textOf(node.author?.name) || textOf(post.author?.name),
      text: textOf(node.content) || textOf(post.content),
      published: textOf(node.published) || textOf(post.published),
      likes: textOf(post.vote_count),
      reply_count: textOf(post.action_buttons?.reply_button?.text),
      attachment_text: attachment.text,
      attachment_video_id: attachment.video_id,
      has_image: Boolean(attachment.image),
      has_poll: Boolean(attachment.poll),
      poll_choices: attachment.choices || [],
      can_vote: canVote,
      title: "-",
    };
  }

  // Os posts da aba "Posts" (comunidade) de um canal; não precisam da conta, mas com ela
  // as enquetes vêm prontas para votar.
  async function channelPosts(request) {
    const channelId = channelIdOf(request);
    const { start, count } = pageBounds(request);
    const account = Boolean(String(request.cookie || "").trim());
    const key = JSON.stringify(["channel_posts", request.lang, request.location, account, channelId]);
    let listing = listings.get(key);
    if (!listing || start === 0) {
      const innertube = account ? await accountClientFor(request) : await clientFor(request);
      const channel = await innertube.getChannel(channelId);
      listing = { entries: [], seen: new Set(), feed: null, innertube, account };
      if (channel.has_community) {
        listing.feed = await channel.getCommunity();
        collectEntries(listing, listing.feed.posts, (node) => postEntry(node, channelId, listing));
      }
    }
    rememberListing(key, listing);
    while (listing.entries.length < start + count && listing.feed?.has_continuation) {
      listing.feed = await listing.feed.getContinuation();
      collectEntries(listing, listing.feed.posts, (node) => postEntry(node, channelId, listing));
    }
    return listingPage(listing, start, count, listing.feed?.has_continuation);
  }

  // Vota numa opção da enquete de um post, ou tira o voto dela (*operation* "unvote").
  async function postVote(request) {
    const record = postRecords.get(String(request.post_id || ""));
    const choice = record?.poll.choices?.[Number(request.choice)];
    if (!choice) {
      throw new Error("Abra os posts do canal de novo, com a conta conectada, para votar.");
    }
    const endpoint = request.operation === "unvote" ? choice.deselect_endpoint : choice.select_endpoint;
    if (!endpoint) {
      throw new Error("O YouTube não permite votar nesta enquete.");
    }
    assertOk(await endpoint.call(record.innertube.actions), "O YouTube recusou o voto");
    return { ok: true };
  }

  // O que a busca de dentro de um canal acha nos vídeos dele.
  async function channelSearch(request) {
    const channelId = channelIdOf(request);
    const query = String(request.query || "").trim();
    const { start, count } = pageBounds(request);
    if (!query) {
      return { entries: [], has_more: false };
    }
    const key = JSON.stringify(["channel_search", request.lang, request.location, channelId, query]);
    let listing = listings.get(key);
    if (!listing || start === 0) {
      const innertube = await clientFor(request);
      const channel = await innertube.getChannel(channelId);
      listing = { entries: [], seen: new Set(), feed: await channel.search(query) };
      collectEntries(listing, listing.feed.videos, feedVideoEntry);
    }
    rememberListing(key, listing);
    while (listing.entries.length < start + count && listing.feed?.has_continuation) {
      listing.feed = await listing.feed.getContinuation();
      collectEntries(listing, listing.feed.videos, feedVideoEntry);
    }
    return listingPage(listing, start, count, listing.feed?.has_continuation);
  }

  // O histórico do YouTube da conta: o que foi assistido, do mais recente para o mais antigo.
  function watchHistory(request) {
    return accountListing(request, "watch_history", (innertube) => innertube.getHistory(), (feed) => feed.videos, feedVideoEntry);
  }

  // Põe um vídeo no histórico da conta, como o YouTube faz quando ele começa a tocar.
  async function addToHistory(request) {
    const videoId = videoIdFrom(request.media_url);
    if (!videoId) {
      throw new Error("URL do YouTube sem identificador de vídeo.");
    }
    const innertube = await accountClientFor(request);
    const info = await innertube.getInfo(videoId);
    const response = await info.addToWatchHistory();
    return { ok: response?.ok !== false };
  }

  // A página "Sobre" do canal: descrição, inscritos, vídeos, visualizações, país e data de entrada.
  async function channelAbout(request) {
    const channelId = channelIdOf(request);
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

  return {
    notifications,
    notification_action: notificationAction,
    channel_state: channelState,
    channel_action: channelAction,
    channel_posts: channelPosts,
    channel_about: channelAbout,
    channel_search: channelSearch,
    post_vote: postVote,
    watch_history: watchHistory,
    add_to_history: addToHistory,
  };
}
