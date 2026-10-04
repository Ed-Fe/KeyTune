"""A aba de rádios online: abrir, achar o painel e mantê-lo em dia."""

from player.radio.models import RADIO_SCREEN_ID
from player.radio.region import default_radio_region
from player.radio.service import RadioService
from player.radio.store import RadioLibraryStore

from ...i18n import _
from ...playlists import ScreenTabState
from .navigation import radio_view_summary


def _radio_tab_panel_class():
    from player.radio.panel import RadioTabPanel

    return RadioTabPanel


class RadioLifecycleMixin:
    def _get_radio_service(self):
        service = getattr(self, "_radio_service", None)
        if service is None:
            service = RadioService(RadioLibraryStore(self._smart_library))
            self._radio_service = service
        return service

    def _radio_region(self):
        """O país do usuário: o que ele escolheu na aba ou, sem escolha, o do sistema."""
        chosen_code = str(getattr(self.settings, "radio_country_code", "") or "").strip().upper()
        if chosen_code:
            return chosen_code, str(getattr(self.settings, "radio_country_name", "") or "").strip() or chosen_code

        region = getattr(self, "_radio_default_region", None)
        if region is None:
            region = default_radio_region()
            self._radio_default_region = region
        return region

    def _radio_search_scopes(self):
        """Onde a busca procura: ``(código do país, rótulo)``; código vazio é o mundo todo."""
        scopes = [("", _("Todo o mundo"))]
        country_code, country_name = self._radio_region()
        if country_code:
            scopes.append((country_code, country_name))
        return scopes

    def _set_radio_country(self, country_code, country_name):
        self.settings.radio_country_code = str(country_code or "").strip().upper()
        self.settings.radio_country_name = str(country_name or "").strip()
        self._save_settings()
        self._sync_radio_local_views()
        panel = self._get_radio_panel()
        if panel is not None:
            panel.set_search_scope_labels([label for _code, label in self._radio_search_scopes()])
        self._refresh_radio_screen()
        self._announce(_("{country} definido como o seu país nas rádios online.").format(country=country_name))

    def _create_radio_page(self, parent):
        return _radio_tab_panel_class()(
            parent,
            search_scope_labels=[label for _code, label in self._radio_search_scopes()],
            on_search=self.on_search_radio,
            on_activate=self._activate_selected_radio_stations,
            on_browse=self.on_browse_radio_result,
            on_back=self.on_radio_results_back,
            on_load_more=self.on_load_more_radio_results,
            on_toggle_favorite=self._toggle_selected_radio_favorite,
            on_copy_stream_url=self._copy_selected_radio_stream_url,
            on_show_actions_menu=self._show_radio_actions_menu,
        )

    def _get_radio_panel(self):
        if not hasattr(self, "playlists") or not hasattr(self, "notebook"):
            return None

        for index, state in enumerate(self.playlists):
            if isinstance(state, ScreenTabState) and state.screen_id == RADIO_SCREEN_ID:
                page = self.notebook.GetPage(index)
                if isinstance(page, _radio_tab_panel_class()):
                    return page

        return None

    def _refresh_radio_screen(self):
        panel = self._get_radio_panel()
        if panel is None:
            return

        view = self._radio_current_view()
        loading = bool(getattr(self, "_radio_loading", False))
        selected_id = getattr(self, "_radio_pending_result_selection", "")
        self._radio_pending_result_selection = ""
        panel.update_view(
            results=view.results,
            summary=_("Carregando…") if loading else radio_view_summary(view),
            favorite_keys=self._get_radio_service().favorite_keys(),
            has_more=view.has_more,
            can_go_back=len(self._radio_views()) > 1,
            loading=loading,
            selected_id=selected_id,
        )
        if getattr(self, "_radio_pending_results_focus", False):
            self._radio_pending_results_focus = False
            panel.focus_results()

    def _on_radio_screen_activated(self):
        # As favoritas e o histórico mudam também fora da aba (Ctrl+D na playlist).
        self._sync_radio_local_views()
        self._refresh_radio_screen()

    def _on_radio_screen_closed(self):
        # O que ainda estiver sendo buscado não tem mais onde aparecer.
        self._cancel_radio_task()

    def on_open_radio(self, _event=None):
        self._sync_radio_local_views()
        self._open_screen_tab(
            RADIO_SCREEN_ID,
            _("Rádios online"),
            self._create_radio_page,
            select=True,
            activation_message=_("Rádios online. Navegue pela lista, busque uma rádio ou cole o endereço de um stream."),
            on_activate=self._on_radio_screen_activated,
            on_close=self._on_radio_screen_closed,
        )
