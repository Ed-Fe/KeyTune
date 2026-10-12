// Os clientes do YouTube.js: os anônimos (um por idioma e região) e o da conta.

import { Innertube, UniversalCache } from "youtubei.js";
import { createHash } from "node:crypto";
import { createAccountFetch } from "./account_fetch.mjs";

const MAX_CLIENTS = 3;
const clients = new Map();
let cacheDir = "";
// Só quem decifra endereços de mídia (a reprodução) precisa do script do player do YouTube.
let needsPlayer = true;

export function configureClients({ cacheDirectory, retrievePlayer = true }) {
  cacheDir = cacheDirectory;
  needsPlayer = retrievePlayer;
}

// Um cliente anônimo por idioma e região. A reprodução usa sempre o padrão
// (sem idioma nem região), para não mudar com as preferências de conteúdo. O mais
// antigo em desuso dá lugar ao novo: quem é usado de novo passa para o fim da fila.
export function clientFor(request = {}) {
  const lang = String(request.lang || "").trim() || "en";
  const location = String(request.location || "").trim().toUpperCase();
  const key = `${lang}|${location}`;
  if (clients.has(key)) {
    const client = clients.get(key);
    clients.delete(key);
    clients.set(key, client);
    return client;
  }
  if (clients.size >= MAX_CLIENTS) {
    clients.delete(clients.keys().next().value);
  }
  const options = {
    cache: new UniversalCache(true, cacheDir),
    // A reprodução gera a sessão aqui, como sempre fez; as listas pedem a sessão ao YouTube.
    generate_session_locally: !request.lang,
    retrieve_player: needsPlayer,
    lang,
  };
  if (location) {
    options.location = location;
  }
  const client = Innertube.create(options);
  client.catch(() => {
    if (clients.get(key) === client) {
      clients.delete(key);
    }
  });
  clients.set(key, client);
  return client;
}

// O cliente da conta: os mesmos cookies do YouTube Music. Fica separado dos anônimos
// porque, com os cookies, o YouTube recusa a reprodução pelos clientes que o KeyTune usa.
let accountClient = null;
// Quem quer guardar o que as respostas da conta trazem (os comentários) se registra aqui.
let responseListener = () => {};

export function onAccountResponse(listener) {
  responseListener = listener;
}

export function accountKey(request) {
  const cookie = String(request.cookie || "").trim();
  if (!cookie) {
    throw new Error("A conta do YouTube não está conectada.");
  }
  return [createHash("sha256").update(cookie).digest("hex"), accountIndex(request), request.lang, request.location].join("|");
}

// Qual das contas Google dos cookies responde, quando o navegador tinha mais de uma.
function accountIndex(request) {
  const index = Number.parseInt(request.account_index, 10);
  return Number.isInteger(index) && index > 0 ? index : 0;
}

export function accountClientFor(request) {
  const key = accountKey(request);
  if (accountClient?.key !== key) {
    const options = {
      cookie: String(request.cookie).trim(),
      account_index: accountIndex(request),
      lang: String(request.lang || "").trim() || "en",
      // A conta nunca decifra endereços de mídia: o script do player não é baixado.
      retrieve_player: false,
      // Mantém as leituras em dia com o que a conta acabou de mudar e guarda, de cada lote
      // de comentários, o que responder, editar e apagar usam.
      fetch: createAccountFetch((data) => responseListener(data)),
    };
    const location = String(request.location || "").trim().toUpperCase();
    if (location) {
      options.location = location;
    }
    const entry = { key, client: Innertube.create(options) };
    entry.client.catch(() => {
      if (accountClient === entry) {
        accountClient = null;
      }
    });
    accountClient = entry;
  }
  return accountClient.client;
}
