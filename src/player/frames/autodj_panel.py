"""Compact controls and status for an AutoDJ playlist tab."""

import wx

from ..i18n import _


class AutoDJSessionPanel(wx.Panel):
    def __init__(
        self,
        parent,
        *,
        on_replace_next,
        on_recalculate,
        on_add_media,
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
        self.info_ctrl.SetMinSize((-1, 88))

        self.replace_next_button = wx.Button(self, label=_("Trocar pró&xima"))
        self.recalculate_button = wx.Button(self, label=_("&Recalcular sequência"))
        self.add_media_button = wx.Button(self, label=_("&Adicionar músicas"))
        self.toggle_preparation_button = wx.Button(self, label=_("&Pausar preparação"))
        self.stop_button = wx.Button(self, label=_("&Encerrar AutoDJ"))

        self.replace_next_button.SetName(_("Trocar próxima faixa do AutoDJ"))
        self.recalculate_button.SetName(_("Recalcular sequência do AutoDJ"))
        self.add_media_button.SetName(_("Adicionar músicas à sessão AutoDJ"))
        self.toggle_preparation_button.SetName(_("Pausar preparação do AutoDJ"))
        self.stop_button.SetName(_("Encerrar AutoDJ e manter sequência"))

        self.replace_next_button.Bind(wx.EVT_BUTTON, on_replace_next)
        self.recalculate_button.Bind(wx.EVT_BUTTON, on_recalculate)
        self.add_media_button.Bind(wx.EVT_BUTTON, on_add_media)
        self.toggle_preparation_button.Bind(wx.EVT_BUTTON, on_toggle_preparation)
        self.stop_button.Bind(wx.EVT_BUTTON, on_stop)

        controls = wx.GridSizer(rows=0, cols=2, vgap=4, hgap=4)
        for button in self.action_controls():
            controls.Add(button, 0, wx.EXPAND)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.info_ctrl, 0, wx.BOTTOM | wx.EXPAND, 6)
        sizer.Add(controls, 0, wx.EXPAND)
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
        else:
            self.toggle_preparation_button.SetLabel(_("&Pausar preparação"))
            self.toggle_preparation_button.SetName(_("Pausar preparação do AutoDJ"))
        changed = self.IsShown() != bool(visible)
        self.Show(bool(visible))
        self.Layout()
        if changed and self.GetParent():
            self.GetParent().Layout()

    def action_controls(self):
        return [
            self.replace_next_button,
            self.recalculate_button,
            self.add_media_button,
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
