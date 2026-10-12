// Um worker de mentira sobre o protocolo real (lib/rpc.mjs), para os testes de Python.
import { serve } from "../../src/player/youtube_music/youtubejs/lib/rpc.mjs";

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

await serve({
  handlers: {
    fast: async (request) => ({ value: request.value }),
    slow: async (request) => {
      await wait(300);
      return { value: request.value };
    },
    boom: async () => {
      throw new Error("falhou de propósito");
    },
    hang: () => new Promise(() => {}),
    stray: async () => {
      Promise.reject(new Error("rejeição solta"));
      await wait(50);
      return { value: "continua de pé" };
    },
  },
  laneOf: (action) => (action === "slow" || action === "hang" || action === "fast" ? "main" : null),
  timeoutMs: 400,
  staleAfterMs: 1000,
});
