"""Manual do usuário numa janela do programa, sem navegador.

Quatro controles, nesta ordem de Tab: o campo de busca, a lista de seções, a
lista de tópicos da seção escolhida e o texto do tópico. Enter numa lista leva
ao controle seguinte; Enter na busca filtra o manual pelas palavras digitadas.
"""

from __future__ import annotations

import wx

from ..i18n import _, ngettext
from ..reading_dialog import add_reading_field
from .service import ManualSection, first_match_line_start, load_manual, search_manual


class ManualDialog(wx.Dialog):
    def __init__(self, parent, sections: list[ManualSection] | None = None, *, announce=None):
        super().__init__(
            parent,
            title=_("Manual do usuário"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.all_sections = list(sections) if sections is not None else load_manual()
        self.sections = list(self.all_sections)
        self._query = ""
        self._announce = announce
        root_sizer = wx.BoxSizer(wx.VERTICAL)

        # Cada controle nasce logo depois do seu rótulo: é desse texto vizinho que o
        # leitor de tela tira o nome dele.
        search_label = wx.StaticText(self, label=_("Buscar no manual:"))
        self.search_ctrl = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.search_ctrl.SetName(_("Buscar no manual"))
        root_sizer.Add(search_label, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 10)
        root_sizer.Add(self.search_ctrl, 0, wx.ALL | wx.EXPAND, 10)

        sections_label = wx.StaticText(self, label=_("Seções:"))
        self.sections_list = wx.ListBox(self, choices=[section.title for section in self.sections])
        self.sections_list.SetName(_("Seções"))
        self.sections_list.SetMinSize(self.FromDIP(wx.Size(520, 130)))
        root_sizer.Add(sections_label, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 10)
        root_sizer.Add(self.sections_list, 0, wx.ALL | wx.EXPAND, 10)

        topics_label = wx.StaticText(self, label=_("Tópicos da seção:"))
        self.topics_list = wx.ListBox(self)
        self.topics_list.SetName(_("Tópicos da seção"))
        self.topics_list.SetMinSize(self.FromDIP(wx.Size(520, 110)))
        root_sizer.Add(topics_label, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 10)
        root_sizer.Add(self.topics_list, 0, wx.ALL | wx.EXPAND, 10)

        self.text_ctrl = add_reading_field(self, root_sizer, _("Texto"), self._empty_text())
        self.text_ctrl.SetMinSize(self.FromDIP(wx.Size(520, 240)))

        close_button = wx.Button(self, wx.ID_CLOSE, _("&Fechar"))
        close_button.SetDefault()
        close_button.Bind(wx.EVT_BUTTON, lambda _event: self.EndModal(wx.ID_CLOSE))
        root_sizer.Add(close_button, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, 10)

        self.SetEscapeId(wx.ID_CLOSE)
        self.SetSizerAndFit(root_sizer)
        self.SetMinSize(self.GetSize())
        self.CentreOnParent()

        self.search_ctrl.Bind(wx.EVT_TEXT_ENTER, self.on_search)
        self.sections_list.Bind(wx.EVT_LISTBOX, self.on_select_section)
        self.topics_list.Bind(wx.EVT_LISTBOX, self.on_select_topic)
        self.sections_list.Bind(wx.EVT_KEY_DOWN, lambda event: self._on_enter(event, self.topics_list))
        self.topics_list.Bind(wx.EVT_KEY_DOWN, lambda event: self._on_enter(event, self.text_ctrl))
        if self.sections:
            self.sections_list.SetSelection(0)
            self._show_section(0)
        self.sections_list.SetFocus()

    @staticmethod
    def _empty_text() -> str:
        return _("Não foi possível localizar o manual do KeyTune nesta instalação.")

    @staticmethod
    def _on_enter(event, target):
        if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and not event.HasModifiers():
            target.SetFocus()
            return
        event.Skip()

    def _say(self, message: str):
        if callable(self._announce):
            self._announce(message)

    def _show_section(self, index: int):
        section = self.sections[index]
        # Troca a lista de uma vez; mexer item a item faz o leitor de tela ler cada um.
        self.topics_list.Set([topic.title for topic in section.topics])
        self.topics_list.SetSelection(0)
        self._show_topic(section, 0)

    def _show_topic(self, section: ManualSection, index: int):
        if 0 <= index < len(section.topics):
            text = section.topics[index].text
            self.text_ctrl.SetValue(text)
            # Com uma busca ativa, o texto abre na linha em que a palavra aparece.
            self.text_ctrl.SetInsertionPoint(first_match_line_start(text, self._query))
            self.text_ctrl.ShowPosition(self.text_ctrl.GetInsertionPoint())
        else:
            self.text_ctrl.SetValue(self._empty_text())
            self.text_ctrl.SetInsertionPoint(0)

    def on_search(self, _event):
        query = self.search_ctrl.GetValue().strip()
        self._query = query
        found = search_manual(self.all_sections, query)
        self.sections = found
        self.sections_list.Set([section.title for section in found])
        if not found:
            self.topics_list.Set([])
            self.text_ctrl.SetValue(_("Nada foi encontrado para esta busca."))
            self.text_ctrl.SetInsertionPoint(0)
            self._say(_("Nada foi encontrado para \"{query}\".").format(query=query))
            return

        self.sections_list.SetSelection(0)
        self._show_section(0)
        if not query:
            self._say(_("Busca limpa. O manual inteiro está de volta."))
            return

        topics = sum(len(section.topics) for section in found)
        found_topics = ngettext("{count} tópico encontrado.", "{count} tópicos encontrados.", topics)
        in_sections = ngettext("Em {count} seção.", "Em {count} seções.", len(found))
        self._say(f"{found_topics.format(count=topics)} {in_sections.format(count=len(found))}")
        self.sections_list.SetFocus()

    def on_select_section(self, _event):
        index = self.sections_list.GetSelection()
        if 0 <= index < len(self.sections):
            self._show_section(index)

    def on_select_topic(self, _event):
        section_index = self.sections_list.GetSelection()
        topic_index = self.topics_list.GetSelection()
        if 0 <= section_index < len(self.sections):
            self._show_topic(self.sections[section_index], topic_index)
