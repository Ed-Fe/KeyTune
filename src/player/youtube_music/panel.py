import wx

from ..accessibility import attach_named_accessible
from .models import YOUTUBE_SEARCH_SCOPE_OPTIONS


class YouTubeMusicTabPanel(wx.Panel):
	DEFAULT_SAVE_SEARCH_RESULT_LABEL = "&Salvar / curtir no Music"

	def __init__(
		self,
		parent,
		*,
		on_connect,
		on_disconnect,
		on_refresh_library,
		on_open_selected,
		on_open_manual_source,
		on_search,
		on_open_search_result,
		on_save_search_result,
		on_add_search_result_to_playlist,
		on_load_more_playlists,
	):
		super().__init__(parent, style=wx.TAB_TRAVERSAL)

		self._all_playlists = []
		self._visible_playlists = []
		self._visible_playlist_ids = []
		self._all_search_results = []
		self._visible_search_result_ids = []
		self._connected = False
		self._operation_in_progress = False
		self._has_more_playlists = False
		self._on_connect = on_connect
		self._on_disconnect = on_disconnect
		self._on_refresh_library = on_refresh_library
		self._on_open_selected = on_open_selected
		self._on_open_manual_source = on_open_manual_source
		self._on_search = on_search
		self._on_open_search_result = on_open_search_result
		self._on_save_search_result = on_save_search_result
		self._on_add_search_result_to_playlist = on_add_search_result_to_playlist
		self._on_load_more_playlists = on_load_more_playlists

		root_sizer = wx.BoxSizer(wx.VERTICAL)

		intro_label = wx.StaticText(
			self,
			label=(
				"Abra sua central do YouTube Music em uma aba dedicada. "
				"Conecte ou atualize o acesso da conta, atualize a biblioteca, pesquise músicas, vídeos e playlists "
				"do YouTube Music, ou faça uma busca rápida por vídeos do YouTube para tocar sem sair do player."
			),
		)
		intro_label.Wrap(640)
		root_sizer.Add(intro_label, 0, wx.ALL | wx.EXPAND, 10)

		status_box = wx.StaticBoxSizer(wx.StaticBox(self, label="Conta e biblioteca"), wx.VERTICAL)
		self.connection_label = wx.StaticText(self, label="Conta: não conectada")
		self.connection_label.SetName("Status da conta do YouTube Music")
		self.connection_label.SetHelpText("Informa se existe uma conta do YouTube Music conectada nesta instalação.")
		self.library_summary_label = wx.StaticText(self, label="Biblioteca: nenhuma playlist carregada.")
		self.library_summary_label.SetName("Resumo da biblioteca do YouTube Music")
		self.library_summary_label.SetHelpText("Resume quantas playlists ou mixes estão disponíveis na aba do YouTube Music.")
		self.status_message_label = wx.StaticText(self, label="")
		self.status_message_label.SetName("Mensagem da central do YouTube Music")
		self.status_message_label.SetHelpText("Mostra o resultado da última atualização, busca ou ação do YouTube Music.")
		self.status_message_label.Wrap(620)

		attach_named_accessible(
			self.connection_label,
			name="Status da conta do YouTube Music",
			description="Informa se existe uma conta do YouTube Music conectada nesta instalação.",
			value_provider=lambda: self.connection_label.GetLabel(),
		)
		attach_named_accessible(
			self.library_summary_label,
			name="Resumo da biblioteca do YouTube Music",
			description="Resume quantas playlists ou mixes estão disponíveis na aba do YouTube Music.",
			value_provider=lambda: self.library_summary_label.GetLabel(),
		)
		attach_named_accessible(
			self.status_message_label,
			name="Mensagem da central do YouTube Music",
			description="Mostra o resultado da última atualização, busca ou ação do YouTube Music.",
			value_provider=lambda: self.status_message_label.GetLabel(),
		)

		status_box.Add(self.connection_label, 0, wx.ALL | wx.EXPAND, 6)
		status_box.Add(self.library_summary_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
		status_box.Add(self.status_message_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)

		button_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.connect_button = wx.Button(self, label="&Conectar conta...")
		self.disconnect_button = wx.Button(self, label="&Desconectar conta")
		self.refresh_button = wx.Button(self, label="Atuali&zar biblioteca")
		self.open_selected_button = wx.Button(self, label="A&brir seleção")

		for button, name, description in (
			(
				self.connect_button,
				"Conectar ou atualizar acesso do YouTube Music",
				"Abre o diálogo para conectar uma conta do YouTube Music ou atualizar a autenticação salva.",
			),
			(
				self.disconnect_button,
				"Desconectar conta do YouTube Music",
				"Remove a autenticação salva da conta do YouTube Music nesta instalação.",
			),
			(
				self.refresh_button,
				"Atualizar biblioteca do YouTube Music",
				"Busca novamente as playlists e mixes disponíveis na conta conectada.",
			),
			(
				self.open_selected_button,
				"Abrir playlist selecionada do YouTube Music",
				"Abre a playlist ou mix atualmente selecionada na lista da aba do YouTube Music.",
			),
		):
			button.SetName(name)
			button.SetHelpText(description)
			button.SetToolTip(description)
			button_sizer.Add(button, 0, wx.RIGHT, 8)

		status_box.Add(button_sizer, 0, wx.ALL | wx.EXPAND, 6)
		root_sizer.Add(status_box, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

		search_box = wx.StaticBoxSizer(wx.StaticBox(self, label="Busca no catálogo e no YouTube"), wx.VERTICAL)
		search_intro = wx.StaticText(
			self,
			label=(
				"Pesquise músicas, vídeos e playlists do YouTube Music, ou faça uma busca rápida por vídeos do YouTube. "
				"Você pode abrir resultados, salvar playlists ou faixas no Music e adicionar resultados à playlist selecionada."
			),
		)
		search_intro.Wrap(620)
		search_box.Add(search_intro, 0, wx.ALL | wx.EXPAND, 6)

		search_label = wx.StaticText(self, label="Buscar por:")
		self.search_query_ctrl = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
		self.search_query_ctrl.SetName("Busca do YouTube Music e do YouTube")
		self.search_query_ctrl.SetHelpText(
			"Digite o que deseja procurar no YouTube Music ou no YouTube e pressione Enter para pesquisar."
		)

		search_scope_row = wx.BoxSizer(wx.HORIZONTAL)
		search_scope_label = wx.StaticText(self, label="Escopo:")
		self.search_scope_choice = wx.Choice(
			self,
			choices=[option.label for option in YOUTUBE_SEARCH_SCOPE_OPTIONS],
		)
		self.search_scope_choice.SetSelection(0)
		self.search_scope_choice.SetName("Escopo da busca do YouTube")
		self.search_scope_choice.SetHelpText(
			"Escolhe se a busca será feita no catálogo do YouTube Music ou em vídeos do YouTube."
		)
		self.search_button = wx.Button(self, label="&Pesquisar")
		self.search_button.SetName("Pesquisar no YouTube Music ou no YouTube")
		self.search_button.SetHelpText(
			"Executa a busca usando o texto informado e o escopo selecionado."
		)
		self.search_button.SetToolTip(self.search_button.GetHelpText())
		search_scope_row.Add(search_scope_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
		search_scope_row.Add(self.search_scope_choice, 1, wx.RIGHT, 8)
		search_scope_row.Add(self.search_button, 0)

		self.search_results_label = wx.StaticText(self, label="Resultados da busca: nenhum ainda.")
		self.search_results_label.SetName("Resumo da busca do YouTube")
		self.search_results_label.SetHelpText("Mostra quantos resultados a busca atual retornou.")
		attach_named_accessible(
			self.search_results_label,
			name="Resumo da busca do YouTube",
			description="Mostra quantos resultados a busca atual retornou.",
			value_provider=lambda: self.search_results_label.GetLabel(),
		)

		self.search_results_list = wx.ListBox(self)
		self.search_results_list.SetName("Resultados da busca do YouTube")
		self.search_results_list.SetHelpText(
			"Mostra os resultados da última busca. Use setas para navegar e Enter para abrir ou tocar o resultado selecionado."
		)
		self.search_results_list.SetMinSize((-1, 180))

		search_actions = wx.BoxSizer(wx.HORIZONTAL)
		self.open_search_result_button = wx.Button(self, label="Abr&ir / tocar resultado")
		self.save_search_result_button = wx.Button(self, label=self.DEFAULT_SAVE_SEARCH_RESULT_LABEL)
		self.add_to_playlist_button = wx.Button(self, label="Adicionar à playlist &selecionada")

		for button, name, description in (
			(
				self.open_search_result_button,
				"Abrir ou tocar resultado da busca",
				"Abre a playlist selecionada ou toca imediatamente a música ou o vídeo destacado nos resultados da busca.",
			),
			(
				self.save_search_result_button,
				"Salvar ou curtir resultado no YouTube Music",
				"Salva playlists ou faixas na biblioteca do YouTube Music, ou marca o resultado como curtido quando isso for mais apropriado.",
			),
			(
				self.add_to_playlist_button,
				"Adicionar resultado à playlist selecionada do YouTube Music",
				"Adiciona a faixa ou vídeo destacado da busca à playlist atualmente selecionada na lista da biblioteca do YouTube Music.",
			),
		):
			button.SetName(name)
			button.SetHelpText(description)
			button.SetToolTip(description)
			search_actions.Add(button, 0, wx.RIGHT, 8)

		search_help_label = wx.StaticText(
			self,
			label=(
				"Enter no campo de busca executa a pesquisa. Enter na lista abre o resultado atual. "
				"Para adicionar um resultado a uma playlist, selecione antes a playlist desejada na lista da biblioteca."
			),
		)
		search_help_label.Wrap(620)

		search_box.Add(search_label, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 6)
		search_box.Add(self.search_query_ctrl, 0, wx.ALL | wx.EXPAND, 6)
		search_box.Add(search_scope_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
		search_box.Add(self.search_results_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
		search_box.Add(self.search_results_list, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
		search_box.Add(search_actions, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
		search_box.Add(search_help_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
		root_sizer.Add(search_box, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

		manual_box = wx.StaticBoxSizer(wx.StaticBox(self, label="Abrir playlist específica"), wx.VERTICAL)
		manual_intro = wx.StaticText(
			self,
			label="Cole um link do YouTube Music/YouTube ou informe apenas o ID da playlist ou mix.",
		)
		manual_intro.Wrap(620)
		self.manual_source_ctrl = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
		self.manual_source_ctrl.SetName("Link ou ID da playlist do YouTube Music")
		self.manual_source_ctrl.SetHelpText(
			"Cole um link de playlist ou mix do YouTube Music, ou informe diretamente o ID que deseja abrir."
		)
		self.manual_open_button = wx.Button(self, label="Abrir pelo &link ou ID")
		self.manual_open_button.SetName("Abrir playlist específica do YouTube Music")
		self.manual_open_button.SetHelpText(
			"Abre a playlist ou mix informada no campo acima, usando um link do YouTube Music ou um ID direto."
		)
		self.manual_open_button.SetToolTip(self.manual_open_button.GetHelpText())

		manual_box.Add(manual_intro, 0, wx.ALL | wx.EXPAND, 6)
		manual_box.Add(self.manual_source_ctrl, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
		manual_box.Add(self.manual_open_button, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_LEFT, 6)
		root_sizer.Add(manual_box, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

		library_box = wx.StaticBoxSizer(wx.StaticBox(self, label="Playlists e mixes"), wx.VERTICAL)
		filter_label = wx.StaticText(self, label="Filtro:")
		self.filter_ctrl = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
		self.filter_ctrl.SetName("Filtro da biblioteca do YouTube Music")
		self.filter_ctrl.SetHelpText(
			"Filtra a lista por título, tipo da lista ou quantidade de faixas, sem abrir mão do teclado."
		)
		self.results_label = wx.StaticText(self, label="Mostrando 0 de 0 resultados.")
		self.results_label.SetName("Contagem de resultados do YouTube Music")
		self.results_label.SetHelpText("Informa quantas playlists ou mixes aparecem após o filtro aplicado.")
		self.playlists_list = wx.ListBox(self)
		self.playlists_list.SetName("Lista de playlists do YouTube Music")
		self.playlists_list.SetHelpText(
			"Mostra as playlists e mixes disponíveis. Use setas para navegar, Enter para abrir e Tab para sair da aba."
			" Pressione Page Down ou desça até o último item para carregar mais playlists."
		)
		self.load_more_button = wx.Button(self, label="Carregar &mais playlists")
		self.load_more_button.SetName("Carregar mais playlists do YouTube Music")
		self.load_more_button.SetHelpText(
			"Busca o próximo lote de playlists da biblioteca quando ainda existem mais a carregar."
		)
		self.load_more_button.SetToolTip(self.load_more_button.GetHelpText())
		self.load_more_button.Disable()
		help_label = wx.StaticText(
			self,
			label=(
				"Enter abre a seleção atual. Esc fecha a aba. Tab volta para a navegação padrão entre controles da tela."
				" Page Down no fim da lista carrega mais playlists."
			),
		)
		help_label.Wrap(620)

		library_box.Add(filter_label, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 6)
		library_box.Add(self.filter_ctrl, 0, wx.ALL | wx.EXPAND, 6)
		library_box.Add(self.results_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
		library_box.Add(self.playlists_list, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
		library_box.Add(self.load_more_button, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_LEFT, 6)
		library_box.Add(help_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
		root_sizer.Add(library_box, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

		self.SetSizer(root_sizer)

		self.connect_button.Bind(wx.EVT_BUTTON, lambda _event: self._on_connect())
		self.disconnect_button.Bind(wx.EVT_BUTTON, lambda _event: self._on_disconnect())
		self.refresh_button.Bind(wx.EVT_BUTTON, lambda _event: self._on_refresh_library())
		self.open_selected_button.Bind(wx.EVT_BUTTON, lambda _event: self._on_open_selected())
		self.manual_open_button.Bind(wx.EVT_BUTTON, lambda _event: self._on_open_manual_source())
		self.search_button.Bind(wx.EVT_BUTTON, lambda _event: self._on_search())
		self.open_search_result_button.Bind(wx.EVT_BUTTON, lambda _event: self._on_open_search_result())
		self.save_search_result_button.Bind(wx.EVT_BUTTON, lambda _event: self._on_save_search_result())
		self.add_to_playlist_button.Bind(wx.EVT_BUTTON, lambda _event: self._on_add_search_result_to_playlist())
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
		self.search_results_list.Bind(wx.EVT_LISTBOX, self._on_search_selection_changed)
		self.search_results_list.Bind(wx.EVT_LISTBOX_DCLICK, self._on_open_search_result_event)
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
		self.playlists_list.Set(labels)

		selection_index = wx.NOT_FOUND
		if selected_playlist_id and selected_playlist_id in self._visible_playlist_ids:
			selection_index = self._visible_playlist_ids.index(selected_playlist_id)
		elif labels:
			selection_index = 0

		if selection_index != wx.NOT_FOUND:
			self.playlists_list.SetSelection(selection_index)

		self.results_label.SetLabel(
			f"Mostrando {len(self._visible_playlists)} de {len(self._all_playlists)} playlists e mixes."
		)
		self._update_library_actions()
		self._update_search_actions()

	def _refresh_search_results_list(self, selected_result_id=None):
		if selected_result_id is None:
			selected_result = self.get_selected_search_result()
			selected_result_id = selected_result.stable_id if selected_result is not None else None

		self._visible_search_result_ids = [result.stable_id for result in self._all_search_results]
		labels = [result.choice_label for result in self._all_search_results]
		self.search_results_list.Set(labels)

		selection_index = wx.NOT_FOUND
		if selected_result_id and selected_result_id in self._visible_search_result_ids:
			selection_index = self._visible_search_result_ids.index(selected_result_id)
		elif labels:
			selection_index = 0

		if selection_index != wx.NOT_FOUND:
			self.search_results_list.SetSelection(selection_index)

		self._update_search_actions()

	def _update_library_actions(self):
		can_open_selected = (
			self._connected
			and not self._operation_in_progress
			and self.get_selected_playlist_id() is not None
		)
		self.open_selected_button.Enable(can_open_selected)
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
		if label == "Salvar playlist na biblioteca":
			return "&Salvar playlist na biblioteca"
		if label == "Salvar faixa na biblioteca":
			return "Salvar &faixa na biblioteca"
		if label == "Curtir no YouTube Music":
			return "&Curtir no YouTube Music"
		return label or self.DEFAULT_SAVE_SEARCH_RESULT_LABEL

	def _update_search_actions(self):
		search_query = self.get_search_query()
		selected_result = self.get_selected_search_result()
		selected_playlist_id = self.get_selected_playlist_id()

		self.search_button.Enable(bool(search_query) and not self._operation_in_progress)
		self.open_search_result_button.Enable(
			bool(selected_result and selected_result.can_open and not self._operation_in_progress)
		)

		save_button_label = self._mnemonic_save_action_label(selected_result)
		self.save_search_result_button.SetLabel(save_button_label)
		self.save_search_result_button.Enable(
			bool(
				selected_result
				and selected_result.can_save
				and self._connected
				and not self._operation_in_progress
			)
		)

		self.add_to_playlist_button.Enable(
			bool(
				selected_result
				and selected_result.can_add_to_playlist
				and selected_playlist_id is not None
				and self._connected
				and not self._operation_in_progress
			)
		)

	def _update_action_state(self, *, connected, operation_in_progress):
		self._connected = bool(connected)
		self._operation_in_progress = bool(operation_in_progress)
		self.connect_button.SetLabel("At&ualizar acesso..." if connected else "&Conectar conta...")
		self.connect_button.Enable(not operation_in_progress)
		self.disconnect_button.Enable(connected and not operation_in_progress)
		self.refresh_button.Enable(connected and not operation_in_progress)
		self.manual_open_button.Enable(not operation_in_progress)
		self.manual_source_ctrl.Enable(not operation_in_progress)
		self.search_query_ctrl.Enable(not operation_in_progress)
		self.search_scope_choice.Enable(not operation_in_progress)
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
			selected_search_result = self.get_selected_search_result()
			selected_search_result_id = selected_search_result.stable_id if selected_search_result is not None else None

			self._all_playlists = list(playlists or [])
			self._all_search_results = list(search_results or [])
			self._has_more_playlists = bool(has_more_playlists)
			self.connection_label.SetLabel(
				f"Conta: {account_name}." if connected and account_name else "Conta: não conectada."
			)
			if connected:
				summary_suffix = " Há mais para carregar." if self._has_more_playlists else ""
				self.library_summary_label.SetLabel(
					f"Biblioteca: {len(self._all_playlists)} playlist(s) e mix(es) disponíveis.{summary_suffix}"
				)
			else:
				self.library_summary_label.SetLabel("Biblioteca: conecte uma conta para listar playlists e mixes.")

			self.status_message_label.SetLabel(str(status_message or "").strip())
			self.status_message_label.Wrap(620)
			self.search_results_label.SetLabel(
				str(search_summary or "Resultados da busca: nenhum ainda.").strip()
			)
			self._refresh_playlist_list(selected_playlist_id=selected_playlist_id)
			self._refresh_search_results_list(selected_result_id=selected_search_result_id)
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
		selection = self.search_results_list.GetSelection()
		if selection == wx.NOT_FOUND or not 0 <= selection < len(self._all_search_results):
			return None
		return self._all_search_results[selection]

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

	def _on_manual_source_enter(self, _event):
		self._on_open_manual_source()

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

		if key_code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
			if self.get_selected_search_result() is not None:
				self._on_open_search_result()
				return

		event.Skip()
