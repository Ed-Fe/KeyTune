// O worker de reprodução: resolve o vídeo e serve a faixa ao MPV pelo proxy local.
// Só isto roda aqui. Comentários, conta, chat e o resto vivem em outro processo
// (actions.mjs), para que nada que demore ou falhe lá interrompa a música que toca.

import { Platform } from "youtubei.js";
import { clientFor, configureClients } from "./lib/clients.mjs";
import { serve } from "./lib/rpc.mjs";
import { resolve } from "./playback/resolve_stream.mjs";

// Os formatos de áudio dos clientes YTMUSIC e MWEB vêm com a assinatura cifrada; o
// YouTube.js pede ao app um avaliador de JavaScript para decifrá-la.
Platform.shim.eval = async (data) => new Function(data.output)();

configureClients({ cacheDirectory: process.argv[2] });
// A sessão já fica pronta quando a primeira faixa for pedida.
clientFor();

await serve({ handlers: { resolve }, defaultAction: "resolve" });
