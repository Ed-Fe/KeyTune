"""Modo Shorts: os shorts do YouTube tocam numa aba, cada um repete até você passar para o próximo."""

import threading

import wx

from player.youtube_music import account_lists
from player.youtube_music.playlists import extract_video_id_from_text

from ...constants import REPEAT_ONE
from ...i18n import _
from ...log import get_logger


_logger = get_logger(__name__)

# Quantos shorts faltam para o fim da fila quando a próxima leva é pedida.
SHORTS_REFILL_THRESHOLD = 3


def short_label(result):
    """O que o leitor de tela fala a cada short: o título e o canal."""
    channel = str(getattr(result, "subtitle", "") or "").strip()
    return f"{result.title} — {channel}" if channel else result.title


class ShortsMixin:
    def start_youtube_shorts_session(self):
        """Abre a aba **Shorts** e toca o primeiro; cada short repete até a tecla de próximo."""
        if not self._ensure_youtube_music_authenticated():
            return False

        def worker():
            results = account_lists.shorts_page(0, 15).results
            if not results:
                raise RuntimeError(_("O YouTube não trouxe nenhum short agora."))
            return results

        def on_done(results):
            items = [result.playback_url for result in results]
            labels = [short_label(result) for result in results]
            index = self._open_prepared_media_playlist(
                items,
                _("Shorts"),
                browser_item_labels=labels,
                announce_message=_("Shorts: {title}. Próximo item passa para o seguinte.").format(title=labels[0]),
            )
            state = self._get_playlist_state(index) if index != wx.NOT_FOUND else None
            if state is None:
                return
            state.repeat_mode = REPEAT_ONE
            state.shorts_session = True

        def on_error(exc):
            wx.MessageBox(
                _("Não foi possível abrir os Shorts agora.")
                + "\n\n"
                + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc)),
                "KeyTube",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        self._announce(_("Abrindo os Shorts."))
        return self._run_youtube_music_background_task(worker, on_done, on_error=on_error)

    def _shorts_session_active(self, state):
        return bool(getattr(state, "shorts_session", False))

    def _shorts_session_refill(self, state, *, force=False):
        """Busca mais shorts quando a fila está acabando (ou já acabou, com *force*)."""
        if not self._shorts_session_active(state) or getattr(state, "shorts_loading", False):
            return False
        remaining = len(state.items) - 1 - max(0, int(state.current_index or 0))
        if remaining > SHORTS_REFILL_THRESHOLD and not force:
            return False
        last_media = str(state.items[-1] or "").strip() if state.items else ""
        if not last_media:
            return False

        state.shorts_loading = True

        def worker():
            try:
                results = account_lists.shorts_after(last_media)
            except Exception as exc:
                _logger.warning("Não foi possível buscar mais shorts: %s", exc, exc_info=True)
                results = []
            wx.CallAfter(self._finish_shorts_refill, state, results, force)

        threading.Thread(target=worker, daemon=True).start()
        return True

    def _finish_shorts_refill(self, state, results, announce_next):
        state.shorts_loading = False
        if self._resolve_playlist_state_index(state) == wx.NOT_FOUND:
            return
        known = {extract_video_id_from_text(item) for item in state.items}
        fresh = [result for result in results if result.video_id and result.video_id not in known]
        if not fresh:
            if announce_next:
                self._announce(_("O YouTube não trouxe mais shorts agora."))
            return
        first_new_index = len(state.items)
        state.append_items([r.playback_url for r in fresh], [short_label(r) for r in fresh])
        self._refresh_playlist_browser()
        if announce_next and self._get_active_playlist_state() is state:
            state.select_index(first_new_index, reset_playback_order=False)
            self._play_media(index=self._get_active_playlist_index())
