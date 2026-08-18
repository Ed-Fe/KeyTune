"""Favoritos (Ctrl+D) e avaliações (Ctrl+0 a Ctrl+5) das mídias locais.

Os comandos agem sobre a seleção da lista de itens; sem seleção, agem sobre a
mídia que está tocando. Cada mudança é falada, porque o marcador não aparece no
rótulo do item.
"""

from ...i18n import _, ngettext
from ...smart_library import format_rating


class SmartLibraryRatingsMixin:
    def _refresh_marks_after_change(self):
        """Repinta a lista para o novo favorito/avaliação aparecer na hora."""
        self._invalidate_library_marks()
        self._refresh_library_marks()

    def _toggle_favorite_for_selection(self):
        service = self._smart_library()
        if service is None:
            self._announce_smart_library_unavailable()
            return

        media_paths = self._smart_library_selected_media_paths()
        if not media_paths:
            self._announce(_("Nenhum item selecionado para favoritar."))
            return

        if len(media_paths) == 1:
            media_path = media_paths[0]
            label = self._smart_library_label_for(media_path)
            new_state = service.toggle_favorite(media_path, label=label)
            if new_state is None:
                self._announce(_("Não foi possível alterar o favorito deste item."))
                return

            self._refresh_marks_after_change()
            if new_state:
                self._announce(_("{item} marcado como favorito.").format(item=label))
            else:
                self._announce(_("{item} não é mais favorito.").format(item=label))
            return

        # Em seleção múltipla, favoritar todos é mais previsível do que
        # inverter item a item.
        marked = 0
        for media_path in media_paths:
            if service.set_favorite(media_path, True, label=self._smart_library_label_for(media_path)):
                marked += 1

        if not marked:
            self._announce(_("Não foi possível favoritar os itens selecionados."))
            return

        self._refresh_marks_after_change()
        self._announce(
            ngettext(
                "{count} item marcado como favorito.",
                "{count} itens marcados como favoritos.",
                marked,
            ).format(count=marked)
        )

    def _rate_selection(self, rating):
        service = self._smart_library()
        if service is None:
            self._announce_smart_library_unavailable()
            return

        media_paths = self._smart_library_selected_media_paths()
        if not media_paths:
            self._announce(_("Nenhum item selecionado para avaliar."))
            return

        rated = 0
        for media_path in media_paths:
            if service.set_rating(media_path, rating, label=self._smart_library_label_for(media_path)):
                rated += 1

        if not rated:
            self._announce(_("Não foi possível avaliar os itens selecionados."))
            return

        self._refresh_marks_after_change()
        rating_label = format_rating(rating)
        if rated == 1:
            self._announce(
                _("{item}: {rating}.").format(
                    item=self._smart_library_label_for(media_paths[0]),
                    rating=rating_label,
                )
            )
        else:
            self._announce(
                ngettext(
                    "{count} item avaliado: {rating}.",
                    "{count} itens avaliados: {rating}.",
                    rated,
                ).format(count=rated, rating=rating_label)
            )

        if hasattr(self, "_set_status_message"):
            self._set_status_message(_("Avaliação: {rating}.").format(rating=rating_label))

    def _announce_current_media_library_marks(self):
        service = self._smart_library()
        if service is None:
            self._announce_smart_library_unavailable()
            return

        media_paths = self._smart_library_selected_media_paths()
        if not media_paths:
            self._announce(_("Nenhum item selecionado."))
            return

        media_path = media_paths[0]
        record = service.get_record(media_path)
        label = self._smart_library_label_for(media_path)
        if record is None:
            self._announce(_("{item}: ainda não está na biblioteca.").format(item=label))
            return

        favorite_sentence = _("favorito") if record.favorite else _("não é favorito")
        played_sentence = ngettext(
            "reproduzido {count} vez",
            "reproduzido {count} vezes",
            record.play_count,
        ).format(count=record.play_count)
        self._announce(
            _("{item}: {favorite}, {rating}, {played}.").format(
                item=label,
                favorite=favorite_sentence,
                rating=format_rating(record.rating),
                played=played_sentence,
            )
        )

    def on_toggle_favorite(self, _event):
        self._toggle_favorite_for_selection()

    def on_rate_media(self, event):
        rating = getattr(self, "_rating_menu_actions", {}).get(event.GetId())
        if rating is None:
            event.Skip()
            return
        self._rate_selection(rating)

    def on_announce_library_marks(self, _event):
        self._announce_current_media_library_marks()
