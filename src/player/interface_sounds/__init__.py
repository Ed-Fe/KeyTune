"""Sons curtos que avisam o que aconteceu: chat, notificações, ações da conta, listas, fila e avisos.

Os arquivos ficam em ``sounds/`` (ver ``LICENSE.md`` ali). Tocam pelo Windows,
fora do MPV, para não mexer na mídia que está tocando; em outros sistemas, ou
quando algo falha, simplesmente não há som.
"""

import array
import collections
import functools
import io
import os
import sys
import threading
import time
import wave
from pathlib import Path

from ..log import get_logger


_logger = get_logger(__name__)

SOUND_CHAT_MESSAGE = "chat_message"
SOUND_CHAT_SENT = "chat_sent"
SOUND_CHAT_ENDED = "chat_ended"
SOUND_NOTIFICATION = "notification"
SOUND_SUCCESS = "success"
SOUND_FAILURE = "failure"
SOUND_CHAT_MENTION = "chat_mention"
SOUND_CHAT_PAID = "chat_paid"
SOUND_LIST_EDGE = "list_edge"
SOUND_OPEN = "open"
SOUND_BACK = "back"
SOUND_LOADING = "loading"
SOUND_LIKE = "like"
SOUND_UNLIKE = "unlike"
SOUND_QUEUE_ADDED = "queue_added"
SOUND_QUEUE_REMOVED = "queue_removed"
SOUND_DOWNLOAD_DONE = "download_done"
SOUND_TIMER_WARNING = "timer_warning"
SOUND_QUESTION = "question"
SOUND_TAB_OPENED = "tab_opened"
SOUND_TAB_CLOSED = "tab_closed"
SOUND_UPDATE_AVAILABLE = "update_available"
SOUND_WELCOME = "welcome"
SOUND_APP_OPENED = "app_opened"
SOUND_APP_CLOSED = "app_closed"

SOUND_NAMES = (
    SOUND_CHAT_MESSAGE,
    SOUND_CHAT_SENT,
    SOUND_CHAT_ENDED,
    SOUND_NOTIFICATION,
    SOUND_SUCCESS,
    SOUND_FAILURE,
    SOUND_CHAT_MENTION,
    SOUND_CHAT_PAID,
    SOUND_LIST_EDGE,
    SOUND_OPEN,
    SOUND_BACK,
    SOUND_LOADING,
    SOUND_LIKE,
    SOUND_UNLIKE,
    SOUND_QUEUE_ADDED,
    SOUND_QUEUE_REMOVED,
    SOUND_DOWNLOAD_DONE,
    SOUND_TIMER_WARNING,
    SOUND_QUESTION,
    SOUND_TAB_OPENED,
    SOUND_TAB_CLOSED,
    SOUND_UPDATE_AVAILABLE,
    SOUND_WELCOME,
    SOUND_APP_OPENED,
    SOUND_APP_CLOSED,
)

DEFAULT_INTERFACE_SOUNDS_ENABLED = True
# Todo som, o do player ou o escolhido pela pessoa, é levado a esta intensidade
# média (fração do máximo, cerca de -20 dB) com o volume em 100: assim nenhum
# sai mais alto que o outro.
_TARGET_LEVEL = 0.1
# Abaixo desta fração do pico é silêncio ou cauda, e não entra na média.
_LEVEL_GATE = 0.05
_PEAK_LIMIT = 29000
DEFAULT_INTERFACE_SOUNDS_VOLUME = 60


def sound_path(name):
    """O arquivo do som *name*, ou ``None`` quando ele não existe."""
    if name not in SOUND_NAMES:
        return None
    path = Path(__file__).with_name("sounds") / f"{name}.wav"
    return path if path.is_file() else None


def normalize_disabled(names):
    """Os sons desligados um a um, só os que existem, em ordem estável."""
    if isinstance(names, str) or not hasattr(names, "__iter__"):
        return []
    chosen = {str(name) for name in names}
    return [name for name in SOUND_NAMES if name in chosen]


def normalize_custom(custom):
    """Os arquivos escolhidos no lugar dos sons: ``{som: caminho}``, só dos sons que existem."""
    if not isinstance(custom, dict):
        return {}
    return {
        name: str(custom[name]).strip()
        for name in SOUND_NAMES
        if isinstance(custom.get(name), str) and custom[name].strip()
    }


def normalize_volume(value, default=DEFAULT_INTERFACE_SOUNDS_VOLUME):
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return default


def volume_gain(volume):
    """Quanto o *volume* (0 a 100) multiplica o som: ao quadrado, como o ouvido percebe."""
    return (normalize_volume(volume) / 100) ** 2


def level_gain(samples):
    """O ganho que leva *samples* (16 bits) à intensidade média comum, sem estourar o pico."""
    peak = max((abs(sample) for sample in samples), default=0)
    if not peak:
        return 1.0
    gate = peak * _LEVEL_GATE
    loud = [sample for sample in samples if abs(sample) >= gate]
    level = (sum(sample * sample for sample in loud) / len(loud)) ** 0.5
    return min(_TARGET_LEVEL * 32768 / level, _PEAK_LIMIT / peak)


