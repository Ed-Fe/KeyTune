"""A sessão da conta do YouTube para o que só o YouTube.js faz com ela.

Notificações, comentários escritos, inscrição e sino dos canais usam os cookies
que a conta do YouTube já salvou. Aqui fica a checagem comum: o YouTube.js
ativado e uma conta conectada.
"""

from __future__ import annotations

from ..i18n import _
from .auth import load_saved_playback_auth
from .dependencies import youtubejs_resolver_enabled


def account_connected():
    """Se há uma conta conectada e o YouTube.js para usá-la, sem levantar erro."""
    return bool(youtubejs_resolver_enabled() and load_saved_playback_auth().cookie_header)


def optional_account_session():
    """``(cookies, índice da conta)`` quando há conta e YouTube.js; ``("", 0)`` sem eles."""
    if not youtubejs_resolver_enabled():
        return "", 0
    playback_auth = load_saved_playback_auth()
    if not playback_auth.cookie_header:
        return "", 0
    return playback_auth.cookie_header, playback_auth.account_index


def require_account_session():
    """``(cookies, índice da conta)`` da sessão salva; erro com o que falta quando não há."""
    if not youtubejs_resolver_enabled():
        raise RuntimeError(_("Isto precisa do YouTube.js, ativado em Preferências > Recursos adicionais."))
    playback_auth = load_saved_playback_auth()
    if not playback_auth.cookie_header:
        raise RuntimeError(_("Conecte a conta do YouTube para fazer isto."))
    return playback_auth.cookie_header, playback_auth.account_index
