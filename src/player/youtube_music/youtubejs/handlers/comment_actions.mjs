// O que a conta faz com um comentário que está numa lista aberta com ela: responder,
// avaliar, editar e apagar. É da lista que o YouTube.js tira o que cada ação precisa.

import { assertSucceeded } from "../lib/results.mjs";
import { commentText } from "./comments.mjs";
import { commentRecord, entityOf, forgetComment } from "./comment_entities.mjs";

const RATINGS = {
  like: (comment) => comment.like(),
  unlike: (comment) => comment.unlike(),
  dislike: (comment) => comment.dislike(),
  undislike: (comment) => comment.undislike(),
};

async function rate(comment, operation) {
  assertSucceeded(await RATINGS[operation](comment), "O YouTube recusou a avaliação");
  // A biblioteca não atualiza o comentário depois da ação; a próxima precisa do estado certo.
  comment.is_liked = operation === "like";
  comment.is_disliked = operation === "dislike";
  return { ok: true, liked: comment.is_liked, disliked: comment.is_disliked };
}

async function reply(request, innertube, details) {
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

async function edit(request, innertube, details) {
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

async function remove(comment, innertube, details) {
  if (!details.deleteAction) {
    throw new Error("O YouTube não permite apagar este comentário.");
  }
  const response = await innertube.actions.execute("/comment/perform_comment_action", {
    actions: [details.deleteAction],
  });
  assertSucceeded(response, "O YouTube recusou apagar o comentário");
  forgetComment(comment.comment_id);
  return { ok: true };
}

export async function commentAction(request) {
  const record = commentRecord(request.comment_id);
  if (!record?.account) {
    throw new Error("Abra os comentários de novo, com a conta conectada, para fazer isto.");
  }
  const { comment, innertube } = record;
  const details = entityOf(comment.keys?.toolbar_surface);
  const operation = String(request.operation || "");

  if (RATINGS[operation]) {
    return rate(comment, operation);
  }
  if (operation === "reply") {
    return reply(request, innertube, details);
  }
  if (operation === "edit") {
    return edit(request, innertube, details);
  }
  if (operation === "delete") {
    return remove(comment, innertube, details);
  }
  throw new Error(`Ação de comentário desconhecida: ${operation}`);
}
