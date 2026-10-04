"""Itens da lista do YouTube Music que só servem para entrar.

A aba mostra tudo numa lista só: o início traz a biblioteca, as curtidas, o
histórico, as inscrições, o que está em alta e os moods e gêneros, e cada um abre por cima,
como uma pasta. Aqui ficam esses itens; quem busca o conteúdo é a janela.
"""

from dataclasses import dataclass

from ..i18n import _
from .models import get_chart_country_groups


FOLDER_LIBRARY = "library"
FOLDER_LIKED = "liked"
FOLDER_HISTORY = "history"
FOLDER_SUBSCRIPTION_VIDEOS = "subscription_videos"
FOLDER_SUBSCRIBED_CHANNELS = "subscribed_channels"
FOLDER_CHARTS = "charts"
FOLDER_CHART_GROUP = "chart_group"
FOLDER_CHART_COUNTRY = "chart_country"
FOLDER_MOODS = "moods"
FOLDER_MOOD_SECTION = "mood_section"
FOLDER_MOOD_CATEGORY = "mood_category"
FOLDER_SECTION = "section"


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


def home_folder_items():
    return [
        YouTubeFolderItem(FOLDER_LIBRARY, _("Suas playlists e mixes"), requires_auth=True),
        YouTubeFolderItem(FOLDER_LIKED, _("Curtidas"), requires_auth=True),
        YouTubeFolderItem(FOLDER_HISTORY, _("Histórico"), requires_auth=True),
        YouTubeFolderItem(FOLDER_SUBSCRIPTION_VIDEOS, _("Vídeos das inscrições"), requires_auth=True),
        YouTubeFolderItem(FOLDER_SUBSCRIBED_CHANNELS, _("Canais inscritos"), requires_auth=True),
        YouTubeFolderItem(FOLDER_CHARTS, _("Em alta")),
        YouTubeFolderItem(FOLDER_MOODS, _("Moods e gêneros")),
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
