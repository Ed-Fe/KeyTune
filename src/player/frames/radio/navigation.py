"""Navegação da lista da aba de rádios online.

A aba tem uma lista só, que é uma pilha de visões: o início fica embaixo e a
busca e cada pasta aberta (país, estado, gênero, idioma) entram por cima.
Voltar desempilha e chegar ao fim da lista traz a página seguinte.
"""

import threading
from dataclasses import dataclass, field

import wx

from player.radio.folders import FOLDER_FAVORITES, FOLDER_RECENTS, home_folder_items, open_radio_folder
from player.radio.models import RADIO_RESULTS_PAGE_SIZE

from ...i18n import _, ngettext


VIEW_KIND_HOME = "home"


@dataclass
class RadioResultsView:
    title: str
    # ``fetch_page(start, count)`` devolve um RadioResultPage; roda fora da thread da interface.
    fetch_page: object = None
    results: list = field(default_factory=list)
    has_more: bool = False
    next_start: int = 0
    selected_id: str = ""
    # Resumo pronto, para a lista que não se descreve pela contagem (o início).
    summary: str = ""
    # ``VIEW_KIND_HOME``, ``FOLDER_FAVORITES`` ou ``FOLDER_RECENTS``; vazio nas demais.
    kind: str = ""


def radio_view_summary(view, *, with_hint=True):
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


