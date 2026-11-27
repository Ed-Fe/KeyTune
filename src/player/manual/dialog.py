"""Manual do usuário numa janela do programa, sem navegador.

Lado a lado, como a ajuda clássica do Windows: à esquerda a árvore do conteúdo
(as seções, que se abrem com a seta para a direita e mostram os tópicos), à
direita o texto do tópico escolhido. Ordem de Tab: o campo de busca, a árvore,
o texto e os botões **Abrir no navegador** e **Fechar**.

Enter na árvore leva ao texto; Enter na busca filtra o manual pelas palavras
digitadas. Enter numa linha do texto que tenha um link segue o link: um trecho
do manual abre aqui mesmo, um endereço abre no navegador. **Abrir no navegador**
abre o ``manual.html`` que a release gera em ``docs/``; sem ele (rodando do
código, por exemplo), o botão fica desativado.

A janela não é modal: o player continua usável com ela aberta, e ``Alt+F6``
alterna entre as duas (ver ``secondary_window``). Esc ou Fechar a destroem.
"""

from __future__ import annotations

import wx

from ..i18n import _, ngettext
from ..links import open_link, open_local_document
from ..reading_dialog import add_reading_field
from ..secondary_window import bring_to_front, is_switch_window_key
from .service import (
    ManualLink,
    ManualSection,
    find_anchor,
    first_match_line_start,
    link_in_line,
    load_manual,
    manual_directories,
    manual_html_path,
    search_manual,
)


def _child_topic_indexes(section: ManualSection) -> range:
    """Os tópicos que viram filhos da seção na árvore.

    A abertura da seção é mostrada pelo próprio nó da seção, para não aparecer
    duas vezes; sem abertura, todos os tópicos são filhos.
    """
    start = 1 if section.topics and section.topics[0].is_overview else 0
    return range(start, len(section.topics))


