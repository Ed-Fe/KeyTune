// Confere a resposta de uma ação que muda algo na conta.

import { findValue } from "./find.mjs";

// Respostas de ações simples: o YouTube.js marca a falha em ``success``.
export function assertOk(response, fallback) {
  if (response?.success === false) {
    throw new Error(`${fallback} (HTTP ${response.status_code})`);
  }
}

// Respostas das ações de comentário: o resultado vem dentro do corpo.
export function assertSucceeded(response, fallback) {
  const status = response?.data?.actionResult?.status || findValue(response?.data, "actionResult")?.status;
  if (response?.success === false || (status && status !== "STATUS_SUCCEEDED")) {
    throw new Error(`${fallback} (${status || `HTTP ${response?.status_code}`})`);
  }
}
