"""Itens da aba de rádios que só servem para entrar, e o que cada um mostra.

A aba tem uma lista só: o início traz as favoritas, as recentes, o país do
usuário, as mais ouvidas e os índices por país, gênero e idioma; cada um abre
por cima, como uma pasta.
"""

from dataclasses import dataclass

from ..i18n import _, ngettext
from .models import RadioFolderItem, RadioResultPage


FOLDER_FAVORITES = "favorites"
FOLDER_RECENTS = "recents"
FOLDER_TOP = "top"
FOLDER_COUNTRIES = "countries"
FOLDER_COUNTRY = "country"
FOLDER_COUNTRY_TOP = "country_top"
FOLDER_COUNTRY_ALL = "country_all"
FOLDER_COUNTRY_STATES = "country_states"
FOLDER_STATE = "state"
FOLDER_TAGS = "tags"
FOLDER_TAG = "tag"
FOLDER_LANGUAGES = "languages"
FOLDER_LANGUAGE = "language"


@dataclass
class RadioFolderContent:
    title: str
    # Lista pronta, para a pasta que não precisa consultar o diretório.
    results: list = None
    # ``fetch_page(start, count)`` devolve um RadioResultPage; roda fora da thread da interface.
    fetch_page: object = None
    # ``FOLDER_FAVORITES`` ou ``FOLDER_RECENTS``: listas locais, refeitas quando mudam.
    kind: str = ""


def _station_count_text(count):
    try:
        normalized_count = int(count or 0)
    except (TypeError, ValueError):
        normalized_count = 0
    if normalized_count <= 0:
        return ""
    return ngettext("{count} rádio", "{count} rádios", normalized_count).format(count=normalized_count)


def home_folder_items(service, region):
    country_code, country_name = region
    items = [
        RadioFolderItem(
            FOLDER_FAVORITES,
            _("Rádios favoritas"),
            _station_count_text(len(service.favorites())),
        ),
        RadioFolderItem(FOLDER_RECENTS, _("Ouvidas recentemente")),
    ]
    if country_code:
        items.append(
            RadioFolderItem(
                FOLDER_COUNTRY,
                _("Rádios do seu país"),
                country_name,
                payload=(country_code, country_name),
            )
        )
    items.extend(
        [
            RadioFolderItem(FOLDER_TOP, _("Mais ouvidas no mundo")),
            RadioFolderItem(FOLDER_COUNTRIES, _("Países")),
            RadioFolderItem(FOLDER_TAGS, _("Gêneros")),
            RadioFolderItem(FOLDER_LANGUAGES, _("Idiomas")),
        ]
    )
    return items


def _country_folder_items(country_code, country_name):
    payload = (country_code, country_name)
    return [
        RadioFolderItem(FOLDER_COUNTRY_TOP, _("Mais ouvidas"), payload=payload),
        RadioFolderItem(FOLDER_COUNTRY_STATES, _("Por estado ou região"), payload=payload),
        RadioFolderItem(FOLDER_COUNTRY_ALL, _("Todas, em ordem alfabética"), payload=payload),
    ]


def _single_page(build_items):
    """Uma lista que o diretório devolve inteira: só existe a primeira página."""

    def fetch_page(start, _count):
        return RadioResultPage(results=build_items() if start == 0 else [])

    return fetch_page


def _group_items(groups, kind, *, payload_for):
    items = []
    for group in groups:
        name = str(group.get("name") or "").strip()
        if not name:
            continue
        items.append(
            RadioFolderItem(
                kind,
                name,
                _station_count_text(group.get("stationcount")),
                payload=payload_for(group, name),
            )
        )
    return items


def open_radio_folder(item, service):
    """O que a pasta *item* mostra; ``None`` quando ela não é conhecida."""
    kind = item.kind
    payload = item.payload

    if kind == FOLDER_FAVORITES:
        return RadioFolderContent(title=_("Rádios favoritas"), results=service.favorites(), kind=kind)
    if kind == FOLDER_RECENTS:
        return RadioFolderContent(title=_("Ouvidas recentemente"), results=service.recents(), kind=kind)

    if kind == FOLDER_TOP:
        return RadioFolderContent(
            title=_("Mais ouvidas no mundo"),
            fetch_page=lambda start, count: service.fetch_top_page(start=start, count=count),
        )

    if kind == FOLDER_COUNTRIES:
        def build_countries():
            return _group_items(
                service.list_countries(),
                FOLDER_COUNTRY,
                payload_for=lambda group, name: (str(group.get("iso_3166_1") or "").strip().upper(), name),
            )

        return RadioFolderContent(title=_("Países"), fetch_page=_single_page(build_countries))

    if kind == FOLDER_COUNTRY:
        country_code, country_name = payload
        return RadioFolderContent(
            title=_("Rádios de {country}").format(country=country_name),
            results=_country_folder_items(country_code, country_name),
        )

    if kind == FOLDER_COUNTRY_TOP:
        country_code, country_name = payload
        return RadioFolderContent(
            title=_("Mais ouvidas de {country}").format(country=country_name),
            fetch_page=lambda start, count: service.fetch_top_page(country_code=country_code, start=start, count=count),
        )

    if kind == FOLDER_COUNTRY_ALL:
        country_code, country_name = payload
        return RadioFolderContent(
            title=_("Todas as rádios de {country}").format(country=country_name),
            fetch_page=lambda start, count: service.fetch_country_page(country_code, start=start, count=count),
        )

    if kind == FOLDER_COUNTRY_STATES:
        country_code, country_name = payload

        def build_states():
            return _group_items(
                service.list_states(country_code),
                FOLDER_STATE,
                payload_for=lambda _group, name: (country_code, name),
            )

        return RadioFolderContent(
            title=_("Estados e regiões de {country}").format(country=country_name),
            fetch_page=_single_page(build_states),
        )

    if kind == FOLDER_STATE:
        country_code, state_name = payload
        return RadioFolderContent(
            title=_("Rádios de {place}").format(place=state_name),
            fetch_page=lambda start, count: service.fetch_state_page(country_code, state_name, start=start, count=count),
        )

    if kind == FOLDER_TAGS:
        def fetch_tags(start, count):
            groups = service.list_tags(start=start, count=count)
            return RadioResultPage(
                results=_group_items(groups, FOLDER_TAG, payload_for=lambda _group, name: name),
                has_more=len(groups) >= count,
            )

        return RadioFolderContent(title=_("Gêneros"), fetch_page=fetch_tags)

    if kind == FOLDER_TAG:
        return RadioFolderContent(
            title=_("Gênero {name}").format(name=payload),
            fetch_page=lambda start, count: service.fetch_tag_page(payload, start=start, count=count),
        )

    if kind == FOLDER_LANGUAGES:
        def fetch_languages(start, count):
            groups = service.list_languages(start=start, count=count)
            return RadioResultPage(
                results=_group_items(groups, FOLDER_LANGUAGE, payload_for=lambda _group, name: name),
                has_more=len(groups) >= count,
            )

        return RadioFolderContent(title=_("Idiomas"), fetch_page=fetch_languages)

    if kind == FOLDER_LANGUAGE:
        return RadioFolderContent(
            title=_("Idioma {name}").format(name=payload),
            fetch_page=lambda start, count: service.fetch_language_page(payload, start=start, count=count),
        )

    return None
