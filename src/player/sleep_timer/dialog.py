import wx

from ..constants import (
    SLEEP_TIMER_DEFAULT_MINUTES,
    SLEEP_TIMER_MAX_MINUTES,
    SLEEP_TIMER_MIN_MINUTES,
    SLEEP_TIMER_MODE_COUNTDOWN,
    SLEEP_TIMER_MODE_END_OF_TRACK,
    SLEEP_TIMER_MODE_OFF,
    SLEEP_TIMER_PRESET_MINUTES,
)
from ..i18n import _


SLEEP_TIMER_DIALOG_TITLE = _("Temporizador")

_CHOICE_END_OF_TRACK = "end_of_track"
_CHOICE_CUSTOM = "custom"
_CHOICE_OFF = "off"


class SleepTimerDialog(wx.Dialog):
    """Escolhe como o temporizador deve encerrar a reprodução.

    Devolve ``(mode, minutes)``: uma das durações predefinidas, um tempo
    personalizado, o fim da faixa atual ou o cancelamento do temporizador.
    """

    def __init__(self, parent, current_mode=SLEEP_TIMER_MODE_OFF, current_minutes=None, status_label=""):
        super().__init__(parent, title=SLEEP_TIMER_DIALOG_TITLE)

        self._options = [(str(minutes), minutes) for minutes in SLEEP_TIMER_PRESET_MINUTES]
        self._options.append((_CHOICE_END_OF_TRACK, None))
        self._options.append((_CHOICE_CUSTOM, None))
        self._options.append((_CHOICE_OFF, None))

        choices = [
            _("{minutes} minutos").format(minutes=minutes) for minutes in SLEEP_TIMER_PRESET_MINUTES
        ]
        choices.append(_("Ao fim da faixa atual"))
        choices.append(_("Tempo personalizado (minutos)"))
        choices.append(_("Não usar temporizador"))

        root_sizer = wx.BoxSizer(wx.VERTICAL)

        description = wx.StaticText(
            self,
            label=status_label
            or _("Escolha quando o KeyTune deve pausar a reprodução automaticamente."),
        )
        description.Wrap(420)

        self.mode_radio = wx.RadioBox(
            self,
            label=_("Encerrar a reprodução"),
            choices=choices,
            majorDimension=1,
            style=wx.RA_SPECIFY_COLS,
        )
        self.mode_radio.SetName(_("Encerrar a reprodução"))

        custom_label = wx.StaticText(self, label=_("&Minutos personalizados"))
        self.custom_spin = wx.SpinCtrl(
            self,
            min=SLEEP_TIMER_MIN_MINUTES,
            max=SLEEP_TIMER_MAX_MINUTES,
            initial=int(current_minutes or SLEEP_TIMER_DEFAULT_MINUTES),
        )
        self.custom_spin.SetName(_("Minutos personalizados"))

        button_sizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        if button_sizer is not None:
            ok_button = self.FindWindow(wx.ID_OK)
            if ok_button is not None:
                ok_button.SetLabel(_("&Aplicar"))
            cancel_button = self.FindWindow(wx.ID_CANCEL)
            if cancel_button is not None:
                cancel_button.SetLabel(_("&Cancelar"))

        root_sizer.Add(description, 0, wx.ALL | wx.EXPAND, 12)
        root_sizer.Add(self.mode_radio, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 12)
        root_sizer.Add(custom_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        root_sizer.Add(self.custom_spin, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM, 12)
        if button_sizer is not None:
            root_sizer.Add(button_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, 12)

        self.SetSizerAndFit(root_sizer)
        self.SetEscapeId(wx.ID_CANCEL)
        self.CentreOnParent()

        self.mode_radio.Bind(wx.EVT_RADIOBOX, self._on_mode_changed)

        self._select_initial_option(current_mode, current_minutes)
        self._refresh_custom_state()
        self.mode_radio.SetFocus()

    def get_selection(self):
        """Devolve ``(mode, minutes)`` conforme a opção escolhida."""
        selection = self.mode_radio.GetSelection()
        if selection == wx.NOT_FOUND:
            return SLEEP_TIMER_MODE_OFF, None

        kind, minutes = self._options[selection]
        if kind == _CHOICE_END_OF_TRACK:
            return SLEEP_TIMER_MODE_END_OF_TRACK, None
        if kind == _CHOICE_OFF:
            return SLEEP_TIMER_MODE_OFF, None
        if kind == _CHOICE_CUSTOM:
            return SLEEP_TIMER_MODE_COUNTDOWN, int(self.custom_spin.GetValue())
        return SLEEP_TIMER_MODE_COUNTDOWN, int(minutes)

    def _select_initial_option(self, current_mode, current_minutes):
        if current_mode == SLEEP_TIMER_MODE_END_OF_TRACK:
            self.mode_radio.SetSelection(len(SLEEP_TIMER_PRESET_MINUTES))
            return

        if current_mode == SLEEP_TIMER_MODE_COUNTDOWN and current_minutes:
            for index, minutes in enumerate(SLEEP_TIMER_PRESET_MINUTES):
                if minutes == current_minutes:
                    self.mode_radio.SetSelection(index)
                    return
            # Duração fora dos presets: volta como tempo personalizado.
            self.mode_radio.SetSelection(len(SLEEP_TIMER_PRESET_MINUTES) + 1)
            return

        default_index = 0
        for index, minutes in enumerate(SLEEP_TIMER_PRESET_MINUTES):
            if minutes == SLEEP_TIMER_DEFAULT_MINUTES:
                default_index = index
                break
        self.mode_radio.SetSelection(default_index)

    def _on_mode_changed(self, _event):
        self._refresh_custom_state()

    def _refresh_custom_state(self):
        selection = self.mode_radio.GetSelection()
        is_custom = (
            selection != wx.NOT_FOUND and self._options[selection][0] == _CHOICE_CUSTOM
        )
        self.custom_spin.Enable(is_custom)
