"""Retomada de vídeos do YouTube a partir da barra de progresso da conta.

As listas do YouTube mostram até onde a conta assistiu cada vídeo. A posição vale uma
vez, na próxima vez que o vídeo começar a tocar a partir da lista, e só nas mesmas
condições da retomada comum (preferências "Retomar de onde parou"): vídeo longo o
bastante e longe das pontas, para que uma música nunca recomece no meio.

Depois que o vídeo toca no KeyTune, a barra antiga da lista deixa de valer: daí em
diante quem sabe onde ele parou é a biblioteca, e o YouTube recebe a posição nova.
"""

from player.constants import DEFAULT_SMART_LIBRARY_RESUME_EDGE_SECONDS, DEFAULT_SMART_LIBRARY_RESUME_MINIMUM_MINUTES
from player.smart_library.resume import ResumeStore
from player.youtube_music.playlists import extract_video_id_from_text


class ResumeHintsMixin:
    def _youtube_resume_position_is_useful(self, position_ms, duration_ms):
        """Se retomar *position_ms* de um vídeo de *duration_ms* segue as regras de retomada."""
        settings = getattr(self, "settings", None)
        if settings is not None and not getattr(settings, "smart_library_resume_enabled", True):
            return False
        minimum_duration_ms = getattr(
            settings, "smart_library_resume_minimum_ms", DEFAULT_SMART_LIBRARY_RESUME_MINIMUM_MINUTES * 60 * 1000
        )
        edges_ms = getattr(settings, "smart_library_resume_edge_ms", DEFAULT_SMART_LIBRARY_RESUME_EDGE_SECONDS * 1000)
        return ResumeStore.should_remember(
            position_ms,
            duration_ms,
            minimum_duration_ms=minimum_duration_ms,
            ignore_edges_ms=edges_ms,
        )

    def _remember_youtube_resume_hint(self, search_result):
        """Guarda onde retomar o vídeo de *search_result*, se a lista informou e vale retomar."""
        position_ms = int(getattr(search_result, "resume_seconds", 0) or 0) * 1000
        duration_ms = int(getattr(search_result, "duration_seconds", 0) or 0) * 1000
        video_id = str(getattr(search_result, "video_id", "") or "").strip()
        if position_ms <= 0 or not video_id:
            return
        # Já tocou nesta sessão: a barra da lista pode ser de antes disso.
        if video_id in self.__dict__.get("_youtube_played_video_ids", ()):
            return
        if not self._youtube_resume_position_is_useful(position_ms, duration_ms):
            return
        hints = self.__dict__.setdefault("_youtube_resume_hints", {})
        hints[video_id] = position_ms

    def _take_youtube_resume_hint_ms(self, media_path):
        """A posição de retomada do vídeo *media_path*, ou 0; chamar sempre que ele começa a tocar.

        A dica é usada uma vez só, e o vídeo fica marcado como tocado para que uma lista
        antiga não traga a posição de volta.
        """
        video_id = extract_video_id_from_text(media_path)
        if not video_id:
            return 0
        self.__dict__.setdefault("_youtube_played_video_ids", set()).add(video_id)
        hints = self.__dict__.get("_youtube_resume_hints")
        if not hints:
            return 0
        return int(hints.pop(video_id, 0) or 0)
