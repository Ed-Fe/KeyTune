// O fetch do cliente da conta. Depois de uma mudança (inscrição, sino, notificação lida)
// o YouTube devolve um token de consistência; sem mandá-lo de volta, as leituras seguintes
// podem vir com o estado antigo por até dez minutos. Cada cliente da conta tem o seu fetch
// e, portanto, o seu token: o de uma conta nunca vai junto dos pedidos de outra.

// Respostas grandes que não trazem nada do que as ações guardam (reprodução, chat ao vivo).
const IGNORED_ENDPOINTS = ["/youtubei/v1/player", "/youtubei/v1/att/", "/youtubei/v1/live_chat/", "/youtubei/v1/log_event"];

// *onResponse* recebe cada resposta JSON útil, já lida.
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
    if (!response.ok || !url.includes("/youtubei/v1/") || IGNORED_ENDPOINTS.some((part) => url.includes(part))) {
      return response;
    }
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
    return response;
  };
}
