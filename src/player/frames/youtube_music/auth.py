from ...i18n import _
import wx

from player.youtube_music.dialog import YouTubeMusicBrowserAuthDialog


class AuthMixin:
    def _handle_invalid_youtube_music_auth(self, service, *, announce=True):
        message = _("Não foi possível validar a autenticação salva do YouTube Music. Conecte a conta novamente.")
        service.clear_client_cache()

        self._set_youtube_music_account_name("")
        self._clear_youtube_music_library_cache(
            loaded=False,
            status_message=message,
        )
        self._refresh_youtube_music_menu_state()
        if hasattr(self, "_set_status_message"):
            self._set_status_message(message)
        if announce:
            self._announce(message)
        return False

    def _handle_youtube_music_auth_validation_failure(self, service, error, *, announce=True):
        if bool(getattr(error, "should_disconnect", True)):
            return self._handle_invalid_youtube_music_auth(service, announce=announce)

        if bool(getattr(error, "is_dependency_unavailable", False)):
            message = str(error).strip()
        else:
            message = _("Não foi possível validar a autenticação salva do YouTube Music agora. Tente novamente em instantes.")
        service.clear_client_cache()
        self._youtube_music_library_status_message = message
        self._refresh_youtube_music_screen_later()
        self._refresh_youtube_music_menu_state()
        if hasattr(self, "_set_status_message"):
            self._set_status_message(message)
        if announce:
            self._announce(message)
        return False

    def _ensure_youtube_music_authenticated(self):
        service = self._get_youtube_music_service()
        if service.has_saved_browser_auth():
            try:
                return service.validate_saved_authentication()
            except Exception as exc:
                return self._handle_youtube_music_auth_validation_failure(service, exc)

        self.on_connect_youtube_music(None)
        if not service.has_saved_browser_auth():
            return False

        try:
            return service.validate_saved_authentication()
        except Exception as exc:
            return self._handle_youtube_music_auth_validation_failure(service, exc)

    def on_connect_youtube_music(self, _event):
        service = self._get_youtube_music_service()
        dialog = YouTubeMusicBrowserAuthDialog(self)
        try:
            if dialog.ShowModal() != wx.ID_OK:
                self._announce(_("Conexão com o YouTube Music cancelada."))
                return

            auth_mode = dialog.get_auth_mode()
            selected_browser = dialog.get_selected_browser()
            headers_raw = dialog.get_headers_raw()
            browser_json_path = dialog.get_browser_json_path()
        finally:
            dialog.Destroy()

        if auth_mode == "browser" and not selected_browser:
            wx.MessageBox(
                _("Selecione um navegador na lista antes de conectar."),
                _("YouTube Music"),
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return False
        if auth_mode != "browser" and not headers_raw and not browser_json_path:
            wx.MessageBox(
                _("Cole os dados de conexão do navegador ou selecione um arquivo válido de browser.json, JSON de cookies ou cookies.txt."),
                _("YouTube Music"),
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return False

        def worker():
            if auth_mode == "browser":
                saved_path = service.save_browser_auth_from_browser(selected_browser)
            else:
                saved_path = service.save_browser_auth(
                    headers_raw=headers_raw,
                    source_file_path=browser_json_path,
                )
            return saved_path, service.get_connected_account_name()

        def on_success(connection_result):
            saved_path, account_name = connection_result
            self._complete_youtube_music_connection(saved_path, account_name)

        def on_error(exc):
            if not service.has_saved_browser_auth():
                self._set_youtube_music_account_name("")
            error_message = _("Não foi possível conectar a conta do YouTube Music.")
            wx.MessageBox(
                error_message
                + "\n\n"
                + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc)),
                _("YouTube Music"),
                wx.OK | wx.ICON_ERROR,
                self,
            )
            if hasattr(self, "_set_status_message"):
                self._set_status_message(error_message)
            self._refresh_youtube_music_menu_state()

        connecting_message = _("Conectando a conta do YouTube Music...")
        self._announce(connecting_message)
        if hasattr(self, "_set_status_message"):
            self._set_status_message(connecting_message)
        return self._run_youtube_music_background_task(
            worker,
            on_success,
            on_error=on_error,
            timeout_ms=90000,
        )

    def _complete_youtube_music_connection(self, saved_path, account_name):
        self._set_youtube_music_account_name(account_name)
        self._youtube_music_library_status_message = _("Conta conectada: {name}.").format(name=account_name)
        self._clear_youtube_music_library_cache(loaded=False, status_message=self._youtube_music_status_message())
        self._refresh_youtube_music_menu_state()
        self._refresh_pending_restored_youtube_music_tabs()
        self._announce(_("Conta do YouTube Music conectada: {name}.").format(name=account_name))
        if hasattr(self, "_set_status_message"):
            self._set_status_message(_("YouTube Music conectado como {name}.").format(name=account_name))
        self.on_refresh_youtube_music_library(None, announce=False)
        wx.MessageBox(
            _("Autenticação do navegador salva em:\n{path}\n\nConta conectada: {name}").format(path=saved_path, name=account_name),
            _("YouTube Music"),
            wx.OK | wx.ICON_INFORMATION,
            self,
        )

    def on_disconnect_youtube_music(self, _event):
        service = self._get_youtube_music_service()
        if not service.has_saved_browser_auth():
            self._announce(_("Nenhuma conta do YouTube Music está conectada."))
            self._refresh_youtube_music_menu_state()
            return

        with wx.MessageDialog(
            self,
            _("Deseja remover a autenticação salva do YouTube Music neste computador?"),
            "YouTube Music",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_YES:
                return

        service.disconnect()
        self._set_youtube_music_account_name("")
        self._clear_youtube_music_library_cache(
            loaded=False,
            status_message=_("A conta do YouTube Music foi desconectada desta instalação."),
        )
        self._refresh_youtube_music_menu_state()
        self._announce(_("Conta do YouTube Music desconectada."))
        if hasattr(self, "_set_status_message"):
            self._set_status_message(_("YouTube Music desconectado."))
        wx.MessageBox(
            _("A autenticação salva do YouTube Music foi removida."),
            "YouTube Music",
            wx.OK | wx.ICON_INFORMATION,
            self,
        )