class RadioNavigationMixin:
    def _radio_home_view(self):
        return RadioResultsView(
            title=_("Início"),
            kind=VIEW_KIND_HOME,
            results=home_folder_items(self._get_radio_service(), self._radio_region()),
            summary=_("Início das rádios online: escolha uma lista, busque uma rádio ou cole o endereço de um stream."),
        )

    def _radio_views(self):
        views = getattr(self, "_radio_view_stack", None)
        if not views:
            views = [self._radio_home_view()]
            self._radio_view_stack = views
        return views

    def _radio_current_view(self):
        return self._radio_views()[-1]

    def _sync_radio_local_views(self):
        """As favoritas ou as recentes mudaram: o início e as listas delas acompanham."""
        service = self._get_radio_service()
        for view in self._radio_views():
            if view.kind == VIEW_KIND_HOME:
                view.results = home_folder_items(service, self._radio_region())
            elif view.kind == FOLDER_FAVORITES:
                view.results = service.favorites()
            elif view.kind == FOLDER_RECENTS:
                view.results = service.recents()

    def _run_radio_task(self, worker, on_success, on_error):
        """Roda *worker* fora da thread da interface; só o pedido mais recente é entregue."""
        task_id = int(getattr(self, "_radio_task_sequence", 0)) + 1
        self._radio_task_sequence = task_id
        self._radio_loading = True
        self._refresh_radio_screen()

        def finish(result, error):
            if task_id != getattr(self, "_radio_task_sequence", 0):
                return
            self._radio_loading = False
            self._refresh_radio_screen()
            if error is not None:
                on_error(error)
            else:
                on_success(result)

        def runner():
            try:
                result = worker()
            except Exception as exc:
                wx.CallAfter(finish, None, exc)
                return
            wx.CallAfter(finish, result, None)

        threading.Thread(target=runner, daemon=True, name="radio-directory").start()

    def _cancel_radio_task(self):
        self._radio_task_sequence = int(getattr(self, "_radio_task_sequence", 0)) + 1
        self._radio_loading = False

    def _show_radio_error(self, message, error):
        detail = str(error or "").strip()
        if detail:
            message = message + "\n\n" + _("Detalhes: {detail}").format(detail=detail)
        wx.MessageBox(message, _("Rádios online"), wx.OK | wx.ICON_ERROR, self)

    def _load_radio_view(self, view, *, mode, error_message, focus_results=False):
        """Carrega a primeira página de *view* e a mostra.

        *mode*: ``"reset"`` recomeça a navegação a partir do início (nova busca) e
        ``"push"`` abre por cima da lista atual.
        """
        if view.fetch_page is None:
            self._install_radio_view(view, mode, focus_results=focus_results)
            return

        def worker():
            return view.fetch_page(0, RADIO_RESULTS_PAGE_SIZE)

        def on_success(page):
            view.results = list(page.results)
            view.has_more = bool(page.has_more and page.results)
            view.next_start = RADIO_RESULTS_PAGE_SIZE
            self._install_radio_view(view, mode, focus_results=focus_results)

        self._run_radio_task(worker, on_success, lambda error: self._show_radio_error(error_message, error))

    def _install_radio_view(self, view, mode, *, focus_results=False):
        views = self._radio_views()
        if mode == "push":
            views[-1].selected_id = self._radio_selected_result_id()
            views.append(view)
        else:
            views[:] = [views[0], view]
            # Depois de pesquisar, o foco vai do campo de busca para a lista.
            focus_results = True
        self._radio_pending_results_focus = bool(focus_results and view.results)
        self._show_radio_view(announce=True)

    def _radio_selected_result_id(self):
        panel = self._get_radio_panel()
        if panel is None:
            return ""
        selected_ids = panel.get_selected_result_ids()
        return selected_ids[0] if selected_ids else ""

    def _show_radio_view(self, *, announce, selected_id=""):
        if selected_id:
            self._radio_pending_result_selection = selected_id
        self._refresh_radio_screen()
        if announce:
            self._announce(radio_view_summary(self._radio_current_view(), with_hint=False))

    def on_browse_radio_result(self, result=None):
        """Abre a pasta selecionada para ver o que há dentro."""
        if result is None:
            result = self._selected_radio_result()
        content = (
            open_radio_folder(result, self._get_radio_service())
            if result is not None and getattr(result, "can_browse", False)
            else None
        )
        if content is None:
            self._announce(_("Este item não tem conteúdo para abrir."))
            return False

        view = RadioResultsView(title=content.title, fetch_page=content.fetch_page, kind=content.kind)
        if content.fetch_page is None:
            view.results = list(content.results or [])
        else:
            self._announce(_("Abrindo {title}.").format(title=view.title))
        self._load_radio_view(
            view,
            mode="push",
            error_message=_("Não foi possível abrir esta lista de rádios agora."),
        )
        return True

    def on_radio_results_back(self):
        views = self._radio_views()
        if len(views) <= 1:
            self._announce(_("Não há lista anterior para voltar."))
            return False

        self._cancel_radio_task()
        views.pop()
        self._show_radio_view(announce=True, selected_id=views[-1].selected_id)
        return True

    def on_load_more_radio_results(self):
        view = self._radio_current_view()
        if not view.has_more or view.fetch_page is None:
            return False

        start = view.next_start
        self._announce(_("Carregando mais itens."))

        def worker():
            return view.fetch_page(start, RADIO_RESULTS_PAGE_SIZE)

        def on_success(page):
            if view is not self._radio_current_view():
                return
            known_ids = {result.stable_id for result in view.results}
            new_results = []
            for result in page.results:
                if result.stable_id not in known_ids:
                    known_ids.add(result.stable_id)
                    new_results.append(result)
            view.results.extend(new_results)
            view.next_start = start + RADIO_RESULTS_PAGE_SIZE
            # Uma página sem nada de novo encerra a lista, para não repetir o pedido sem fim.
            view.has_more = bool(page.has_more and new_results)
            self._show_radio_view(announce=False)
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

        self._run_radio_task(
            worker,
            on_success,
            lambda error: self._show_radio_error(_("Não foi possível carregar mais rádios agora."), error),
        )
        return True

    def on_search_radio(self):
        panel = self._get_radio_panel()
        if panel is None:
            return False

        query = panel.get_search_query()
        if not query:
            self._announce(_("Digite o nome de uma rádio para pesquisar."))
            return False

        service = self._get_radio_service()
        custom_station = service.custom_station(query)
        if custom_station is not None:
            return self._play_radio_stations([custom_station], play=True)

        country_code = self._radio_search_scopes()[panel.get_search_scope_index()][0]
        self._announce(_("Pesquisando {query}.").format(query=query))

        def fetch_page(start, count):
            return service.fetch_search_page(query, country_code=country_code, start=start, count=count)

        view = RadioResultsView(title=_("Busca por {query}").format(query=query), fetch_page=fetch_page)
        self._load_radio_view(
            view,
            mode="reset",
            error_message=_("Não foi possível concluir a busca de rádios agora."),
        )
        return True
