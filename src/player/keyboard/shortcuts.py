"""Catálogo de ações do teclado e as regras para personalizá-las.

Não depende do wx: guarda o texto canônico dos atalhos ("Ctrl+Shift+P"), as
ações que o usuário pode remapear, os atalhos padrão e a resolução das
personalizações gravadas nas preferências. A janela (``frames/keyboard.py``) e
os atalhos globais (``frames/global_hotkeys.py``) traduzem isso para o wx.

O texto canônico é o mesmo que o wx aceita depois do ``\\t`` de um item de menu,
então serve tanto para gravar quanto para montar o acelerador.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..i18n import _

# Ordem fixa dos modificadores no texto canônico.
MODIFIERS = ("Ctrl", "Alt", "Shift", "Win")

_MODIFIER_ALIASES = {
    "ctrl": "Ctrl",
    "control": "Ctrl",
    "alt": "Alt",
    "shift": "Shift",
    "win": "Win",
    "windows": "Win",
    "super": "Win",
}

# Nomes de teclas especiais: apelido em minúsculas -> nome canônico.
_NAMED_KEYS = {
    "space": "Space",
    "espaço": "Space",
    "left": "Left",
    "right": "Right",
    "up": "Up",
    "down": "Down",
    "home": "Home",
    "end": "End",
    "pageup": "PageUp",
    "pgup": "PageUp",
    "pagedown": "PageDown",
    "pgdn": "PageDown",
    "insert": "Insert",
    "ins": "Insert",
    "delete": "Delete",
    "del": "Delete",
    "back": "Back",
    "backspace": "Back",
    "enter": "Enter",
    "return": "Enter",
    "tab": "Tab",
    "escape": "Escape",
    "esc": "Escape",
    "pause": "Pause",
}
_NAMED_KEYS.update({f"f{number}": f"F{number}" for number in range(1, 25)})

# Teclas de pontuação aceitas como estão (as do teclado americano que o wx reconhece).
_PUNCTUATION_KEYS = set(",.;/\\[]'`-=")

FUNCTION_KEYS = frozenset(f"F{number}" for number in range(1, 25))

# Atalhos que nenhuma ação pode receber: navegação e edição de texto.
RESERVED_SHORTCUTS = frozenset(
    {
        "Tab",
        "Shift+Tab",
        "Ctrl+Tab",
        "Ctrl+Shift+Tab",
        "Escape",
        "Enter",
        "Shift+F10",
        "Ctrl+A",
        "Ctrl+C",
        "Ctrl+V",
        "Ctrl+X",
        "Ctrl+Z",
        "Ctrl+Shift+V",
    }
)

# Combinações do Windows: trocar ou fechar a janela, menu Iniciar, Gerenciador de
# Tarefas e a barra de menus.
SYSTEM_SHORTCUTS = frozenset(
    {
        "Alt+F4",
        "Alt+Tab",
        "Alt+Shift+Tab",
        "Alt+Escape",
        "Ctrl+Escape",
        "Ctrl+Shift+Escape",
        "Ctrl+Alt+Delete",
        "F10",
    }
)

# Sem modificador: só teclas que o usuário não usa para digitar o nome de algo.
SCOPE_LOCAL = "local"
SCOPE_GLOBAL = "global"


def _split_parts(text):
    # "Ctrl++" e "Ctrl+-" usam o próprio sinal como tecla.
    parts = []
    current = ""
    for char in text:
        if char == "+" and current:
            parts.append(current)
            current = ""
        else:
            current += char
    if current:
        parts.append(current)
    return [part.strip() for part in parts if part.strip()]


def _normalize_key_name(name):
    lowered = name.lower()
    if lowered in _NAMED_KEYS:
        return _NAMED_KEYS[lowered]
    if len(name) == 1:
        if name.isalnum() and name.isascii():
            return name.upper()
        if name in _PUNCTUATION_KEYS or name == "+":
            return name
    return None


def normalize_shortcut(text):
    """Texto canônico do atalho ("ctrl+shift+p" -> "Ctrl+Shift+P"); ``""`` se for inválido.

    Um atalho tem zero ou mais modificadores e exatamente uma tecla.
    """
    if not isinstance(text, str):
        return ""
    parts = _split_parts(text.strip())
    if not parts:
        return ""
    modifiers = set()
    key = None
    for part in parts:
        modifier = _MODIFIER_ALIASES.get(part.lower())
        if modifier is not None:
            modifiers.add(modifier)
            continue
        if key is not None:
            return ""
        key = _normalize_key_name(part)
        if key is None:
            return ""
    if key is None:
        return ""
    ordered = [modifier for modifier in MODIFIERS if modifier in modifiers]
    return "+".join([*ordered, key])


def shortcut_parts(shortcut):
    """``(modificadores, tecla)`` de um atalho canônico."""
    parts = _split_parts(shortcut)
    if not parts:
        return (), ""
    return tuple(parts[:-1]), parts[-1]


def is_bare_shortcut(shortcut):
    """Atalho sem Ctrl, Alt nem Win e que não é tecla de função.

    Esses atalhos ("Espaço", "Shift+Seta direita", "T") só valem com o foco na
    superfície do player: em qualquer outro controle a tecla é dele.
    """
    modifiers, key = shortcut_parts(shortcut)
    if key in FUNCTION_KEYS:
        return False
    return not any(modifier in ("Ctrl", "Alt", "Win") for modifier in modifiers)


def shortcut_problem(shortcut, scope):
    """Por que o atalho não pode ser usado nesse escopo; ``""`` se puder."""
    normalized = normalize_shortcut(shortcut)
    if not normalized:
        return _("Esta combinação de teclas não é reconhecida.")
    if normalized in RESERVED_SHORTCUTS:
        return _("{shortcut} é reservado para navegar e editar texto.").format(
            shortcut=format_shortcut(normalized)
        )
    if normalized in SYSTEM_SHORTCUTS:
        return _("{shortcut} é usado pelo Windows.").format(shortcut=format_shortcut(normalized))
    modifiers, key = shortcut_parts(normalized)
    if scope == SCOPE_GLOBAL:
        if not any(modifier in ("Ctrl", "Alt", "Win") for modifier in modifiers) and key not in FUNCTION_KEYS:
            return _("Um atalho global precisa de Ctrl, Alt ou Windows, senão a tecla deixaria de funcionar nos outros programas.")
    elif "Win" in modifiers:
        return _("A tecla Windows só pode ser usada em atalhos globais.")
    return ""


_KEY_DISPLAY_NAMES = None


def _key_display_names():
    global _KEY_DISPLAY_NAMES
    if _KEY_DISPLAY_NAMES is None:
        _KEY_DISPLAY_NAMES = {
            "Space": _("Espaço"),
            "Left": _("Seta esquerda"),
            "Right": _("Seta direita"),
            "Up": _("Seta acima"),
            "Down": _("Seta abaixo"),
            "PageUp": "Page Up",
            "PageDown": "Page Down",
            "Back": "Backspace",
            "Escape": "Esc",
        }
    return _KEY_DISPLAY_NAMES


def format_shortcut(shortcut):
    """Atalho como é lido e mostrado ao usuário; ``""`` para nenhum."""
    normalized = normalize_shortcut(shortcut)
    if not normalized:
        return ""
    modifiers, key = shortcut_parts(normalized)
    return "+".join([*modifiers, _key_display_names().get(key, key)])


@dataclass(frozen=True)
class KeyAction:
    """Uma ação que pode receber um atalho.

    ``handler`` é o método do frame: os ``on_*`` recebem ``None`` como evento,
    os demais são chamados sem argumentos. ``menu`` é o
    atributo do id do item de menu que mostra o atalho; ``accelerator`` indica
    que a ação também está na tabela de aceleradores do frame.
    """

    action_id: str
    category: str
    label: str
    default: str
    handler: str
    menu: str = ""
    accelerator: bool = False


def _categories():
    return {
        "playback": _("Reprodução"),
        "navigation": _("Navegação na mídia"),
        "announce": _("Anúncios"),
        "files": _("Arquivos e playlists"),
        "view": _("Exibir e ferramentas"),
        "library": _("Biblioteca"),
        "window": _("Janela"),
    }


def category_label(category):
    return _categories().get(category, category)


def _local_actions():
    A = KeyAction
    return (
        # Reprodução
        A("play_pause", "playback", _("Reproduzir ou pausar"), "Space", "on_play_pause", "menu_play_pause_id"),
        A("stop", "playback", _("Parar"), "Ctrl+.", "on_stop", "menu_stop_id"),
        A("previous_track", "playback", _("Faixa anterior"), "Ctrl+PageUp", "on_previous_track", "menu_previous_track_id"),
        A("next_track", "playback", _("Próxima faixa"), "Ctrl+PageDown", "on_next_track", "menu_next_track_id"),
        A("previous_track_alt", "playback", _("Faixa anterior (alternativo)"), "Alt+Left", "on_previous_track"),
        A("next_track_alt", "playback", _("Próxima faixa (alternativo)"), "Alt+Right", "on_next_track"),
        A("volume_up", "playback", _("Aumentar volume"), "Up", "_shortcut_volume_up"),
        A("volume_down", "playback", _("Diminuir volume"), "Down", "_shortcut_volume_down"),
        A("toggle_shuffle", "playback", _("Embaralhar"), "E", "on_toggle_shuffle", "menu_toggle_shuffle_id"),
        A("cycle_repeat", "playback", _("Modo de repetição"), "R", "on_cycle_repeat_mode", "menu_cycle_repeat_id"),
        A(
            "toggle_related_autoplay",
            "playback",
            _("Conteúdo relacionado do YouTube Music"),
            "A",
            "on_toggle_related_autoplay",
            "menu_toggle_related_autoplay_id",
        ),
        A("increase_rate", "playback", _("Aumentar velocidade"), "]", "on_increase_playback_rate", "menu_increase_playback_rate_id"),
        A("decrease_rate", "playback", _("Diminuir velocidade"), "[", "on_decrease_playback_rate", "menu_decrease_playback_rate_id"),
        A("reset_rate", "playback", _("Restaurar velocidade normal"), "\\", "on_reset_playback_rate", "menu_reset_playback_rate_id"),
        A("increase_pitch", "playback", _("Aumentar tom"), "Shift+]", "on_increase_pitch", "menu_increase_pitch_id"),
        A("decrease_pitch", "playback", _("Diminuir tom"), "Shift+[", "on_decrease_pitch", "menu_decrease_pitch_id"),
        A("reset_pitch", "playback", _("Restaurar tom original"), "Shift+\\", "on_reset_pitch", "menu_reset_pitch_id"),
        A("start_radio", "playback", _("Iniciar rádio desta faixa"), "Ctrl+R", "on_start_radio_from_current", "menu_start_radio_id"),
        A(
            "enqueue_item",
            "playback",
            _("Adicionar à fila de reprodução"),
            "Ctrl+Shift+F",
            "on_enqueue_item",
            "menu_enqueue_item_id",
            accelerator=True,
        ),
        A(
            "manage_queue",
            "playback",
            _("Gerenciar fila de reprodução"),
            "Ctrl+Shift+Q",
            "on_manage_queue",
            "menu_manage_queue_id",
            accelerator=True,
        ),
        A(
            "cycle_audio_output",
            "playback",
            _("Selecionar dispositivo de áudio"),
            "Alt+D",
            "on_cycle_audio_output_device",
            "menu_cycle_audio_output_device_id",
            accelerator=True,
        ),
        A("sleep_timer", "playback", _("Configurar temporizador"), "Ctrl+Shift+D", "_open_sleep_timer_dialog", "menu_sleep_timer_dialog_id"),
        A("toggle_live_video", "playback", _("Mostrar ou ocultar a imagem da transmissão ao vivo"), "Ctrl+Alt+V", "_toggle_live_video"),
        A("like_media", "playback", _("Gostei da mídia atual (YouTube Music)"), "Ctrl+L", "_shortcut_like_media"),
        A("dislike_media", "playback", _("Não gostei da mídia atual (YouTube Music)"), "Ctrl+Shift+L", "_shortcut_dislike_media"),
        # Navegação na mídia
        A("seek_backward", "navigation", _("Voltar"), "Left", "_shortcut_seek_backward"),
        A("seek_forward", "navigation", _("Avançar"), "Right", "_shortcut_seek_forward"),
        A("seek_backward_large", "navigation", _("Voltar mais"), "Shift+Left", "_shortcut_seek_backward_large"),
        A("seek_forward_large", "navigation", _("Avançar mais"), "Shift+Right", "_shortcut_seek_forward_large"),
        A("seek_start", "navigation", _("Ir para o início da mídia"), "Home", "_seek_to_start"),
        A("seek_end", "navigation", _("Ir para o fim da mídia"), "End", "_seek_to_end"),
        # Anúncios
        A("announce_time", "announce", _("Anunciar tempo"), "T", "on_announce_time", "menu_announce_time_id"),
        A("announce_volume", "announce", _("Anunciar volume"), "V", "on_announce_volume", "menu_announce_volume_id"),
        A("announce_status", "announce", _("Anunciar status"), "S", "on_announce_status", "menu_announce_status_id"),
        # Arquivos e playlists
        A("open_file", "files", _("Abrir"), "Ctrl+O", "on_open", "menu_open_file_id", accelerator=True),
        A(
            "open_without_playing",
            "files",
            _("Abrir sem tocar"),
            "Ctrl+Shift+O",
            "on_add_files_without_playing",
            "menu_add_files_without_playing_id",
            accelerator=True,
        ),
        A("open_folder", "files", _("Explorador de pastas"), "Ctrl+E", "on_open_folder", "menu_open_folder_id", accelerator=True),
        A("new_playlist", "files", _("Nova playlist"), "Ctrl+T", "on_new_playlist", "menu_new_playlist_id"),
        A("save_playlist", "files", _("Salvar playlist"), "Ctrl+Shift+S", "on_save_playlist", "menu_save_playlist_id"),
        A("close_media", "files", _("Fechar mídia"), "Ctrl+Shift+W", "_close_current_media", "menu_close_media_id"),
        A("close_tab", "files", _("Fechar aba ou playlist"), "Ctrl+W", "on_close_current_tab", "menu_close_tab_id"),
        A("move_item_up", "files", _("Mover o item atual para cima na playlist"), "Alt+Up", "_shortcut_move_item_up"),
        A("move_item_down", "files", _("Mover o item atual para baixo na playlist"), "Alt+Down", "_shortcut_move_item_down"),
        A("first_item", "files", _("Ir ao primeiro item da playlist"), "Alt+Home", "_shortcut_first_item"),
        A("last_item", "files", _("Ir ao último item da playlist"), "Alt+End", "_shortcut_last_item"),
        A("copy_playing_path", "files", _("Copiar o caminho da mídia em execução"), "Ctrl+Shift+C", "on_copy_playing_media_path"),
        A("convert", "files", _("Converter seleção ou mídia atual"), "Ctrl+Shift+K", "on_convert_shortcut", "menu_convert_shortcut_id", accelerator=True),
        A("download", "files", _("Baixar seleção ou mídia atual"), "Ctrl+Shift+B", "on_download_shortcut", "menu_download_shortcut_id", accelerator=True),
        # Exibir e ferramentas
        A("toggle_item_navigation", "view", _("Alternar foco entre itens e player"), "Ctrl+B", "on_toggle_playlist_browser"),
        A("find_item", "view", _("Localizar item"), "Ctrl+F", "_open_item_search_dialog", "menu_find_item_id"),
        A("find_next", "view", _("Próximo resultado"), "F3", "_shortcut_find_next", "menu_find_next_item_id"),
        A("find_previous", "view", _("Resultado anterior"), "Shift+F3", "_shortcut_find_previous", "menu_find_previous_item_id"),
        A("toggle_lyrics", "view", _("Mostrar ou ocultar a letra"), "Ctrl+Alt+L", "toggle_lyrics_panel"),
        A("open_equalizer", "view", _("Equalizador"), "Ctrl+Shift+E", "on_open_equalizer", "menu_open_equalizer_id"),
        A("open_youtube_music", "view", _("KeyTube por aba"), "Ctrl+Shift+Y", "on_open_youtube_music", "menu_open_youtube_music_id"),
        A("open_radio", "view", _("Rádios online por aba"), "Ctrl+Shift+N", "on_open_radio", "menu_open_radio_id"),
        A(
            "add_to_youtube_playlist",
            "view",
            _("Adicionar à playlist do YouTube Music"),
            "Ctrl+Shift+A",
            "on_add_to_youtube_playlist",
            "menu_add_to_youtube_playlist_id",
        ),
        A("media_comments", "view", _("Ver comentários da mídia atual"), "Ctrl+Shift+M", "on_show_media_comments", "menu_show_media_comments_id"),
        A("media_details", "view", _("Ver detalhes da mídia atual"), "Ctrl+Shift+I", "on_show_media_details", "menu_show_media_details_id"),
        A("preferences", "view", _("Preferências"), "Ctrl+,", "on_open_preferences", "menu_preferences_id"),
        A("customize_keyboard", "view", _("Personalizar teclado"), "", "_open_keyboard_customization", "menu_customize_keyboard_id"),
        A("keyboard_help", "view", _("Ajuda rápida de atalhos"), "F1", "on_show_keyboard_help", "menu_keyboard_help_id"),
        # Biblioteca
        A("search_library", "library", _("Buscar na biblioteca"), "Ctrl+G", "on_search_library", "menu_search_library_id"),
        A("continue_listening", "library", _("Continuar ouvindo"), "Ctrl+Shift+R", "on_continue_listening", "menu_continue_listening_id"),
        A("toggle_favorite", "library", _("Favoritar ou desfavoritar seleção"), "Ctrl+D", "on_toggle_favorite", "menu_toggle_favorite_id"),
        A("playback_history", "library", _("Histórico de reprodução"), "Ctrl+Shift+H", "on_open_playback_history", "menu_playback_history_id"),
        *(
            A(
                f"rate_{stars}",
                "library",
                _("Sem avaliação") if stars == 0 else _("Avaliar com {stars} estrela(s)").format(stars=stars),
                f"Ctrl+{stars}",
                f"_shortcut_rate_{stars}",
            )
            for stars in range(6)
        ),
        # Janela
        A("hide_to_tray", "window", _("Ocultar na bandeja do sistema"), "", "_hide_to_tray", "menu_hide_to_tray_id"),
    )


def _global_actions():
    A = KeyAction
    return (
        A("play_pause", "playback", _("Reproduzir ou pausar"), "Ctrl+Alt+Shift+P", "on_play_pause"),
        A("next_track", "playback", _("Próxima faixa"), "Ctrl+Alt+Shift+Right", "on_next_track"),
        A("previous_track", "playback", _("Faixa anterior"), "Ctrl+Alt+Shift+Left", "on_previous_track"),
        A("stop", "playback", _("Parar"), "Ctrl+Alt+Shift+X", "on_stop"),
        A("volume_up", "playback", _("Aumentar volume"), "Ctrl+Alt+Shift+Up", "_shortcut_volume_up_announced"),
        A("volume_down", "playback", _("Diminuir volume"), "Ctrl+Alt+Shift+Down", "_shortcut_volume_down_announced"),
        A("seek_forward", "navigation", _("Avançar"), "", "_shortcut_seek_forward"),
        A("seek_backward", "navigation", _("Voltar"), "", "_shortcut_seek_backward"),
        A("toggle_shuffle", "playback", _("Embaralhar"), "", "on_toggle_shuffle"),
        A("cycle_repeat", "playback", _("Modo de repetição"), "", "on_cycle_repeat_mode"),
        A("announce_status", "announce", _("Anunciar status"), "Ctrl+Alt+Shift+I", "on_announce_status"),
        A("announce_time", "announce", _("Anunciar tempo"), "Ctrl+Alt+Shift+T", "on_announce_time"),
        A("announce_volume", "announce", _("Anunciar volume"), "", "on_announce_volume"),
        A("toggle_tray", "window", _("Mostrar ou ocultar o KeyTune na bandeja do sistema"), "Ctrl+Alt+Shift+K", "_toggle_tray_visibility"),
        A("minimize_restore", "window", _("Minimizar ou restaurar a janela"), "Ctrl+Alt+Shift+M", "_toggle_minimized"),
        A("bring_to_front", "window", _("Trazer o KeyTune para a frente"), "", "_bring_to_front"),
    )


_ACTION_CACHE = {}


def actions(scope=SCOPE_LOCAL):
    """Ações do escopo, na ordem em que aparecem na tela de personalização."""
    if scope not in _ACTION_CACHE:
        _ACTION_CACHE[scope] = _global_actions() if scope == SCOPE_GLOBAL else _local_actions()
    return _ACTION_CACHE[scope]


def action_by_id(action_id, scope=SCOPE_LOCAL):
    for action in actions(scope):
        if action.action_id == action_id:
            return action
    return None


def normalize_overrides(value, scope=SCOPE_LOCAL):
    """Personalizações válidas lidas das preferências: ``{id da ação: atalho}``.

    ``""`` significa "sem atalho". Ids desconhecidos, atalhos inválidos e
    personalizações iguais ao padrão são descartados.
    """
    if not isinstance(value, dict):
        return {}
    known = {action.action_id: action for action in actions(scope)}
    result = {}
    for action_id, raw_shortcut in value.items():
        action = known.get(action_id)
        if action is None or not isinstance(raw_shortcut, str):
            continue
        shortcut = normalize_shortcut(raw_shortcut) if raw_shortcut.strip() else ""
        if raw_shortcut.strip() and (not shortcut or shortcut_problem(shortcut, scope)):
            continue
        if shortcut == normalize_shortcut(action.default):
            continue
        result[action_id] = shortcut
    return result


def effective_bindings(overrides, scope=SCOPE_LOCAL):
    """``{id da ação: atalho}`` em vigor, com ``""`` para as ações sem atalho."""
    overrides = overrides or {}
    return {
        action.action_id: overrides.get(action.action_id, normalize_shortcut(action.default))
        for action in actions(scope)
    }


def find_conflicts(bindings, shortcut, *, exclude=None):
    """Ids das ações que já usam *shortcut*, menos *exclude*."""
    normalized = normalize_shortcut(shortcut)
    if not normalized:
        return []
    return [
        action_id
        for action_id, bound in bindings.items()
        if bound == normalized and action_id != exclude
    ]


def overrides_from_bindings(bindings, scope=SCOPE_LOCAL):
    """O que precisa ser gravado: só o que difere do padrão."""
    result = {}
    for action in actions(scope):
        shortcut = bindings.get(action.action_id, "")
        if shortcut != normalize_shortcut(action.default):
            result[action.action_id] = shortcut
    return result


class Keymap:
    """Consulta rápida dos atalhos personalizados da janela principal.

    Só as ações personalizadas passam por aqui; as demais seguem tratadas pelos
    atalhos fixos do player. ``freed`` guarda os atalhos padrão que deixaram de
    pertencer à ação original, para que não disparem mais nada.
    """

    def __init__(self, overrides=None):
        self.overrides = dict(overrides or {})
        self.bindings = effective_bindings(self.overrides)
        self.custom = {}
        for action_id, shortcut in self.overrides.items():
            if shortcut:
                self.custom[shortcut] = action_by_id(action_id)
        self.freed = set()
        # Padrões que saíram da ação original, mesmo os que outra ação pegou.
        self._displaced = []
        for action_id in self.overrides:
            default = normalize_shortcut(action_by_id(action_id).default)
            if not default:
                continue
            modifiers, key = shortcut_parts(default)
            self._displaced.append((frozenset(modifiers), key))
            if default not in self.custom:
                self.freed.add(default)
        self._bound = {shortcut for shortcut in self.bindings.values() if shortcut}

    @property
    def has_overrides(self):
        return bool(self.overrides)

    def resolve(self, shortcut):
        """``(ação, consumida)``: a ação personalizada do atalho, ou se ele deve ser ignorado."""
        action = self.custom.get(shortcut)
        if action is not None:
            return action, True
        return None, shortcut in self.freed

    def is_displaced_variant(self, shortcut):
        """Se *shortcut* é um padrão que mudou de dono com modificadores a mais.

        O tratamento fixo do player aceita variações que ninguém documentou
        (``Ctrl+Seta esquerda`` volta como a ``Seta esquerda``). Depois que a
        ação original perde o atalho, a variação não pode continuar a
        dispará-la. Um atalho que alguma ação usa de fato nunca é variação.
        """
        if not shortcut or shortcut in self._bound:
            return False
        if shortcut in RESERVED_SHORTCUTS or shortcut in SYSTEM_SHORTCUTS:
            return False
        modifiers, key = shortcut_parts(shortcut)
        modifiers = frozenset(modifiers)
        return any(
            displaced_key == key and displaced_modifiers < modifiers
            for displaced_modifiers, displaced_key in self._displaced
        )

    def shortcut_for(self, action_id):
        return self.bindings.get(action_id, "")
