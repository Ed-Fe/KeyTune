// Comentários de vídeos e de posts: ler as listas, as respostas e escrever um novo. O que
// se faz com um comentário que já está na lista (responder, avaliar, editar, apagar) fica
// em comment_actions.mjs. Com os cookies da conta os comentários vêm com o que é preciso
// para agir sobre cada um.

import { accountClientFor, clientFor } from "../lib/clients.mjs";
import { assertSucceeded } from "../lib/results.mjs";
import { collectEntries, listingPage, listings, pageBounds, rememberListing } from "../lib/listings.mjs";
import { requireVideoId, textOf } from "../lib/text.mjs";
import { entityOf, commentRecord, rememberComment } from "./comment_entities.mjs";

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
  const details = entityOf(comment.keys?.toolbar_surface);
  const mine = Boolean(entityOf(comment.keys?.comment).mine);
  rememberComment(comment.comment_id, { thread, comment, innertube: listing.innertube, account: listing.account });
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
  return {
    ...listingPage(listing, start, count, listing.feed?.has_continuation),
    can_comment: Boolean(listing.account && listing.createParams),
  };
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
  return JSON.stringify(["post_comments", request.lang, request.location, Boolean(request.cookie), request.post_id, sortOf(request)]);
}

// Com *linked_comment* a lista começa pela conversa desse comentário (o de uma notificação).
export function comments(request) {
  const videoId = requireVideoId(request);
  const linked = String(request.linked_comment || "").trim() || undefined;
  return commentsListing(request, videoCommentsKey(request, videoId), (innertube) =>
    innertube.getComments(videoId, sortOf(request), linked),
  );
}

export function postComments(request) {
  const postId = String(request.post_id || "").trim();
  const channelId = String(request.channel_id || "").trim();
  if (!postId || !channelId) {
    throw new Error("Post do YouTube sem identificador.");
  }
  return commentsListing(request, postCommentsKey(request), (innertube) =>
    innertube.getPostComments(postId, channelId, sortOf(request)),
  );
}

function takeReplyNodes(listing, nodes) {
  collectEntries(listing, nodes.filter((node) => node.type !== "ContinuationItem"), (reply) => commentEntry(reply, listing));
  listing.next = nodes.find((node) => node.type === "ContinuationItem") || listing.next;
}

export async function commentReplies(request) {
  const commentId = String(request.comment_id || "");
  const { start, count } = pageBounds(request);
  const key = JSON.stringify(["replies", request.lang, request.location, Boolean(request.cookie), commentId]);
  let listing = listings.get(key);
  if (!listing || start === 0) {
    const record = commentRecord(commentId);
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

// O texto de um comentário, uma resposta ou uma edição: vazio não vale.
export function commentText(request) {
  const text = String(request.text || "").trim();
  if (!text) {
    throw new Error("O comentário está vazio.");
  }
  return text;
}

// Escreve um comentário novo no vídeo ou no post cujos comentários estão abertos.
export async function createComment(request) {
  const text = commentText(request);
  const videoId = request.post_id ? "" : requireVideoId(request);
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
