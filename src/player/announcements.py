"""Os avisos falados pelo leitor de tela que chegam sozinhos, separados por categoria.

Os avisos que respondem a uma tecla (volume, troca de aba, menus) seguem a opção
geral de anúncios. Estes são os eventos que acontecem sem a pessoa pedir: mensagens
do chat, notificações, downloads. Cada categoria liga e desliga à parte, e a
opção "falar com a janela ativa" decide se eles falam quando o foco está no KeyTune.
"""

from .i18n import _


ANNOUNCE_CHAT_MESSAGES = "chat_messages"
ANNOUNCE_CHAT_STATUS = "chat_status"
ANNOUNCE_NOTIFICATIONS = "notifications"
ANNOUNCE_DOWNLOADS = "downloads"
ANNOUNCE_TIMER = "timer"

ANNOUNCEMENT_CATEGORIES = (
    ANNOUNCE_CHAT_MESSAGES,
    ANNOUNCE_CHAT_STATUS,
    ANNOUNCE_NOTIFICATIONS,
    ANNOUNCE_DOWNLOADS,
    ANNOUNCE_TIMER,
)

DEFAULT_ANNOUNCEMENTS_INTERRUPT = False
DEFAULT_ANNOUNCEMENTS_IN_WINDOW = True


def announcement_labels():
    """``(categoria, nome)`` na ordem em que as preferências mostram."""
    return [
        (ANNOUNCE_CHAT_MESSAGES, _("Chat ao vivo: mensagens novas")),
        (ANNOUNCE_CHAT_STATUS, _("Chat ao vivo: mensagem enviada ou chat encerrado")),
        (ANNOUNCE_NOTIFICATIONS, _("Notificações novas do YouTube")),
        (ANNOUNCE_DOWNLOADS, _("Download concluído")),
        (ANNOUNCE_TIMER, _("Avisos do temporizador")),
    ]


def normalize_disabled_announcements(names):
    """As categorias desligadas, só as que existem, em ordem estável."""
    if isinstance(names, str) or not hasattr(names, "__iter__"):
        return []
    chosen = {str(name) for name in names}
    return [name for name in ANNOUNCEMENT_CATEGORIES if name in chosen]


def should_speak(settings, category, *, window_active):
    """Se o aviso de *category* deve ser falado agora, conforme as preferências."""
    if category is None:
        return True
    if category in (getattr(settings, "announcements_disabled", None) or ()):
        return False
    if window_active and not getattr(settings, "announcements_in_window", DEFAULT_ANNOUNCEMENTS_IN_WINDOW):
        return False
    return True
