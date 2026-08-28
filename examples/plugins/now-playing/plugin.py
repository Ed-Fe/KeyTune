"""Plugin de exemplo que mostra menus, abas e telas do KeyTune."""

import wx

from player.i18n import _


class Plugin:
    def __init__(self, api):
        self.api = api

    def on_start(self):
        self.api.add_menu_action("announce-current", _("Anunciar faixa atual"), self.announce, submenu=_("Exemplos"))
        self.api.add_menu_action("announce-library", _("Anunciar resumo da biblioteca"), self.announce_library, submenu=_("Exemplos"))
        self.api.add_tab("now-playing", _("Exemplo: faixa atual"), self.create_now_playing_tab)
        self.api.add_view("library-summary", _("Exemplo: resumo da biblioteca"), self.create_library_view)
        starts = int(self.api.get_setting("starts", 0)) + 1
        self.api.set_setting("starts", starts)

    def announce(self):
        state = self.api.playback_state()
        self.api.notify(state.get("media_path") or _("Nenhuma mídia em reprodução."))

    def announce_library(self):
        playlists = self.api.playlists()
        self.api.notify(_("{count} lista(s) carregada(s) na biblioteca.").format(count=len(playlists)))

    def create_now_playing_tab(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        title = wx.StaticText(panel, label=_("Faixa atual"))
        title.SetFont(title.GetFont().Bold())
        state_label = wx.StaticText(panel, label="")
        state_label.SetName(_("Informações da faixa atual"))
        refresh = wx.Button(panel, label=_("&Atualizar"))
        announce = wx.Button(panel, label=_("&Anunciar faixa"))

        def update_state(_event=None):
            state = self.api.playback_state()
            media = state.get("media_path") or _("Nenhuma mídia em reprodução.")
            try:
                position = float(state.get("position") or 0)
            except (TypeError, ValueError):
                position = 0
            state_label.SetLabel(_("{media}\nPosição: {position:.1f} segundos").format(media=media, position=position))
            panel.Layout()

        refresh.Bind(wx.EVT_BUTTON, update_state)
        announce.Bind(wx.EVT_BUTTON, lambda _event: self.announce())
        sizer.Add(title, 0, wx.ALL, 12)
        sizer.Add(state_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
        sizer.Add(refresh, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        sizer.Add(announce, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        panel.SetSizer(sizer)
        update_state()
        return panel

    def create_library_view(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        title = wx.StaticText(panel, label=_("Resumo da biblioteca"))
        title.SetFont(title.GetFont().Bold())
        summary = wx.StaticText(panel, label="")
        summary.SetName(_("Resumo das listas carregadas"))
        refresh = wx.Button(panel, label=_("&Atualizar resumo"))

        def update_summary(_event=None):
            playlists = self.api.playlists()
            lines = [_("Listas carregadas: {count}").format(count=len(playlists))]
            for playlist in playlists:
                lines.append(
                    _("{name}: {count} item(ns)").format(
                        name=playlist.get("title") or _("Sem nome"),
                        count=len(playlist.get("items", [])),
                    )
                )
            summary.SetLabel("\n".join(lines))
            panel.Layout()

        refresh.Bind(wx.EVT_BUTTON, update_summary)
        sizer.Add(title, 0, wx.ALL, 12)
        sizer.Add(summary, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
        sizer.Add(refresh, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        panel.SetSizer(sizer)
        update_summary()
        return panel
