import wx

from player.youtube_music.dialog import YouTubeMusicBrowserAuthDialog


class AuthMixin:
    def _handle_invalid_youtube_music_auth(self, service, *, announce=True):
        message = "Não foi possível validar a autenticação salva do YouTube Music. Conecte a conta novamente."
        try:
            service.disconnect()
        except Exception:
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

        message = "Não foi possível validar a autenticação salva do YouTube Music agora. Tente novamente em instantes."
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
                self._announce("Conexão com o YouTube Music cancelada.")
                return

            headers_raw = dialog.get_headers_raw()
            browser_json_path = dialog.get_browser_json_path()
        finally:
            dialog.Destroy()

        if not headers_raw and not browser_json_path:
            wx.MessageBox(
                "Cole os dados de conexão do navegador ou selecione um arquivo válido de browser.json, JSON de cookies ou cookies.txt.",
                "YouTube Music",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return

        try:
            saved_path = service.save_browser_auth(headers_raw=headers_raw, source_file_path=browser_json_path)
            account_name = service.get_connected_account_name()
        except Exception as exc:
            service.clear_client_cache()
            self._set_youtube_music_account_name("")
            wx.MessageBox(
                "Não foi possível conectar a conta do YouTube Music.\n\n"
                f"Detalhes: {self._format_youtube_music_error_detail(exc)}",
                "YouTube Music",
                wx.OK | wx.ICON_ERROR,
                self,
            )
            self._refresh_youtube_music_menu_state()
            return

        self._set_youtube_music_account_name(account_name)
        self._youtube_music_library_status_message = f"Conta conectada: {account_name}."
        self._clear_youtube_music_library_cache(loaded=False, status_message=self._youtube_music_status_message())
        self._refresh_youtube_music_menu_state()
        self._refresh_pending_restored_youtube_music_tabs()
        self._announce(f"Conta do YouTube Music conectada: {account_name}.")
        if hasattr(self, "_set_status_message"):
            self._set_status_message(f"YouTube Music conectado como {account_name}.")
        self.on_refresh_youtube_music_library(None, announce=False)
        wx.MessageBox(
            f"Autenticação do navegador salva em:\n{saved_path}\n\nConta conectada: {account_name}",
            "YouTube Music",
            wx.OK | wx.ICON_INFORMATION,
            self,
        )

    def on_disconnect_youtube_music(self, _event):
        service = self._get_youtube_music_service()
        if not service.has_saved_browser_auth():
            self._announce("Nenhuma conta do YouTube Music está conectada.")
            self._refresh_youtube_music_menu_state()
            return

        with wx.MessageDialog(
            self,
            "Deseja remover a autenticação salva do YouTube Music neste computador?",
            "YouTube Music",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_YES:
                return

        service.disconnect()
        self._set_youtube_music_account_name("")
        self._clear_youtube_music_library_cache(
            loaded=False,
            status_message="A conta do YouTube Music foi desconectada desta instalação.",
        )
        self._refresh_youtube_music_menu_state()
        self._announce("Conta do YouTube Music desconectada.")
        if hasattr(self, "_set_status_message"):
            self._set_status_message("YouTube Music desconectado.")
        wx.MessageBox(
            "A autenticação salva do YouTube Music foi removida.",
            "YouTube Music",
            wx.OK | wx.ICON_INFORMATION,
            self,
        )
