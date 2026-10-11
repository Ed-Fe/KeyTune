// Procura, em qualquer fundo de uma resposta do YouTube, o primeiro valor de uma chave.
export function findValue(node, key, depth = 0) {
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
