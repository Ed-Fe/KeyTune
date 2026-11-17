"""Os avisos falados pelo leitor de tela, separados por categoria.

Cada aviso do player pertence a uma categoria, e cada categoria liga e desliga à
parte em Preferências > Acessibilidade. O interruptor geral de anúncios continua
valendo por cima de todas. Um aviso sem categoria só obedece a esse interruptor
geral (é o caso do que os diálogos dizem sobre si mesmos).

Há dois grupos:

- avisos que respondem a uma tecla ou a um comando (reprodução, troca de faixa,
  velocidade e tom, modos, navegação, progresso, confirmações, erros). O que a
  pessoa pede para ouvir (T tempo, V volume, S status) fica sem categoria, para
  nenhuma caixa calar a resposta a uma pergunta direta;
- eventos que chegam sozinhos (mensagens do chat, notificações, download,
  temporizador). Só estes obedecem à opção "falar com a janela ativa", que decide
  se eles falam quando o foco está no KeyTune.
"""

from .i18n import _


# Respostas a teclas e comandos.
ANNOUNCE_PLAYBACK = "playback"
ANNOUNCE_TRACK_CHANGE = "track_change"
ANNOUNCE_SPEED_PITCH = "speed_pitch"
ANNOUNCE_STATE = "state"
ANNOUNCE_NAVIGATION = "navigation"
ANNOUNCE_PROGRESS = "progress"
ANNOUNCE_CONFIRMATIONS = "confirmations"
ANNOUNCE_ERRORS = "errors"

# Eventos que acontecem sem a pessoa pedir.
ANNOUNCE_CHAT_MESSAGES = "chat_messages"
ANNOUNCE_CHAT_STATUS = "chat_status"
ANNOUNCE_NOTIFICATIONS = "notifications"
ANNOUNCE_DOWNLOADS = "downloads"
ANNOUNCE_TIMER = "timer"

RESPONSE_CATEGORIES = (
    ANNOUNCE_PLAYBACK,
    ANNOUNCE_TRACK_CHANGE,
    ANNOUNCE_SPEED_PITCH,
    ANNOUNCE_STATE,
    ANNOUNCE_NAVIGATION,
    ANNOUNCE_PROGRESS,
    ANNOUNCE_CONFIRMATIONS,
    ANNOUNCE_ERRORS,
)

EVENT_CATEGORIES = (
    ANNOUNCE_CHAT_MESSAGES,
    ANNOUNCE_CHAT_STATUS,
    ANNOUNCE_NOTIFICATIONS,
    ANNOUNCE_DOWNLOADS,
    ANNOUNCE_TIMER,
)

ANNOUNCEMENT_CATEGORIES = RESPONSE_CATEGORIES + EVENT_CATEGORIES

DEFAULT_ANNOUNCEMENTS_INTERRUPT = False
DEFAULT_ANNOUNCEMENTS_IN_WINDOW = True


def announcement_labels():
    """``(categoria, nome)`` na ordem em que as preferências mostram."""
    return [
        (ANNOUNCE_PLAYBACK, _("Reprodução: pausa, retomada, início e fim do arquivo, dispositivo de áudio")),
        (ANNOUNCE_TRACK_CHANGE, _("Troca de faixa e SponsorBlock: faixa que começou e trechos pulados")),
        (ANNOUNCE_SPEED_PITCH, _("Velocidade e tom ao mudar")),
        (ANNOUNCE_STATE, _("Modos ligados ou desligados: aleatório, repetição, equalizador, AutoDJ")),
        (ANNOUNCE_NAVIGATION, _("Navegação: abas, início e fim de listas, abertura de itens")),
        (ANNOUNCE_PROGRESS, _("Progresso: carregando, pesquisando, iniciando")),
        (ANNOUNCE_CONFIRMATIONS, _("Confirmações: copiado, salvo, adicionado, removido")),
        (ANNOUNCE_ERRORS, _("Erros e ações indisponíveis")),
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
    # "Falar com a janela ativa" vale só para os eventos. Um aviso que responde a
    # uma tecla acontece, por definição, com o KeyTune ativo.
    if (
        category in EVENT_CATEGORIES
        and window_active
        and not getattr(settings, "announcements_in_window", DEFAULT_ANNOUNCEMENTS_IN_WINDOW)
    ):
        return False
    return True
