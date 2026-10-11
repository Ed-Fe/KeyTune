// Guarda *value* em *map* sob *key* como o mais recente; passando de *limit*, o mais antigo sai.
export function rememberBounded(map, key, value, limit) {
  map.delete(key);
  map.set(key, value);
  if (map.size > limit) {
    map.delete(map.keys().next().value);
  }
}