@functools.lru_cache(maxsize=64)
def sound_data(name, volume, custom_path=""):
    """O som *name* como WAV em memória, já no *volume* (0 a 100); ``b""`` sem o arquivo.

    Com *custom_path*, é esse arquivo que toca no lugar do que vem com o player.
    """
    path = Path(custom_path) if custom_path else sound_path(name)
    if path is None:
        return b""
    with wave.open(str(path), "rb") as source:
        parameters = source.getparams()
        frames = source.readframes(parameters.nframes)
    if parameters.sampwidth == 2:
        samples = array.array("h")
        samples.frombytes(frames)
        if sys.byteorder == "big":
            samples.byteswap()
        gain = level_gain(samples) * volume_gain(volume)
        samples = array.array("h", (max(-32768, min(32767, round(sample * gain))) for sample in samples))
        if sys.byteorder == "big":
            samples.byteswap()
        frames = samples.tobytes()
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as target:
        target.setparams(parameters)
        target.writeframes(frames)
    return buffer.getvalue()


def _output_silenced():
    """Se o som não deve sair de verdade: nos testes, ou com ``KEYTUNE_SILENT_INTERFACE_SOUNDS``."""
    if os.environ.get("KEYTUNE_SILENT_INTERFACE_SOUNDS"):
        return True
    main_spec = getattr(sys.modules.get("__main__"), "__spec__", None)
    return str(getattr(main_spec, "name", "") or "").split(".")[0] in ("unittest", "pytest")


_player = None


def _windows_play(data):
    """Manda *data* (um WAV em memória) para o Windows e volta na hora; toca por cima do que já tocava."""
    global _player
    if _player is None:
        from .wave_out import WaveOutPlayer

        _player = WaveOutPlayer()
    _player.play(data)


# Os pedidos que ainda esperam a thread: além disto, os mais antigos são esquecidos.
_MAX_PENDING = 4
# De quanto em quanto a thread confere se os sons acabaram, para fechar a saída deles.
_REAP_SECONDS = 0.25


class _Output:
    """Toca os sons numa thread só, na ordem em que foram pedidos.

    Só os últimos pedidos esperam: segurar uma tecla não empilha sons para
    tocar depois, nem cria uma thread por toque.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._pending = collections.deque(maxlen=_MAX_PENDING)
        self._thread = None

    def submit(self, data):
        with self._lock:
            self._pending.append(data)
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._run, daemon=True, name="interface-sound")
                self._thread.start()
        self._wake.set()

    def _run(self):
        while True:
            self._wake.wait(_REAP_SECONDS if _player is not None and _player.active else None)
            self._wake.clear()
            with self._lock:
                waiting = list(self._pending)
                self._pending.clear()
            try:
                if not _output_silenced():
                    for data in waiting:
                        _windows_play(data)
                if _player is not None:
                    _player.reap()
            except Exception as exc:
                _logger.debug("The interface sound could not be played: %s", exc)


_output = _Output()
_last_played = {}
# Quando o último som pedido acaba de tocar, para o fechamento poder esperar por ele.
_last_sound_ends_at = 0.0
# O mesmo som pedido de novo antes disto é ignorado: só tocaria em dobro.
_REPEAT_GUARD_SECONDS = 0.08
# O tempo que a saída leva para abrir, somado à espera pelo fim do som.
_OUTPUT_LATENCY_SECONDS = 0.15


def play(name, volume=DEFAULT_INTERFACE_SOUNDS_VOLUME, custom_path=""):
    """Toca o som *name* sem esperar ele acabar; ``False`` quando não há como tocar.

    Um *custom_path* que sumiu ou não abre dá lugar ao som que vem com o player.
    """
    volume = normalize_volume(volume)
    if not volume or not sys.platform.startswith("win"):
        return False
    data = b""
    if custom_path:
        try:
            data = sound_data(name, volume, str(custom_path))
        except Exception as exc:
            _logger.info("The custom interface sound %s could not be read: %s", custom_path, exc)
    try:
        data = data or sound_data(name, volume)
    except Exception as exc:
        _logger.debug("The interface sound %s could not be read: %s", name, exc)
        return False
    if not data:
        return False
    now = time.monotonic()
    if now - _last_played.get(name, 0.0) < _REPEAT_GUARD_SECONDS:
        return False
    _last_played[name] = now
    global _last_sound_ends_at
    _last_sound_ends_at = now + sound_seconds(data) + _OUTPUT_LATENCY_SECONDS
    _output.submit(data)
    return True


def sound_seconds(data):
    """Quanto dura o WAV em memória *data*; 0 quando não dá para saber."""
    try:
        with wave.open(io.BytesIO(data), "rb") as sound:
            return sound.getnframes() / float(sound.getframerate() or 1)
    except (wave.Error, EOFError):
        return 0.0


def seconds_until_played(limit_seconds=4.0):
    """Quanto falta para o último som pedido acabar, no máximo *limit_seconds*; 0 se nada toca."""
    if _output_silenced():
        return 0.0
    return max(0.0, min(float(limit_seconds), _last_sound_ends_at - time.monotonic()))


def wait_until_played(limit_seconds=4.0):
    """Espera o último som pedido acabar, no máximo *limit_seconds*: o programa que sai corta o som."""
    remaining = seconds_until_played(limit_seconds)
    if remaining:
        time.sleep(remaining)
    return remaining


def play_for(frame, name):
    """Toca *name* conforme as preferências da janela *frame*; sem elas, fica em silêncio."""
    settings = getattr(frame, "settings", None)
    if settings is None or not getattr(settings, "interface_sounds_enabled", DEFAULT_INTERFACE_SOUNDS_ENABLED):
        return False
    if name in (getattr(settings, "interface_sounds_disabled", None) or ()):
        return False
    custom = getattr(settings, "interface_sounds_custom", None) or {}
    return play(
        name,
        getattr(settings, "interface_sounds_volume", DEFAULT_INTERFACE_SOUNDS_VOLUME),
        custom.get(name, ""),
    )
