"""Keyboard-first plugin manager and permission consent dialogs."""

from __future__ import annotations

from pathlib import Path
import tempfile
import threading
import wx

from ..i18n import _
from .installer import InstallationError, download_package, inspect_archive, install_archive, uninstall_plugin
from .manifest import PERMISSION_DESCRIPTIONS
from .marketplace import fetch_catalog


def permission_summary(manifest):
    if not manifest.permissions:
        return _("Nenhuma permissão especial.")
    return "\n".join(f"• {PERMISSION_DESCRIPTIONS[item]}" for item in sorted(manifest.permissions, key=lambda value: value.value))


def security_notice(manifest):
    if manifest.isolation == "in_process":
        return _(
            "Este plugin será executado dentro do processo do KeyTune e terá o mesmo acesso do aplicativo ao computador. "
            "Ative somente código de um autor em quem você confia plenamente."
        )
    return _(
        "O processo separado evita que falhas comuns derrubem o player e não recebe variáveis de ambiente sensíveis. "
        "As permissões acima controlam a API do KeyTune, mas o plugin ainda pode usar Python normalmente e acessar o computador; "
        "este modo não é uma sandbox de segurança."
    )


def installation_summary(manifest, source):
    details = [
        _("Nome: {name}").format(name=manifest.name),
        _("Versão: {version}").format(version=manifest.version),
        _("Autor: {author}").format(author=manifest.author),
        _("Origem: {source}").format(source=source),
        _("Isolamento: {mode}").format(
            mode=_("Processo separado") if manifest.isolation == "process" else _("No processo do player")
        ),
    ]
    if manifest.description:
        details.append(_("Descrição: {description}").format(description=manifest.description))
    if manifest.license:
        details.append(_("Licença: {license}").format(license=manifest.license))
    if manifest.homepage:
        details.append(_("Página: {homepage}").format(homepage=manifest.homepage))
    return _("{details}\n\nPermissões solicitadas:\n{permissions}\n\n{security_notice}").format(
        details="\n".join(details),
        permissions=permission_summary(manifest),
        security_notice=security_notice(manifest),
    )


