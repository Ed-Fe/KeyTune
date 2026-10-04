"""O que acontece quando uma rádio entra no ar no player e o que ela diz que está tocando."""

import threading

from player.radio.media import is_radio_media, radio_stream_url

from ...i18n import _


def clean_radio_stream_title(media_path, station_name, runtime_title):
    """O título que o stream anuncia (ICY), ou vazio quando ele não diz nada de útil.

    Sem título próprio, o player devolve um pedaço do endereço ou o próprio nome
    da estação: nada disso é "a música de agora".
    """
    title = str(runtime_title or "").strip().strip("-–—").strip()
    if not title:
        return ""
    if title.casefold() in radio_stream_url(media_path).casefold():
        return ""
    if title.casefold() == str(station_name or "").strip().casefold():
        return ""
    return title


class RadioNowPlayingMixin:
    def _remember_online_radio_playback(self, media_path):
        """Chamado quando uma mídia começa: guarda os dados da rádio e conta a audição no diretório."""
        self._radio_now_playing_title = ""
        if not is_radio_media(media_path):
            return

        service = self._get_radio_service()
        station = service.station_for_media_path(media_path, self._media_label(media_path))
        if station is None:
            return

        service.remember(station)
        threading.Thread(
            target=service.count_click,
            args=(station,),
            daemon=True,
            name="radio-click",
        ).start()

    def _handle_radio_stream_title(self, media_path, runtime_title):
        """O stream mudou de título: mostra a música de agora sem trocar o nome da rádio na playlist."""
        station_name = self._media_label(media_path)
        title = clean_radio_stream_title(media_path, station_name, runtime_title)
        if title == getattr(self, "_radio_now_playing_title", ""):
            return
        self._radio_now_playing_title = title
        if title:
            self._set_status_message(
                _("{station}: {title}").format(station=station_name, title=title),
                auto_clear_ms=0,
            )

    def _radio_now_playing_sentence(self):
        """Frase para o anúncio de status (S); vazia fora de uma rádio ou sem título no stream."""
        state = self._get_active_playlist_state()
        media_path = getattr(state, "current_media_path", None)
        title = getattr(self, "_radio_now_playing_title", "")
        if not title or not media_path or not is_radio_media(media_path):
            return ""
        return _("Tocando na rádio: {title}.").format(title=title)
