"""O que se faz com as rádios da lista: tocar, adicionar, favoritar e ver detalhes."""

import threading

import wx

from player.radio.client import RadioBrowserError
from player.radio.folders import FOLDER_COUNTRY
from player.radio.manual_dialog import AddRadioManuallyDialog
from player.radio.media import is_radio_media

from ...i18n import _, ngettext
from ...playlists import PlaylistState


class RadioActionsMixin:
    def _selected_radio_results(self):
        panel = self._get_radio_panel()
        return panel.get_selected_results() if panel is not None else []

    def _selected_radio_result(self):
        selected_results = self._selected_radio_results()
        return selected_results[0] if len(selected_results) == 1 else None

    def _selected_radio_stations(self):
        return [
            result
            for result in self._selected_radio_results()
            if getattr(result, "result_type", "") == "station"
        ]

    def _radio_playlist_target(self):
        candidates = [
            self._get_playlist_state(self._get_current_tab_index()),
            self._get_active_playlist_state(),
        ]
        for candidate in candidates:
            if isinstance(candidate, PlaylistState) and not candidate.is_folder_tab and not candidate.is_loading:
                return candidate

        return self._get_playlist_state(self._create_empty_playlist_tab(select=False))

    def _retitle_radio_playlist(self, state):
        """Uma playlist só de rádios leva o nome delas, não um pedaço do endereço do stream."""
        if getattr(state, "source_path", None) or not state.items:
            return
        if not all(is_radio_media(item) for item in state.items):
            return

        if len(state.items) == 1:
            title = self._media_label(state.items[0])
        else:
            title = _("Rádios ({count})").format(count=len(state.items))
        if title == state.title:
            return

        state.title = title
        target_index = self._resolve_playlist_state_index(state)
        if target_index != wx.NOT_FOUND:
            self.notebook.SetPageText(target_index, title)

    def _activate_selected_radio_stations(self, play=True):
        stations = self._selected_radio_stations()
        if not stations:
            self._announce(_("Selecione ao menos uma rádio."))
            return False
        return self._play_radio_stations(stations, play=play)

    def _play_radio_stations(self, stations, *, play):
        """Põe *stations* na playlist atual; com *play*, toca a primeira delas."""
        target_state = self._radio_playlist_target()
        if not isinstance(target_state, PlaylistState):
            self._announce(_("Não foi possível localizar uma playlist de destino no player."))
            return False

        added_count, play_item = self._append_prepared_items_to_playlist(
            [station.media_path for station in stations],
            target_state,
            browser_item_labels=[station.name for station in stations],
        )
        if not play_item:
            return False

        # Com os dados na biblioteca, o Ctrl+D da playlist também leva a rádio às favoritas.
        service = self._get_radio_service()
        for station in stations:
            service.remember(station)

        self._retitle_radio_playlist(target_state)
        target_state.sync_playback_order()
        target_index = self._resolve_playlist_state_index(target_state)

        if play and target_index != wx.NOT_FOUND:
            play_index = target_state.index_of_item(play_item)
            if play_index is not None:
                target_state.select_index(play_index)
                self.active_playlist_index = target_index
                self._play_media(
                    index=target_index,
                    announce_message=_("Tocando {name}.").format(name=stations[0].name),
                )
        elif added_count:
            self._announce(
                ngettext(
                    "{count} rádio adicionada a {title}, sem tocar.",
                    "{count} rádios adicionadas a {title}, sem tocar.",
                    added_count,
                ).format(count=added_count, title=target_state.title)
            )
        else:
            self._announce(_("As rádios selecionadas já estavam em {title}.").format(title=target_state.title))

        self._refresh_playlist_browser()
        self._update_title()
        return True

    def _toggle_radio_favorite(self, station):
        became_favorite = self._get_radio_service().toggle_favorite(station)
        if became_favorite is None:
            self._announce_smart_library_unavailable()
            return None
        self._sync_radio_local_views()
        self._refresh_radio_screen()
        # O favorito é o mesmo da playlist: o marcador de lá acompanha.
        self._refresh_marks_after_change()
        if became_favorite:
            self._announce(_("{name} adicionada às rádios favoritas.").format(name=station.name))
        else:
            self._announce(_("{name} removida das rádios favoritas.").format(name=station.name))
        return became_favorite

    def _toggle_selected_radio_favorite(self):
        stations = self._selected_radio_stations()
        if len(stations) != 1:
            self._announce(_("Selecione uma rádio para favoritar."))
            return False
        self._toggle_radio_favorite(stations[0])
        return True

    def _current_radio_station(self):
        """A rádio que está na playlist ativa agora, ou ``None``."""
        state = self._get_active_playlist_state()
        media_path = getattr(state, "current_media_path", None)
        if not media_path or not is_radio_media(media_path):
            return None
        return self._get_radio_service().station_for_media_path(media_path, self._media_label(media_path))

    def _toggle_current_radio_favorite(self):
        station = self._current_radio_station()
        if station is None:
            self._announce(_("Nenhuma rádio tocando agora."))
            return False
        self._toggle_radio_favorite(station)
        return True

    def _add_radio_manually(self):
        """Cadastra pelo nome e pelo endereço uma rádio fora do diretório e a favorita."""
        panel = self._get_radio_panel()
        dialog = AddRadioManuallyDialog(panel or self)
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return False
            name = dialog.get_name()
            stream_url = dialog.get_stream_url()
        finally:
            dialog.Destroy()

        service = self._get_radio_service()
        station = service.build_manual_station(name, stream_url)
        if station is None:
            wx.MessageBox(
                _("Não foi possível reconhecer este endereço como um stream de rádio válido."),
                _("Endereço inválido"),
                wx.OK | wx.ICON_WARNING,
                panel or self,
            )
            return False

        if not service.set_favorite(station, True):
            self._announce_smart_library_unavailable()
            return False

        self._sync_radio_local_views()
        self._refresh_radio_screen()
        self._refresh_marks_after_change()
        self._announce(_("{name} adicionada às rádios favoritas.").format(name=station.name))
        return True

    def _copy_selected_radio_stream_url(self):
        stations = self._selected_radio_stations()
        if len(stations) != 1:
            self._announce(_("Selecione uma rádio para copiar o endereço do stream."))
            return False
        if not self._copy_text_to_clipboard(stations[0].stream_url):
            self._announce(_("Não foi possível copiar para a área de transferência."))
            return False
        self._announce(_("Endereço do stream copiado."))
        return True

    def _open_radio_homepage(self, station):
        # O endereço vem do diretório: só um site http(s) vai para o navegador.
        homepage = str(station.homepage or "").strip()
        if not homepage.lower().startswith(("http://", "https://")) or not wx.LaunchDefaultBrowser(homepage):
            self._announce(_("Não foi possível abrir o site desta rádio."))
            return False
        self._announce(_("Abrindo o site de {name} no navegador.").format(name=station.name))
        return True

    def _show_radio_station_details(self, station):
        lines = [_("Nome: {value}").format(value=station.name)]
        for template, value in (
            (_("País: {value}"), station.country),
            (_("Estado ou região: {value}"), station.state),
            (_("Idioma: {value}"), station.language),
            (_("Gêneros: {value}"), ", ".join(station.tags)),
            (_("Qualidade: {value}"), station.quality_text),
            (_("Votos: {value}"), station.votes or ""),
            (_("Ouvintes nas últimas 24 horas: {value}"), station.click_count or ""),
            (_("Site: {value}"), station.homepage),
            (_("Stream: {value}"), station.stream_url),
        ):
            if value:
                lines.append(template.format(value=value))

        actions = []
        if station.homepage:
            actions.append((_("Abrir o &site"), lambda: self._open_radio_homepage(station)))
        # A mesma caixa de leitura dos detalhes do KeyTube: dá para reler linha a linha e copiar.
        self._show_reading_dialog(
            title=_("Detalhes de {title}").format(title=station.name),
            text="\n".join(lines),
            label=_("Detalhes"),
            actions=actions,
        )

    def _vote_for_radio_station(self, station):
        service = self._get_radio_service()

        def finish(accepted, detail):
            if accepted:
                self._announce(_("Voto registrado para {name}.").format(name=station.name))
            elif detail:
                self._announce(_("O diretório não aceitou o voto: {detail}").format(detail=detail))
            else:
                self._announce(_("Não foi possível votar nesta rádio agora."))

        def runner():
            try:
                accepted, detail = service.vote(station)
            except RadioBrowserError:
                accepted, detail = False, ""
            wx.CallAfter(finish, accepted, detail)

        threading.Thread(target=runner, daemon=True, name="radio-vote").start()

    def _show_radio_actions_menu(self, anchor_window=None):
        selected_results = self._selected_radio_results()
        stations = self._selected_radio_stations()
        single_result = self._selected_radio_result()
        single_station = stations[0] if len(stations) == 1 and len(selected_results) == 1 else None
        can_go_back = len(self._radio_views()) > 1
        service = self._get_radio_service()

        menu = wx.Menu()

        def append(label, handler, enabled=True):
            menu_item = menu.Append(wx.ID_ANY, label)
            menu_item.Enable(bool(enabled))
            menu.Bind(wx.EVT_MENU, lambda _event: handler(), id=menu_item.GetId())

        append(_("Tocar (Enter)"), lambda: self._activate_selected_radio_stations(play=True), stations)
        append(
            _("Adicionar sem tocar (Shift+Enter)"),
            lambda: self._activate_selected_radio_stations(play=False),
            stations,
        )
        append(
            _("Ver conteúdo (Seta para a direita)"),
            self.on_browse_radio_result,
            single_result is not None and getattr(single_result, "can_browse", False),
        )
        append(_("Voltar à lista anterior (Backspace)"), self.on_radio_results_back, can_go_back)
        append(_("Adicionar rádio manualmente..."), self._add_radio_manually, True)
        if single_result is not None and getattr(single_result, "kind", "") == FOLDER_COUNTRY:
            country_code, country_name = single_result.payload
            append(
                _("Definir {country} como o meu país").format(country=country_name).replace("&", "&&"),
                lambda: self._set_radio_country(country_code, country_name),
                country_code and country_code != self._radio_region()[0],
            )
        menu.AppendSeparator()

        if single_station is not None and service.is_favorite(single_station):
            favorite_label = _("Remover das favoritas (Ctrl+D)")
        else:
            favorite_label = _("Adicionar às favoritas (Ctrl+D)")
        append(favorite_label, self._toggle_selected_radio_favorite, single_station)
        append(
            _("Ver detalhes da rádio"),
            lambda: self._show_radio_station_details(single_station),
            single_station,
        )
        append(
            _("Abrir o site da rádio no navegador"),
            lambda: self._open_radio_homepage(single_station),
            single_station is not None and single_station.homepage,
        )
        append(_("Copiar o endereço do stream (Ctrl+C)"), self._copy_selected_radio_stream_url, single_station)
        append(
            _("Votar nesta rádio no diretório"),
            lambda: self._vote_for_radio_station(single_station),
            single_station is not None and single_station.station_uuid,
        )
        menu.AppendSeparator()

        current_station = self._current_radio_station()
        if current_station is not None and service.is_favorite(current_station):
            current_label = _("Remover das favoritas a rádio que está tocando")
        else:
            current_label = _("Adicionar às favoritas a rádio que está tocando")
        append(current_label, self._toggle_current_radio_favorite, current_station)

        popup_parent = anchor_window or self._get_radio_panel() or self
        try:
            popup_parent.PopupMenu(menu)
        finally:
            menu.Destroy()
        return True
