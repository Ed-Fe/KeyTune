// Comentários de vídeos e de posts: ler, escrever, responder, avaliar, editar e apagar.
// O resolve.mjs entrega os clientes e os ajudantes de listagem; com os cookies da
// conta os comentários vêm com o que é preciso para agir sobre cada um.

const MAX_COMMENT_RECORDS = 3000;
const MAX_RAW_ENTITIES = 6000;

// O que a biblioteca descarta da resposta e as ações precisam: de quem é o comentário,
// os parâmetros para responder e os itens do menu dele (editar, apagar).
const rawEntities = new Map();
// Cada comentário mostrado, pelo identificador: é nele que as ações são feitas depois.
const commentRecords = new Map();

function rememberBounded(map, key, value, limit) {
  map.delete(key);
  map.set(key, value);
  if (map.size > limit) {
    map.delete(map.keys().next().value);
  }
}

function findValue(node, key, depth = 0) {
  if (!node || typeof node !== "object" || depth > 24) {
    return undefined;
  }
  if (!Array.isArray(node) && node[key] !== undefined) {
    return node[key];
  }
  for (const value of Array.isArray(node) ? node : Object.values(node)) {
    const found = findValue(value, key, depth + 1);
    if (found !== undefined) {
      return found;
    }
  }
  return undefined;
}

function toolbarDetails(payload) {
  const details = { replyParams: findValue(payload.replyCommand, "createReplyParams") || "" };
  const items = payload.menuCommand?.innertubeCommand?.menuEndpoint?.menu?.menuRenderer?.items || [];
  for (const item of items) {
    const renderer = Object.values(item || {})[0] || {};
    const icon = renderer.icon?.iconType;
    if (icon === "DELETE") {
      details.deleteAction = findValue(renderer, "performCommentActionEndpoint")?.action || "";
    } else if (icon === "EDIT") {
      details.editParams = findValue(renderer, "updateCommentParams") || "";
      details.editReplyParams = findValue(renderer, "updateReplyParams") || "";
    }
  }
  return details;
}

// Chamado pelo fetch do cliente da conta com cada resposta: guarda, de cada lote de
// comentários, o que as ações usam.
export function rememberRawEntities(data) {
  for (const mutation of data?.frameworkUpdates?.entityBatchUpdate?.mutations || []) {
    const payload = mutation.payload || {};
    if (!mutation.entityKey) {
      continue;
    }
    if (payload.commentEntityPayload) {
      const mine = Boolean(payload.commentEntityPayload.author?.isCurrentUser);
      rememberBounded(rawEntities, mutation.entityKey, { mine }, MAX_RAW_ENTITIES);
    } else if (payload.engagementToolbarSurfaceEntityPayload) {
      rememberBounded(
        rawEntities,
        mutation.entityKey,
        toolbarDetails(payload.engagementToolbarSurfaceEntityPayload),
        MAX_RAW_ENTITIES,
      );
    }
  }
}

function assertSucceeded(response, fallback) {
  const status = response?.data?.actionResult?.status || findValue(response?.data, "actionResult")?.status;
  if (response?.success === false || (status && status !== "STATUS_SUCCEEDED")) {
    throw new Error(`${fallback} (${status || `HTTP ${response?.status_code}`})`);
  }
}

