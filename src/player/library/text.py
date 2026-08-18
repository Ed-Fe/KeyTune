"""Normalização de texto usada pelas buscas do KeyTune.

Fica em um módulo sem wxPython para que tanto o navegador de itens quanto os
serviços da biblioteca inteligente comparem texto exatamente do mesmo jeito.
"""

import unicodedata


def normalize_search_text(text):
    """Fold accents and case so buscas comparem texto de forma tolerante."""
    if not text:
        return ""

    normalized = unicodedata.normalize("NFKD", text)
    without_accents = "".join(character for character in normalized if not unicodedata.combining(character))
    return without_accents.casefold().strip()
