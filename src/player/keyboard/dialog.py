"""Tela «Personalizar teclado»: atalhos da janela do player e atalhos globais."""

from __future__ import annotations

import wx

from ..accessibility import attach_named_accessible
from ..i18n import _
from ..widgets import ROW_BORDER, describe_control
from .shortcuts import (
    SCOPE_GLOBAL,
    SCOPE_LOCAL,
    action_by_id,
    actions,
    category_label,
    effective_bindings,
    find_conflicts,
    format_shortcut,
    normalize_shortcut,
    overrides_from_bindings,
    shortcut_problem,
)
from .wx_keys import MODIFIER_KEY_CODES, shortcut_from_key_event


def _announce(window, message):
    """Fala pelo leitor de tela da janela principal, se houver uma."""
    top = window.GetParent()
    while top is not None and not hasattr(top, "_announce"):
        top = top.GetParent()
    if top is not None:
        top._announce(message)


class ShortcutCaptureDialog(wx.Dialog):
    """Captura uma combinação de teclas para uma ação.

    O campo recebe as teclas como são pressionadas; Tab, Shift+Tab e Esc
    continuam navegando, e Enter sem modificador confirma.
    """

    def __init__(self, parent, action_label, current_shortcut, scope=SCOPE_LOCAL, menu_shortcuts=()):
        super().__init__(parent, title=_("Alterar atalho"))
        self._scope = scope
        self._menu_shortcuts = frozenset(menu_shortcuts)
        self._shortcut = normalize_shortcut(current_shortcut)

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        label = wx.StaticText(panel, label=_("Pressione o novo atalho para «{action}»:").format(action=action_label))
        # Sem TE_READONLY: no Windows um campo de uma linha somente leitura sai
        # da ordem do Tab. A digitação é barrada em ``_on_capture_char``.
        self.capture_ctrl = wx.TextCtrl(panel)
        capture_name = _("Novo atalho")
        capture_help = _("Tab sai do campo, Enter confirma e Esc cancela.")
        self.capture_ctrl.SetName(capture_name)
        self.capture_ctrl.SetToolTip(capture_help)
        self.capture_ctrl.SetHelpText(capture_help)
        attach_named_accessible(
            self.capture_ctrl,
            name=capture_name,
            description=capture_help,
            role=wx.ROLE_SYSTEM_HOTKEYFIELD,
            value_provider=self.capture_ctrl.GetValue,
        )
        self.capture_ctrl.ChangeValue(format_shortcut(self._shortcut) or _("Nenhum"))
        self.capture_ctrl.SetMinSize(self.FromDIP(wx.Size(320, -1)))
        sizer.Add(label, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 10)
        sizer.Add(self.capture_ctrl, 0, wx.ALL | wx.EXPAND, 10)

        self.status_label = wx.StaticText(panel, label="")
        sizer.Add(self.status_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

        buttons = wx.StdDialogButtonSizer()
        self.ok_button = wx.Button(panel, wx.ID_OK, _("&Confirmar"))
        cancel_button = wx.Button(panel, wx.ID_CANCEL, _("Ca&ncelar"))
        self.ok_button.SetDefault()
        buttons.AddButton(self.ok_button)
        buttons.AddButton(cancel_button)
        buttons.Realize()
        sizer.Add(buttons, 0, wx.ALL | wx.EXPAND, 10)

        panel.SetSizer(sizer)
        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizerAndFit(frame_sizer)
        self.SetEscapeId(wx.ID_CANCEL)

        self.capture_ctrl.Bind(wx.EVT_CHAR_HOOK, self._on_capture_key)
        self.capture_ctrl.Bind(wx.EVT_CHAR, self._on_capture_char)
        for blocked in (wx.EVT_TEXT_PASTE, wx.EVT_TEXT_CUT):
            self.capture_ctrl.Bind(blocked, lambda _event: None)
        self.ok_button.Bind(wx.EVT_BUTTON, self._on_ok)
        self._refresh_status(announce=False)
        self.CentreOnParent()

    @property
    def shortcut(self):
        return self._shortcut

    def _on_capture_char(self, event):
        # O campo mostra o atalho capturado; nada é digitado nele.
        if event.GetKeyCode() == wx.WXK_TAB:
            event.Skip()

    def _on_capture_key(self, event):
        key_code = event.GetKeyCode()
        if key_code == wx.WXK_TAB and not event.ControlDown() and not event.AltDown():
            event.Skip()
            return
        if key_code == wx.WXK_ESCAPE and not event.HasAnyModifiers():
            event.Skip()
            return
        if key_code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and not event.HasAnyModifiers():
            self._on_ok(None)
            return
        shortcut = shortcut_from_key_event(event, allow_win=self._scope == SCOPE_GLOBAL)
        if not shortcut:
            # Um modificador sozinho espera a tecla que completa o atalho; uma
            # tecla que não serve (teclado numérico, mídia, acentos) é avisada.
            if key_code not in MODIFIER_KEY_CODES and key_code not in (0, wx.WXK_NONE):
                text = _("Esta tecla não pode ser usada em atalhos.")
                self._show_status(text)
                _announce(self, text)
            return
        self._shortcut = shortcut
        self.capture_ctrl.ChangeValue(format_shortcut(shortcut))
        self.capture_ctrl.SelectAll()
        self._refresh_status(announce=True)

    def _problem(self):
        if not self._shortcut:
            return _("Pressione uma combinação de teclas.")
        if self._shortcut in self._menu_shortcuts:
            return _("{shortcut} abre um menu do KeyTune.").format(shortcut=format_shortcut(self._shortcut))
        return shortcut_problem(self._shortcut, self._scope)

    def _show_status(self, text):
        self.status_label.SetLabel(text)
        self.status_label.Wrap(self.FromDIP(320))
        self.Layout()
        self.Fit()

    def _refresh_status(self, *, announce):
        problem = self._problem()
        text = problem or _("{shortcut}. Enter confirma.").format(shortcut=format_shortcut(self._shortcut))
        self.ok_button.Enable(not problem)
        self._show_status(text)
        if announce:
            _announce(self, text)

    def _on_ok(self, _event):
        problem = self._problem()
        if problem:
            _announce(self, problem)
            return
        self.EndModal(wx.ID_OK)


class _ShortcutPage:
    """Filtro e lista de ações de um escopo, dentro de uma aba do diálogo."""

    def __init__(self, dialog, page, sizer, scope, bindings, filter_label, list_label):
        self.dialog = dialog
        self.scope = scope
        self.bindings = dict(bindings)
        self.visible_ids = []

        label = wx.StaticText(page, label=filter_label)
        self.filter_ctrl = wx.TextCtrl(page)
        describe_control(
            self.filter_ctrl,
            filter_label.replace("&", "").rstrip(":"),
            _("Procura pelo nome da ação, pela categoria ou pelo atalho."),
        )
        sizer.Add(label, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, ROW_BORDER)
        sizer.Add(self.filter_ctrl, 0, wx.ALL | wx.EXPAND, ROW_BORDER)

        list_caption = wx.StaticText(page, label=list_label)
        self.list_ctrl = wx.ListCtrl(page, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        attach_named_accessible(self.list_ctrl, name=list_label.rstrip(":"))
        self.list_ctrl.InsertColumn(0, _("Ação"), width=self.dialog.FromDIP(300))
        self.list_ctrl.InsertColumn(1, _("Atalho"), width=self.dialog.FromDIP(170))
        self.list_ctrl.InsertColumn(2, _("Categoria"), width=self.dialog.FromDIP(170))
        sizer.Add(list_caption, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, ROW_BORDER)
        sizer.Add(self.list_ctrl, 1, wx.ALL | wx.EXPAND, ROW_BORDER)

        self.filter_ctrl.Bind(wx.EVT_TEXT, lambda _event: self.refresh())
        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda _event: self.dialog.change_selected())
        self.list_ctrl.Bind(wx.EVT_KEY_DOWN, self._on_list_key)
        self.refresh()

    def _on_list_key(self, event):
        if event.GetKeyCode() in (wx.WXK_DELETE, wx.WXK_BACK) and not event.HasAnyModifiers():
            self.dialog.remove_selected()
            return
        event.Skip()

    def _matches(self, action, query):
        if not query:
            return True
        haystack = " ".join(
            (action.label, category_label(action.category), format_shortcut(self.bindings.get(action.action_id, "")))
        ).lower()
        return all(word in haystack for word in query.split())

    def refresh(self, select_id=None):
        if select_id is None:
            select_id = self.selected_id()
        query = self.filter_ctrl.GetValue().strip().lower()
        self.list_ctrl.DeleteAllItems()
        self.visible_ids = []
        for action in actions(self.scope):
            if not self._matches(action, query):
                continue
            row = self.list_ctrl.GetItemCount()
            self.list_ctrl.InsertItem(row, action.label)
            self.list_ctrl.SetItem(row, 1, format_shortcut(self.bindings.get(action.action_id, "")) or _("Nenhum"))
            self.list_ctrl.SetItem(row, 2, category_label(action.category))
            self.visible_ids.append(action.action_id)
        if not self.visible_ids:
            return
        row = self.visible_ids.index(select_id) if select_id in self.visible_ids else 0
        self.list_ctrl.SetItemState(row, wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED, wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED)
        self.list_ctrl.EnsureVisible(row)

    def selected_id(self):
        row = self.list_ctrl.GetFirstSelected() if hasattr(self, "list_ctrl") else -1
        if row is None or row < 0 or row >= len(self.visible_ids):
            return None
        return self.visible_ids[row]


class KeyboardCustomizationDialog(wx.Dialog):
    """Lista as ações com seus atalhos e permite trocar, remover ou restaurar cada um."""

    def __init__(
        self,
        parent,
        *,
        local_overrides=None,
        global_overrides=None,
        global_enabled=False,
        global_available=True,
        menu_shortcuts=(),
    ):
        super().__init__(
            parent,
            title=_("Personalizar teclado"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._menu_shortcuts = frozenset(menu_shortcuts)
        panel = wx.Panel(self)
        root = wx.BoxSizer(wx.VERTICAL)

        self.notebook = wx.Notebook(panel)
        self.notebook.SetName(_("Tipos de atalho"))

        local_page = wx.Panel(self.notebook)
        local_sizer = wx.BoxSizer(wx.VERTICAL)
        self.local_page = _ShortcutPage(
            self,
            local_page,
            local_sizer,
            SCOPE_LOCAL,
            effective_bindings(local_overrides, SCOPE_LOCAL),
            _("&Filtrar ações:"),
            _("Atalhos do player:"),
        )
        local_page.SetSizer(local_sizer)
        self.notebook.AddPage(local_page, _("Atalhos do player"), select=True)

        global_page = wx.Panel(self.notebook)
        global_sizer = wx.BoxSizer(wx.VERTICAL)
        self.global_enabled_checkbox = wx.CheckBox(global_page, label=_("Ativar atalhos &globais"))
        describe_control(
            self.global_enabled_checkbox,
            self.global_enabled_checkbox.GetLabelText(),
            _("Funcionam mesmo com o KeyTune minimizado, na bandeja ou com outro programa em foco.")
            if global_available
            else _("Disponível apenas no Windows."),
        )
        self.global_enabled_checkbox.SetValue(bool(global_enabled) and global_available)
        self.global_enabled_checkbox.Enable(global_available)
        global_sizer.Add(self.global_enabled_checkbox, 0, wx.ALL, ROW_BORDER)
        self.global_page = _ShortcutPage(
            self,
            global_page,
            global_sizer,
            SCOPE_GLOBAL,
            effective_bindings(global_overrides, SCOPE_GLOBAL),
            _("Filtrar ações glo&bais:"),
            _("Atalhos globais:"),
        )
        global_page.SetSizer(global_sizer)
        self.notebook.AddPage(global_page, _("Atalhos globais"))
        root.Add(self.notebook, 1, wx.ALL | wx.EXPAND, 10)

        action_row = wx.BoxSizer(wx.HORIZONTAL)
        self.change_button = wx.Button(panel, label=_("&Alterar atalho..."))
        self.remove_button = wx.Button(panel, label=_("&Remover atalho"))
        self.restore_button = wx.Button(panel, label=_("Restaurar &padrão"))
        self.restore_all_button = wx.Button(panel, label=_("Restaurar t&odos"))
        describe_control(self.change_button, self.change_button.GetLabelText(), _("Enter na lista faz o mesmo."))
        describe_control(self.remove_button, self.remove_button.GetLabelText(), _("Delete na lista faz o mesmo."))
        describe_control(
            self.restore_all_button,
            self.restore_all_button.GetLabelText(),
            _("Volta todos os atalhos da aba atual ao padrão."),
        )
        for button in (self.change_button, self.remove_button, self.restore_button, self.restore_all_button):
            action_row.Add(button, 0, wx.RIGHT, 6)
        root.Add(action_row, 0, wx.LEFT | wx.RIGHT, 10)

        buttons = wx.StdDialogButtonSizer()
        self.save_button = wx.Button(panel, wx.ID_OK, _("&Salvar"))
        cancel_button = wx.Button(panel, wx.ID_CANCEL, _("&Cancelar"))
        self.save_button.SetDefault()
        buttons.AddButton(self.save_button)
        buttons.AddButton(cancel_button)
        buttons.Realize()
        root.Add(buttons, 0, wx.ALL | wx.EXPAND, 10)

        panel.SetSizer(root)
        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(frame_sizer)
        self.SetMinSize(self.FromDIP(wx.Size(560, 420)))
        self.SetSize(self.FromDIP(wx.Size(720, 560)))
        self.SetEscapeId(wx.ID_CANCEL)
        self.CentreOnParent()

        self.change_button.Bind(wx.EVT_BUTTON, lambda _event: self.change_selected())
        self.remove_button.Bind(wx.EVT_BUTTON, lambda _event: self.remove_selected())
        self.restore_button.Bind(wx.EVT_BUTTON, lambda _event: self.restore_selected())
        self.restore_all_button.Bind(wx.EVT_BUTTON, self._on_restore_all)

    # ------------------------------------------------------------------
    # Resultado
    # ------------------------------------------------------------------
    def get_local_overrides(self):
        return overrides_from_bindings(self.local_page.bindings, SCOPE_LOCAL)

    def get_global_overrides(self):
        return overrides_from_bindings(self.global_page.bindings, SCOPE_GLOBAL)

    def get_global_enabled(self):
        return self.global_enabled_checkbox.GetValue()

    # ------------------------------------------------------------------
    # Ações sobre a aba atual
    # ------------------------------------------------------------------
    def _current_page(self):
        return self.global_page if self.notebook.GetSelection() == 1 else self.local_page

    def _selected(self):
        page = self._current_page()
        action_id = page.selected_id()
        if action_id is None:
            _announce(self, _("Nenhuma ação selecionada."))
            return page, None
        return page, action_by_id(action_id, page.scope)

    def _set_binding(self, page, action, shortcut):
        page.bindings[action.action_id] = shortcut
        page.refresh(select_id=action.action_id)
        page.list_ctrl.SetFocus()

    def change_selected(self):
        page, action = self._selected()
        if action is None:
            return
        dialog = ShortcutCaptureDialog(
            self,
            action.label,
            page.bindings.get(action.action_id, ""),
            page.scope,
            menu_shortcuts=self._menu_shortcuts,
        )
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            shortcut = dialog.shortcut
        finally:
            dialog.Destroy()

        if shortcut == page.bindings.get(action.action_id):
            return
        conflicts = find_conflicts(page.bindings, shortcut, exclude=action.action_id)
        if conflicts:
            other_labels = ", ".join(action_by_id(other, page.scope).label for other in conflicts)
            message = _("{shortcut} já é usado por «{other}». Passar o atalho para «{action}» e deixar «{other}» sem atalho?").format(
                shortcut=format_shortcut(shortcut), other=other_labels, action=action.label
            )
            with wx.MessageDialog(self, message, _("Atalho em uso"), wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION) as confirm:
                if confirm.ShowModal() != wx.ID_YES:
                    return
            for other in conflicts:
                page.bindings[other] = ""
        self._set_binding(page, action, shortcut)
        _announce(self, _("{action}: {shortcut}").format(action=action.label, shortcut=format_shortcut(shortcut)))

    def remove_selected(self):
        page, action = self._selected()
        if action is None:
            return
        self._set_binding(page, action, "")
        _announce(self, _("{action}: sem atalho").format(action=action.label))

    def restore_selected(self):
        page, action = self._selected()
        if action is None:
            return
        default = normalize_shortcut(action.default)
        conflicts = find_conflicts(page.bindings, default, exclude=action.action_id)
        for other in conflicts:
            page.bindings[other] = ""
        self._set_binding(page, action, default)
        message = _("{action}: {shortcut}").format(action=action.label, shortcut=format_shortcut(default) or _("sem atalho"))
        if conflicts:
            message += ". " + _("Removido de: {others}").format(
                others=", ".join(action_by_id(other, page.scope).label for other in conflicts)
            )
        _announce(self, message)

    def _on_restore_all(self, _event):
        page = self._current_page()
        with wx.MessageDialog(
            self,
            _("Voltar todos os atalhos desta aba ao padrão?"),
            _("Restaurar todos"),
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
        ) as confirm:
            if confirm.ShowModal() != wx.ID_YES:
                return
        page.bindings = effective_bindings({}, page.scope)
        page.refresh()
        _announce(self, _("Atalhos restaurados ao padrão."))
