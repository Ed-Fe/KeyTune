"""Compact controls and status for an AutoDJ playlist tab."""

import wx

from ..accessibility import attach_named_accessible
from ..i18n import _


class AutoDJSessionPanel(wx.Panel):
    def __init__(
        self,
        parent,
        *,
        on_replace_next,
        on_recalculate,
        on_toggle_preparation,
        on_stop,
    ):
        super().__init__(parent, style=wx.TAB_TRAVERSAL)

        self.info_ctrl = wx.TextCtrl(
            self,
            value="",
            style=wx.TE_READONLY | wx.TE_MULTILINE,
        )
        self.info_ctrl.SetName(_("Informações da sessão AutoDJ"))
        self.info_ctrl.SetToolTip(_("Resume o estado da sessão e informa como será a próxima transição."))
        attach_named_accessible(
            self.info_ctrl,
            name=_("Informações da sessão AutoDJ"),
            description=_("Resume o estado da sessão e informa como será a próxima transição."),
            value_provider=lambda: self.info_ctrl.GetValue(),
        )
        self.info_ctrl.SetMinSize((-1, 88))

        self.replace_next_button = wx.Button(self, label=_("Trocar pró&xima"))
        self.recalculate_button = wx.Button(self, label=_("&Recalcular sequência"))
        self.toggle_preparation_button = wx.Button(self, label=_("&Pausar preparação"))
        self.stop_button = wx.Button(self, label=_("&Encerrar AutoDJ"))

        for button, name, description in (
            (self.replace_next_button, _("Trocar próxima faixa do AutoDJ"), _("Escolhe outra faixa preparada para a próxima transição.")),
            (self.recalculate_button, _("Recalcular sequência do AutoDJ"), _("Descarta a sequência preparada e calcula uma nova ordem de reprodução.")),
            (self.toggle_preparation_button, _("Pausar preparação do AutoDJ"), _("Interrompe temporariamente a análise e preparação de novas faixas.")),
            (self.stop_button, _("Encerrar AutoDJ e manter sequência"), _("Encerra o AutoDJ sem remover as músicas que já foram preparadas.")),
        ):
            button.SetName(name)
            button.SetToolTip(description)

        self.replace_next_button.Bind(wx.EVT_BUTTON, on_replace_next)
        self.recalculate_button.Bind(wx.EVT_BUTTON, on_recalculate)
        self.toggle_preparation_button.Bind(wx.EVT_BUTTON, on_toggle_preparation)
        self.stop_button.Bind(wx.EVT_BUTTON, on_stop)

        controls = wx.GridSizer(rows=0, cols=2, vgap=4, hgap=4)
        for button in self.action_controls():
            controls.Add(button, 0, wx.EXPAND)

        sizer = wx.StaticBoxSizer(wx.StaticBox(self, label=_("Sessão AutoDJ")), wx.VERTICAL)
        sizer.Add(self.info_ctrl, 0, wx.ALL | wx.EXPAND, 6)
        sizer.Add(controls, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
        self.SetSizer(sizer)
        self.Hide()

    def update_session(
        self,
        *,
        visible,
        summary="",
        details="",
        preparation_paused=False,
        can_replace_next=False,
        can_recalculate=False,
    ):
        information = "\r\n".join(part for part in (summary, details) if part)
        if self.info_ctrl.GetValue() != information:
            self.info_ctrl.ChangeValue(information)
            if wx.Window.FindFocus() is not self.info_ctrl:
                self.info_ctrl.SetInsertionPoint(0)
        self.replace_next_button.Enable(can_replace_next)
        self.recalculate_button.Enable(can_recalculate)
        if preparation_paused:
            self.toggle_preparation_button.SetLabel(_("&Retomar preparação"))
            self.toggle_preparation_button.SetName(_("Retomar preparação do AutoDJ"))
            self.toggle_preparation_button.SetToolTip(_("Retoma a análise e preparação de novas faixas."))
        else:
            self.toggle_preparation_button.SetLabel(_("&Pausar preparação"))
            self.toggle_preparation_button.SetName(_("Pausar preparação do AutoDJ"))
            self.toggle_preparation_button.SetToolTip(_("Interrompe temporariamente a análise e preparação de novas faixas."))
        changed = self.IsShown() != bool(visible)
        self.Show(bool(visible))
        self.Layout()
        if changed and self.GetParent():
            self.GetParent().Layout()

    def action_controls(self):
        return [
            self.replace_next_button,
            self.recalculate_button,
            self.toggle_preparation_button,
            self.stop_button,
        ]

    def focusable_controls(self):
        return [self.info_ctrl, *self.action_controls()]

    def contains_focus(self):
        focused = wx.Window.FindFocus()
        return focused in self.focusable_controls()

    def focus_first_control(self):
        for control in self.focusable_controls():
            if control.IsEnabled() and control.IsShownOnScreen():
                control.SetFocus()
                return True
        return False

    def focus_last_control(self):
        for control in reversed(self.focusable_controls()):
            if control.IsEnabled() and control.IsShownOnScreen():
                control.SetFocus()
                return True
        return False

    def focus_adjacent_control(self, *, backward=False):
        controls = [control for control in self.focusable_controls() if control.IsEnabled() and control.IsShownOnScreen()]
        focused = wx.Window.FindFocus()
        if focused not in controls:
            return False
        target_index = controls.index(focused) + (-1 if backward else 1)
        if not 0 <= target_index < len(controls):
            return False
        controls[target_index].SetFocus()
        return True