export function createCommentHandlers({
  clientFor,
  accountClientFor,
  listings,
  rememberListing,
  pageBounds,
  collectEntries,
  listingPage,
  textOf,
  videoIdFrom,
}) {
  // Com a conta conectada os comentários vêm por ela; sem ela, pelo cliente anônimo.
  async function commentClient(request) {
    const account = Boolean(String(request.cookie || "").trim());
    return { innertube: account ? await accountClientFor(request) : await clientFor(request), account };
  }

  function commentEntry(thread, listing) {
    const comment = thread.comment || thread;
    if (!comment?.comment_id) {
      return null;
    }
    const details = rawEntities.get(comment.keys?.toolbar_surface) || {};
    const mine = Boolean(rawEntities.get(comment.keys?.comment)?.mine);
    rememberBounded(
      commentRecords,
      comment.comment_id,
      { thread, comment, innertube: listing.innertube, account: listing.account },
      MAX_COMMENT_RECORDS,
    );
    return {
      id: comment.comment_id,
      author: textOf(comment.author?.name),
      text: textOf(comment.content),
      likes: textOf(comment.like_count),
      published: textOf(comment.published_time),
      reply_count: textOf(comment.reply_count),
      // Só os comentários principais guardam a conversa de onde saem as respostas.
      has_replies: Boolean(listing.top_level && thread.has_replies),
      pinned: Boolean(comment.is_pinned),
      liked: Boolean(comment.is_liked),
      disliked: Boolean(comment.is_disliked),
      mine,
      can_rate: Boolean(listing.account && comment.like_command),
      can_reply: Boolean(listing.account && details.replyParams),
      can_edit: Boolean(listing.account && (details.editParams || details.editReplyParams)),
      can_delete: Boolean(listing.account && details.deleteAction),
      title: "-",
    };
  }

  async function commentsListing(request, key, fetchFeed) {
    const { start, count } = pageBounds(request);
    let listing = listings.get(key);
    if (!listing || start === 0) {
      const { innertube, account } = await commentClient(request);
      listing = { entries: [], seen: new Set(), top_level: true, innertube, account, feed: null, createParams: "" };
      try {
        listing.feed = await fetchFeed(innertube);
      } catch (error) {
        // É assim que a biblioteca avisa que os comentários estão desativados.
        if (!String(error?.message).includes("did not have any content")) {
          throw error;
        }
      }
      listing.createParams =
        listing.feed?.header?.create_renderer?.submit_button?.endpoint?.payload?.createCommentParams || "";
      collectEntries(listing, listing.feed?.contents, (thread) => commentEntry(thread, listing));
    }
    rememberListing(key, listing);
    while (listing.entries.length < start + count && listing.feed?.has_continuation) {
      listing.feed = await listing.feed.getContinuation();
      collectEntries(listing, listing.feed.contents, (thread) => commentEntry(thread, listing));
    }
    return { ...listingPage(listing, start, count, listing.feed?.has_continuation), can_comment: Boolean(listing.account && listing.createParams) };
  }

  // "newest" traz os mais recentes primeiro; o padrão são os principais.
  function sortOf(request) {
    return request.sort === "newest" ? "NEWEST_FIRST" : "TOP_COMMENTS";
  }

  function videoCommentsKey(request, videoId) {
    return JSON.stringify([
      "comments",
      request.lang,
      request.location,
      Boolean(request.cookie),
      videoId,
      sortOf(request),
      String(request.linked_comment || ""),
    ]);
  }

  function postCommentsKey(request) {
    return JSON.stringify([
      "post_comments",
      request.lang,
      request.location,
      Boolean(request.cookie),
      request.post_id,
      sortOf(request),
    ]);
  }

  // Com *linked_comment* a lista começa pela conversa desse comentário (o de uma notificação).
  function comments(request) {
    const videoId = videoIdFrom(request.media_url);
    if (!videoId) {
      throw new Error("URL do YouTube sem identificador de vídeo.");
    }
    const linked = String(request.linked_comment || "").trim() || undefined;
    return commentsListing(request, videoCommentsKey(request, videoId), (innertube) =>
      innertube.getComments(videoId, sortOf(request), linked),
    );
  }

  function postComments(request) {
    const postId = String(request.post_id || "").trim();
    const channelId = String(request.channel_id || "").trim();
    if (!postId || !channelId) {
      throw new Error("Post do YouTube sem identificador.");
    }
    return commentsListing(request, postCommentsKey(request), (innertube) =>
      innertube.getPostComments(postId, channelId, sortOf(request)),
    );
  }

  async function commentReplies(request) {
    const commentId = String(request.comment_id || "");
    const { start, count } = pageBounds(request);
    const key = JSON.stringify(["replies", request.lang, request.location, Boolean(request.cookie), commentId]);
    let listing = listings.get(key);
    if (!listing || start === 0) {
      const record = commentRecords.get(commentId);
      if (!record?.thread?.comment) {
        throw new Error("Os comentários deste vídeo precisam ser abertos de novo.");
      }
      listing = { entries: [], seen: new Set(), innertube: record.innertube, account: record.account, next: null };
      // O YouTube manda as respostas em dois formatos, conforme a sessão; os dois chegam aqui.
      const replyData = record.thread.comment_replies_data;
      takeReplyNodes(listing, [...(replyData?.sub_threads || []), ...(replyData?.contents || [])]);
    }
    rememberListing(key, listing);
    while (listing.entries.length < start + count && listing.next) {
      const endpoint = listing.next.button?.endpoint || listing.next.endpoint;
      listing.next = null;
      const response = await endpoint.call(listing.innertube.actions, { parse: true });
      for (const action of response.on_response_received_endpoints || []) {
        takeReplyNodes(listing, [...(action.contents || [])]);
      }
    }
    return listingPage(listing, start, count, listing.next);
  }

  function takeReplyNodes(listing, nodes) {
    collectEntries(listing, nodes.filter((node) => node.type !== "ContinuationItem"), (reply) => commentEntry(reply, listing));
    listing.next = nodes.find((node) => node.type === "ContinuationItem") || listing.next;
  }

  function commentText(request) {
    const text = String(request.text || "").trim();
    if (!text) {
      throw new Error("O comentário está vazio.");
    }
    return text;
  }

  // Escreve um comentário novo no vídeo ou no post cujos comentários estão abertos.
  async function createComment(request) {
    const text = commentText(request);
    const videoId = request.post_id ? "" : videoIdFrom(request.media_url);
    const key = request.post_id ? postCommentsKey(request) : videoCommentsKey(request, videoId);
    let listing = listings.get(key);
    if (!listing?.account) {
      // A lista aberta veio sem a conta (ou já saiu da memória): busca de novo com ela.
      await (request.post_id ? postComments({ ...request, start: 0 }) : comments({ ...request, start: 0 }));
      listing = listings.get(key);
    }
    if (!listing?.createParams) {
      throw new Error("O YouTube não permite comentar aqui com esta conta.");
    }
    const response = await listing.innertube.actions.execute("/comment/create_comment", {
      createCommentParams: listing.createParams,
      commentText: text,
    });
    assertSucceeded(response, "O YouTube recusou o comentário");
    return { ok: true };
  }

  const RATINGS = {
    like: (comment) => comment.like(),
    unlike: (comment) => comment.unlike(),
    dislike: (comment) => comment.dislike(),
    undislike: (comment) => comment.undislike(),
  };

  // Responde, avalia, edita ou apaga um comentário que está numa lista aberta com a conta.
  async function commentAction(request) {
    const record = commentRecords.get(String(request.comment_id || ""));
    if (!record?.account) {
      throw new Error("Abra os comentários de novo, com a conta conectada, para fazer isto.");
    }
    const { comment, innertube } = record;
    const details = rawEntities.get(comment.keys?.toolbar_surface) || {};
    const operation = String(request.operation || "");

    if (RATINGS[operation]) {
      assertSucceeded(await RATINGS[operation](comment), "O YouTube recusou a avaliação");
      // A biblioteca não atualiza o comentário depois da ação; a próxima precisa do estado certo.
      comment.is_liked = operation === "like";
      comment.is_disliked = operation === "dislike";
      return { ok: true, liked: comment.is_liked, disliked: comment.is_disliked };
    }
    if (operation === "reply") {
      if (!details.replyParams) {
        throw new Error("O YouTube não permite responder a este comentário.");
      }
      const response = await innertube.actions.execute("/comment/create_comment_reply", {
        createReplyParams: details.replyParams,
        commentText: commentText(request),
      });
      assertSucceeded(response, "O YouTube recusou a resposta");
      return { ok: true };
    }
    if (operation === "edit") {
      if (!details.editParams && !details.editReplyParams) {
        throw new Error("O YouTube não permite editar este comentário.");
      }
      const response = details.editParams
        ? await innertube.actions.execute("/comment/update_comment", {
            updateCommentParams: details.editParams,
            commentText: commentText(request),
          })
        : await innertube.actions.execute("/comment/update_comment_reply", {
            updateReplyParams: details.editReplyParams,
            commentText: commentText(request),
          });
      assertSucceeded(response, "O YouTube recusou a edição");
      return { ok: true };
    }
    if (operation === "delete") {
      if (!details.deleteAction) {
        throw new Error("O YouTube não permite apagar este comentário.");
      }
      const response = await innertube.actions.execute("/comment/perform_comment_action", {
        actions: [details.deleteAction],
      });
      assertSucceeded(response, "O YouTube recusou apagar o comentário");
      commentRecords.delete(comment.comment_id);
      return { ok: true };
    }
    throw new Error(`Ação de comentário desconhecida: ${operation}`);
  }

  return {
    comments,
    comment_replies: commentReplies,
    post_comments: postComments,
    create_comment: createComment,
    comment_action: commentAction,
  };
}
