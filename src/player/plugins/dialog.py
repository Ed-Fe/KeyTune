"""Keyboard-first plugin manager and permission consent dialogs."""

from __future__ import annotations

from pathlib import Path
import tempfile
import threading
import wx

from ..i18n import _
from .installer import download_package, install_archive, uninstall_plugin
from .manifest import PERMISSION_DESCRIPTIONS
from .marketplace import fetch_catalog


def permission_summary(manifest):
    if not manifest.permissions:
        return _("Nenhuma permissão especial.")
    return "\n".join(f"• {PERMISSION_DESCRIPTIONS[item]}" for item in sorted(manifest.permissions, key=lambda value: value.value))


class PermissionDialog(wx.Dialog):
    def __init__(self, parent, manifest):
        super().__init__(parent, title=_("Permissões do plugin"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        root = wx.BoxSizer(wx.VERTICAL)
        warning = _(
            "{name}, de {author}, solicita:\n\n{permissions}\n\n"
            "Plugins em processo separado não derrubam o player se falharem, mas isso não é uma sandbox do sistema operacional. "
            "Instale apenas código de autores em quem você confia."
        ).format(name=manifest.name, author=manifest.author, permissions=permission_summary(manifest))
        text = wx.TextCtrl(self, value=warning, style=wx.TE_MULTILINE | wx.TE_READONLY)
        text.SetName(_("Permissões solicitadas e aviso de segurança"))
        buttons = self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)
        root.Add(text, 1, wx.ALL | wx.EXPAND, 12)
        root.Add(buttons, 0, wx.ALL | wx.EXPAND, 12)
        self.SetSizer(root); self.SetSize((620, 420)); self.SetEscapeId(wx.ID_CANCEL)


class PluginManagerDialog(wx.Dialog):
    def __init__(self, parent, service):
        super().__init__(parent, title=_("Gerenciador de plugins"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.service = service
        root = wx.BoxSizer(wx.VERTICAL)
        root.Add(wx.StaticText(self, label=_("Plugins instalados:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        self.items = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.items.SetName(_("Lista de plugins instalados"))
        for index, (label, width) in enumerate(((_("Plugin"), 210), (_("Versão"), 90), (_("Estado"), 120), (_("Isolamento"), 120))):
            self.items.InsertColumn(index, label, width=width)
        root.Add(self.items, 1, wx.ALL | wx.EXPAND, 12)
        actions = wx.BoxSizer(wx.HORIZONTAL)
        self.toggle = wx.Button(self, label=_("&Ativar ou desativar"))
        self.permissions = wx.Button(self, label=_("Ver &permissões"))
        self.install = wx.Button(self, label=_("&Instalar pacote..."))
        self.remove = wx.Button(self, label=_("&Remover"))
        self.marketplace = wx.Button(self, label=_("Abrir &marketplace"))
        for button in (self.toggle, self.permissions, self.install, self.remove, self.marketplace): actions.Add(button, 0, wx.RIGHT, 8)
        root.Add(actions, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        root.Add(self.CreateSeparatedButtonSizer(wx.CLOSE), 0, wx.ALL | wx.EXPAND, 12)
        self.SetSizer(root); self.SetSize((760, 520)); self.SetEscapeId(wx.ID_CLOSE)
        self.toggle.Bind(wx.EVT_BUTTON, self._on_toggle)
        self.permissions.Bind(wx.EVT_BUTTON, self._on_permissions)
        self.install.Bind(wx.EVT_BUTTON, self._on_install)
        self.remove.Bind(wx.EVT_BUTTON, self._on_remove)
        self.marketplace.Bind(wx.EVT_BUTTON, self._on_marketplace)
        self._refresh()

    def _refresh(self):
        self._plugins = self.service.discover(); self.items.DeleteAllItems()
        for plugin in self._plugins:
            row = self.items.InsertItem(self.items.GetItemCount(), plugin.manifest.name)
            self.items.SetItem(row, 1, plugin.manifest.version)
            self.items.SetItem(row, 2, _("Ativado") if plugin.enabled else _("Desativado"))
            self.items.SetItem(row, 3, _("Processo separado") if plugin.manifest.isolation == "process" else _("No processo do player"))

    def _selected(self):
        index = self.items.GetFirstSelected()
        return self._plugins[index] if 0 <= index < len(self._plugins) else None

    def _on_toggle(self, _event):
        plugin = self._selected()
        if not plugin: return
        enable = not plugin.enabled
        if enable:
            dialog = PermissionDialog(self, plugin.manifest)
            try:
                if dialog.ShowModal() != wx.ID_OK: return
            finally: dialog.Destroy()
        self.service.registry.update(plugin.manifest.id, enabled=enable, granted_permissions=plugin.manifest.permissions if enable else plugin.granted_permissions)
        self._refresh()
        if enable:
            updated = next((item for item in self._plugins if item.manifest.id == plugin.manifest.id), None)
            runtime = self.service.start(updated) if updated else None
            if runtime is not None and runtime.error:
                self.service.registry.update(plugin.manifest.id, enabled=False, granted_permissions=plugin.manifest.permissions)
                self._refresh()
                wx.MessageBox(
                    _("O plugin não iniciou e voltou a ficar desativado: {error}").format(error=runtime.error),
                    _("Plugins"), wx.OK | wx.ICON_ERROR, self,
                )
                return
        else:
            self.service.stop(plugin.manifest.id)
        wx.MessageBox(_("A alteração foi aplicada."), _("Plugins"), wx.OK | wx.ICON_INFORMATION, self)

    def _on_permissions(self, _event):
        plugin = self._selected()
        if plugin: wx.MessageBox(permission_summary(plugin.manifest), _("Permissões do plugin"), wx.OK | wx.ICON_INFORMATION, self)

    def _on_install(self, _event):
        chooser = wx.FileDialog(self, _("Instalar pacote de plugin"), wildcard=_("Plugin do KeyTune (*.ktplugin)|*.ktplugin|Todos os arquivos|*.*"), style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        try:
            if chooser.ShowModal() != wx.ID_OK: return
            manifest = install_archive(chooser.GetPath(), self.service.plugins_dir)
        except Exception as exc:
            wx.MessageBox(_("Não foi possível instalar o plugin: {error}").format(error=exc), _("Plugins"), wx.OK | wx.ICON_ERROR, self); return
        finally: chooser.Destroy()
        self._refresh()
        wx.MessageBox(_("{name} foi instalado desativado. Revise as permissões antes de ativá-lo.").format(name=manifest.name), _("Plugins"), wx.OK | wx.ICON_INFORMATION, self)

    def _on_marketplace(self, _event):
        self.marketplace.Disable()
        threading.Thread(target=self._load_marketplace, daemon=True).start()

    def _on_remove(self, _event):
        plugin = self._selected()
        if not plugin:
            return
        answer = wx.MessageBox(
            _("Remover o plugin {name}? Os dados e ajustes privados serão preservados.").format(name=plugin.manifest.name),
            _("Remover plugin"), wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING, self,
        )
        if answer != wx.YES:
            return
        try:
            self.service.stop(plugin.manifest.id)
            uninstall_plugin(plugin.manifest.id, self.service.plugins_dir)
            self.service.registry.remove(plugin.manifest.id)
        except Exception as exc:
            wx.MessageBox(_("Não foi possível remover o plugin: {error}").format(error=exc), _("Plugins"), wx.OK | wx.ICON_ERROR, self)
            return
        self._refresh()

    def _load_marketplace(self):
        try: result = fetch_catalog()
        except Exception as exc: wx.CallAfter(self._show_marketplace_error, str(exc)); return
        wx.CallAfter(self._show_marketplace, result)

    def _show_marketplace_error(self, error):
        self.marketplace.Enable(); wx.MessageBox(_("Não foi possível carregar o marketplace: {error}").format(error=error), _("Marketplace de plugins"), wx.OK | wx.ICON_ERROR, self)

    def _show_marketplace(self, entries):
        self.marketplace.Enable()
        installed_versions = {plugin.manifest.id: plugin.manifest.version for plugin in self._plugins}
        choices = []
        for item in entries:
            current = installed_versions.get(item.id)
            status = _(" — atualização de {version}").format(version=current) if current and current != item.version else (_(" — instalado") if current else "")
            choices.append(f"{item.name} {item.version} — {item.author}{status}")
        dialog = wx.SingleChoiceDialog(self, _("Escolha um plugin. Pacotes são verificados por SHA-256 antes da instalação."), _("Marketplace de plugins"), choices)
        try:
            if dialog.ShowModal() != wx.ID_OK: return
            entry = entries[dialog.GetSelection()]
        finally: dialog.Destroy()
        consent = wx.MessageBox(_("Baixar e instalar {name}? Ele permanecerá desativado até você aprovar as permissões.").format(name=entry.name), _("Marketplace de plugins"), wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, self)
        if consent != wx.YES: return
        self.marketplace.Disable(); threading.Thread(target=self._download_entry, args=(entry,), daemon=True).start()

    def _download_entry(self, entry):
        try:
            with tempfile.TemporaryDirectory() as temporary:
                package = download_package(entry.download_url, Path(temporary) / f"{entry.id}.ktplugin")
                manifest = install_archive(package, self.service.plugins_dir, expected_sha256=entry.sha256)
        except Exception as exc: wx.CallAfter(self._show_marketplace_error, str(exc)); return
        wx.CallAfter(self._installed_from_marketplace, manifest)

    def _installed_from_marketplace(self, manifest):
        self.marketplace.Enable(); self._refresh(); wx.MessageBox(_("{name} foi instalado desativado. Revise e aprove as permissões para ativá-lo.").format(name=manifest.name), _("Marketplace de plugins"), wx.OK | wx.ICON_INFORMATION, self)
