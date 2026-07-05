import wx

from ...constants import LARGE_SEEK_STEP_MS
from ...playlists import ScreenTabState


class KeyNavigationMixin:
    def _window_is_descendant_of(self, window, ancestor):
        current_window = window
        while isinstance(current_window, wx.Window):
            if current_window == ancestor:
                return True
            current_window = current_window.GetParent()

        return False

    def _screen_tab_focusable_windows(self, root_window):
        focusable_windows = []

        def collect(window):
            if not isinstance(window, wx.Window):
                return

            for child in window.GetChildren():
                collect(child)

            if window is root_window:
                return

            if not window.IsShownOnScreen() or not window.IsEnabled():
                return

            accepts_focus = False
            try:
                if not isinstance(window, (wx.Panel, wx.StaticBox, wx.CollapsiblePane)):
                    accepts_focus = bool(window.CanAcceptFocusFromKeyboard() or window.CanAcceptFocus())
            except Exception:
                accepts_focus = False

            if accepts_focus:
                focusable_windows.append(window)

        collect(root_window)
        return focusable_windows

    def _focus_screen_tab_edge_control(self, current_page, *, backward=False):
        focusable_windows = self._screen_tab_focusable_windows(current_page)
        if not focusable_windows:
            return False

        target_window = focusable_windows[-1] if backward else focusable_windows[0]
        try:
            target_window.SetFocus()
            return True
        except Exception:
            return False

    def _navigate_screen_tab_controls(self, *, backward=False):
        current_page = self.notebook.GetCurrentPage() if hasattr(self, "notebook") else None
        if not isinstance(current_page, wx.Window):
            return False

        focusable = self._screen_tab_focusable_windows(current_page)
        if not focusable:
            return False

        focused_window = wx.Window.FindFocus()
        focused_idx = -1
        for i, w in enumerate(focusable):
            if w == focused_window or self._window_is_descendant_of(focused_window, w):
                focused_idx = i
                break

        if focused_idx != -1:
            if backward:
                if focused_idx == 0:
                    try:
                        self.notebook.SetFocus()
                        return True
                    except Exception:
                        return False
                target = focusable[focused_idx - 1]
            else:
                if focused_idx == len(focusable) - 1:
                    try:
                        self.notebook.SetFocus()
                        return True
                    except Exception:
                        return False
                target = focusable[focused_idx + 1]
            try:
                target.SetFocus()
                return True
            except Exception:
                return False
        else:
            return self._focus_screen_tab_edge_control(current_page, backward=backward)

    def _handle_screen_tab_key_down(self, event, current_tab):
        if not isinstance(current_tab, ScreenTabState):
            return False

        key_code = event.GetKeyCode()

        if key_code == wx.WXK_ESCAPE:
            self._close_current_tab()
            return True

        if key_code == wx.WXK_TAB and not event.ControlDown() and not event.AltDown():
            if self._navigate_screen_tab_controls(backward=event.ShiftDown()):
                return True
            event.Skip()
            return True

        event.Skip()
        return True

    def _focused_window_drives_playback(self):
        """Whether bare keys (Space, arrows, letters) should control playback.

        The single-key playback shortcuts belong to the "player surface": the
        frame itself (where focus lands from the video area) and the playlist
        list. Any other focused control — buttons, checkboxes, edit fields,
        screen-tab widgets, the lyrics panel — must own those keys so, e.g.,
        Space activates the control instead of toggling play/pause.
        """
        focused_window = wx.Window.FindFocus()
        if focused_window is None:
            return False
        if focused_window is self:
            return True
        page = self.notebook.GetCurrentPage() if hasattr(self, "notebook") else None
        if page is not None and focused_window is getattr(page, "video_panel", None):
            return True
        browser = self._get_browser_panel()
        if browser is not None and focused_window is getattr(browser, "items_list", None):
            return True
        return False

    def _lyrics_text_is_focused(self):
        lyrics_panel = getattr(self, "lyrics_panel", None)
        if lyrics_panel is None or not lyrics_panel.IsShown():
            return False
        text_ctrl = getattr(lyrics_panel, "lyrics_text_ctrl", None)
        return text_ctrl is not None and wx.Window.FindFocus() == text_ctrl

    def _close_lyrics_panel(self):
        lyrics_panel = getattr(self, "lyrics_panel", None)
        if lyrics_panel is None or not lyrics_panel.IsShown():
            return
        # toggle_lyrics_panel hides the panel and restores focus to wherever it
        # was before the panel opened (not the tab switcher).
        self.toggle_lyrics_panel()

    def on_key_down(self, event):
        key_code = event.GetKeyCode()
        browser = self._get_browser_panel()
        current_tab = self._get_tab_state()

        # A focused text field owns the whole keyboard: caret moves, word jumps
        # (Ctrl+Arrows), selection (Shift+...) and clipboard keys must reach the
        # control, not the global player shortcuts (Left/Right = seek, Ctrl+C =
        # copy media path, etc.). Only Esc and F1 stay global (close panel/tab,
        # help). This covers the lyrics reader and every edit field (Filtro,
        # busca, link).
        if isinstance(wx.Window.FindFocus(), wx.TextEntry) and key_code not in (wx.WXK_ESCAPE, wx.WXK_F1):
            event.Skip()
            return

        # Bare keys (no Ctrl/Alt) drive playback only while focus is on the
        # player surface — the frame or the playlist list. On any other control
        # (buttons, checkboxes, screen-tab widgets, the lyrics copy button) let
        # the control own the key so Space activates it instead of toggling
        # play/pause. Esc, F1 and Tab stay globally routed below.
        if (
            not event.ControlDown()
            and not event.AltDown()
            and key_code not in (wx.WXK_ESCAPE, wx.WXK_F1, wx.WXK_TAB)
            and not self._focused_window_drives_playback()
        ):
            event.Skip()
            return

        if key_code == wx.WXK_F1:
            self.on_show_keyboard_help(None)
            return

        # Ctrl+Alt+L toggles the lyrics panel. Plain Ctrl+L stays reserved for
        # rating the current YouTube Music media (handled further below).
        if event.ControlDown() and event.AltDown() and not event.ShiftDown() and key_code in (ord("L"), ord("l")):
            self.toggle_lyrics_panel()
            return

        # While the lyrics text is focused, Esc closes the panel. Caret keys are
        # handled natively — the player-surface guard above already lets the
        # text control own them instead of driving seek/volume.
        if self._lyrics_text_is_focused() and key_code == wx.WXK_ESCAPE:
            self._close_lyrics_panel()
            return

        if event.ControlDown() and event.ShiftDown() and key_code in (ord("Y"), ord("y")):
            self.on_open_youtube_music(None)
            return

        if key_code == wx.WXK_ESCAPE and isinstance(current_tab, ScreenTabState):
            self._close_current_tab()
            return

        if event.ControlDown() and key_code == wx.WXK_TAB:
            self._cycle_tabs(-1 if event.ShiftDown() else 1)
            return

        if self._handle_screen_tab_key_down(event, current_tab):
            return

        if event.ControlDown() and not event.AltDown() and key_code in (ord("C"), ord("c")):
            if not event.ShiftDown():
                self.on_copy_current_item_path(None)
                return

        if event.ControlDown() and not event.ShiftDown() and not event.AltDown() and key_code in (ord("V"), ord("v")):
            self.on_paste_open_from_clipboard(None)
            return

        if event.ControlDown() and event.ShiftDown() and not event.AltDown() and key_code in (ord("V"), ord("v")):
            self.on_paste_open_from_clipboard_new_playlist(None)
            return

        if browser and browser.is_item_navigation_active():
            if key_code == wx.WXK_TAB and not event.ControlDown() and not event.AltDown():
                self._toggle_navigation_mode()
                return
            event.Skip()
            return

        if not event.ControlDown() and not event.AltDown() and key_code in (ord("E"), ord("e")):
            self._toggle_shuffle()
            return

        if not event.ControlDown() and not event.AltDown() and key_code in (ord("R"), ord("r")):
            self._cycle_repeat_mode()
            return

        if not event.ControlDown() and not event.AltDown() and key_code in (ord("A"), ord("a")):
            self._toggle_related_autoplay()
            return

        if event.AltDown() and not event.ControlDown() and key_code == wx.WXK_UP:
            self._move_current_item(-1)
            return

        if event.AltDown() and not event.ControlDown() and key_code == wx.WXK_DOWN:
            self._move_current_item(1)
            return

        if event.AltDown() and not event.ControlDown() and key_code == wx.WXK_LEFT:
            self._play_adjacent_item(-1)
            return

        if event.AltDown() and not event.ControlDown() and key_code == wx.WXK_RIGHT:
            self._play_adjacent_item(1)
            return

        if event.AltDown() and not event.ControlDown() and key_code == wx.WXK_HOME:
            self._jump_to_playlist_boundary(to_last=False)
            return

        if event.AltDown() and not event.ControlDown() and key_code == wx.WXK_END:
            self._jump_to_playlist_boundary(to_last=True)
            return

        if event.ControlDown() and key_code == wx.WXK_PAGEUP:
            self._play_adjacent_item(-1)
            return

        if event.ControlDown() and key_code == wx.WXK_PAGEDOWN:
            self._play_adjacent_item(1)
            return

        if event.ControlDown() and key_code in (ord("T"), ord("t")):
            self.on_new_playlist(None)
            return

        if event.ControlDown() and event.AltDown() and not event.ShiftDown() and key_code in (ord("O"), ord("o")):
            self.on_open_source(None)
            return

        if event.ControlDown() and event.ShiftDown() and key_code in (ord("E"), ord("e")):
            self.on_open_equalizer(None)
            return

        if event.ControlDown() and event.ShiftDown() and key_code in (ord("S"), ord("s")):
            self.on_save_playlist(None)
            return

        if event.ControlDown() and not event.AltDown() and key_code in (ord("L"), ord("l")):
            rate_current_youtube_music_media = getattr(self, "_rate_current_youtube_music_media", None)
            if callable(rate_current_youtube_music_media):
                rate_current_youtube_music_media("DISLIKE" if event.ShiftDown() else "LIKE")
            return

        if event.ControlDown() and key_code in (ord("B"), ord("b")):
            self.on_toggle_playlist_browser(None)
            return

        if event.ControlDown() and key_code == ord(","):
            self.on_open_preferences(None)
            return

        if event.ControlDown() and event.ShiftDown() and key_code in (ord("W"), ord("w")):
            self._close_current_media()
            return

        if event.ControlDown() and key_code in (ord("W"), ord("w")):
            self.on_close_current_tab(None)
            return

        if not event.ControlDown() and not event.AltDown() and key_code in (ord("T"), ord("t")):
            self._announce_playback_time()
            return

        if not event.ControlDown() and not event.AltDown() and key_code in (ord("V"), ord("v")):
            self._announce_current_volume()
            return

        if not event.ControlDown() and not event.AltDown() and key_code in (ord("S"), ord("s")):
            self._announce_player_status()
            return

        if key_code == wx.WXK_TAB:
            self._toggle_navigation_mode()
            return

        if key_code == wx.WXK_SPACE:
            self._toggle_play_pause()
            return

        if key_code == wx.WXK_HOME:
            self._seek_to_start()
            return

        if key_code == wx.WXK_END:
            self._seek_to_end()
            return

        if not event.ControlDown() and event.ShiftDown() and key_code == wx.WXK_LEFT:
            self._seek_relative(-LARGE_SEEK_STEP_MS)
            return

        if not event.ControlDown() and event.ShiftDown() and key_code == wx.WXK_RIGHT:
            self._seek_relative(LARGE_SEEK_STEP_MS)
            return

        if key_code == wx.WXK_LEFT:
            self._seek_relative(-self.settings.seek_step_ms)
            return

        if key_code == wx.WXK_RIGHT:
            self._seek_relative(self.settings.seek_step_ms)
            return

        if key_code == wx.WXK_UP:
            self._change_volume(self.settings.volume_step)
            return

        if key_code == wx.WXK_DOWN:
            self._change_volume(-self.settings.volume_step)
            return

        if not event.ControlDown() and not event.AltDown() and not event.ShiftDown() and key_code == ord("]"):
            self._change_playback_rate(0.25)
            return

        if not event.ControlDown() and not event.AltDown() and not event.ShiftDown() and key_code == ord("["):
            self._change_playback_rate(-0.25)
            return

        if not event.ControlDown() and not event.AltDown() and not event.ShiftDown() and key_code == ord("\\"):
            self._reset_playback_rate()
            return

        if not event.ControlDown() and not event.AltDown() and event.ShiftDown() and key_code == ord("]"):
            self._change_pitch_semitones(1)
            return

        if not event.ControlDown() and not event.AltDown() and event.ShiftDown() and key_code == ord("["):
            self._change_pitch_semitones(-1)
            return

        if not event.ControlDown() and not event.AltDown() and event.ShiftDown() and key_code == ord("\\"):
            self._reset_pitch_semitones()
            return

        event.Skip()