class PermissionDialog(wx.Dialog):
    def __init__(self, parent, manifest):
        super().__init__(parent, title=_("Permissões do plugin"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        root = wx.BoxSizer(wx.VERTICAL)
        warning = _("{name}, de {author}, solicita:\n\n{permissions}\n\n{security_notice}").format(
            name=manifest.name,
            author=manifest.author,
            permissions=permission_summary(manifest),
            security_notice=security_notice(manifest),
        )
        text = wx.TextCtrl(self, value=warning, style=wx.TE_MULTILINE | wx.TE_READONLY)
        text.SetName(_("Permissões solicitadas e aviso de segurança"))
        buttons = self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)
        root.Add(text, 1, wx.ALL | wx.EXPAND, 12)
        root.Add(buttons, 0, wx.ALL | wx.EXPAND, 12)
        self.SetSizer(root); self.SetSize((620, 420)); self.SetEscapeId(wx.ID_CANCEL)


class InstallationConfirmationDialog(wx.Dialog):
    def __init__(self, parent, manifest, source):
        super().__init__(parent, title=_("Confirmar instalação do plugin"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        root = wx.BoxSizer(wx.VERTICAL)
        text = wx.TextCtrl(self, value=installation_summary(manifest, source), style=wx.TE_MULTILINE | wx.TE_READONLY)
        text.SetName(_("Dados e permissões do plugin"))
        buttons = self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)
        install_button = self.FindWindow(wx.ID_OK)
        if install_button is not None:
            install_button.SetLabel(_("&Instalar e ativar"))
        cancel_button = self.FindWindow(wx.ID_CANCEL)
        if cancel_button is not None:
            cancel_button.SetLabel(_("&Cancelar"))
        root.Add(text, 1, wx.ALL | wx.EXPAND, 12)
        root.Add(buttons, 0, wx.ALL | wx.EXPAND, 12)
        self.SetSizer(root); self.SetSize((660, 460)); self.SetEscapeId(wx.ID_CANCEL)


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
            runtime = self.service.runtimes.get(plugin.manifest.id)
            if runtime is not None and runtime.error:
                state = _("Falhou")
            elif runtime is not None and runtime.process is not None and not runtime.ready.is_set():
                state = _("Inicializando")
            else:
                state = _("Ativado") if plugin.enabled else _("Desativado")
            self.items.SetItem(row, 2, state)
            self.items.SetItem(row, 3, _("Processo separado") if plugin.manifest.isolation == "process" else _("No processo do player"))

    def _selected(self):
        index = self.items.GetFirstSelected()
        return self._plugins[index] if 0 <= index < len(self._plugins) else None

    def _has_open_plugin_screen(self, plugin_id):
        prefix = f"plugin:{plugin_id}:"
        return any(str(getattr(state, "screen_id", "")).startswith(prefix) for state in self.GetParent().playlists)

    def _require_closed_plugin_screens(self, plugin_id):
        if not self._has_open_plugin_screen(plugin_id):
            return True
        wx.MessageBox(
            _("Feche as abas ou telas abertas por este plugin antes de desativá-lo, atualizá-lo ou removê-lo."),
            _("Plugin em uso"), wx.OK | wx.ICON_WARNING, self,
        )
        return False

    def _on_toggle(self, _event):
        plugin = self._selected()
        if not plugin: return
        enable = not plugin.enabled
        if not enable and not self._require_closed_plugin_screens(plugin.manifest.id):
            return
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
                self._handle_start_failure(plugin.manifest.id, runtime.error)
                return
            if runtime is not None and runtime.process is not None:
                self._refresh()
                wx.CallLater(100, self._poll_process_startup, plugin.manifest.id, runtime, 300)
                return
        else:
            self.service.stop(plugin.manifest.id)
        wx.MessageBox(_("A alteração foi aplicada."), _("Plugins"), wx.OK | wx.ICON_INFORMATION, self)

    def _poll_process_startup(self, plugin_id, runtime, attempts):
        try:
            if not self.IsShown():
                return
        except RuntimeError:
            return
        if runtime.ready.is_set():
            self._refresh()
            wx.MessageBox(_("O plugin foi ativado."), _("Plugins"), wx.OK | wx.ICON_INFORMATION, self)
            return
        if runtime.error or runtime.process is None or runtime.process.poll() is not None:
            self._handle_start_failure(plugin_id, runtime.error or _("O processo terminou durante a inicialização."))
            return
        if attempts <= 0:
            self._handle_start_failure(plugin_id, _("O plugin não concluiu a inicialização em 30 segundos."))
            return
        wx.CallLater(100, self._poll_process_startup, plugin_id, runtime, attempts - 1)

    def _handle_start_failure(self, plugin_id, error):
        self.service.stop(plugin_id)
        self.service.registry.update(plugin_id, enabled=False, granted_permissions=())
        self._refresh()
        wx.MessageBox(
            _("O plugin não iniciou e voltou a ficar desativado: {error}").format(error=error),
            _("Plugins"), wx.OK | wx.ICON_ERROR, self,
        )

    def _confirm_installation(self, manifest, source):
        dialog = InstallationConfirmationDialog(self, manifest, source)
        try:
            return dialog.ShowModal() == wx.ID_OK
        finally:
            dialog.Destroy()

    def _install_and_activate(self, package, *, source, expected_sha256=None, expected_plugin_id=None, expected_version=None):
        pending_manifest = inspect_archive(package)
        if not self._require_closed_plugin_screens(pending_manifest.id):
            return None
        if not self._confirm_installation(pending_manifest, source):
            return None
        self.service.stop(pending_manifest.id)
        manifest = install_archive(
            package,
            self.service.plugins_dir,
            expected_sha256=expected_sha256,
            expected_plugin_id=expected_plugin_id,
            expected_version=expected_version,
        )
        self.service.registry.update(manifest.id, enabled=True, granted_permissions=manifest.permissions)
        self._refresh()
        installed = next((item for item in self._plugins if item.manifest.id == manifest.id), None)
        runtime = self.service.start(installed) if installed else None
        if runtime is not None and runtime.error:
            self._handle_start_failure(manifest.id, runtime.error)
            return None
        if runtime is not None and runtime.process is not None:
            self._refresh()
            wx.CallLater(100, self._poll_process_startup, manifest.id, runtime, 300)
            return manifest
        wx.MessageBox(
            _("{name} foi instalado e ativado.").format(name=manifest.name),
            _("Plugins"), wx.OK | wx.ICON_INFORMATION, self,
        )
        return manifest

    def _on_permissions(self, _event):
        plugin = self._selected()
        if plugin: wx.MessageBox(permission_summary(plugin.manifest), _("Permissões do plugin"), wx.OK | wx.ICON_INFORMATION, self)

    def _on_install(self, _event):
        chooser = wx.FileDialog(self, _("Instalar pacote de plugin"), wildcard=_("Plugin do KeyTune (*.ktplugin)|*.ktplugin|Todos os arquivos|*.*"), style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        try:
            if chooser.ShowModal() != wx.ID_OK: return
            self._install_and_activate(chooser.GetPath(), source=_("Pacote local selecionado"))
        except Exception as exc:
            wx.MessageBox(_("Não foi possível instalar o plugin: {error}").format(error=exc), _("Plugins"), wx.OK | wx.ICON_ERROR, self); return
        finally: chooser.Destroy()

    def _on_marketplace(self, _event):
        self.marketplace.Disable()
        threading.Thread(target=self._load_marketplace, daemon=True).start()

    def _on_remove(self, _event):
        plugin = self._selected()
        if not plugin:
            return
        if not self._require_closed_plugin_screens(plugin.manifest.id):
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
            review = _("verificado") if item.verified else _("não verificado")
            choices.append(f"{item.name} {item.version} — {item.author} — {review}{status}")
        dialog = wx.SingleChoiceDialog(self, _("Escolha um plugin. Pacotes são verificados por SHA-256 antes da instalação."), _("Marketplace de plugins"), choices)
        try:
            if dialog.ShowModal() != wx.ID_OK: return
            entry = entries[dialog.GetSelection()]
        finally: dialog.Destroy()
        if not self._require_closed_plugin_screens(entry.id):
            return
        self.marketplace.Disable(); threading.Thread(target=self._download_entry, args=(entry,), daemon=True).start()

    def _download_entry(self, entry):
        package = None
        try:
            with tempfile.NamedTemporaryFile(prefix="keytune-plugin-", suffix=".ktplugin", delete=False) as stream:
                package = Path(stream.name)
            download_package(entry.download_url, package)
            manifest = inspect_archive(package)
            if manifest.id != entry.id or manifest.version != entry.version:
                raise InstallationError(_("O pacote não corresponde ao plugin selecionado no marketplace."))
        except Exception as exc:
            if package is not None:
                package.unlink(missing_ok=True)
            wx.CallAfter(self._show_marketplace_error, str(exc)); return
        wx.CallAfter(self._confirm_marketplace_install, entry, package)

    def _confirm_marketplace_install(self, entry, package):
        source = _("Marketplace verificado") if entry.verified else _("Marketplace não verificado")
        try:
            self._install_and_activate(
                package,
                source=source,
                expected_sha256=entry.sha256,
                expected_plugin_id=entry.id,
                expected_version=entry.version,
            )
        except Exception as exc:
            wx.MessageBox(_("Não foi possível instalar o plugin: {error}").format(error=exc), _("Marketplace de plugins"), wx.OK | wx.ICON_ERROR, self)
        finally:
            package.unlink(missing_ok=True)
            self.marketplace.Enable()