class ManualDialog(wx.Dialog):
    def __init__(self, parent, sections: list[ManualSection] | None = None, *, announce=None):
        super().__init__(
            parent,
            title=_("Manual do usuário"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX,
        )

        self.all_sections = list(sections) if sections is not None else load_manual()
        self.sections = list(self.all_sections)
        self._query = ""
        self._announce = announce
        self._current_links: list[ManualLink] = []
        # (seção, tópico) -> nó da árvore; o tópico 0 de uma seção com abertura é o nó dela.
        self._tree_items: dict[tuple[int, int], wx.TreeItemId] = {}
        self._filling_tree = False
        self._html_path = manual_html_path()
        root_sizer = wx.BoxSizer(wx.VERTICAL)

        # Cada controle nasce logo depois do seu rótulo: é desse texto vizinho que o
        # leitor de tela tira o nome dele. A ordem de criação é a ordem do Tab.
        search_label = wx.StaticText(self, label=_("&Buscar no manual:"))
        self.search_ctrl = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.search_ctrl.SetName(_("Buscar no manual"))
        root_sizer.Add(search_label, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 10)
        root_sizer.Add(self.search_ctrl, 0, wx.ALL | wx.EXPAND, 10)

        body_sizer = wx.BoxSizer(wx.HORIZONTAL)
        contents_sizer = wx.BoxSizer(wx.VERTICAL)
        contents_label = wx.StaticText(self, label=_("&Conteúdo:"))
        self.contents_tree = wx.TreeCtrl(
            self,
            style=wx.TR_HAS_BUTTONS | wx.TR_LINES_AT_ROOT | wx.TR_HIDE_ROOT | wx.TR_SINGLE,
        )
        self.contents_tree.SetName(_("Conteúdo"))
        self.contents_tree.SetMinSize(self.FromDIP(wx.Size(280, 400)))
        contents_sizer.Add(contents_label, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 10)
        contents_sizer.Add(self.contents_tree, 1, wx.ALL | wx.EXPAND, 10)
        body_sizer.Add(contents_sizer, 0, wx.EXPAND)

        text_sizer = wx.BoxSizer(wx.VERTICAL)
        self.text_ctrl = add_reading_field(self, text_sizer, _("&Texto"), self._empty_text())
        self.text_ctrl.SetMinSize(self.FromDIP(wx.Size(520, 400)))
        body_sizer.Add(text_sizer, 1, wx.EXPAND)
        root_sizer.Add(body_sizer, 1, wx.EXPAND)

        buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.browser_button = wx.Button(self, wx.ID_ANY, _("Abrir no &navegador"))
        self.browser_button.Bind(wx.EVT_BUTTON, lambda _event: self.open_in_browser())
        # Desativado, não escondido, quando a instalação não traz o HTML.
        self.browser_button.Enable(self._html_path is not None)
        buttons_sizer.Add(self.browser_button, 0, wx.RIGHT, 8)
        close_button = wx.Button(self, wx.ID_CLOSE, _("&Fechar"))
        close_button.Bind(wx.EVT_BUTTON, lambda _event: self.Close())
        buttons_sizer.Add(close_button, 0)
        root_sizer.Add(buttons_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, 10)

        self.SetEscapeId(wx.ID_CLOSE)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        self.SetSizerAndFit(root_sizer)
        self.SetMinSize(self.GetSize())
        self.CentreOnParent()

        self.search_ctrl.Bind(wx.EVT_TEXT_ENTER, self.on_search)
        self.contents_tree.Bind(wx.EVT_TREE_SEL_CHANGED, self.on_select_item)
        self.contents_tree.Bind(wx.EVT_TREE_ITEM_ACTIVATED, lambda _event: self.text_ctrl.SetFocus())
        self.text_ctrl.Bind(wx.EVT_KEY_DOWN, self._on_text_key)
        self._fill_tree(expand=False)
        if self.sections:
            self._select(0, 0)
        self.contents_tree.SetFocus()

    def _on_close(self, _event):
        # Aberta sem modo modal (o normal), fechar destrói a janela; a auditoria e
        # quem ainda chamar ShowModal recebem o fim modal de sempre.
        if self.IsModal():
            self.EndModal(wx.ID_CLOSE)
        else:
            self.Destroy()

    def _on_char_hook(self, event):
        parent = self.GetParent()
        # Com outro diálogo modal aberto (a tela de boas-vindas), a principal fica bloqueada.
        if is_switch_window_key(event) and parent is not None and parent.IsEnabled() and not self.IsModal():
            bring_to_front(parent)
            return
        event.Skip()

    @staticmethod
    def _empty_text() -> str:
        return _("Não foi possível localizar o manual do KeyTune nesta instalação.")

    def _say(self, message: str):
        if callable(self._announce):
            self._announce(message)

    # ------------------------------------------------------------------
    # Árvore do conteúdo
    # ------------------------------------------------------------------

    def _fill_tree(self, *, expand: bool):
        """Monta a árvore com ``self.sections``; *expand* abre todas as seções (busca)."""
        tree = self.contents_tree
        self._filling_tree = True
        tree.Freeze()
        try:
            tree.DeleteAllItems()
            self._tree_items = {}
            root = tree.AddRoot("")
            for section_index, section in enumerate(self.sections):
                section_item = tree.AppendItem(root, section.title, data=(section_index, 0))
                self._tree_items[(section_index, 0)] = section_item
                for topic_index in _child_topic_indexes(section):
                    topic_item = tree.AppendItem(
                        section_item, section.topics[topic_index].title, data=(section_index, topic_index)
                    )
                    self._tree_items[(section_index, topic_index)] = topic_item
                if expand and tree.ItemHasChildren(section_item):
                    tree.Expand(section_item)
        finally:
            tree.Thaw()
            self._filling_tree = False

    def _select(self, section_index: int, topic_index: int):
        """Seleciona o tópico na árvore (abrindo a seção dele) e mostra o texto."""
        item = self._tree_items.get((section_index, topic_index))
        if item is None:
            return
        parent = self.contents_tree.GetItemParent(item)
        if parent.IsOk() and parent != self.contents_tree.GetRootItem():
            self.contents_tree.Expand(parent)
        self._filling_tree = True
        try:
            self.contents_tree.SelectItem(item)
        finally:
            self._filling_tree = False
        self.contents_tree.EnsureVisible(item)
        self._show_topic(self.sections[section_index], topic_index)

    def on_select_item(self, event):
        # Ao fechar, a árvore se esvazia e avisa de cada seleção perdida: ignora.
        if self._filling_tree or not self or self.IsBeingDeleted() or not self.contents_tree:
            return
        item = event.GetItem()
        if not item.IsOk():
            return
        position = self.contents_tree.GetItemData(item)
        if not position:
            return
        section_index, topic_index = position
        if 0 <= section_index < len(self.sections):
            self._show_topic(self.sections[section_index], topic_index)

    def _show_topic(self, section: ManualSection, index: int):
        if 0 <= index < len(section.topics):
            topic = section.topics[index]
            text = topic.text
            self.text_ctrl.SetValue(text)
            # Com uma busca ativa, o texto abre na linha em que a palavra aparece.
            self.text_ctrl.SetInsertionPoint(first_match_line_start(text, self._query))
            self.text_ctrl.ShowPosition(self.text_ctrl.GetInsertionPoint())
            self._current_links = list(topic.links)
        else:
            self.text_ctrl.SetValue(self._empty_text())
            self.text_ctrl.SetInsertionPoint(0)
            self._current_links = []

    # ------------------------------------------------------------------
    # Links e navegador
    # ------------------------------------------------------------------

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

    def open_in_browser(self):
        """Abre o ``manual.html`` da instalação no navegador padrão."""
        if self._html_path is not None and open_local_document(self._html_path):
            self._say(_("Abrindo o manual no navegador."))
        else:
            self._say(_("Não foi possível abrir o manual no navegador."))

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
            self._fill_tree(expand=False)
        section_index, topic_index = position
        section = self.sections[section_index]
        self._select(section_index, topic_index)
        self._say(
            _("{topic}, em {section}.").format(topic=section.topics[topic_index].title, section=section.title)
        )
        self.text_ctrl.SetFocus()

    # ------------------------------------------------------------------
    # Busca
    # ------------------------------------------------------------------

    def on_search(self, _event):
        query = self.search_ctrl.GetValue().strip()
        self._query = query
        found = search_manual(self.all_sections, query)
        self.sections = found
        # Com resultado, todas as seções achadas ficam abertas, mostrando os tópicos.
        self._fill_tree(expand=bool(query))
        if not found:
            self.text_ctrl.SetValue(_("Nada foi encontrado para esta busca."))
            self.text_ctrl.SetInsertionPoint(0)
            self._current_links = []
            self._say(_("Nada foi encontrado para \"{query}\".").format(query=query))
            return

        self._select(0, 0)
        if not query:
            self._say(_("Busca limpa. O manual inteiro está de volta."))
            return

        topics = sum(len(section.topics) for section in found)
        found_topics = ngettext("{count} tópico encontrado.", "{count} tópicos encontrados.", topics)
        in_sections = ngettext("Em {count} seção.", "Em {count} seções.", len(found))
        self._say(f"{found_topics.format(count=topics)} {in_sections.format(count=len(found))}")
        self.contents_tree.SetFocus()
