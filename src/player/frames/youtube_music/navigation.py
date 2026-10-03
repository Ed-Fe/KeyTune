"""Navegação da lista da aba do YouTube Music.

A aba tem uma lista só, que é uma pilha de visões: o início fica embaixo e a
busca, a biblioteca e cada canal, artista, álbum ou playlist aberto entram por
cima. Um canal ou artista abre primeiro a lista do que há nele (vídeos,
playlists, álbuns...). Voltar desempilha e chegar ao fim da lista traz a
página seguinte.
"""

from dataclasses import dataclass, field

import wx

from player.youtube_music.folders import (
    FOLDER_LIBRARY,
    FOLDER_SECTION,
    home_folder_items,
    section_folder_items,
)
from player.youtube_music.models import (
    YOUTUBE_ARTIST_SECTIONS,
    YOUTUBE_CHANNEL_SECTIONS,
    YOUTUBE_RESULTS_PAGE_SIZE,
)

from ...i18n import _, ngettext


VIEW_KIND_HOME = "home"
VIEW_KIND_LIBRARY = "library"


@dataclass
class YouTubeResultsView:
    title: str
    # ``fetch_page(start, count)`` devolve um YouTubeResultPage; roda fora da thread da interface.
    fetch_page: object = None
    results: list = field(default_factory=list)
    has_more: bool = False
    next_start: int = 0
    selected_id: str = ""
    # Resumo pronto, para a lista que não se descreve pela contagem (o início).
    summary: str = ""
    # ``VIEW_KIND_HOME`` ou ``VIEW_KIND_LIBRARY``; vazio nas demais.
    kind: str = ""


def results_view_summary(view, *, with_hint=True):
    if view.summary:
        return view.summary

    result_count = len(view.results)
    if result_count == 0:
        return _("{title}: nenhum item.").format(title=view.title)

    summary = ngettext(
        "{title}: {count} item.",
        "{title}: {count} itens.",
        result_count,
    ).format(title=view.title, count=result_count)
    if with_hint and view.has_more:
        summary = summary + " " + _("Desça até o fim da lista para carregar mais.")
    return summary


def container_sections(result):
    result_type = getattr(result, "result_type", "")
    if result_type == "channel":
        return YOUTUBE_CHANNEL_SECTIONS
    if result_type == "artist":
        return YOUTUBE_ARTIST_SECTIONS
    return ()


def container_title(result, section_id=""):
    name = str(getattr(result, "title", "") or "").strip()
    title = {
        "channel": _("Canal {name}"),
        "artist": _("Artista {name}"),
        "album": _("Álbum {name}"),
        "playlist": _("Playlist {name}"),
    }.get(getattr(result, "result_type", ""), "{name}").format(name=name)
    for section in container_sections(result):
        if section.section_id == section_id:
            return f"{title} — {section.label}"
    return title


