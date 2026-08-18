"""Caixas das playlists inteligentes: gerenciar a lista e editar uma regra.

O editor é todo por teclado: caixas de seleção, listas de escolha e campos
numéricos, sem construtor visual de regras. Cada campo tem nome acessível e um
texto de ajuda, e o resumo falado no fim descreve a regra em uma frase — para
quem usa leitor de tela, é o jeito mais rápido de conferir o que foi montado.
"""

import wx

from ..accessibility import attach_named_accessible
from ..i18n import _, ngettext
from .smart_playlists import (
    DEFAULT_SMART_PLAYLIST_LIMIT,
    MAX_NOT_PLAYED_DAYS,
    MAX_SMART_PLAYLIST_LIMIT,
    MIN_SMART_PLAYLIST_LIMIT,
    SORT_HIGHEST_RATED,
    SORT_LEAST_RECENTLY_PLAYED,
    SORT_MOST_PLAYED,
    SORT_RANDOM,
    SORT_RECENTLY_PLAYED,
    SORT_TITLE,
    SmartPlaylistRule,
)


SMART_PLAYLIST_MANAGER_TITLE = _("Playlists inteligentes")
SMART_PLAYLIST_EDITOR_TITLE = _("Regra da playlist inteligente")


def sort_order_labels():
    return [
        (SORT_RECENTLY_PLAYED, _("Tocadas mais recentemente")),
        (SORT_LEAST_RECENTLY_PLAYED, _("Sem tocar há mais tempo")),
        (SORT_MOST_PLAYED, _("Mais tocadas")),
        (SORT_HIGHEST_RATED, _("Melhor avaliadas")),
        (SORT_TITLE, _("Ordem alfabética")),
        (SORT_RANDOM, _("Aleatória")),
    ]


def describe_rule(rule):
    """Resume a regra em uma frase, para a lista e para o anúncio falado."""
    if rule is None:
        return ""

    parts = []
    if rule.favorites_only:
        parts.append(_("só favoritos"))
    if rule.minimum_rating > 0:
        parts.append(
            ngettext(
                "pelo menos {count} estrela",
                "pelo menos {count} estrelas",
                rule.minimum_rating,
            ).format(count=rule.minimum_rating)
        )
    if rule.folder_path:
        parts.append(_("na pasta {folder}").format(folder=rule.folder_path))
    if rule.not_played_for_days > 0:
        parts.append(
            ngettext(
                "sem tocar há {count} dia",
                "sem tocar há {count} dias",
                rule.not_played_for_days,
            ).format(count=rule.not_played_for_days)
        )
    if rule.minimum_play_count > 0:
        parts.append(
            ngettext(
                "tocadas ao menos {count} vez",
                "tocadas ao menos {count} vezes",
                rule.minimum_play_count,
            ).format(count=rule.minimum_play_count)
        )
    if not rule.include_never_played:
        parts.append(_("sem as nunca tocadas"))
    if not rule.exclude_remote:
        parts.append(_("incluindo mídias remotas"))

    if not parts:
        parts.append(_("toda a biblioteca"))

    sort_label = dict(sort_order_labels()).get(rule.sort_order, "")
    return _("{criteria}; {sort}; até {limit} itens").format(
        criteria=", ".join(parts),
        sort=sort_label.lower(),
        limit=rule.limit,
    )


