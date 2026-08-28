"""Small frame integration layer for the plugin platform."""

import threading
import wx

from ..i18n import _
from ..plugins.dialog import PluginManagerDialog
from ..plugins.host import PluginHostAdapter
from ..plugins.service import PluginService


class FramePluginMixin:
    def _initialize_plugin_service(self):
        self._plugin_menu_items = {}
        self.plugin_service = PluginService(
            contribution_handler=self._add_plugin_contribution,
            contribution_removal_handler=self._remove_plugin_contributions,
        )
        self._plugin_host = PluginHostAdapter(self, self.plugin_service.data_dir)
        self.plugin_service.host_dispatch = self._dispatch_plugin_api
        self.plugin_service.start_enabled()

    def _emit_plugin_event(self, event, payload=None):
        service = getattr(self, "plugin_service", None)
        if service is not None:
            service.emit(event, payload or {})

    def on_manage_plugins(self, _event):
        dialog = PluginManagerDialog(self, self.plugin_service)
        try:
            dialog.ShowModal()
        finally:
            dialog.Destroy()

    def _dispatch_plugin_api(self, method, arguments, manifest):
        ui_methods = {
            "playback.state", "playback.control", "library.playlists",
            "library.active_playlist", "library.add_to_playlist", "notifications.show",
            "clipboard.read_text", "clipboard.write_text",
        }
        if method not in ui_methods or wx.IsMainThread():
            return self._plugin_host.dispatch(method, arguments, manifest)
        finished = threading.Event()
        outcome = {}

        def invoke_on_ui_thread():
            try:
                outcome["result"] = self._plugin_host.dispatch(method, arguments, manifest)
            except Exception as exc:
                outcome["error"] = exc
            finally:
                finished.set()

        wx.CallAfter(invoke_on_ui_thread)
        if not finished.wait(timeout=30):
            raise TimeoutError(_("O player não respondeu ao plugin em 30 segundos."))
        if "error" in outcome:
            raise outcome["error"]
        return outcome.get("result")

    def _add_plugin_contribution(self, manifest, kind, contribution):
        if not wx.IsMainThread():
            wx.CallAfter(self._add_plugin_contribution, manifest, kind, contribution)
            return
        if not hasattr(self, "plugins_extensions_menu"):
            return
        if kind == "menu":
            callback = lambda: self.plugin_service.invoke_callback(manifest.id, contribution["callback"])
        elif kind in {"tab", "view"}:
            callback = lambda: self._open_screen_tab(
                f"plugin:{manifest.id}:{contribution['id']}",
                contribution["label"],
                contribution["factory"],
                activation_message=_("Tela do plugin {name} aberta.").format(name=manifest.name),
            )
        else:
            return
        target_menu = self.plugins_extensions_menu
        submenu_label = contribution.get("submenu", "")
        if submenu_label:
            target_menu = self._plugin_submenus.get(submenu_label)
            if target_menu is None:
                target_menu = wx.Menu()
                self._plugin_submenus[submenu_label] = target_menu
                self.plugins_extensions_menu.AppendSubMenu(target_menu, submenu_label)
        item = target_menu.Append(-1, contribution["label"])
        self.Bind(wx.EVT_MENU, lambda _event: callback(), item)
        self._plugin_menu_items.setdefault(manifest.id, []).append((target_menu, item))

    def _remove_plugin_contributions(self, manifest, _contributions):
        if not wx.IsMainThread():
            wx.CallAfter(self._remove_plugin_contributions, manifest, _contributions)
            return
        for menu, item in self._plugin_menu_items.pop(manifest.id, []):
            try:
                menu.DestroyItem(item)
            except RuntimeError:
                pass
        for label, submenu in tuple(self._plugin_submenus.items()):
            if submenu.GetMenuItemCount():
                continue
            for item in self.plugins_extensions_menu.GetMenuItems():
                if item.GetSubMenu() is submenu:
                    self.plugins_extensions_menu.DestroyItem(item)
                    break
            self._plugin_submenus.pop(label, None)
