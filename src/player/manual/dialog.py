"""Manual do usuário numa janela do programa, sem navegador.

Cinco controles, nesta ordem de Tab: o campo de busca, a lista de seções, a
lista de tópicos da seção escolhida, o texto do tópico e a lista de links dele.
Enter numa lista leva ao controle seguinte; Enter na busca filtra o manual pelas
palavras digitadas. Enter num link, ou no texto, numa linha com link, segue o
link: um trecho do manual abre aqui mesmo, um endereço abre no navegador.
"""

from __future__ import annotations

import wx

from ..i18n import _, ngettext
from ..links import open_link
from ..reading_dialog import add_reading_field
from .service import (
    ManualLink,
    ManualSection,
    find_anchor,
    first_match_line_start,
    link_in_line,
    load_manual,
    manual_directories,
    search_manual,
)


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
        self._current_links: list[ManualLink] = []
        root_sizer = wx.BoxSizer(wx.VERTICAL)

        # Cada controle nasce logo depois do seu rótulo: é desse texto vizinho que o
        # leitor de tela tira o nome dele.
        search_label = wx.StaticText(self, label=_("&Buscar no manual:"))
        self.search_ctrl = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.search_ctrl.SetName(_("Buscar no manual"))
        root_sizer.Add(search_label, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 10)
        root_sizer.Add(self.search_ctrl, 0, wx.ALL | wx.EXPAND, 10)

        sections_label = wx.StaticText(self, label=_("&Seções:"))
        self.sections_list = wx.ListBox(self, choices=[section.title for section in self.sections])
        self.sections_list.SetName(_("Seções"))
        self.sections_list.SetMinSize(self.FromDIP(wx.Size(520, 130)))
        root_sizer.Add(sections_label, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 10)
        root_sizer.Add(self.sections_list, 0, wx.ALL | wx.EXPAND, 10)

        topics_label = wx.StaticText(self, label=_("Tó&picos da seção:"))
        self.topics_list = wx.ListBox(self)
        self.topics_list.SetName(_("Tópicos da seção"))
        self.topics_list.SetMinSize(self.FromDIP(wx.Size(520, 110)))
        root_sizer.Add(topics_label, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 10)
        root_sizer.Add(self.topics_list, 0, wx.ALL | wx.EXPAND, 10)

        self.text_ctrl = add_reading_field(self, root_sizer, _("&Texto"), self._empty_text())
        self.text_ctrl.SetMinSize(self.FromDIP(wx.Size(520, 240)))

        links_label = wx.StaticText(self, label=_("&Links do tópico:"))
        self.links_list = wx.ListBox(self)
        self.links_list.SetName(_("Links do tópico"))
        self.links_list.SetMinSize(self.FromDIP(wx.Size(520, 70)))
        root_sizer.Add(links_label, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 10)
        root_sizer.Add(self.links_list, 0, wx.ALL | wx.EXPAND, 10)

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
        self.text_ctrl.Bind(wx.EVT_KEY_DOWN, self._on_text_key)
        self.links_list.Bind(wx.EVT_KEY_DOWN, self._on_links_key)
        self.links_list.Bind(wx.EVT_LISTBOX_DCLICK, lambda _event: self._activate_selected_link())
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
            topic = section.topics[index]
            text = topic.text
            self.text_ctrl.SetValue(text)
            # Com uma busca ativa, o texto abre na linha em que a palavra aparece.
            self.text_ctrl.SetInsertionPoint(first_match_line_start(text, self._query))
            self.text_ctrl.ShowPosition(self.text_ctrl.GetInsertionPoint())
            self._show_links(topic.links)
        else:
            self.text_ctrl.SetValue(self._empty_text())
            self.text_ctrl.SetInsertionPoint(0)
            self._show_links([])

    # ------------------------------------------------------------------
    # Links
    # ------------------------------------------------------------------

    @staticmethod
    def _link_label(link: ManualLink) -> str:
        if link.is_internal:
            return _("{text} (no manual)").format(text=link.text)
        return _("{text} (abre no navegador)").format(text=link.text)

    def _show_links(self, links: list[ManualLink]):
        self._current_links = list(links)
        self.links_list.Set([self._link_label(link) for link in self._current_links])
        # Sem links a lista fica desativada (e fora do Tab), não escondida.
        self.links_list.Enable(bool(self._current_links))
        if self._current_links:
            self.links_list.SetSelection(0)

    def _on_links_key(self, event):
        if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and not event.HasModifiers():
            self._activate_selected_link()
            return
        event.Skip()

    def _activate_selected_link(self):
        index = self.links_list.GetSelection()
        if 0 <= index < len(self._current_links):
            self.activate_link(self._current_links[index])

    def _on_text_key(self, event):
        if event.GetKeyCode() not in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) or event.HasModifiers():
            event.Skip()
            return
        found, column, line_number = self.text_ctrl.PositionToXY(self.text_ctrl.GetInsertionPoint())
        line = self.text_ctrl.GetLineText(line_number) if found else ""
        link = link_in_line(self._current_links, line, column if found else 0)
        if link is None:
            self._say(_("Não há link nesta linha."))
            return
        self.activate_link(link)

    def activate_link(self, link: ManualLink):
        """Segue *link*: um trecho do manual abre nesta janela; um endereço, no navegador."""
        if link.is_internal:
            self._go_to_anchor(link.anchor, link.text)
            return
        if open_link(link.target, manual_directories()):
            self._say(_("Abrindo no navegador: {text}.").format(text=link.text))
        else:
            self._say(_("Não foi possível abrir o link {text}.").format(text=link.text))

    def _go_to_anchor(self, anchor: str, text: str):
        position = find_anchor(self.all_sections, anchor)
        if position is None:
            self._say(_("O trecho \"{text}\" não foi encontrado no manual.").format(text=text))
            return
        if self._query or len(self.sections) != len(self.all_sections):
            # O destino pode estar fora do resultado da busca: volta ao manual inteiro.
            self.search_ctrl.ChangeValue("")
            self._query = ""
            self.sections = list(self.all_sections)
            self.sections_list.Set([section.title for section in self.sections])
        section_index, topic_index = position
        section = self.sections[section_index]
        self.sections_list.SetSelection(section_index)
        self.topics_list.Set([topic.title for topic in section.topics])
        self.topics_list.SetSelection(topic_index)
        self._show_topic(section, topic_index)
        self._say(
            _("{topic}, em {section}.").format(topic=section.topics[topic_index].title, section=section.title)
        )
        self.text_ctrl.SetFocus()

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
            self._show_links([])
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
