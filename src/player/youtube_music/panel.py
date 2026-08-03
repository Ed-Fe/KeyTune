import wx

from ..accessibility import attach_named_accessible
from ..library.browser import VirtualItemsListCtrl
from ..i18n import _, ngettext
from .models import YOUTUBE_SEARCH_SCOPE_OPTIONS


class YouTubeMusicTabPanel(wx.Panel):
	DEFAULT_SAVE_SEARCH_RESULT_LABEL = _("&Salvar no Music")

	def __init__(
		self,
		parent,
		*,
		on_connect,
		on_disconnect,
		on_refresh_library,
		on_open_selected,
		on_open_manual_source,
		on_create_playlist=None,
		on_delete_playlist=None,
		on_search,
		on_open_search_result,
		on_save_search_result,
		on_add_search_results_to_current_playlist,
		on_show_search_actions_menu,
		on_load_more_playlists,
		on_show_charts,
		on_show_moods,
		on_show_liked,
		on_show_history,
		on_announce=None,
	):
		super().__init__(parent, style=wx.TAB_TRAVERSAL)

		self._all_playlists = []
		self._visible_playlists = []
		self._visible_playlist_ids = []
		self._last_playlist_labels = []
		self._all_search_results = []
		self._visible_search_result_ids = []
		self._last_search_result_labels = []
		self._connected = False
		self._operation_in_progress = False
		self._has_more_playlists = False
		self._on_connect = on_connect
		self._on_disconnect = on_disconnect
		self._on_refresh_library = on_refresh_library
		self._on_open_selected = on_open_selected
		self._on_create_playlist = on_create_playlist
		self._on_delete_playlist = on_delete_playlist
		self._on_open_manual_source = on_open_manual_source
		self._on_search = on_search
		self._on_open_search_result = on_open_search_result
		self._on_save_search_result = on_save_search_result
		self._on_add_search_results_to_current_playlist = on_add_search_results_to_current_playlist
		self._on_show_search_actions_menu = on_show_search_actions_menu
		self._on_load_more_playlists = on_load_more_playlists
		self._on_show_charts = on_show_charts
		self._on_show_moods = on_show_moods
		self._on_show_liked = on_show_liked
		self._on_show_history = on_show_history
		self._on_announce = on_announce

		root_sizer = wx.BoxSizer(wx.VERTICAL)

		intro_label = wx.StaticText(
			self,
			label=_(
				"Abra sua central do YouTube Music em uma aba dedicada. "
				"Conecte ou atualize o acesso da conta, atualize a biblioteca, pesquise músicas, vídeos e playlists "
				"do YouTube Music, ou faça uma busca rápida por vídeos do YouTube para tocar sem sair do player."
			),
		)
		intro_label.Wrap(640)
		root_sizer.Add(intro_label, 0, wx.ALL | wx.EXPAND, 10)

		status_box = wx.StaticBoxSizer(wx.StaticBox(self, label=_("Conta e biblioteca")), wx.VERTICAL)
		self.connection_label = wx.StaticText(self, label=_("Conta: não conectada"))
		self.connection_label.SetName(_("Status da conta do YouTube Music"))
		self.library_summary_label = wx.StaticText(self, label=_("Biblioteca: nenhuma playlist carregada."))
		self.library_summary_label.SetName(_("Resumo da biblioteca do YouTube Music"))
		self.status_message_label = wx.StaticText(self, label="")
		self.status_message_label.SetName(_("Mensagem da central do YouTube Music"))
		self.status_message_label.Wrap(620)

		attach_named_accessible(
			self.connection_label,
			name=_("Status da conta do YouTube Music"),
			description=_("Informa se existe uma conta do YouTube Music conectada nesta instalação."),
			value_provider=lambda: self.connection_label.GetLabel(),
		)
		attach_named_accessible(
			self.library_summary_label,
			name=_("Resumo da biblioteca do YouTube Music"),
			description=_("Resume quantas playlists ou mixes estão disponíveis na aba do YouTube Music."),
			value_provider=lambda: self.library_summary_label.GetLabel(),
		)
		attach_named_accessible(
			self.status_message_label,
			name=_("Mensagem da central do YouTube Music"),
			description=_("Mostra o resultado da última atualização, busca ou ação do YouTube Music."),
			value_provider=lambda: self.status_message_label.GetLabel(),
		)

		status_box.Add(self.connection_label, 0, wx.ALL | wx.EXPAND, 6)
		status_box.Add(self.library_summary_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
		status_box.Add(self.status_message_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)

		button_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.connect_button = wx.Button(self, label=_("&Conectar conta..."))
		self.disconnect_button = wx.Button(self, label=_("&Desconectar conta"))
		self.refresh_button = wx.Button(self, label=_("Atuali&zar biblioteca"))

		for button, name, description in (
			(
				self.connect_button,
				_("Conectar ou atualizar acesso do YouTube Music"),
				_("Abre o diálogo para conectar uma conta do YouTube Music ou atualizar a autenticação salva."),
			),
			(
				self.disconnect_button,
				_("Desconectar conta do YouTube Music"),
				_("Remove a autenticação salva da conta do YouTube Music nesta instalação."),
			),
			(
				self.refresh_button,
				_("Atualizar biblioteca do YouTube Music"),
				_("Busca novamente as playlists e mixes disponíveis na conta conectada."),
			),
		):
			button.SetName(name)
			button.SetToolTip(description)
			button_sizer.Add(button, 0, wx.RIGHT, 8)

		status_box.Add(button_sizer, 0, wx.ALL | wx.EXPAND, 6)
		root_sizer.Add(status_box, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

		self.search_pane = wx.CollapsiblePane(
			self,
			label=_("Busca no catálogo e no YouTube"),
			style=wx.CP_DEFAULT_STYLE | wx.CP_NO_TLW_RESIZE,
		)
		self.search_pane.SetName(_("Seção de busca do YouTube Music e do YouTube"))
		self.search_pane.Collapse(True)
		self.search_pane.Bind(wx.EVT_COLLAPSIBLEPANE_CHANGED, self._on_collapsible_pane_changed)
		search_pane_window = self.search_pane.GetPane()
		search_box = wx.BoxSizer(wx.VERTICAL)
		search_intro = wx.StaticText(
			search_pane_window,
			label=_(
				"Pesquise músicas, vídeos e playlists do YouTube Music, ou faça uma busca rápida por vídeos do YouTube. "
				"Você pode salvar playlists ou faixas no Music e adicionar resultados a uma playlist do player."
			),
		)
		search_intro.Wrap(620)
		search_box.Add(search_intro, 0, wx.ALL | wx.EXPAND, 6)

		search_label = wx.StaticText(search_pane_window, label=_("Buscar por:"))
		self.search_query_ctrl = wx.TextCtrl(search_pane_window, style=wx.TE_PROCESS_ENTER)
		self.search_query_ctrl.SetName(_("Busca do YouTube Music e do YouTube"))

		search_scope_row = wx.BoxSizer(wx.HORIZONTAL)
		search_scope_label = wx.StaticText(search_pane_window, label=_("Escopo:"))
		self.search_scope_choice = wx.Choice(
			search_pane_window,
			choices=[option.label for option in YOUTUBE_SEARCH_SCOPE_OPTIONS],
		)
		self.search_scope_choice.SetSelection(0)
		self.search_scope_choice.SetName(_("Escopo da busca do YouTube"))
		self.search_button = wx.Button(search_pane_window, label=_("&Pesquisar"))
		self.search_button.SetName(_("Pesquisar no YouTube Music ou no YouTube"))
		self.search_button.SetToolTip(_("Executa a busca usando o texto informado e o escopo selecionado."))
		search_scope_row.Add(search_scope_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
		search_scope_row.Add(self.search_scope_choice, 1, wx.RIGHT, 8)
		search_scope_row.Add(self.search_button, 0)

		browse_row = wx.BoxSizer(wx.HORIZONTAL)
		browse_label = wx.StaticText(search_pane_window, label=_("Explorar:"))
		self.charts_button = wx.Button(search_pane_window, label=_("Em &alta..."))
		self.moods_button = wx.Button(search_pane_window, label=_("Moods e &gêneros..."))
		self.liked_button = wx.Button(search_pane_window, label=_("C&urtidas"))
		self.history_button = wx.Button(search_pane_window, label=_("&Histórico"))
		for button, name, description in (
			(
				self.charts_button,
				_("Ver o que está em alta no YouTube Music"),
				_("Abre um menu para escolher o país e carrega as paradas e os destaques em alta nos resultados abaixo."),
			),
			(
				self.moods_button,
				_("Explorar moods e gêneros do YouTube Music"),
				_("Lista as categorias de climas e gêneros do YouTube Music e carrega as playlists da categoria escolhida nos resultados abaixo."),
			),
			(
				self.liked_button,
				_("Carregar suas músicas curtidas do YouTube Music"),
				_("Traz para os resultados abaixo as faixas curtidas (Curtidas) da conta conectada."),
			),
			(
				self.history_button,
				_("Carregar seu histórico do YouTube Music"),
				_("Traz para os resultados abaixo o histórico de reprodução da conta conectada, da mais recente para a mais antiga."),
			),
		):
			button.SetName(name)
			button.SetToolTip(description)
		browse_row.Add(browse_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
		browse_row.Add(self.charts_button, 0, wx.RIGHT, 8)
		browse_row.Add(self.moods_button, 0, wx.RIGHT, 8)
		browse_row.Add(self.liked_button, 0, wx.RIGHT, 8)
		browse_row.Add(self.history_button, 0)

		self.search_results_label = wx.StaticText(search_pane_window, label=_("Resultados da busca: nenhum ainda."))
		self.search_results_label.SetName(_("Resumo da busca do YouTube"))
		attach_named_accessible(
			self.search_results_label,
			name=_("Resumo da busca do YouTube"),
			description=_("Mostra quantos resultados a busca atual retornou."),
			value_provider=lambda: self.search_results_label.GetLabel(),
		)

		self.search_results_list = VirtualItemsListCtrl(search_pane_window, self._get_search_result_label)
		self.search_results_list.SetName(_("Resultados da busca do YouTube"))
		self.search_results_list.SetMinSize((-1, 180))

		search_actions = wx.BoxSizer(wx.HORIZONTAL)
		self.save_search_result_button = wx.Button(search_pane_window, label=self.DEFAULT_SAVE_SEARCH_RESULT_LABEL)
		self.search_actions_button = wx.Button(search_pane_window, label=_("Ações..."))

		for button, name, description in (
			(
				self.save_search_result_button,
				_("Salvar resultado no YouTube Music"),
				_("Salva playlists ou faixas na biblioteca do YouTube Music quando o resultado for compatível."),
			),
			(
				self.search_actions_button,
				_("Ações da seleção de resultados do YouTube"),
				_("Abre um menu de contexto com ações para o resultado atual ou para toda a seleção da busca."),
			),
		):
			button.SetName(name)
			button.SetToolTip(description)
			search_actions.Add(button, 0, wx.RIGHT, 8)

		search_help_label = wx.StaticText(
			search_pane_window,
			label=_(
				"Enter no campo de busca executa a pesquisa. Enter na lista adiciona a seleção à playlist atual. "
				"Ctrl+Enter abre a seleção em nova playlist. Use Shift+F10 ou o botão Ações para mais opções."
			),
		)
		search_help_label.Wrap(620)

		search_box.Add(search_label, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 6)
		search_box.Add(self.search_query_ctrl, 0, wx.ALL | wx.EXPAND, 6)
		search_box.Add(search_scope_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
		search_box.Add(browse_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
		search_box.Add(self.search_results_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
		search_box.Add(self.search_results_list, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
		search_box.Add(search_actions, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
		search_box.Add(search_help_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
		search_pane_window.SetSizer(search_box)

		self.manual_pane = wx.CollapsiblePane(
			self,
			label=_("Abrir playlist ou vídeo"),
			style=wx.CP_DEFAULT_STYLE | wx.CP_NO_TLW_RESIZE,
		)
		self.manual_pane.SetName(_("Seção para abrir playlist ou vídeo por link"))
		self.manual_pane.Collapse(True)
		self.manual_pane.Bind(wx.EVT_COLLAPSIBLEPANE_CHANGED, self._on_collapsible_pane_changed)
		manual_pane_window = self.manual_pane.GetPane()
		manual_box = wx.BoxSizer(wx.VERTICAL)
		manual_intro = wx.StaticText(
			manual_pane_window,
			label=_("Cole um link de playlist, mix ou vídeo do YouTube Music/YouTube."),
		)
		manual_intro.Wrap(620)
		self.manual_source_ctrl = wx.TextCtrl(manual_pane_window, style=wx.TE_PROCESS_ENTER)
		self.manual_source_ctrl.SetName(_("Link da playlist, mix ou vídeo do YouTube Music"))
		self.manual_open_button = wx.Button(manual_pane_window, label=_("&Abrir link"))
		self.manual_open_button.SetName(_("Abrir playlist ou vídeo do YouTube Music"))
		self.manual_open_button.SetToolTip(_("Abre a playlist, mix ou vídeo informado no campo acima."))

		manual_box.Add(manual_intro, 0, wx.ALL | wx.EXPAND, 6)
		manual_box.Add(self.manual_source_ctrl, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
		manual_box.Add(self.manual_open_button, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_LEFT, 6)
		manual_pane_window.SetSizer(manual_box)

		library_box = wx.StaticBoxSizer(wx.StaticBox(self, label=_("Playlists e mixes")), wx.VERTICAL)
		filter_label = wx.StaticText(self, label=_("Filtro:"))
		self.filter_ctrl = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
		self.filter_ctrl.SetName(_("Filtro da biblioteca do YouTube Music"))
		self.results_label = wx.StaticText(self, label=_("Mostrando 0 de 0 resultados."))
		self.results_label.SetName(_("Contagem de resultados do YouTube Music"))
		self.playlists_list = wx.ListBox(self)
		self.playlists_list.SetName(_("Lista de playlists do YouTube Music"))
		self.open_selected_button = wx.Button(self, label=_("A&brir seleção"))
		self.open_selected_button.SetName(_("Abrir playlist selecionada do YouTube Music"))
		self.open_selected_button.SetToolTip(_("Abre a playlist ou mix atualmente selecionada na lista da aba do YouTube Music."))
		self.new_playlist_button = wx.Button(self, label=_("&Nova playlist..."))
		self.new_playlist_button.SetName(_("Criar nova playlist no YouTube Music"))
		self.new_playlist_button.SetToolTip(_("Cria uma nova playlist (privada) na conta conectada do YouTube Music."))
		self.delete_playlist_button = wx.Button(self, label=_("E&xcluir playlist..."))
		self.delete_playlist_button.SetName(_("Excluir playlist do YouTube Music"))
		self.delete_playlist_button.SetToolTip(_("Exclui a playlist selecionada da conta. Só funciona em playlists que você criou e pede confirmação."))
		self.load_more_button = wx.Button(self, label=_("Carregar &mais playlists"))
		self.load_more_button.SetName(_("Carregar mais playlists do YouTube Music"))
		self.load_more_button.SetToolTip(_("Busca o próximo lote de playlists da biblioteca quando ainda existem mais a carregar."))
		self.load_more_button.Disable()
		help_label = wx.StaticText(
			self,
			label=_(
				"Enter abre a seleção atual. Esc fecha a aba. Tab volta para a navegação padrão entre controles da tela."
				" Page Down no fim da lista carrega mais playlists."
			),
		)
		help_label.Wrap(620)

		library_box.Add(filter_label, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 6)
		library_box.Add(self.filter_ctrl, 0, wx.ALL | wx.EXPAND, 6)
		library_box.Add(self.results_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
		library_box.Add(self.playlists_list, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
		library_actions_sizer = wx.BoxSizer(wx.HORIZONTAL)
		library_actions_sizer.Add(self.open_selected_button, 0, wx.RIGHT, 8)
		library_actions_sizer.Add(self.new_playlist_button, 0, wx.RIGHT, 8)
		library_actions_sizer.Add(self.delete_playlist_button, 0, wx.RIGHT, 8)
		library_actions_sizer.Add(self.load_more_button, 0, 0, 0)
		library_box.Add(library_actions_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_LEFT, 6)
		library_box.Add(help_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
		root_sizer.Add(library_box, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
		root_sizer.Add(self.search_pane, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
		root_sizer.Add(self.manual_pane, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

		self.SetSizer(root_sizer)

		self.connect_button.Bind(wx.EVT_BUTTON, lambda _event: self._on_connect())
		self.disconnect_button.Bind(wx.EVT_BUTTON, lambda _event: self._on_disconnect())
		self.refresh_button.Bind(wx.EVT_BUTTON, lambda _event: self._on_refresh_library())
		self.open_selected_button.Bind(wx.EVT_BUTTON, lambda _event: self._on_open_selected())
		self.new_playlist_button.Bind(wx.EVT_BUTTON, self._on_new_playlist_button)
		self.delete_playlist_button.Bind(wx.EVT_BUTTON, self._on_delete_playlist_button)
		self.manual_open_button.Bind(wx.EVT_BUTTON, lambda _event: self._on_open_manual_source())
		self.search_button.Bind(wx.EVT_BUTTON, lambda _event: self._on_search())
		self.charts_button.Bind(wx.EVT_BUTTON, self._on_charts_button)
		self.moods_button.Bind(wx.EVT_BUTTON, self._on_moods_button)
		self.liked_button.Bind(wx.EVT_BUTTON, lambda _event: self._on_show_liked())
		self.history_button.Bind(wx.EVT_BUTTON, lambda _event: self._on_show_history())
		self.save_search_result_button.Bind(wx.EVT_BUTTON, lambda _event: self._on_save_search_result())
		self.search_actions_button.Bind(wx.EVT_BUTTON, self._on_search_actions_button)
		self.load_more_button.Bind(wx.EVT_BUTTON, lambda _event: self._on_load_more_playlists())

		self.manual_source_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_manual_source_enter)
		self.search_query_ctrl.Bind(wx.EVT_TEXT, self._on_search_query_changed)
		self.search_query_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_search_query_enter)
		self.search_scope_choice.Bind(wx.EVT_CHOICE, self._on_search_scope_changed)
		self.filter_ctrl.Bind(wx.EVT_TEXT, self._on_filter_changed)
		self.filter_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_filter_text_enter)
		self.playlists_list.Bind(wx.EVT_LISTBOX, self._on_selection_changed)
		self.playlists_list.Bind(wx.EVT_LISTBOX_DCLICK, self._on_open_selected_event)
		self.playlists_list.Bind(wx.EVT_CHAR_HOOK, self._on_list_key_down)
		self.search_results_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_search_selection_changed)
		self.search_results_list.Bind(wx.EVT_LIST_ITEM_DESELECTED, self._on_search_selection_changed)
		self.search_results_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_open_search_result_event)
		self.search_results_list.Bind(wx.EVT_CHAR_HOOK, self._on_search_list_key_down)

		self._refresh_playlist_list()
		self._refresh_search_results_list()
		self._update_action_state(connected=False, operation_in_progress=False)

	def _normalized_filter_text(self):
		return str(self.filter_ctrl.GetValue() or "").strip().casefold()

	def _filtered_playlists(self):
		filter_text = self._normalized_filter_text()
		if not filter_text:
			return list(self._all_playlists)

		filtered = []
		for playlist in self._all_playlists:
			haystack = " ".join(
				part
				for part in (
					getattr(playlist, "title", ""),
					getattr(playlist, "track_count_text", ""),
					getattr(playlist, "source_badge", ""),
					getattr(playlist, "choice_label", ""),
				)
				if part
			).casefold()
			if filter_text in haystack:
				filtered.append(playlist)

		return filtered

	def _refresh_playlist_list(self, selected_playlist_id=None):
		if selected_playlist_id is None:
			selected_playlist_id = self.get_selected_playlist_id()

		self._visible_playlists = self._filtered_playlists()
		self._visible_playlist_ids = [playlist.playlist_id for playlist in self._visible_playlists]

		labels = [playlist.choice_label for playlist in self._visible_playlists]
		# Avoid Set() when labels are unchanged: it resets the listbox selection
		# and triggers redundant screen reader announcements when refreshes are
		# scheduled by unrelated UI updates (menus, busy state, etc.).
		labels_changed = labels != self._last_playlist_labels
		if labels_changed:
			self.playlists_list.Set(labels)
			self._last_playlist_labels = list(labels)

		selection_index = wx.NOT_FOUND
		if selected_playlist_id and selected_playlist_id in self._visible_playlist_ids:
			selection_index = self._visible_playlist_ids.index(selected_playlist_id)
		elif labels:
			selection_index = 0

		if selection_index != wx.NOT_FOUND and (
			labels_changed or self.playlists_list.GetSelection() != selection_index
		):
			self.playlists_list.SetSelection(selection_index)

		self.results_label.SetLabel(
			_("Mostrando {visible} de {total} playlists e mixes.").format(visible=len(self._visible_playlists), total=len(self._all_playlists))
		)
		self._update_library_actions()
		self._update_search_actions()

	def _refresh_search_results_list(self, selected_result_id=None):
		if selected_result_id is None:
			selected_result_ids = self.get_selected_search_result_ids()
		elif isinstance(selected_result_id, (list, tuple, set)):
			selected_result_ids = [str(value or "").strip() for value in selected_result_id if str(value or "").strip()]
		else:
			selected_result_ids = [str(selected_result_id or "").strip()] if str(selected_result_id or "").strip() else []

		self._visible_search_result_ids = [result.stable_id for result in self._all_search_results]
		
		old_count = self.search_results_list.GetItemCount()
		new_count = len(self._all_search_results)
		
		self.search_results_list.SetItemCount(new_count)
		self.search_results_list.Refresh()

		selected_indices = [
			self._visible_search_result_ids.index(result_id)
			for result_id in selected_result_ids
			if result_id in self._visible_search_result_ids
		]
		if not selected_indices and new_count > 0:
			selected_indices = [0]

		if old_count != new_count:
			self._clear_search_results_selection()
			
		current_selections = self._get_search_list_selections()
		if selected_indices != current_selections:
			self._clear_search_results_selection()
			for selection_index in selected_indices:
				self.search_results_list.Select(selection_index, on=True)
			if selected_indices:
				self.search_results_list.Focus(selected_indices[0])

		self._update_search_actions()

	def _update_library_actions(self):
		has_selection = self.get_selected_playlist_id() is not None
		can_open_selected = (
			self._connected
			and not self._operation_in_progress
			and has_selection
		)
		self.open_selected_button.Enable(can_open_selected)
		self.new_playlist_button.Enable(self._connected and not self._operation_in_progress)
		self.delete_playlist_button.Enable(
			self._connected and not self._operation_in_progress and has_selection
		)
		can_load_more = (
			self._connected
			and not self._operation_in_progress
			and self._has_more_playlists
		)
		self.load_more_button.Enable(can_load_more)

	def _mnemonic_save_action_label(self, selected_result):
		if selected_result is None:
			return self.DEFAULT_SAVE_SEARCH_RESULT_LABEL

		label = str(getattr(selected_result, "save_action_label", "") or "").strip()
		if label == _("Salvar playlist na biblioteca"):
			return _("&Salvar playlist na biblioteca")
		if label == _("Salvar faixa na biblioteca"):
			return _("Salvar &faixa na biblioteca")
		return label or self.DEFAULT_SAVE_SEARCH_RESULT_LABEL

	def _update_search_actions(self):
		search_query = self.get_search_query()
		selected_results = self.get_selected_search_results()
		selected_result = selected_results[0] if selected_results else None
		selected_result_count = len(selected_results)

		self.search_button.Enable(bool(search_query) and not self._operation_in_progress)

		save_button_label = (
			_("&Salvar seleção no Music")
			if selected_result_count > 1
			else self._mnemonic_save_action_label(selected_result)
		)
		self.save_search_result_button.SetLabel(save_button_label)
		self.save_search_result_button.Enable(
			bool(
				selected_results
				and any(result.can_save for result in selected_results)
				and self._connected
				and not self._operation_in_progress
			)
		)

		self.search_actions_button.Enable(
			bool(
				selected_results
				and not self._operation_in_progress
			)
		)

	def _update_action_state(self, *, connected, operation_in_progress):
		self._connected = bool(connected)
		self._operation_in_progress = bool(operation_in_progress)
		self.connect_button.SetLabel(_("At&ualizar acesso...") if connected else _("&Conectar conta..."))
		self.connect_button.Enable(not operation_in_progress)
		self.disconnect_button.Enable(connected and not operation_in_progress)
		self.refresh_button.Enable(connected and not operation_in_progress)
		self.manual_open_button.Enable(not operation_in_progress)
		self.manual_source_ctrl.Enable(not operation_in_progress)
		self.search_query_ctrl.Enable(not operation_in_progress)
		self.search_scope_choice.Enable(not operation_in_progress)
		self.charts_button.Enable(not operation_in_progress)
		self.moods_button.Enable(not operation_in_progress)
		self.liked_button.Enable(not operation_in_progress)
		self.history_button.Enable(not operation_in_progress)
		self.filter_ctrl.Enable(True)
		self.playlists_list.Enable(True)
		self.search_results_list.Enable(True)
		self._update_library_actions()
		self._update_search_actions()

	def update_view(
		self,
		*,
		connected,
		account_name,
		playlists,
		operation_in_progress,
		status_message,
		search_results,
		search_summary,
		has_more_playlists=False,
	):
		self.Freeze()
		try:
			selected_playlist_id = self.get_selected_playlist_id()
			selected_search_result_ids = self.get_selected_search_result_ids()

			self._all_playlists = list(playlists or [])
			self._all_search_results = list(search_results or [])
			self._has_more_playlists = bool(has_more_playlists)
			if connected and account_name:
				self.connection_label.SetLabel(_("Conta: {name}.").format(name=account_name))
			elif connected and operation_in_progress:
				self.connection_label.SetLabel(_("Conta: carregando informações da conta…"))
			elif connected:
				self.connection_label.SetLabel(_("Conta: conectada (nome ainda não carregado)."))
			else:
				self.connection_label.SetLabel(_("Conta: não conectada."))
			if connected:
				if not self._all_playlists and operation_in_progress:
					self.library_summary_label.SetLabel(_("Biblioteca: carregando playlists e mixes…"))
				else:
					summary_suffix = _(" Há mais para carregar.") if self._has_more_playlists else ""
					self.library_summary_label.SetLabel(
						ngettext(
							"Biblioteca: {count} playlist ou mix disponível.",
							"Biblioteca: {count} playlists e mixes disponíveis.",
							len(self._all_playlists),
						).format(count=len(self._all_playlists)) + summary_suffix
					)
			else:
				self.library_summary_label.SetLabel(_("Biblioteca: conecte uma conta para listar playlists e mixes."))

			self.status_message_label.SetLabel(str(status_message or "").strip())
			self.status_message_label.Wrap(620)
			self.search_results_label.SetLabel(
				str(search_summary or _("Resultados da busca: nenhum ainda.")).strip()
			)
			self._refresh_playlist_list(selected_playlist_id=selected_playlist_id)
			self._refresh_search_results_list(selected_result_id=selected_search_result_ids)
			self._update_action_state(connected=connected, operation_in_progress=operation_in_progress)
			self.Layout()
		finally:
			self.Thaw()

	def get_selected_playlist_id(self):
		selection = self.playlists_list.GetSelection()
		if selection == wx.NOT_FOUND or not 0 <= selection < len(self._visible_playlist_ids):
			return None
		return self._visible_playlist_ids[selection]

	def get_selected_search_result(self):
		selected_results = self.get_selected_search_results()
		return selected_results[0] if selected_results else None

	def get_selected_search_result_ids(self):
		selected_ids = []
		for selection in self._get_search_list_selections():
			if 0 <= selection < len(self._visible_search_result_ids):
				selected_ids.append(self._visible_search_result_ids[selection])
		return selected_ids

	def get_selected_search_results(self):
		results = []
		for selection in self._get_search_list_selections():
			if 0 <= selection < len(self._all_search_results):
				results.append(self._all_search_results[selection])
		return results

	def _clear_search_results_selection(self):
		for selection in self._get_search_list_selections():
			self.search_results_list.Select(selection, on=False)

	def _get_search_result_label(self, index):
		if not 0 <= index < len(self._all_search_results):
			return ""
		return self._all_search_results[index].choice_label

	def _get_search_list_selections(self):
		selections = []
		selection = self.search_results_list.GetFirstSelected()
		while selection != -1:
			selections.append(selection)
			selection = self.search_results_list.GetNextSelected(selection)
		return selections

	def get_manual_source(self):
		return str(self.manual_source_ctrl.GetValue() or "").strip()

	def get_search_query(self):
		return str(self.search_query_ctrl.GetValue() or "").strip()

	def get_search_scope_id(self):
		selection = self.search_scope_choice.GetSelection()
		if selection == wx.NOT_FOUND or not 0 <= selection < len(YOUTUBE_SEARCH_SCOPE_OPTIONS):
			return YOUTUBE_SEARCH_SCOPE_OPTIONS[0].scope_id
		return YOUTUBE_SEARCH_SCOPE_OPTIONS[selection].scope_id

	def clear_manual_source(self):
		self.manual_source_ctrl.SetValue("")

	def _on_filter_changed(self, _event):
		self._refresh_playlist_list()

	def _on_filter_text_enter(self, _event):
		if self.get_selected_playlist_id() is not None:
			self._on_open_selected()

	def _on_search_query_changed(self, _event):
		self._update_search_actions()

	def _on_search_query_enter(self, _event):
		if self.get_search_query():
			self._on_search()

	def _on_search_scope_changed(self, _event):
		self._update_search_actions()

	def _on_selection_changed(self, _event):
		self._update_library_actions()
		self._update_search_actions()

	def _on_search_selection_changed(self, _event):
		self._update_search_actions()

	def _on_open_selected_event(self, _event):
		if self.get_selected_playlist_id() is not None:
			self._on_open_selected()

	def _on_open_search_result_event(self, _event):
		if self.get_selected_search_result() is not None:
			self._on_open_search_result()

	def _on_new_playlist_button(self, _event):
		if callable(self._on_create_playlist):
			self._on_create_playlist()

	def _on_delete_playlist_button(self, _event):
		if callable(self._on_delete_playlist):
			self._on_delete_playlist()

	def _on_search_actions_button(self, event):
		if not callable(self._on_show_search_actions_menu):
			return
		self._on_show_search_actions_menu(self, event.GetEventObject())

	def _on_charts_button(self, event):
		if not callable(self._on_show_charts):
			return
		self._on_show_charts(self, event.GetEventObject())

	def _on_moods_button(self, event):
		if not callable(self._on_show_moods):
			return
		self._on_show_moods(self, event.GetEventObject())

	def _on_manual_source_enter(self, _event):
		self._on_open_manual_source()

	def _on_collapsible_pane_changed(self, event):
		self.Layout()
		pane = event.GetEventObject() if hasattr(event, "GetEventObject") else None
		label = ""
		if pane is self.search_pane:
			label = _("Busca no catálogo e no YouTube")
		elif pane is self.manual_pane:
			label = _("Abrir playlist ou vídeo")
		if label and callable(self._on_announce):
			state = _("expandida") if (pane is not None and pane.IsExpanded()) else _("recolhida")
			try:
				self._on_announce(_("Seção {label} {state}.").format(label=label, state=state))
			except Exception:
				pass
		event.Skip()

	def _on_list_key_down(self, event):
		key_code = event.GetKeyCode()
		if key_code == wx.WXK_TAB:
			event.Skip()
			return

		if key_code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
			if self.get_selected_playlist_id() is not None:
				self._on_open_selected()
				return

		if key_code in (wx.WXK_PAGEDOWN, wx.WXK_NUMPAD_PAGEDOWN):
			if self._maybe_trigger_load_more_playlists():
				return

		if key_code in (wx.WXK_DOWN, wx.WXK_NUMPAD_DOWN):
			selection = self.playlists_list.GetSelection()
			last_index = len(self._visible_playlist_ids) - 1
			if selection != wx.NOT_FOUND and selection >= last_index:
				if self._maybe_trigger_load_more_playlists():
					return

		event.Skip()

	def _maybe_trigger_load_more_playlists(self):
		if not self._has_more_playlists:
			return False
		if self._operation_in_progress or not self._connected:
			return False
		if self._normalized_filter_text():
			return False
		self._on_load_more_playlists()
		return True

	def _on_search_list_key_down(self, event):
		key_code = event.GetKeyCode()
		if key_code == wx.WXK_TAB:
			event.Skip()
			return

		if key_code == wx.WXK_F10 and event.ShiftDown():
			self._on_search_actions_button(event)
			return

		if key_code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
			if event.ControlDown():
				if self.get_selected_search_result() is not None:
					self._on_open_search_result()
					return
			else:
				if self.get_selected_search_result() is not None:
					self._on_add_search_results_to_current_playlist()
					return

		event.Skip()
