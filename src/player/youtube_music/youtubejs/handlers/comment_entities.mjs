// O que as ações de comentário precisam e a biblioteca descarta da resposta: de quem é o
// comentário, os parâmetros para responder e os itens do menu dele (editar, apagar). O
// cliente da conta entrega cada resposta aqui (veja lib/clients.mjs).

import { findValue } from "../lib/find.mjs";
import { rememberBounded } from "../lib/bounded.mjs";

const MAX_COMMENT_RECORDS = 3000;
const MAX_RAW_ENTITIES = 6000;

const rawEntities = new Map();
// Cada comentário mostrado, pelo identificador: é nele que as ações são feitas depois.
const commentRecords = new Map();

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

// Guarda, de cada lote de comentários, o que as ações usam.
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

export function entityOf(key) {
  return rawEntities.get(key) || {};
}

export function rememberComment(commentId, record) {
  rememberBounded(commentRecords, commentId, record, MAX_COMMENT_RECORDS);
}

export function commentRecord(commentId) {
  return commentRecords.get(String(commentId || ""));
}

export function forgetComment(commentId) {
  commentRecords.delete(commentId);
}