class SmartPlaylistEditorDialog(wx.Dialog):
    def __init__(self, parent, rule=None):
        super().__init__(
            parent,
            title=SMART_PLAYLIST_EDITOR_TITLE,
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self._rule = SmartPlaylistRule.from_dict((rule or SmartPlaylistRule()).to_dict())
        self._sort_values = [value for value, _label in sort_order_labels()]

        root_sizer = wx.BoxSizer(wx.VERTICAL)

        description = wx.StaticText(
            self,
            label=_(
                "A lista é montada toda vez que você abre a playlist, então ela acompanha as "
                "mudanças de avaliação e de histórico."
            ),
        )
        description.Wrap(520)

        name_label = wx.StaticText(self, label=_("&Nome da playlist"))
        self.name_text = wx.TextCtrl(self, value=self._rule.name)
        self.name_text.SetName(_("Nome da playlist inteligente"))

        criteria_box = wx.StaticBoxSizer(wx.StaticBox(self, label=_("Critérios")), wx.VERTICAL)

        self.favorites_checkbox = wx.CheckBox(self, label=_("Somente &favoritos"))
        self.favorites_checkbox.SetValue(self._rule.favorites_only)
        self.favorites_checkbox.SetName(_("Somente favoritos"))

        self.remote_checkbox = wx.CheckBox(self, label=_("Incluir mídias &remotas"))
        self.remote_checkbox.SetValue(not self._rule.exclude_remote)
        self.remote_checkbox.SetName(_("Incluir mídias remotas"))

        self.never_played_checkbox = wx.CheckBox(self, label=_("Incluir mídias &nunca tocadas"))
        self.never_played_checkbox.SetValue(self._rule.include_never_played)
        self.never_played_checkbox.SetName(_("Incluir mídias nunca tocadas"))

        rating_label = wx.StaticText(self, label=_("A&valiação mínima (0 ignora)"))
        self.rating_ctrl = wx.SpinCtrl(self, min=0, max=5, initial=self._rule.minimum_rating)
        self.rating_ctrl.SetName(_("Avaliação mínima"))

        days_label = wx.StaticText(self, label=_("Sem tocar há pelo menos (&dias, 0 ignora)"))
        self.days_ctrl = wx.SpinCtrl(
            self,
            min=0,
            max=MAX_NOT_PLAYED_DAYS,
            initial=self._rule.not_played_for_days,
        )
        self.days_ctrl.SetName(_("Dias sem tocar"))

        play_count_label = wx.StaticText(self, label=_("Reproduções &mínimas (0 ignora)"))
        self.play_count_ctrl = wx.SpinCtrl(self, min=0, max=100000, initial=self._rule.minimum_play_count)
        self.play_count_ctrl.SetName(_("Reproduções mínimas"))

        folder_label = wx.StaticText(self, label=_("Limitar à &pasta (vazio ignora)"))
        self.folder_text = wx.TextCtrl(self, value=self._rule.folder_path)
        self.folder_text.SetName(_("Pasta da playlist inteligente"))
        self.folder_button = wx.Button(self, wx.ID_ANY, _("&Escolher pasta..."))

        folder_sizer = wx.BoxSizer(wx.HORIZONTAL)
        folder_sizer.Add(self.folder_text, 1, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 8)
        folder_sizer.Add(self.folder_button, 0, wx.ALIGN_CENTER_VERTICAL)

        for control in (
            self.favorites_checkbox,
            self.remote_checkbox,
            self.never_played_checkbox,
        ):
            criteria_box.Add(control, 0, wx.ALL | wx.EXPAND, 6)
        criteria_box.Add(rating_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
        criteria_box.Add(self.rating_ctrl, 0, wx.ALL, 6)
        criteria_box.Add(days_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
        criteria_box.Add(self.days_ctrl, 0, wx.ALL, 6)
        criteria_box.Add(play_count_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
        criteria_box.Add(self.play_count_ctrl, 0, wx.ALL, 6)
        criteria_box.Add(folder_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
        criteria_box.Add(folder_sizer, 0, wx.ALL | wx.EXPAND, 6)

        output_box = wx.StaticBoxSizer(wx.StaticBox(self, label=_("Resultado")), wx.VERTICAL)

        sort_label = wx.StaticText(self, label=_("&Ordenar por"))
        self.sort_choice = wx.Choice(self, choices=[label for _value, label in sort_order_labels()])
        try:
            self.sort_choice.SetSelection(self._sort_values.index(self._rule.sort_order))
        except ValueError:
            self.sort_choice.SetSelection(0)
        self.sort_choice.SetName(_("Ordenação da playlist inteligente"))

        limit_label = wx.StaticText(self, label=_("Número máximo de &itens"))
        self.limit_ctrl = wx.SpinCtrl(
            self,
            min=MIN_SMART_PLAYLIST_LIMIT,
            max=MAX_SMART_PLAYLIST_LIMIT,
            initial=self._rule.limit or DEFAULT_SMART_PLAYLIST_LIMIT,
        )
        self.limit_ctrl.SetName(_("Número máximo de itens"))

        output_box.Add(sort_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
        output_box.Add(self.sort_choice, 0, wx.ALL, 6)
        output_box.Add(limit_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
        output_box.Add(self.limit_ctrl, 0, wx.ALL, 6)

        self.summary_label = wx.StaticText(self, label="")
        self.summary_label.SetName(_("Resumo da regra"))
        attach_named_accessible(
            self.summary_label,
            name=_("Resumo da regra"),
            description=_("Descreve em uma frase o que a playlist vai reunir."),
            value_provider=lambda: self.summary_label.GetLabel(),
        )

        button_sizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        if button_sizer is not None:
            ok_button = self.FindWindow(wx.ID_OK)
            if ok_button is not None:
                ok_button.SetLabel(_("&Salvar"))
            cancel_button = self.FindWindow(wx.ID_CANCEL)
            if cancel_button is not None:
                cancel_button.SetLabel(_("&Cancelar"))

        root_sizer.Add(description, 0, wx.ALL | wx.EXPAND, 12)
        root_sizer.Add(name_label, 0, wx.LEFT | wx.RIGHT, 12)
        root_sizer.Add(self.name_text, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 12)
        root_sizer.Add(criteria_box, 0, wx.ALL | wx.EXPAND, 12)
        root_sizer.Add(output_box, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
        root_sizer.Add(self.summary_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
        if button_sizer is not None:
            root_sizer.Add(button_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, 12)

        self.SetSizer(root_sizer)
        self.SetMinSize((560, 620))
        self.Fit()
        self.SetEscapeId(wx.ID_CANCEL)
        self.CentreOnParent()

        self.folder_button.Bind(wx.EVT_BUTTON, self._on_choose_folder)
        for control in (
            self.favorites_checkbox,
            self.remote_checkbox,
            self.never_played_checkbox,
        ):
            control.Bind(wx.EVT_CHECKBOX, self._on_rule_changed)
        for control in (self.rating_ctrl, self.days_ctrl, self.play_count_ctrl, self.limit_ctrl):
            control.Bind(wx.EVT_SPINCTRL, self._on_rule_changed)
        self.sort_choice.Bind(wx.EVT_CHOICE, self._on_rule_changed)
        self.folder_text.Bind(wx.EVT_TEXT, self._on_rule_changed)
        self.Bind(wx.EVT_BUTTON, self._on_confirm, id=wx.ID_OK)

        self._refresh_summary()
        self.name_text.SetFocus()
        self.name_text.SelectAll()

    # ------------------------------------------------------------------
    def get_rule(self):
        rule = SmartPlaylistRule()
        rule.name = str(self.name_text.GetValue() or "").strip()
        rule.favorites_only = self.favorites_checkbox.GetValue()
        rule.minimum_rating = int(self.rating_ctrl.GetValue())
        rule.folder_path = str(self.folder_text.GetValue() or "").strip()
        rule.not_played_for_days = int(self.days_ctrl.GetValue())
        rule.minimum_play_count = int(self.play_count_ctrl.GetValue())
        rule.include_never_played = self.never_played_checkbox.GetValue()
        rule.exclude_remote = not self.remote_checkbox.GetValue()
        selection = self.sort_choice.GetSelection()
        if 0 <= selection < len(self._sort_values):
            rule.sort_order = self._sort_values[selection]
        rule.limit = int(self.limit_ctrl.GetValue())
        return rule

    def _refresh_summary(self):
        self.summary_label.SetLabel(_("Vai reunir: {summary}").format(summary=describe_rule(self.get_rule())))
        self.summary_label.Wrap(520)

    def _on_rule_changed(self, event):
        self._refresh_summary()
        event.Skip()

    def _on_choose_folder(self, _event):
        with wx.DirDialog(
            self,
            _("Escolha a pasta da playlist inteligente"),
            defaultPath=str(self.folder_text.GetValue() or ""),
            style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            self.folder_text.SetValue(dialog.GetPath())

        self._refresh_summary()

    def _on_confirm(self, event):
        if not str(self.name_text.GetValue() or "").strip():
            wx.MessageBox(
                _("Dê um nome à playlist inteligente antes de salvar."),
                _("Nome obrigatório"),
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            self.name_text.SetFocus()
            return

        event.Skip()


class SmartPlaylistManagerDialog(wx.Dialog):
    def __init__(self, parent, rules, announce=None):
        super().__init__(
            parent,
            title=SMART_PLAYLIST_MANAGER_TITLE,
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self._rules = [SmartPlaylistRule.from_dict(rule.to_dict()) for rule in (rules or [])]
        self._announce = announce
        self._open_requested = False

        root_sizer = wx.BoxSizer(wx.VERTICAL)

        description = wx.StaticText(
            self,
            label=_("Regras salvas. Enter abre a playlist selecionada."),
        )
        description.Wrap(520)

        self.rules_list = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.rules_list.InsertColumn(0, _("Nome"), width=200)
        self.rules_list.InsertColumn(1, _("Regra"), width=420)
        self.rules_list.SetName(_("Playlists inteligentes salvas"))
        attach_named_accessible(
            self.rules_list,
            name=_("Playlists inteligentes salvas"),
            description=_("Use as setas para percorrer as regras e Enter para abrir a playlist."),
        )

        self.status_label = wx.StaticText(self, label="")
        self.status_label.SetName(_("Situação das playlists inteligentes"))
        attach_named_accessible(
            self.status_label,
            name=_("Situação das playlists inteligentes"),
            description=_("Informa quantas regras estão salvas."),
            value_provider=lambda: self.status_label.GetLabel(),
        )

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.open_button = wx.Button(self, wx.ID_OK, _("&Abrir"))
        self.add_button = wx.Button(self, wx.ID_ANY, _("&Nova..."))
        self.edit_button = wx.Button(self, wx.ID_ANY, _("&Editar..."))
        self.remove_button = wx.Button(self, wx.ID_ANY, _("&Remover"))
        self.close_button = wx.Button(self, wx.ID_CANCEL, _("F&echar"))
        for button in (self.open_button, self.add_button, self.edit_button, self.remove_button):
            button_sizer.Add(button, 0, wx.RIGHT, 8)
        button_sizer.Add(self.close_button, 0)

        root_sizer.Add(description, 0, wx.ALL | wx.EXPAND, 12)
        root_sizer.Add(self.rules_list, 1, wx.ALL | wx.EXPAND, 12)
        root_sizer.Add(self.status_label, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 12)
        root_sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 12)

        self.SetSizer(root_sizer)
        self.SetMinSize((680, 440))
        self.SetSize((760, 500))
        self.SetEscapeId(wx.ID_CANCEL)
        self.SetAffirmativeId(wx.ID_OK)
        self.CentreOnParent()

        self.rules_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_open)
        self.rules_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_selection_changed)
        self.rules_list.Bind(wx.EVT_LIST_ITEM_DESELECTED, self._on_selection_changed)
        self.open_button.Bind(wx.EVT_BUTTON, self._on_open)
        self.add_button.Bind(wx.EVT_BUTTON, self._on_add)
        self.edit_button.Bind(wx.EVT_BUTTON, self._on_edit)
        self.remove_button.Bind(wx.EVT_BUTTON, self._on_remove)

        self._populate()
        self.rules_list.SetFocus()

    # ------------------------------------------------------------------
    def get_rules(self):
        return list(self._rules)

    def get_selected_rule(self):
        selection = self.rules_list.GetFirstSelected()
        if not 0 <= selection < len(self._rules):
            return None
        return self._rules[selection]

    def wants_to_open(self):
        return self._open_requested

    # ------------------------------------------------------------------
    def _populate(self, preserve_position=None):
        self.rules_list.DeleteAllItems()
        for row_index, rule in enumerate(self._rules):
            self.rules_list.InsertItem(row_index, rule.name)
            self.rules_list.SetItem(row_index, 1, describe_rule(rule))

        if self._rules:
            target_row = 0
            if preserve_position is not None:
                target_row = max(0, min(int(preserve_position), len(self._rules) - 1))
            self.rules_list.Select(target_row)
            self.rules_list.Focus(target_row)
            self.status_label.SetLabel(
                ngettext(
                    "{count} playlist inteligente salva.",
                    "{count} playlists inteligentes salvas.",
                    len(self._rules),
                ).format(count=len(self._rules))
            )
        else:
            self.status_label.SetLabel(_("Nenhuma playlist inteligente ainda. Use Nova para criar a primeira."))

        self._refresh_action_buttons()

    def _refresh_action_buttons(self):
        has_selection = self.get_selected_rule() is not None
        self.open_button.Enable(has_selection)
        self.edit_button.Enable(has_selection)
        self.remove_button.Enable(has_selection)

    def _on_selection_changed(self, event):
        self._refresh_action_buttons()
        event.Skip()

    def _speak(self, message):
        if callable(self._announce) and message:
            self._announce(message)

    def _unique_name(self, name, ignore_index=None):
        """Evita dois nomes iguais no menu, acrescentando um sufixo numérico."""
        existing = {
            rule.name.casefold()
            for index, rule in enumerate(self._rules)
            if index != ignore_index
        }
        candidate = name
        suffix = 2
        while candidate.casefold() in existing:
            candidate = f"{name} ({suffix})"
            suffix += 1
        return candidate

    def _on_add(self, _event):
        dialog = SmartPlaylistEditorDialog(self)
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            rule = dialog.get_rule()
        finally:
            dialog.Destroy()

        rule.name = self._unique_name(rule.name)
        self._rules.append(rule)
        self._populate(preserve_position=len(self._rules) - 1)
        self._speak(_("Playlist inteligente {name} criada.").format(name=rule.name))
        self.rules_list.SetFocus()

    def _on_edit(self, _event):
        selected_row = self.rules_list.GetFirstSelected()
        rule = self.get_selected_rule()
        if rule is None:
            return

        dialog = SmartPlaylistEditorDialog(self, rule)
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            updated_rule = dialog.get_rule()
        finally:
            dialog.Destroy()

        updated_rule.name = self._unique_name(updated_rule.name, ignore_index=selected_row)
        self._rules[selected_row] = updated_rule
        self._populate(preserve_position=selected_row)
        self._speak(_("Playlist inteligente {name} atualizada.").format(name=updated_rule.name))
        self.rules_list.SetFocus()

    def _on_remove(self, _event):
        selected_row = self.rules_list.GetFirstSelected()
        rule = self.get_selected_rule()
        if rule is None:
            return

        with wx.MessageDialog(
            self,
            _("Deseja remover a playlist inteligente {name}?").format(name=rule.name),
            _("Remover playlist inteligente"),
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
        ) as confirmation:
            if confirmation.ShowModal() != wx.ID_YES:
                return

        self._rules.pop(selected_row)
        self._populate(preserve_position=selected_row)
        self._speak(_("Playlist inteligente {name} removida.").format(name=rule.name))
        self.rules_list.SetFocus()

    def _on_open(self, _event):
        if self.get_selected_rule() is None:
            return

        self._open_requested = True
        if self.IsModal():
            self.EndModal(wx.ID_OK)
            return
        self.SetReturnCode(wx.ID_OK)
        self.Show(False)
