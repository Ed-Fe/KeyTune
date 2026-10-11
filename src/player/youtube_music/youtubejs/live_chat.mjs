// O chat de uma transmissão ao vivo: as mensagens que chegam e, com a conta, enviar uma.
// Cada pedido traz só o que chegou desde o anterior; quem quer acompanhar pede de novo
// a cada poucos segundos.

import { randomUUID } from "node:crypto";

const MAX_CHATS = 3;
const MAX_SEEN_MESSAGES = 2000;

export function createLiveChatHandlers({ clientFor, accountClientFor, videoIdFrom }) {
  // Um chat aberto por vídeo e por tipo de cliente: a continuação e o que já foi entregue.
  const chats = new Map();

  function chatKey(request, videoId) {
    return `${videoId}|${request.cookie ? "account" : "guest"}`;
  }

  function messageText(message) {
    return (message?.runs || [])
      .map((run) => run.text ?? (run.emoji?.isCustomEmoji ? run.emoji.shortcuts?.[0] : run.emoji?.emojiId) ?? "")
      .join("")
      .trim();
  }

  function messageEntry(action) {
    const item = action.addChatItemAction?.item || {};
    const renderer = item.liveChatTextMessageRenderer || item.liveChatPaidMessageRenderer;
    if (!renderer?.id) {
      return null;
    }
    const text = messageText(renderer.message);
    const amount = renderer.purchaseAmountText?.simpleText || "";
    if (!text && !amount) {
      return null;
    }
    return {
      id: renderer.id,
      author: renderer.authorName?.simpleText || "",
      text,
      amount,
    };
  }

  async function openChat(request, videoId) {
    const account = Boolean(String(request.cookie || "").trim());
    const innertube = account ? await accountClientFor(request) : await clientFor(request);
    const info = await innertube.getInfo(videoId);
    if (!info.livechat?.continuation || info.livechat.is_replay) {
      throw new Error("Este vídeo não tem chat ao vivo.");
    }
    return { innertube, account, continuation: info.livechat.continuation, sendParams: "", seen: new Set() };
  }

  // As mensagens novas do chat de um vídeo ao vivo; *restart* recomeça das mais recentes.
  async function liveChat(request) {
    const videoId = videoIdFrom(request.media_url);
    if (!videoId) {
      throw new Error("URL do YouTube sem identificador de vídeo.");
    }
    const key = chatKey(request, videoId);
    let chat = chats.get(key);
    if (!chat || request.restart) {
      chat = await openChat(request, videoId);
      chats.delete(key);
      chats.set(key, chat);
      if (chats.size > MAX_CHATS) {
        chats.delete(chats.keys().next().value);
      }
    }

    const response = await chat.innertube.actions.execute("/live_chat/get_live_chat", {
      continuation: chat.continuation,
    });
    const contents = response.data?.continuationContents?.liveChatContinuation;
    if (!contents) {
      // A transmissão acabou: o YouTube para de devolver o chat.
      chats.delete(key);
      return { entries: [], can_send: false, ended: true };
    }

    const entries = [];
    for (const action of contents.actions || []) {
      const entry = messageEntry(action);
      if (entry && !chat.seen.has(entry.id)) {
        chat.seen.add(entry.id);
        entries.push(entry);
      }
    }
    if (chat.seen.size > MAX_SEEN_MESSAGES) {
      chat.seen = new Set([...chat.seen].slice(-MAX_SEEN_MESSAGES / 2));
    }
    const next = Object.values(contents.continuations?.[0] || {})[0];
    chat.continuation = next?.continuation || chat.continuation;
    chat.sendParams =
      contents.actionPanel?.liveChatMessageInputRenderer?.sendButton?.buttonRenderer?.serviceEndpoint
        ?.sendLiveChatMessageEndpoint?.params || chat.sendParams;
    chat.viewer =
      contents.actionPanel?.liveChatMessageInputRenderer?.authorName?.simpleText ||
      (typeof contents.viewerName === "string" ? contents.viewerName : "") ||
      chat.viewer ||
      "";
    // Num chat só para inscritos ou membros, o YouTube manda o motivo no lugar do campo de escrita.
    const restricted = contents.actionPanel?.liveChatRestrictedParticipationRenderer?.message;
    if (contents.actionPanel) {
      chat.restriction = restricted ? messageText(restricted) || restricted.simpleText || "" : "";
    }
    return {
      entries,
      can_send: Boolean(chat.account && chat.sendParams),
      ended: false,
      viewer: chat.viewer,
      restriction: chat.account ? chat.restriction || "" : "",
    };
  }

  async function liveChatSend(request) {
    const videoId = videoIdFrom(request.media_url);
    const text = String(request.text || "").trim();
    if (!text) {
      throw new Error("A mensagem está vazia.");
    }
    let chat = chats.get(chatKey(request, videoId));
    if (!chat?.sendParams) {
      // O chat aberto veio sem a conta, ou já saiu da memória: é buscado de novo com ela.
      await liveChat({ ...request, restart: true });
      chat = chats.get(chatKey(request, videoId));
    }
    if (!chat?.account || !chat.sendParams) {
      throw new Error("O YouTube não permite enviar mensagens neste chat com esta conta.");
    }
    const response = await chat.innertube.actions.execute("/live_chat/send_message", {
      params: chat.sendParams,
      richMessage: { textSegments: [{ text }] },
      clientMessageId: randomUUID(),
    });
    if (response?.success === false) {
      throw new Error(`O YouTube recusou a mensagem (HTTP ${response.status_code}).`);
    }
    return { ok: true };
  }

  return { live_chat: liveChat, live_chat_send: liveChatSend };
}
