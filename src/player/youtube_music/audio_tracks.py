"""Faixas de áudio dos vídeos dublados do YouTube.

Um vídeo pode trazer o áudio original e várias dublagens. A preferência vale
para tudo o que toca; a escolha feita para uma mídia vale só para ela, nesta
sessão. O YouTube.js lista as faixas; quem toca uma faixa que não é a padrão é
sempre o yt-dlp, o único que consegue a mídia inteira dela.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from ..i18n import _
from ..log import get_logger
from . import youtubejs_runtime
from .content_locale import CONTENT_LANGUAGES
from .dependencies import ensure_yt_dlp_executable_available, youtubejs_resolver_enabled
from .playlists import extract_video_id_from_text
from .search import _clean_external_tool_error
from .yt_dlp_runtime import extract_info as extract_yt_dlp_info, find_all_available_javascript_runtimes


_logger = get_logger(__name__)

AUDIO_CHOICE_DEFAULT = ""
AUDIO_CHOICE_ORIGINAL = "original"
# Os idiomas oferecidos nas preferências; a escolha por mídia aceita qualquer faixa do vídeo.
AUDIO_LANGUAGES = tuple((code.split("-")[0], label) for code, label in CONTENT_LANGUAGES if code != "pt-PT")
_AUDIO_LANGUAGE_CODES = {code for code, _label in AUDIO_LANGUAGES}

YT_DLP_ORIGINAL_LANGUAGE_PREFERENCE = 10
YT_DLP_TRACKS_SOCKET_TIMEOUT_SECONDS = 20
YT_DLP_TRACKS_PLAYER_CLIENT = "visionos"

_lock = threading.Lock()
_preference = AUDIO_CHOICE_DEFAULT
_media_choices: dict[str, str] = {}


@dataclass(frozen=True)
class YouTubeAudioTrack:
    track_id: str
    name: str
    language: str = ""
    default: bool = False
    original: bool = False
    descriptive: bool = False

    @property
    def yt_dlp_selector(self):
        """Como o yt-dlp reconhece esta faixa entre os formatos: "original" ou o idioma."""
        return AUDIO_CHOICE_ORIGINAL if self.original else self.language


def normalize_audio_preference(preference):
    preference = str(preference or "").strip()
    if preference == AUDIO_CHOICE_ORIGINAL or preference in _AUDIO_LANGUAGE_CODES:
        return preference
    return AUDIO_CHOICE_DEFAULT


def configure_audio_preference(preference):
    """Guarda o idioma de áudio preferido; devolve se ele mudou."""
    global _preference

    preference = normalize_audio_preference(preference)
    with _lock:
        changed = preference != _preference
        _preference = preference
    return changed


def set_media_audio_choice(media_path, track_id):
    """A faixa escolhida para *media_path*, que passa na frente da preferência até o KeyTune fechar."""
    video_id = extract_video_id_from_text(media_path)
    if video_id:
        with _lock:
            _media_choices[video_id] = str(track_id or "").strip()


def audio_choice_for(media_path):
    """``(escolha, feita para esta mídia)``: a faixa pedida ou, sem pedido, a preferência."""
    video_id = extract_video_id_from_text(media_path)
    with _lock:
        if video_id in _media_choices:
            return _media_choices[video_id], True
        return _preference, False


def pick_track(tracks, choice):
    """A faixa de *tracks* que atende a *choice*: o id de uma faixa, "original" ou um idioma."""
    choice = str(choice or "").strip()
    if not choice:
        return None
    if choice == AUDIO_CHOICE_ORIGINAL:
        return next((track for track in tracks if track.original), None)
    for track in tracks:
        if track.track_id == choice:
            return track
    language = choice.casefold()
    matches = [track for track in tracks if track.language.casefold().split("-")[0] == language.split("-")[0]]
    # Entre as faixas do idioma, a comum vem antes da audiodescrição.
    matches.sort(key=lambda track: (track.descriptive, track.language.casefold() != language))
    return matches[0] if matches else None


def yt_dlp_selector_for_playback(media_path):
    """O que o yt-dlp deve tocar em *media_path*, ou vazio quando a faixa padrão já serve.

    Vazio é o caminho de sempre, rápido. Só um vídeo dublado cuja faixa pedida
    não é a padrão passa pelo yt-dlp com a faixa escolhida.
    """
    choice, for_this_media = audio_choice_for(media_path)
    if not choice:
        return ""
    if not youtubejs_resolver_enabled():
        # Sem a lista do YouTube.js, o yt-dlp procura a faixa nos formatos que ele mesmo traz.
        return choice.split(".")[0]
    try:
        tracks = _youtubejs_tracks(media_path, names=False)
    except Exception as exc:
        _logger.warning("O YouTube.js não listou as faixas de áudio: %s", exc)
        return choice.split(".")[0] if for_this_media else ""
    track = pick_track(tracks, choice)
    if track is None or track.default:
        return ""
    return track.yt_dlp_selector


def list_audio_tracks(media_path):
    """As faixas de áudio de *media_path*; vazio quando o vídeo só tem uma."""
    if youtubejs_resolver_enabled():
        try:
            return _youtubejs_tracks(media_path, names=True)
        except Exception as exc:
            _logger.warning("O YouTube.js não listou as faixas de áudio; usando o yt-dlp: %s", exc)
    return _yt_dlp_tracks(media_path)


def _youtubejs_tracks(media_path, *, names):
    return [
        YouTubeAudioTrack(
            track_id=str(entry.get("id") or "").strip(),
            name=str(entry.get("name") or entry.get("language") or "").strip(),
            language=str(entry.get("language") or "").strip(),
            default=bool(entry.get("default")),
            original=bool(entry.get("original")),
            descriptive=bool(entry.get("descriptive")),
        )
        for entry in youtubejs_runtime.audio_tracks(media_path, names=names)
        if isinstance(entry, dict) and str(entry.get("id") or "").strip()
    ]


def _yt_dlp_tracks(media_path):
    ensure_yt_dlp_executable_available()
    try:
        response = extract_yt_dlp_info(
            media_path,
            noplaylist=True,
            ignore_no_formats_error=True,
            extractor_args={"youtube": {"player_client": [YT_DLP_TRACKS_PLAYER_CLIENT]}},
            js_runtimes=find_all_available_javascript_runtimes(),
            socket_timeout_seconds=YT_DLP_TRACKS_SOCKET_TIMEOUT_SECONDS,
            quiet=True,
            no_warnings=True,
        )
    except Exception as exc:
        raise RuntimeError(
            _clean_external_tool_error(exc) or _("O yt-dlp não conseguiu listar as faixas de áudio.")
        ) from exc

    tracks = {}
    for fmt in (response.data or {}).get("formats") or []:
        language = str(fmt.get("language") or "").strip() if isinstance(fmt, dict) else ""
        if not language or language in tracks or str(fmt.get("vcodec") or "") != "none":
            continue
        original = is_original_yt_dlp_format(fmt)
        tracks[language] = YouTubeAudioTrack(
            track_id=language,
            # A nota vem como "Portuguese, low": o nome é o que está antes da qualidade.
            name=str(fmt.get("format_note") or "").split(",")[0].strip() or language,
            language=language,
            default=original,
            original=original,
        )
    return list(tracks.values()) if len(tracks) > 1 else []


def is_original_yt_dlp_format(fmt):
    return fmt.get("language_preference") == YT_DLP_ORIGINAL_LANGUAGE_PREFERENCE or "original" in str(
        fmt.get("format_note") or ""
    ).casefold()


def yt_dlp_formats_for_selector(formats, selector):
    """Os *formats* da faixa pedida; todos, quando o vídeo não tem essa faixa."""
    selector = str(selector or "").strip().casefold()
    if not selector:
        return formats
    if selector == AUDIO_CHOICE_ORIGINAL:
        matches = [fmt for fmt in formats if is_original_yt_dlp_format(fmt)]
    else:
        languages = [str(fmt.get("language") or "").casefold() for fmt in formats]
        matches = [fmt for fmt, language in zip(formats, languages) if language == selector] or [
            fmt for fmt, language in zip(formats, languages) if language.split("-")[0] == selector.split("-")[0]
        ]
    return matches or formats


def audio_track_label(track):
    if track.descriptive:
        return _("{name} (audiodescrição)").format(name=track.name)
    return track.name
