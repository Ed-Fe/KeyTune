"""A saída dos sons de aviso no Windows, pelo ``waveOut``.

O ``PlaySound`` toca um som só por programa, e o próprio Windows o chama a cada
movimento numa lista (o evento "Selecionar", mesmo sem som associado), o que
cortava o aviso que estava tocando. Aqui cada som abre a saída dele: os sons se
misturam e nada de fora os interrompe.
"""

import ctypes
import io
import wave


_WAVE_MAPPER = 0xFFFFFFFF
_WAVE_FORMAT_PCM = 1
_WHDR_DONE = 0x00000001
# Sons demais ao mesmo tempo viram barulho: o mais antigo dá lugar ao novo.
_MAX_VOICES = 6


class _WaveFormat(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("wFormatTag", ctypes.c_uint16),
        ("nChannels", ctypes.c_uint16),
        ("nSamplesPerSec", ctypes.c_uint32),
        ("nAvgBytesPerSec", ctypes.c_uint32),
        ("nBlockAlign", ctypes.c_uint16),
        ("wBitsPerSample", ctypes.c_uint16),
        ("cbSize", ctypes.c_uint16),
    ]


class _WaveHeader(ctypes.Structure):
    _fields_ = [
        ("lpData", ctypes.c_void_p),
        ("dwBufferLength", ctypes.c_uint32),
        ("dwBytesRecorded", ctypes.c_uint32),
        ("dwUser", ctypes.c_size_t),
        ("dwFlags", ctypes.c_uint32),
        ("dwLoops", ctypes.c_uint32),
        ("lpNext", ctypes.c_void_p),
        ("reserved", ctypes.c_size_t),
    ]


class _Voice:
    """Um som tocando: a saída aberta para ele e a memória que o Windows lê."""

    def __init__(self, handle, header, buffer):
        self.handle = handle
        self.header = header
        self.buffer = buffer

    @property
    def done(self):
        return bool(self.header.dwFlags & _WHDR_DONE)


class WaveOutPlayer:
    """Toca WAVs em memória, um por cima do outro. Usar sempre da mesma thread."""

    def __init__(self):
        self._winmm = None
        self._voices = []

    @property
    def active(self):
        return bool(self._voices)

    def _library(self):
        if self._winmm is None:
            winmm = ctypes.WinDLL("winmm")
            handle, header, size = ctypes.c_void_p, ctypes.POINTER(_WaveHeader), ctypes.c_uint
            winmm.waveOutOpen.argtypes = [
                ctypes.POINTER(handle), ctypes.c_uint, ctypes.POINTER(_WaveFormat),
                ctypes.c_size_t, ctypes.c_size_t, ctypes.c_uint32,
            ]
            winmm.waveOutPrepareHeader.argtypes = [handle, header, size]
            winmm.waveOutWrite.argtypes = [handle, header, size]
            winmm.waveOutUnprepareHeader.argtypes = [handle, header, size]
            winmm.waveOutReset.argtypes = [handle]
            winmm.waveOutClose.argtypes = [handle]
            self._winmm = winmm
        return self._winmm

    def play(self, data):
        """Começa a tocar *data* e volta na hora; levanta ``OSError`` se a saída não abre."""
        with wave.open(io.BytesIO(data), "rb") as sound:
            channels, width, rate = sound.getnchannels(), sound.getsampwidth(), sound.getframerate()
            frames = sound.readframes(sound.getnframes())
        if not frames:
            return
        self.reap()
        while len(self._voices) >= _MAX_VOICES:
            self._close(self._voices.pop(0))
        winmm = self._library()
        wave_format = _WaveFormat(
            _WAVE_FORMAT_PCM, channels, rate, rate * channels * width, channels * width, width * 8, 0
        )
        handle = ctypes.c_void_p()
        error = winmm.waveOutOpen(ctypes.byref(handle), _WAVE_MAPPER, ctypes.byref(wave_format), 0, 0, 0)
        if error:
            raise OSError(f"waveOutOpen failed with code {error}")
        buffer = (ctypes.c_char * len(frames)).from_buffer_copy(frames)
        header = _WaveHeader(lpData=ctypes.addressof(buffer), dwBufferLength=len(frames))
        voice = _Voice(handle, header, buffer)
        size = ctypes.sizeof(_WaveHeader)
        error = winmm.waveOutPrepareHeader(handle, ctypes.byref(header), size) or winmm.waveOutWrite(
            handle, ctypes.byref(header), size
        )
        if error:
            self._close(voice)
            raise OSError(f"waveOutWrite failed with code {error}")
        self._voices.append(voice)

    def reap(self):
        """Fecha a saída dos sons que já acabaram."""
        finished = [voice for voice in self._voices if voice.done]
        self._voices = [voice for voice in self._voices if not voice.done]
        for voice in finished:
            self._close(voice)

    def _close(self, voice):
        winmm = self._library()
        winmm.waveOutReset(voice.handle)
        winmm.waveOutUnprepareHeader(voice.handle, ctypes.byref(voice.header), ctypes.sizeof(_WaveHeader))
        winmm.waveOutClose(voice.handle)
