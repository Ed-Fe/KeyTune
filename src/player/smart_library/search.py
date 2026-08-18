"""Busca global sobre as mídias indexadas.

A consulta usa o mesmo `normalize_search_text` do navegador de itens, então
uma busca por "cancao" encontra "Canção". Cada termo digitado precisa aparecer
em algum lugar do texto indexado (rótulo, nome do arquivo ou pasta).

Há dois caminhos, na ordem:

1. **FTS5**, quando o SQLite foi compilado com ele. Cada termo vira uma
   consulta por prefixo (`estrad*`), respondida por índice mesmo com dezenas de
   milhares de arquivos, e os resultados saem ordenados por relevância.
2. **Varredura com LIKE**, usada quando o FTS5 não existe ou quando ele não
   encontrou nada. É o caminho que acha trechos no meio da palavra ("cao" em
   "canção"), que o índice por prefixo não cobre. Só roda quando o caminho
   rápido falhou, então a busca nunca fica mais lenta do que era antes.
"""

from ..library.text import normalize_search_text
from .models import (
    SEARCH_SCOPE_ALL,
    SEARCH_SCOPE_FAVORITES,
    SEARCH_SCOPE_HISTORY,
    SEARCH_SCOPE_RATED,
    MediaRecord,
)


DEFAULT_SEARCH_LIMIT = 500


_MEDIA_COLUMNS = (
    "id, media_path, label, folder_path, is_remote, duration_ms, favorite, rating, "
    "play_count, last_played_epoch, resume_position_ms, resume_updated_epoch"
)

# Caracteres com significado próprio na sintaxe de consulta do FTS5.
_FTS_SPECIAL_CHARACTERS = '"*():^-,'


def search_terms(query):
    """Quebra o texto procurado em termos normalizados, sem duplicatas."""
    normalized_query = normalize_search_text(query)
    if not normalized_query:
        return []

    terms = []
    for term in normalized_query.split():
        if term and term not in terms:
            terms.append(term)
    return terms


def escape_like(term):
    """Neutraliza os curingas do LIKE para que `%` e `_` sejam texto comum."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def build_full_text_query(terms):
    """Monta a expressão MATCH: todos os termos, cada um por prefixo.

    Os termos vão entre aspas para que pontuação digitada pelo usuário não seja
    lida como operador do FTS5 (`-`, `*`, `:`, `^` e afins).
    """
    prepared = []
    for term in terms:
        cleaned = "".join(character for character in term if character not in _FTS_SPECIAL_CHARACTERS)
        cleaned = cleaned.strip()
        if cleaned:
            prepared.append(f'"{cleaned}"*')

    return " AND ".join(prepared)


def _scope_condition(scope):
    if scope == SEARCH_SCOPE_FAVORITES:
        return "favorite = 1"
    if scope == SEARCH_SCOPE_RATED:
        return "rating > 0"
    if scope == SEARCH_SCOPE_HISTORY:
        return "last_played_epoch > 0"
    return ""


def _order_by(scope):
    if scope == SEARCH_SCOPE_HISTORY:
        return "last_played_epoch DESC, label COLLATE NOCASE"
    return "favorite DESC, rating DESC, last_played_epoch DESC, label COLLATE NOCASE"


def _normalize_limit(limit):
    try:
        return max(1, int(limit))
    except (TypeError, ValueError):
        return DEFAULT_SEARCH_LIMIT


class MediaSearchStore:
    def __init__(self, database):
        self._database = database

    def search(self, query, scope=SEARCH_SCOPE_ALL, limit=DEFAULT_SEARCH_LIMIT):
        terms = search_terms(query)
        scope_condition = _scope_condition(scope)

        if not terms and not scope_condition:
            # Sem texto e sem filtro não há busca a fazer: uma listagem da
            # biblioteca inteira seria só ruído para quem usa leitor de tela.
            return []

        normalized_limit = _normalize_limit(limit)

        if not terms:
            return self._search_by_scope_only(scope_condition, scope, normalized_limit)

        if getattr(self._database, "supports_full_text_search", False):
            results = self._search_with_full_text(terms, scope_condition, scope, normalized_limit)
            if results:
                return results

        return self._search_with_scan(terms, scope_condition, scope, normalized_limit)

    def _search_by_scope_only(self, scope_condition, scope, limit):
        rows = self._database.query(
            f"SELECT {_MEDIA_COLUMNS} FROM media WHERE {scope_condition} "
            f"ORDER BY {_order_by(scope)} LIMIT ?",
            (limit,),
        )
        return [MediaRecord.from_row(row) for row in rows]

    def _search_with_full_text(self, terms, scope_condition, scope, limit):
        match_query = build_full_text_query(terms)
        if not match_query:
            return []

        conditions = ["media.id IN (SELECT rowid FROM media_fts WHERE media_fts MATCH ?)"]
        parameters = [match_query]
        if scope_condition:
            conditions.append(scope_condition)

        rows = self._database.query(
            f"SELECT {_MEDIA_COLUMNS} FROM media WHERE {' AND '.join(conditions)} "
            f"ORDER BY {_order_by(scope)} LIMIT ?",
            tuple(parameters) + (limit,),
        )
        return [MediaRecord.from_row(row) for row in rows]

    def _search_with_scan(self, terms, scope_condition, scope, limit):
        conditions = []
        parameters = []
        for term in terms:
            conditions.append("search_text LIKE ? ESCAPE '\\'")
            parameters.append(f"%{escape_like(term)}%")

        if scope_condition:
            conditions.append(scope_condition)

        rows = self._database.query(
            f"SELECT {_MEDIA_COLUMNS} FROM media WHERE {' AND '.join(conditions)} "
            f"ORDER BY {_order_by(scope)} LIMIT ?",
            tuple(parameters) + (limit,),
        )
        return [MediaRecord.from_row(row) for row in rows]

    def favorites(self, limit=DEFAULT_SEARCH_LIMIT):
        rows = self._database.query(
            f"SELECT {_MEDIA_COLUMNS} FROM media WHERE favorite = 1 "
            "ORDER BY rating DESC, last_played_epoch DESC, label COLLATE NOCASE LIMIT ?",
            (_normalize_limit(limit),),
        )
        return [MediaRecord.from_row(row) for row in rows]

    def top_rated(self, minimum_rating=1, limit=DEFAULT_SEARCH_LIMIT):
        rows = self._database.query(
            f"SELECT {_MEDIA_COLUMNS} FROM media WHERE rating >= ? "
            "ORDER BY rating DESC, last_played_epoch DESC, label COLLATE NOCASE LIMIT ?",
            (max(1, int(minimum_rating or 1)), _normalize_limit(limit)),
        )
        return [MediaRecord.from_row(row) for row in rows]
