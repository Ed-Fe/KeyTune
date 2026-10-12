"""Itens da lista do YouTube Music que só servem para entrar.

A aba mostra tudo numa lista só: o início traz a biblioteca, as curtidas, o
histórico, as inscrições, as notificações, o que está em alta e os moods e gêneros, e cada
um abre por cima, como uma pasta. Aqui ficam esses itens; quem busca o conteúdo é a janela.
"""

from dataclasses import dataclass

from ..i18n import _
from .models import get_chart_country_groups


FOLDER_LIBRARY = "library"
FOLDER_LIKED = "liked"
FOLDER_HISTORY = "history"
FOLDER_WATCH_HISTORY = "watch_history"
FOLDER_SUBSCRIPTION_VIDEOS = "subscription_videos"
FOLDER_GROUP_YOUTUBE = "group_youtube"
FOLDER_GROUP_MUSIC = "group_music"
FOLDER_HOME_FEED = "home_feed"
FOLDER_MUSIC_HOME = "music_home"
FOLDER_MUSIC_HOME_ROW = "music_home_row"
FOLDER_WATCH_LATER = "watch_later"
FOLDER_LIKED_VIDEOS = "liked_videos"
FOLDER_SHORTS = "shorts"
FOLDER_SUBSCRIBED_CHANNELS = "subscribed_channels"
FOLDER_NOTIFICATIONS = "notifications"
FOLDER_CHARTS = "charts"
FOLDER_CHART_GROUP = "chart_group"
FOLDER_CHART_COUNTRY = "chart_country"
FOLDER_MOODS = "moods"
FOLDER_MOOD_SECTION = "mood_section"
FOLDER_MOOD_CATEGORY = "mood_category"
FOLDER_SECTION = "section"
FOLDER_CHANNEL_POSTS = "channel_posts"

ACTION_WRITE_COMMENT = "write_comment"
ACTION_CHANNEL_SUBSCRIPTION = "channel_subscription"
ACTION_CHANNEL_ABOUT = "channel_about"
ACTION_CHANNEL_SEARCH = "channel_search"
ACTION_SEND_CHAT_MESSAGE = "send_chat_message"


@dataclass(frozen=True)
class YouTubeFolderItem:
    """Um item que não toca: Enter ou Seta para a direita mostram o que há dentro."""

    kind: str
    title: str
    detail_text: str = ""
    # O que a pasta precisa para ser aberta: países, código do país, categorias...
    payload: object = None
    requires_auth: bool = False

    # A lista trata a pasta como um resultado qualquer que não toca nem é salvo.
    result_type = "folder"
    source = ""
    playlist_id = ""
    video_id = ""
    browse_id = ""
    playback_url = ""
    library_playlist = False
    can_browse = True
    opens_on_enter = True
    can_save = False
    can_open = False

    @property
    def stable_id(self):
        return f"folder:{self.kind}:{self.title}"

    @property
    def choice_label(self):
        if self.detail_text:
            return f"{self.title} — {self.detail_text}"
        return self.title


@dataclass(frozen=True)
class YouTubeActionItem:
    """Um item que faz algo com a lista em que está (comentar, inscrever-se): Enter executa."""

    kind: str
    title: str
    # De que a ação trata, quando não é da lista inteira: o canal, por exemplo.
    payload: object = None

    # A lista trata a ação como um resultado que não toca nem é salvo.
    result_type = "action"
    source = ""
    playlist_id = ""
    video_id = ""
    browse_id = ""
    playback_url = ""
    detail_text = ""
    library_playlist = False
    can_browse = True
    opens_on_enter = True
    can_save = False
    can_open = False

    @property
    def stable_id(self):
        return f"action:{self.kind}"

    @property
    def choice_label(self):
        return self.title


def write_comment_item():
    """A primeira linha de uma lista de comentários em que a conta pode escrever."""
    return YouTubeActionItem(ACTION_WRITE_COMMENT, _("Escrever um comentário..."))


def send_chat_message_item(restriction=""):
    """A primeira linha de um chat ao vivo: escrever ou, com *restriction*, por que a conta não pode."""
    if restriction:
        return YouTubeActionItem(
            ACTION_SEND_CHAT_MESSAGE,
            _("Você não pode escrever neste chat: {reason}").format(reason=restriction),
            payload=restriction,
        )
    return YouTubeActionItem(ACTION_SEND_CHAT_MESSAGE, _("Enviar uma mensagem..."))


def channel_action_items(channel):
    """O que a conta faz com um canal, depois das listas dele."""
    return [
        YouTubeActionItem(ACTION_CHANNEL_SEARCH, _("Buscar neste canal..."), payload=channel),
        YouTubeActionItem(ACTION_CHANNEL_SUBSCRIPTION, _("Inscrição e notificações do canal..."), payload=channel),
        YouTubeActionItem(ACTION_CHANNEL_ABOUT, _("Sobre o canal"), payload=channel),
    ]


