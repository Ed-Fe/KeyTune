"""Escolha da faixa de áudio (original ou dublagem) da mídia do YouTube que está tocando."""

import wx

from player.youtube_music import audio_tracks as youtube_audio_tracks
from player.youtube_music.playlists import extract_video_id_from_text

from ...i18n import _


class AudioTrackMixin:
    def choose_current_media_audio_track(self):
        """Lista as faixas de áudio da mídia atual e passa a tocar a escolhida, do mesmo ponto."""
        state = self._get_active_playlist_state()
        media_path = str(getattr(state, "current_media_path", "") or "").strip()
        if not media_path or not extract_video_id_from_text(media_path):
            self._announce(_("A mídia atual não é do YouTube: não há faixas de áudio para escolher."))
            return False

        self._announce(_("Procurando as faixas de áudio desta mídia."))

        def worker():
            return youtube_audio_tracks.list_audio_tracks(media_path)

        def on_success(tracks):
            self._pick_audio_track(media_path, tracks)

        def on_error(exc):
            wx.MessageBox(
                _("Não foi possível listar as faixas de áudio agora.")
                + "\n\n"
                + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc)),
                "KeyTube",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    def _pick_audio_track(self, media_path, tracks):
        state = self._get_active_playlist_state()
        if str(getattr(state, "current_media_path", "") or "").strip() != media_path:
            # A faixa mudou enquanto a lista chegava: a escolha já não seria desta mídia.
            return False
        if len(tracks) < 2:
            self._announce(_("Esta mídia tem só uma faixa de áudio."))
            return False

        choice, _for_this_media = youtube_audio_tracks.audio_choice_for(media_path)
        current = youtube_audio_tracks.pick_track(tracks, choice) or next(
            (track for track in tracks if track.default), tracks[0]
        )
        dialog = wx.SingleChoiceDialog(
            self,
            _("Faixa de áudio desta mídia:"),
            _("Idioma do áudio"),
            [youtube_audio_tracks.audio_track_label(track) for track in tracks],
        )
        try:
            dialog.SetSelection(tracks.index(current))
            if dialog.ShowModal() != wx.ID_OK:
                return False
            chosen = tracks[dialog.GetSelection()]
        finally:
            dialog.Destroy()

        if chosen is current:
            return False
        return self._play_current_media_with_audio_track(media_path, chosen)

    def _play_current_media_with_audio_track(self, media_path, track):
        youtube_audio_tracks.set_media_audio_choice(media_path, track.track_id)
        service = self._youtube_music_service_for_playback()
        if service is not None:
            service.invalidate_cached_stream(media_path)

        self._capture_active_playlist_state()
        state = self._get_active_playlist_state()
        self._queue_media_start(
            media_path,
            tab_index=self._get_active_playlist_index(),
            announce_message=_("Áudio em {name}.").format(name=youtube_audio_tracks.audio_track_label(track)),
            restore_position_ms=int(getattr(state, "last_position_ms", 0) or 0),
            pause_after_start=not getattr(state, "was_playing", True),
        )
        return True
