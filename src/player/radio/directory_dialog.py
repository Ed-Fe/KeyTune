"""Caixa para publicar uma rádio no diretório público do Radio Browser."""

import wx

from ..i18n import _
from ..reading_dialog import add_reading_field
from ..widgets import ROW_BORDER, add_labeled_row, create_group, describe_control, equalize_row_controls
from .submission import (
    DIRECTORY_NAME_LIMIT,
    RadioDirectorySubmission,
    directory_submission_preview,
    validate_directory_submission,
)

ADD_RADIO_TO_DIRECTORY_DIALOG_TITLE = _("Adicionar rádio ao diretório")


class ConfirmRadioDirectoryDialog(wx.Dialog):
    """Relê, linha a linha, o que será publicado. Não é o padrão; Enter no texto não publica."""

    def __init__(self, parent, text=""):
        super().__init__(
            parent,
            title=_("Publicar no diretório"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        root = wx.BoxSizer(wx.VERTICAL)
        question = wx.StaticText(self, label=_("Publicar no diretório?"))
        root.Add(question, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 12)

        self.reading_ctrl = add_reading_field(self, root, _("&Dados do cadastro"), text)
        self.reading_ctrl.SetMinSize(self.FromDIP(wx.Size(480, 220)))

        yes_button = wx.Button(self, wx.ID_YES, _("&Sim"))
        no_button = wx.Button(self, wx.ID_NO, _("&Não"))
        no_button.SetDefault()
        yes_button.Bind(wx.EVT_BUTTON, lambda _event: self.EndModal(wx.ID_YES))
        no_button.Bind(wx.EVT_BUTTON, lambda _event: self.EndModal(wx.ID_NO))
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        buttons.Add(yes_button, 0, wx.RIGHT, 8)
        buttons.Add(no_button, 0)
        root.Add(buttons, 0, wx.ALL | wx.ALIGN_RIGHT, 12)

        self.SetEscapeId(wx.ID_NO)
        self.SetSizer(root)
        equalize_row_controls(self)
        self.SetMinSize(self.FromDIP(wx.Size(420, 280)))
        display_index = wx.Display.GetFromWindow(parent) if parent is not None else 0
        display_size = wx.Display(max(display_index, 0)).GetClientArea().GetSize()
        wanted = self.FromDIP(wx.Size(520, 380))
        self.SetSize((min(wanted.width, display_size.width), min(wanted.height, display_size.height)))
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        self.Bind(wx.EVT_SHOW, self._on_show)
        self.reading_ctrl.SetFocus()
        self.reading_ctrl.SetInsertionPoint(0)
        self.CentreOnParent()

    def _on_show(self, event):
        if event.IsShown():
            self.reading_ctrl.SetFocus()
            self.reading_ctrl.SetInsertionPoint(0)
        event.Skip()

    def _on_char_hook(self, event):
        if (
            event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER)
            and not event.HasAnyModifiers()
            and self.FindFocus() is self.reading_ctrl
        ):
            return
        event.Skip()


def _add_text_field(parent, sizer, label_text, help_text, value=""):
    label = wx.StaticText(parent, label=f"{label_text}:")
    control = wx.TextCtrl(parent, value=value)
    # Nome igual ao rótulo, com os dois-pontos: se diferir, o NVDA lê o rótulo
    # também na descrição do diálogo.
    describe_control(control, label.GetLabelText(), help_text)
    sizer.Add(label, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, ROW_BORDER)
    sizer.Add(control, 0, wx.ALL | wx.EXPAND, ROW_BORDER)
    return control


class AddRadioToDirectoryDialog(wx.Dialog):
    """Nome, stream e os dados opcionais de uma rádio a publicar no diretório."""

    def __init__(self, parent, initial=None):
        super().__init__(
            parent,
            title=ADD_RADIO_TO_DIRECTORY_DIALOG_TITLE,
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        initial = initial or RadioDirectorySubmission(name="", url="")
        self.submission = None

        root = wx.BoxSizer(wx.VERTICAL)
        intro = wx.StaticText(self, label=_("O cadastro é público e o KeyTune não pode desfazê-lo."))
        intro.Wrap(self.FromDIP(440))
        root.Add(intro, 0, wx.ALL | wx.EXPAND, 12)

        scrolled = wx.ScrolledWindow(self, style=wx.TAB_TRAVERSAL | wx.VSCROLL)
        scrolled.SetScrollRate(0, self.FromDIP(16))
        form = wx.BoxSizer(wx.VERTICAL)
        self._scrolled = scrolled

        station_box, station_sizer = create_group(scrolled, _("Estação"))
        self.name_ctrl = _add_text_field(
            station_box,
            station_sizer,
            _("&Nome"),
            _("Até {limit} caracteres.").format(limit=DIRECTORY_NAME_LIMIT),
            initial.name,
        )
        self.url_ctrl = _add_text_field(
            station_box,
            station_sizer,
            _("&Endereço do stream"),
            _("Começa com http:// ou https://."),
            initial.url,
        )
        form.Add(station_sizer, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 8)

        class_box, class_sizer = create_group(scrolled, _("Classificação"))
        country_label = wx.StaticText(class_box, label=_("Código do &país:"))
        self.country_ctrl = wx.TextCtrl(class_box, value=str(initial.country_code or "").strip().upper())
        self.country_ctrl.SetMinSize(self.FromDIP(wx.Size(72, -1)))
        describe_control(
            self.country_ctrl,
            country_label.GetLabelText(),
            _("Duas letras, como BR, ou em branco."),
        )
        add_labeled_row(class_sizer, country_label, self.country_ctrl)
        self.language_ctrl = _add_text_field(
            class_box,
            class_sizer,
            _("Códigos de &idioma"),
            _("Separados por vírgula, como pt,en."),
            initial.language_codes,
        )
        self.tags_ctrl = _add_text_field(
            class_box,
            class_sizer,
            _("&Gêneros"),
            _("Separados por vírgula, como rock, jazz."),
            initial.tags,
        )
        form.Add(class_sizer, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 8)

        links_box, links_sizer = create_group(scrolled, _("Site e ícone"))
        self.homepage_ctrl = _add_text_field(
            links_box,
            links_sizer,
            _("&Site"),
            _("Página http ou https. Pode ficar em branco."),
            initial.homepage,
        )
        self.favicon_ctrl = _add_text_field(
            links_box,
            links_sizer,
            _("En&dereço do ícone"),
            _("Imagem http ou https. Pode ficar em branco."),
            initial.favicon,
        )
        form.Add(links_sizer, 0, wx.ALL | wx.EXPAND, 8)

        self._fields = {
            "name": self.name_ctrl,
            "url": self.url_ctrl,
            "country_code": self.country_ctrl,
            "homepage": self.homepage_ctrl,
            "favicon": self.favicon_ctrl,
        }

        scrolled.SetSizer(form)
        scrolled.SetMinSize(self.FromDIP(wx.Size(440, 320)))
        root.Add(scrolled, 1, wx.LEFT | wx.RIGHT | wx.EXPAND, 12)

        button_sizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        ok_button = self.FindWindow(wx.ID_OK)
        if ok_button is not None:
            ok_button.SetLabel(_("&OK"))
            ok_button.SetDefault()
            ok_button.Bind(wx.EVT_BUTTON, self._on_confirm)
        cancel_button = self.FindWindow(wx.ID_CANCEL)
        if cancel_button is not None:
            cancel_button.SetLabel(_("&Cancelar"))
        if button_sizer is not None:
            root.Add(button_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 12)

        self.SetSizer(root)
        equalize_row_controls(self)
        self.SetMinSize(self.FromDIP(wx.Size(420, 320)))
        display_index = wx.Display.GetFromWindow(parent) if parent is not None else 0
        display_size = wx.Display(max(display_index, 0)).GetClientArea().GetSize()
        wanted = self.FromDIP(wx.Size(500, 560))
        self.SetSize((min(wanted.width, display_size.width), min(wanted.height, display_size.height)))
        self.SetEscapeId(wx.ID_CANCEL)
        self.CentreOnParent()
        # Sem isto o wx não enxerga os campos dentro da área rolável e foca o OK.
        self.name_ctrl.SetFocus()

    def _focus_field(self, field):
        control = self._fields.get(field)
        if control is None:
            return
        control.SetFocus()
        if hasattr(self._scrolled, "ScrollChildIntoView"):
            self._scrolled.ScrollChildIntoView(control)

    def _confirm_publish(self, submission):
        dialog = ConfirmRadioDirectoryDialog(self, directory_submission_preview(submission))
        try:
            return dialog.ShowModal() == wx.ID_YES
        finally:
            dialog.Destroy()

    def _on_confirm(self, _event):
        submission, field, message = validate_directory_submission(
            name=self.name_ctrl.GetValue(),
            url=self.url_ctrl.GetValue(),
            country_code=self.country_ctrl.GetValue(),
            language_codes=self.language_ctrl.GetValue(),
            tags=self.tags_ctrl.GetValue(),
            homepage=self.homepage_ctrl.GetValue(),
            favicon=self.favicon_ctrl.GetValue(),
        )
        if submission is None:
            wx.MessageBox(message, _("Cadastro incompleto"), wx.OK | wx.ICON_WARNING, self)
            self._focus_field(field)
            return
        if not self._confirm_publish(submission):
            return
        self.submission = submission
        if self.IsModal():
            self.EndModal(wx.ID_OK)
            return
        self.SetReturnCode(wx.ID_OK)
        self.Show(False)