class ResultsNavigationMixin:
    def _youtube_music_home_view(self):
        return YouTubeResultsView(
            title=_("Início"),
            kind=VIEW_KIND_HOME,
            results=home_folder_items(),
            summary=_("Início: escolha uma lista, faça uma busca ou cole um link."),
        )

    def _youtube_music_results_views(self):
        views = getattr(self, "_youtube_music_results_view_stack", None)
        if not views:
            views = [self._youtube_music_home_view()]
            self._youtube_music_results_view_stack = views
        return views

    def _youtube_music_current_results_view(self):
        return self._youtube_music_results_views()[-1]

    def _reset_youtube_music_results_views(self, view):
        """Deixa *view* logo acima do início, de onde Backspace volta para ele."""
        views = self._youtube_music_results_views()
        home = views[0] if views[0].kind == VIEW_KIND_HOME else self._youtube_music_home_view()
        views[:] = [home, view]

    def _build_youtube_music_library_view(self):
        view = YouTubeResultsView(title=_("Suas playlists e mixes"), kind=VIEW_KIND_LIBRARY)
        self._fill_youtube_music_library_view(view)
        return view

    def _fill_youtube_music_library_view(self, view):
        view.results = [playlist.as_result() for playlist in self._youtube_music_library_cache()]
        view.has_more = self._youtube_music_library_has_more_playlists()

    def _sync_youtube_music_library_view(self):
        """A biblioteca mudou (atualizou, carregou mais, excluiu): a lista dela acompanha."""
        for view in self._youtube_music_results_views():
            if view.kind == VIEW_KIND_LIBRARY:
                self._fill_youtube_music_library_view(view)

    def _youtube_music_can_go_back_in_results(self):
        return len(self._youtube_music_results_views()) > 1

    def _build_youtube_music_container_view(self, result, section_id=""):
        sections = container_sections(result)
        if sections and not section_id:
            # Canal e artista têm várias listas: primeiro se escolhe qual ver.
            return YouTubeResultsView(
                title=container_title(result),
                results=section_folder_items(result, sections),
            )
        service = self._get_youtube_music_service()

        def fetch_page(start, count):
            return service.fetch_browse_page(result, section_id=section_id, start=start, count=count)

        return YouTubeResultsView(title=container_title(result, section_id), fetch_page=fetch_page)

    def _load_youtube_music_results_view(self, view, *, mode, error_message=None):
        """Carrega a primeira página de *view* e a mostra.

        *mode*: ``"reset"`` recomeça a navegação a partir do início (nova busca) e
        ``"push"`` abre por cima da lista atual.
        """
        if error_message is None:
            error_message = _("Não foi possível carregar esta lista agora.")

        if view.fetch_page is None:
            # Lista que já vem pronta (continentes, países, a biblioteca em cache).
            self._install_youtube_music_results_view(view, mode)
            return True

        def worker():
            return view.fetch_page(0, YOUTUBE_RESULTS_PAGE_SIZE)

        def on_success(page):
            view.results = list(page.results)
            view.has_more = bool(page.has_more and page.results)
            view.next_start = YOUTUBE_RESULTS_PAGE_SIZE
            self._install_youtube_music_results_view(view, mode)

        def on_error(exc):
            wx.MessageBox(
                error_message + "\n\n" + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc)),
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        started = self._run_youtube_music_background_task(worker, on_success, on_error=on_error)
        if not started:
            self._refresh_youtube_music_screen_later()
        return started

    def _install_youtube_music_results_view(self, view, mode):
        views = self._youtube_music_results_views()
        if mode == "push":
            views[-1].selected_id = self._youtube_music_selected_result_id()
            views.append(view)
        else:
            self._reset_youtube_music_results_views(view)
            # Depois de pesquisar, o foco vai do campo de busca para a lista.
            self._youtube_music_pending_results_focus = bool(view.results)
        self._show_youtube_music_results_view(announce=True)

    def _youtube_music_selected_result_id(self):
        panel = self._get_youtube_music_panel()
        if panel is None:
            return ""
        selected_ids = panel.get_selected_search_result_ids()
        return selected_ids[0] if selected_ids else ""

    def _show_youtube_music_results_view(self, *, announce, selected_id=""):
        view = self._youtube_music_current_results_view()
        if selected_id:
            self._youtube_music_pending_result_selection = selected_id
        self._set_youtube_music_search_results(
            view.results,
            status_message=results_view_summary(view) if announce else None,
            view=view,
        )
        if announce:
            self._announce(results_view_summary(view, with_hint=False))

    def on_browse_youtube_music_search_result(self, result=None):
        """Abre a pasta, canal, artista, álbum ou playlist selecionado para ver o que há dentro."""
        if result is None:
            result = self._selected_youtube_music_search_result()
        if result is None or not getattr(result, "can_browse", False):
            self._announce(_("Este resultado não tem conteúdo para abrir."))
            return False

        if getattr(result, "kind", "") == FOLDER_SECTION:
            container, section_id = result.payload
            view = self._build_youtube_music_container_view(container, section_id)
        elif getattr(result, "result_type", "") == "folder":
            if result.requires_auth and not self._ensure_youtube_music_authenticated():
                return False
            view = self._build_youtube_music_folder_view(result)
        else:
            view = self._build_youtube_music_container_view(result)
        if view is None:
            self._announce(_("Este resultado não tem conteúdo para abrir."))
            return False

        if view.fetch_page is not None:
            self._announce(_("Abrindo {title}.").format(title=view.title))
        started = self._load_youtube_music_results_view(
            view,
            mode="push",
            error_message=_("Não foi possível abrir este resultado agora."),
        )
        if started and getattr(result, "kind", "") == FOLDER_LIBRARY:
            # Aberta antes de a biblioteca chegar: a lista se preenche quando ela carregar.
            self._auto_load_youtube_music_library_if_needed()
        return started

    def on_youtube_music_results_back(self):
        views = self._youtube_music_results_views()
        if len(views) <= 1:
            self._announce(_("Não há lista anterior para voltar."))
            return False

        views.pop()
        self._show_youtube_music_results_view(announce=True, selected_id=views[-1].selected_id)
        return True

    def on_load_more_youtube_music_results(self):
        view = self._youtube_music_current_results_view()
        if view.kind == VIEW_KIND_LIBRARY:
            return self._load_more_youtube_music_playlists()
        if not view.has_more or view.fetch_page is None:
            return False

        start = view.next_start
        self._announce(_("Carregando mais itens."))

        def worker():
            return view.fetch_page(start, YOUTUBE_RESULTS_PAGE_SIZE)

        def on_success(page):
            if view is not self._youtube_music_current_results_view():
                return
            known_ids = {result.stable_id for result in view.results}
            new_results = []
            for result in page.results:
                if result.stable_id not in known_ids:
                    known_ids.add(result.stable_id)
                    new_results.append(result)
            view.results.extend(new_results)
            view.next_start = start + YOUTUBE_RESULTS_PAGE_SIZE
            # Uma página sem nada de novo encerra a lista, para não repetir o pedido sem fim.
            view.has_more = bool(page.has_more and new_results)
            self._show_youtube_music_results_view(announce=False)
            if new_results:
                self._announce(
                    ngettext(
                        "Mais {count} item. Total: {total}.",
                        "Mais {count} itens. Total: {total}.",
                        len(new_results),
                    ).format(count=len(new_results), total=len(view.results))
                )
            else:
                self._announce(_("Fim da lista: não há mais itens."))

        def on_error(exc):
            wx.MessageBox(
                _("Não foi possível carregar mais resultados agora.") + "\n\n" + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc)),
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)
