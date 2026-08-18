"""Retomada por arquivo para mídias longas (podcasts, audiolivros, vídeos).

A posição é gravada periodicamente enquanto a faixa toca e consultada quando
ela recomeça. Só vale para mídias locais e longas: pular de volta para o meio de
uma música de três minutos seria irritante, não útil.
"""

from ...i18n import _, ngettext
from ...library import is_remote_media_path


class SmartLibraryResumeMixin:
    def _resume_is_enabled_for(self, media_path):
        if not getattr(self.settings, "smart_library_resume_enabled", True):
            return False
        if self._smart_library() is None:
            return False
        # Streams remotos não têm uma linha do tempo estável entre sessões.
        return not is_remote_media_path(media_path)

    def _library_resume_position_ms(self, media_path):
        """Posição salva para esta mídia, ou 0 quando não há nada a retomar."""
        if not self._resume_is_enabled_for(media_path):
            return 0

        service = self._smart_library()
        if service is None:
            return 0

        return service.resume_position_ms(media_path)

    def _announce_resume_position(self, media_path, position_ms):
        if position_ms <= 0:
            return

        formatter = getattr(self, "_format_time_ms", None)
        position_label = formatter(position_ms) if callable(formatter) else str(position_ms // 1000)
        message = _("Retomando {item} em {position}.").format(
            item=self._smart_library_label_for(media_path),
            position=position_label,
        )
        if hasattr(self, "_set_status_message"):
            self._set_status_message(message)

    def _maybe_save_resume_position(self, media_path, position_ms, duration_ms):
        service = self._smart_library()
        if service is None or not self._resume_is_enabled_for(media_path):
            return False

        if not service.should_remember_position(
            position_ms,
            duration_ms,
            minimum_duration_ms=self.settings.smart_library_resume_minimum_ms,
            ignore_edges_ms=self.settings.smart_library_resume_edge_ms,
        ):
            # Fora da janela útil: se havia uma marca antiga (a faixa chegou ao
            # fim, por exemplo), ela deixa de valer.
            tracking_state = getattr(self, "_smart_library_playback_tracking", None)
            if tracking_state and tracking_state.get("resume_saved"):
                tracking_state["resume_saved"] = False
                service.forget_position(media_path)
            return False

        service.remember_position(
            media_path,
            position_ms,
            duration_ms=duration_ms,
            label=self._smart_library_label_for(media_path),
        )
        tracking_state = getattr(self, "_smart_library_playback_tracking", None)
        if tracking_state:
            tracking_state["resume_saved"] = True
        return True

    def _forget_resume_position(self, media_path):
        service = self._smart_library()
        if service is None:
            return
        service.forget_position(media_path)

    def _resume_entry_label(self, record):
        """Rótulo com o ponto de parada, para a lista "Continuar ouvindo"."""
        formatter = getattr(self, "_format_time_ms", None)
        if not callable(formatter) or record.resume_position_ms <= 0:
            return record.display_label

        if record.duration_ms > 0:
            position = _("{position} de {total}").format(
                position=formatter(record.resume_position_ms),
                total=formatter(record.duration_ms),
            )
        else:
            position = formatter(record.resume_position_ms)

        return _("{item} — parou em {position}").format(item=record.display_label, position=position)

    def _open_continue_listening_playlist(self):
        service = self._smart_library()
        if service is None:
            self._announce_smart_library_unavailable()
            return

        pending = service.pending_resumes()
        if not pending:
            self._announce(_("Nada para continuar ouvindo. Nenhuma mídia longa está pela metade."))
            return

        self._open_prepared_media_playlist(
            [record.media_path for record in pending],
            _("Continuar ouvindo"),
            browser_item_labels=[self._resume_entry_label(record) for record in pending],
            announce_message=ngettext(
                "{count} mídia para continuar ouvindo.",
                "{count} mídias para continuar ouvindo.",
                len(pending),
            ).format(count=len(pending)),
        )

    def _clear_all_resume_positions(self):
        service = self._smart_library()
        if service is None:
            self._announce_smart_library_unavailable()
            return

        if service.clear_resume_positions():
            self._announce(_("Posições de retomada apagadas."))
        else:
            self._announce(_("Não foi possível apagar as posições de retomada."))

    def on_continue_listening(self, _event):
        self._open_continue_listening_playlist()

    def on_clear_resume_positions(self, _event):
        self._clear_all_resume_positions()