def youtube_folder_items():
    """O que é só do YouTube comum: o que a conta vê, guarda e acompanha nele."""
    return [
        YouTubeFolderItem(FOLDER_HOME_FEED, _("Recomendados do YouTube"), requires_auth=True),
        YouTubeFolderItem(FOLDER_WATCH_LATER, _("Assistir mais tarde"), requires_auth=True),
        YouTubeFolderItem(FOLDER_LIKED_VIDEOS, _("Vídeos curtidos do YouTube"), requires_auth=True),
        YouTubeFolderItem(FOLDER_WATCH_HISTORY, _("Histórico do YouTube"), requires_auth=True),
        YouTubeFolderItem(FOLDER_SUBSCRIPTION_VIDEOS, _("Vídeos das inscrições"), requires_auth=True),
        YouTubeFolderItem(FOLDER_SUBSCRIBED_CHANNELS, _("Canais inscritos"), requires_auth=True),
        YouTubeFolderItem(FOLDER_SHORTS, _("Shorts"), requires_auth=True),
        YouTubeFolderItem(FOLDER_NOTIFICATIONS, _("Notificações"), requires_auth=True),
    ]


def music_folder_items():
    """O que é só do YouTube Music: as playlists, as curtidas e o histórico de músicas."""
    return [
        YouTubeFolderItem(FOLDER_MUSIC_HOME, _("Para você no YouTube Music")),
        YouTubeFolderItem(FOLDER_LIBRARY, _("Suas playlists e mixes"), requires_auth=True),
        YouTubeFolderItem(FOLDER_LIKED, _("Curtidas"), requires_auth=True),
        YouTubeFolderItem(FOLDER_HISTORY, _("Histórico do YouTube Music"), requires_auth=True),
    ]


def home_folder_items():
    """O início da aba: uma pasta para cada serviço e o que vale para os dois."""
    return [
        YouTubeFolderItem(FOLDER_GROUP_YOUTUBE, _("YouTube"), payload=tuple(youtube_folder_items())),
        YouTubeFolderItem(FOLDER_GROUP_MUSIC, _("YouTube Music"), payload=tuple(music_folder_items())),
        YouTubeFolderItem(FOLDER_CHARTS, _("Em alta")),
        YouTubeFolderItem(FOLDER_MOODS, _("Moods e gêneros")),
    ]


def flat_folder_items():
    """Todas as pastas do início, sem os grupos que as reúnem."""
    flat = []
    for item in home_folder_items():
        flat.extend(item.payload if item.kind in (FOLDER_GROUP_YOUTUBE, FOLDER_GROUP_MUSIC) else [item])
    return flat


def music_home_row_items(sections):
    """As fileiras do início do YouTube Music como pastas; cada uma abre as faixas e playlists dela."""
    return [
        YouTubeFolderItem(FOLDER_MUSIC_HOME_ROW, title, payload=tuple(results)) for title, results in sections
    ]


def chart_country_items(countries):
    return [YouTubeFolderItem(FOLDER_CHART_COUNTRY, label, payload=code) for code, label in countries]


def chart_folder_items():
    """Global primeiro e depois os continentes, cada um com os seus países."""
    items = []
    for group_title, countries in get_chart_country_groups():
        if not group_title:
            items.extend(chart_country_items(countries))
            continue
        items.append(YouTubeFolderItem(FOLDER_CHART_GROUP, group_title, payload=tuple(countries)))
    return items


def section_folder_items(container, sections):
    """O que dá para ver dentro de um canal ou artista: vídeos, playlists, álbuns..."""
    return [
        YouTubeFolderItem(FOLDER_SECTION, section.label, payload=(container, section.section_id))
        for section in sections
    ]


def channel_posts_item(channel):
    """A aba "Posts" de um canal, que vem do YouTube.js e não das seções do catálogo."""
    return YouTubeFolderItem(FOLDER_CHANNEL_POSTS, _("Posts"), payload=channel)


def mood_category_items(categories):
    return [
        YouTubeFolderItem(FOLDER_MOOD_CATEGORY, category.title, payload=category)
        for category in categories
    ]


def mood_folder_items(sections):
    """As seções de moods e gêneros; com uma só, mostra direto as categorias dela."""
    sections = [(title, categories) for title, categories in sections or [] if categories]
    if len(sections) == 1:
        return mood_category_items(sections[0][1])
    return [
        YouTubeFolderItem(FOLDER_MOOD_SECTION, title or _("Categorias"), payload=tuple(categories))
        for title, categories in sections
    ]
