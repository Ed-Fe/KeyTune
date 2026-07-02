import json
import ssl
import threading
import traceback
import urllib.error
import urllib.parse
import urllib.request
import wx

from ..accessibility import attach_named_accessible
from ..i18n import _

# Attempt to load the YouTube Music API which should be available in KeyTune's environment
try:
    from ytmusicapi import YTMusic
    HAS_YTMUSIC = True
except ImportError:
    HAS_YTMUSIC = False


class LyricsPanel(wx.Panel):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        
        self.SetName(_("Painel de Letras"))
        self.current_track_info = _("desconhecida")
        
        # Main sizer for the panel
        root_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Multiline, read-only text control for the lyrics
        self.lyrics_text_ctrl = wx.TextCtrl(
            self, 
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.VSCROLL
        )
        self.lyrics_text_ctrl.SetName(_("Letra da música"))
        
        # Accessibility hook for screen readers
        attach_named_accessible(
            self.lyrics_text_ctrl,
            name=_("Letra da música"),
            description=_("Área de leitura das letras. Use as setas para navegar pelo texto."),
            value_provider=lambda: self.lyrics_text_ctrl.GetValue()
        )
        
        root_sizer.Add(self.lyrics_text_ctrl, 1, wx.EXPAND | wx.ALL, 10)
        self.SetSizer(root_sizer)
        
    def update_lyrics(self, text):
        """
        Updates the text control with new lyrics on the main UI thread.
        """
        if text:
            self.lyrics_text_ctrl.SetValue(text)
        else:
            self.lyrics_text_ctrl.SetValue(_("Letra não encontrada para esta mídia."))

    def load_lyrics_for_track(self, artist, title):
        """
        Starts a background thread to fetch lyrics without freezing the UI.
        """
        artist_str = str(artist or "").strip()
        title_str = str(title or "").strip()
        
        if title_str and artist_str:
            self.current_track_info = f"{title_str}, {artist_str}"
        elif title_str:
            self.current_track_info = title_str
        else:
            self.current_track_info = _("desconhecida")
            
        dynamic_name = _("Letra da música {info}").format(info=self.current_track_info)
        self.lyrics_text_ctrl.SetName(dynamic_name)
        
        attach_named_accessible(
            self.lyrics_text_ctrl,
            name=dynamic_name,
            description=_("Área de leitura das letras. Use as setas para navegar pelo texto."),
            value_provider=lambda: self.lyrics_text_ctrl.GetValue()
        )

        self.lyrics_text_ctrl.SetValue(_("Buscando letra..."))
        thread = threading.Thread(target=self._fetch_lyrics_worker, args=(artist_str, title_str))
        thread.daemon = True
        thread.start()

    def _fetch_lyrics_worker(self, artist, title):
        """
        Dual-engine worker method: attempts LRCLIB first, falls back to YTMusic API.
        """
        search_query = f"{artist} {title}".strip()
        if not search_query:
            wx.CallAfter(self.update_lyrics, _("Informações da faixa incompletas para buscar a letra."))
            return

        lyrics_found = False

        # --- ENGINE 1: LRCLIB (Fast, great for international/mainstream music) ---
        try:
            base_url = "https://lrclib.net/api/search"
            params = urllib.parse.urlencode({'q': search_query})
            url = f"{base_url}?{params}"

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json'
            }
            req = urllib.request.Request(url, headers=headers)
            
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            with urllib.request.urlopen(req, context=ctx, timeout=8) as response:
                if response.getcode() == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    for track in data:
                        raw_lyrics = track.get('plainLyrics')
                        if raw_lyrics:
                            found_title = track.get('trackName', _('Desconhecido'))
                            found_artist = track.get('artistName', _('Desconhecido'))
                            
                            safe_lyrics = raw_lyrics.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\r\n')
                            header = _("[LRCLIB: {title} - {artist}]").format(title=found_title, artist=found_artist)
                            lyrics = f"{header}\r\n\r\n{safe_lyrics}"
                            
                            wx.CallAfter(self.update_lyrics, lyrics)
                            lyrics_found = True
                            return
        except Exception:
            pass # Fails silently and moves to Engine 2

        # --- ENGINE 2: YOUTUBE MUSIC (Slower, but massive library for regional/obscure music) ---
        if not lyrics_found and HAS_YTMUSIC:
            wx.CallAfter(self.lyrics_text_ctrl.SetValue, _("Buscando letra no YouTube Music..."))
            try:
                yt = YTMusic()
                search_results = yt.search(search_query, filter="songs")
                if search_results:
                    video_id = search_results[0].get('videoId')
                    found_title = search_results[0].get('title', _('Desconhecido'))
                    
                    artists_list = search_results[0].get('artists', [])
                    found_artist = ", ".join([a['name'] for a in artists_list]) if artists_list else _('Desconhecido')

                    if video_id:
                        watch_playlist = yt.get_watch_playlist(videoId=video_id)
                        lyrics_id = watch_playlist.get('lyrics')
                        
                        if lyrics_id:
                            lyrics_data = yt.get_lyrics(lyrics_id)
                            raw_lyrics = lyrics_data.get('lyrics')
                            if raw_lyrics:
                                safe_lyrics = raw_lyrics.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\r\n')
                                header = _("[YT Music: {title} - {artist}]").format(title=found_title, artist=found_artist)
                                lyrics_text = f"{header}\r\n\r\n{safe_lyrics}"
                                
                                wx.CallAfter(self.update_lyrics, lyrics_text)
                                lyrics_found = True
                                return
            except Exception:
                pass # Fails silently if YTM also doesn't have the lyrics

        # --- FINAL FALLBACK: NOT FOUND ANYWHERE ---
        if not lyrics_found:
            msg = _("Letra não encontrada em nenhum banco de dados para: {query}").format(query=search_query)
            wx.CallAfter(self.update_lyrics, msg)