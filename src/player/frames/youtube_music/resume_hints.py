"""Retomada de vídeos do YouTube a partir do histórico da conta.

O histórico diz onde a conta parou cada vídeo. A posição vale uma vez, na próxima
vez que o vídeo começar a tocar a partir da lista; depois disso a retomada comum
(posição salva pelo KeyTune) não se aplica a mídias remotas.
"""

from player.youtube_music.playlists import extract_video_id_from_text


class ResumeHintsMixin:
    def _remember_youtube_resume_hint(self, search_result):
        """Guarda onde retomar o vídeo de *search_result*, se o histórico informou."""
        seconds = int(getattr(search_result, "resume_seconds", 0) or 0)
        video_id = str(getattr(search_result, "video_id", "") or "").strip()
        if seconds <= 0 or not video_id:
            return
        hints = self.__dict__.setdefault("_youtube_resume_hints", {})
        hints[video_id] = seconds * 1000

    def _take_youtube_resume_hint_ms(self, media_path):
        """A posição de retomada do vídeo *media_path* (e a esquece), ou 0."""
        hints = self.__dict__.get("_youtube_resume_hints")
        if not hints:
            return 0
        video_id = extract_video_id_from_text(media_path)
        return int(hints.pop(video_id, 0) or 0) if video_id else 0
