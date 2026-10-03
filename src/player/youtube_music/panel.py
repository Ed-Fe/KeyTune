import wx

from ..accessibility import attach_named_accessible
from ..library.browser import VirtualItemsListCtrl
from ..i18n import _, ngettext
from .models import YOUTUBE_SEARCH_SCOPE_OPTIONS


class YouTubeMusicTabPanel(wx.Panel):
	"""A aba do YouTube Music: a conta em cima, a busca e uma lista só para todo o resto.

	A lista começa no início (biblioteca, curtidas, histórico, em alta, moods) e
	mostra também a busca e o que há dentro de cada item aberto.
	"""

	def __init__(
		self,
		parent,
		*,
		on_connect,
		on_disconnect,
		on_refresh_library,
		on_search,
		on_add_search_results_to_current_playlist,
		on_show_search_actions_menu,
		on_create_playlist=None,
		on_browse_search_result=None,
		on_results_back=None,
		on_load_more_results=None,
		on_announce=None,
	):
		super().__init__(parent, style=wx.TAB_TRAVERSAL)

		self._all_search_results = []
		self._visible_search_result_ids = []
		self._connected = False
		self._operation_in_progress = False
		self._has_more_results = False
		self._can_go_back = False
		self._on_connect = on_connect
		self._on_disconnect = on_disconnect
		self._on_refresh_library = on_refresh_library
		self._on_create_playlist = on_create_playlist
		self._on_search = on_search
		self._on_add_search_results_to_current_playlist = on_add_search_results_to_current_playlist
		self._on_show_search_actions_menu = on_show_search_actions_menu
		self._on_browse_search_result = on_browse_search_result
		self._on_results_back = on_results_back
		self._on_load_more_results = on_load_more_results
		self._on_announce = on_announce

		root_sizer = wx.BoxSizer(wx.VERTICAL)

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
			value_provider=lambda: self.connection_label.GetLabel(),
		)
		attach_named_accessible(
			self.library_summary_label,
			name=_("Resumo da biblioteca do YouTube Music"),
			value_provider=lambda: self.library_summary_label.GetLabel(),
		)
		attach_named_accessible(
			self.status_message_label,
			name=_("Mensagem da central do YouTube Music"),
			value_provider=lambda: self.status_message_label.GetLabel(),
		)

		status_box.Add(self.connection_label, 0, wx.ALL | wx.EXPAND, 6)
		status_box.Add(self.library_summary_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
		status_box.Add(self.status_message_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)

		button_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.connect_button = wx.Button(self, label=_("&Conectar conta..."))
		self.disconnect_button = wx.Button(self, label=_("&Desconectar conta"))
		self.refresh_button = wx.Button(self, label=_("Atuali&zar biblioteca"))
		self.new_playlist_button = wx.Button(self, label=_("&Nova playlist..."))

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
			(
				self.new_playlist_button,
				_("Criar nova playlist no YouTube Music"),
				_("Cria uma nova playlist (privada) na conta conectada do YouTube Music."),
			),
		):
			button.SetName(name)
			button.SetToolTip(description)
			button_sizer.Add(button, 0, wx.RIGHT, 8)

		status_box.Add(button_sizer, 0, wx.ALL | wx.EXPAND, 6)
		root_sizer.Add(status_box, 0, wx.ALL | wx.EXPAND, 10)

		search_row = wx.BoxSizer(wx.HORIZONTAL)
		search_label = wx.StaticText(self, label=_("Buscar ou colar link:"))
		self.search_query_ctrl = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
		self.search_query_ctrl.SetName(_("Buscar no YouTube Music e no YouTube, ou colar um link"))
		self.search_query_ctrl.SetToolTip(
			_("Digite o que procura e pressione Enter. Um link de playlist, mix ou vídeo colado aqui é aberto direto.")
		)
		search_scope_label = wx.StaticText(self, label=_("Em:"))
		self.search_scope_choice = wx.Choice(
			self,
			choices=[option.label for option in YOUTUBE_SEARCH_SCOPE_OPTIONS],
		)
		self.search_scope_choice.SetSelection(0)
		self.search_scope_choice.SetName(_("Onde buscar"))
		search_row.Add(search_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
		search_row.Add(self.search_query_ctrl, 1, wx.RIGHT, 12)
		search_row.Add(search_scope_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
		search_row.Add(self.search_scope_choice, 0)

		self.search_results_label = wx.StaticText(self, label="")
		self.search_results_label.SetName(_("Lista atual do YouTube Music"))
		attach_named_accessible(
			self.search_results_label,
			name=_("Lista atual do YouTube Music"),
			value_provider=lambda: self.search_results_label.GetLabel(),
		)

		self.search_results_list = VirtualItemsListCtrl(self, self._get_search_result_label)
		self.search_results_list.SetName("YouTube Music")
		self.search_results_list.SetMinSize((-1, 180))

		self.search_actions_button = wx.Button(self, label=_("&Ações..."))
		self.search_actions_button.SetName(_("Ações do item selecionado"))
		self.search_actions_button.SetToolTip(
			_("Abre o menu com as ações do item selecionado: tocar, adicionar, ver conteúdo, baixar, salvar e outras.")
		)

		help_label = wx.StaticText(
			self,
			label=_(
				"Enter entra no item ou toca; Shift+Enter adiciona sem tocar. "
				"Seta para a direita mostra o que há dentro e Backspace volta. "
				"Descer além do último item carrega mais. Shift+F10 abre as ações."
			),
		)
		help_label.Wrap(620)

		root_sizer.Add(search_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
		root_sizer.Add(self.search_results_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
		root_sizer.Add(self.search_results_list, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
		root_sizer.Add(self.search_actions_button, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
		root_sizer.Add(help_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

		self.SetSizer(root_sizer)

		self.connect_button.Bind(wx.EVT_BUTTON, lambda _event: self._on_connect())
		self.disconnect_button.Bind(wx.EVT_BUTTON, lambda _event: self._on_disconnect())
		self.refresh_button.Bind(wx.EVT_BUTTON, lambda _event: self._on_refresh_library())
		self.new_playlist_button.Bind(wx.EVT_BUTTON, self._on_new_playlist_button)
		self.search_actions_button.Bind(wx.EVT_BUTTON, self._on_search_actions_button)

		self.search_query_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_search_query_enter)
		self.search_results_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_search_selection_changed)
		self.search_results_list.Bind(wx.EVT_LIST_ITEM_DESELECTED, self._on_search_selection_changed)
		self.search_results_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_open_search_result_event)
		self.search_results_list.Bind(wx.EVT_CONTEXT_MENU, self._on_search_list_context_menu)
		self.search_results_list.Bind(wx.EVT_CHAR_HOOK, self._on_search_list_key_down)

		self._refresh_search_results_list()
		self._update_action_state(connected=False, operation_in_progress=False)

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

	def _update_search_actions(self):
		self.search_actions_button.Enable(
			bool(
				(self.get_selected_search_results() or self._can_go_back)
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
		self.new_playlist_button.Enable(connected and not operation_in_progress)
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
		has_more_results=False,
		can_go_back=False,
		selected_result_id="",
	):
		self.Freeze()
		try:
			selected_search_result_ids = [selected_result_id] if selected_result_id else self.get_selected_search_result_ids()
			self._has_more_results = bool(has_more_results)
			self._can_go_back = bool(can_go_back)

			playlist_count = len(playlists or [])
			self._all_search_results = list(search_results or [])
			if connected and account_name:
				self.connection_label.SetLabel(_("Conta: {name}.").format(name=account_name))
			elif connected and operation_in_progress:
				self.connection_label.SetLabel(_("Conta: carregando informações da conta…"))
			elif connected:
				self.connection_label.SetLabel(_("Conta: conectada (nome ainda não carregado)."))
			else:
				self.connection_label.SetLabel(_("Conta: não conectada."))
			if connected:
				if not playlist_count and operation_in_progress:
					self.library_summary_label.SetLabel(_("Biblioteca: carregando playlists e mixes…"))
				else:
					summary_suffix = _(" Há mais para carregar.") if has_more_playlists else ""
					self.library_summary_label.SetLabel(
						ngettext(
							"Biblioteca: {count} playlist ou mix disponível.",
							"Biblioteca: {count} playlists e mixes disponíveis.",
							playlist_count,
						).format(count=playlist_count) + summary_suffix
					)
			else:
				self.library_summary_label.SetLabel(_("Biblioteca: conecte uma conta para listar playlists e mixes."))

			self.status_message_label.SetLabel(str(status_message or "").strip())
			self.status_message_label.Wrap(620)
			self.search_results_label.SetLabel(str(search_summary or "").strip())
			self._refresh_search_results_list(selected_result_id=selected_search_result_ids)
			self._update_action_state(connected=connected, operation_in_progress=operation_in_progress)
			self.Layout()
		finally:
			self.Thaw()

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

	def focus_search_results(self):
		"""Leva o foco à lista de resultados, se houver algo nela."""
		if self.search_results_list.GetItemCount() > 0:
			self.search_results_list.SetFocus()

	def get_search_query(self):
		return str(self.search_query_ctrl.GetValue() or "").strip()

	def get_search_scope_id(self):
		selection = self.search_scope_choice.GetSelection()
		if selection == wx.NOT_FOUND or not 0 <= selection < len(YOUTUBE_SEARCH_SCOPE_OPTIONS):
			return YOUTUBE_SEARCH_SCOPE_OPTIONS[0].scope_id
		return YOUTUBE_SEARCH_SCOPE_OPTIONS[selection].scope_id

	def _on_search_query_enter(self, _event):
		if self.get_search_query():
			self._on_search()

	def _on_search_selection_changed(self, _event):
		self._update_search_actions()

	def _browse_selected_search_result(self):
		selected_results = self.get_selected_search_results()
		if len(selected_results) != 1 or not getattr(selected_results[0], "can_browse", False):
			return False
		if not callable(self._on_browse_search_result):
			return False
		self._on_browse_search_result()
		return True

	def _maybe_trigger_load_more_results(self):
		if not self._has_more_results or self._operation_in_progress:
			return False
		if not callable(self._on_load_more_results):
			return False
		last_index = self.search_results_list.GetItemCount() - 1
		if last_index < 0 or self.search_results_list.GetFocusedItem() < last_index:
			return False
		self._on_load_more_results()
		return True

	def _on_open_search_result_event(self, _event):
		selected_results = self.get_selected_search_results()
		if not selected_results:
			return
		# O duplo clique faz o mesmo que Enter: entra no que não toca, toca o resto.
		if (
			len(selected_results) == 1
			and getattr(selected_results[0], "opens_on_enter", False)
			and self._browse_selected_search_result()
		):
			return
		self._on_add_search_results_to_current_playlist(play=True)

	def _on_new_playlist_button(self, _event):
		if callable(self._on_create_playlist):
			self._on_create_playlist()

	def _on_search_actions_button(self, event):
		if not callable(self._on_show_search_actions_menu):
			return
		self._on_show_search_actions_menu(self, event.GetEventObject())

	def _on_search_list_context_menu(self, _event):
		if callable(self._on_show_search_actions_menu):
			self._on_show_search_actions_menu(self, self.search_results_list)

	def _on_search_list_key_down(self, event):
		key_code = event.GetKeyCode()
		if key_code == wx.WXK_TAB:
			event.Skip()
			return

		if key_code == wx.WXK_F10 and event.ShiftDown():
			self._on_search_actions_button(event)
			return

		has_modifiers = event.ControlDown() or event.AltDown() or event.ShiftDown()

		if key_code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and not event.ControlDown() and not event.AltDown():
			selected_results = self.get_selected_search_results()
			if selected_results:
				# Pasta, canal e artista não tocam: Enter entra neles.
				if (
					len(selected_results) == 1
					and not event.ShiftDown()
					and getattr(selected_results[0], "opens_on_enter", False)
					and self._browse_selected_search_result()
				):
					return
				# Como no explorador de pastas: Enter toca, Shift+Enter adiciona sem tocar.
				self._on_add_search_results_to_current_playlist(play=not event.ShiftDown())
				return

		if key_code in (wx.WXK_RIGHT, wx.WXK_NUMPAD_RIGHT) and not has_modifiers:
			if self._browse_selected_search_result():
				return

		is_back_key = (
			(key_code == wx.WXK_BACK and not has_modifiers)
			or (key_code in (wx.WXK_LEFT, wx.WXK_NUMPAD_LEFT) and event.AltDown() and not event.ControlDown())
			or (key_code in (wx.WXK_LEFT, wx.WXK_NUMPAD_LEFT) and not has_modifiers and self._can_go_back)
		)
		if is_back_key and callable(self._on_results_back):
			self._on_results_back()
			return

		if key_code in (wx.WXK_DOWN, wx.WXK_NUMPAD_DOWN, wx.WXK_PAGEDOWN, wx.WXK_NUMPAD_PAGEDOWN) and not has_modifiers:
			if self._maybe_trigger_load_more_results():
				return

		event.Skip()
