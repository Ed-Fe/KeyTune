"""O arquivo que a pessoa escolhe para tocar no lugar de um som de aviso.

O arquivo escolhido é copiado para a pasta de dados do KeyTune, como WAV de
16 bits: assim ele continua valendo se o original for movido, e toca pelo
mesmo caminho dos sons que vêm com o player.
"""

import shutil
import subprocess
import time
import wave
from pathlib import Path

from ..download.ffmpeg import FFMPEG_EXECUTABLE_NAME, find_ffmpeg_directory
from ..i18n import _
from ..session import get_app_storage_dir
from . import SOUND_NAMES


# Um aviso é curto: o que passar disso é cortado, ou recusado sem o FFmpeg.
CUSTOM_SOUND_MAX_SECONDS = 5
_CONVERT_TIMEOUT_SECONDS = 30


class CustomSoundError(Exception):
    """O arquivo escolhido não serve como som de aviso; a mensagem diz por quê."""


def custom_sounds_dir():
    return Path(get_app_storage_dir()) / "interface_sounds"


def _plain_wav_problem(path):
    """Por que *path* não toca sem conversão; vazio quando toca."""
    try:
        with wave.open(str(path), "rb") as sound:
            if sound.getcomptype() != "NONE" or sound.getsampwidth() != 2:
                return _("Sem o FFmpeg, só serve arquivo WAV de 16 bits.")
            if sound.getnframes() > sound.getframerate() * CUSTOM_SOUND_MAX_SECONDS:
                return _("Sem o FFmpeg, o som precisa ter até {seconds} segundos.").format(
                    seconds=CUSTOM_SOUND_MAX_SECONDS
                )
    except (OSError, EOFError, wave.Error):
        return _("Sem o FFmpeg, só serve arquivo WAV de 16 bits.")
    return ""


def import_custom_sound(name, source_path):
    """Guarda *source_path* como o som *name* e devolve o caminho do arquivo guardado."""
    source = Path(str(source_path or ""))
    if name not in SOUND_NAMES or not source.is_file():
        raise CustomSoundError(_("O arquivo escolhido não foi encontrado."))
    folder = custom_sounds_dir()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{name}-{int(time.time() * 1000)}.wav"

    ffmpeg_dir = find_ffmpeg_directory()
    if ffmpeg_dir is None:
        problem = _plain_wav_problem(source)
        if problem:
            raise CustomSoundError(problem)
        shutil.copyfile(source, target)
        return str(target)

    command = [
        str(Path(ffmpeg_dir) / FFMPEG_EXECUTABLE_NAME),
        "-v", "error", "-y", "-i", str(source),
        # O silêncio do começo sai: um aviso tem de soar na hora.
        "-af", "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.005",
        "-t", str(CUSTOM_SOUND_MAX_SECONDS), "-vn", "-ar", "44100", "-c:a", "pcm_s16le",
        str(target),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            timeout=_CONVERT_TIMEOUT_SECONDS,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CustomSoundError(_("Não foi possível converter o arquivo escolhido.")) from exc
    if result.returncode != 0 or not target.is_file() or _plain_wav_problem(target):
        target.unlink(missing_ok=True)
        raise CustomSoundError(_("O arquivo escolhido não é um áudio que o KeyTune consiga usar."))
    return str(target)


def remove_unused_custom_sounds(custom):
    """Apaga da pasta os arquivos que não são mais o som de nenhum evento."""
    kept = {Path(path).resolve() for path in (custom or {}).values() if path}
    try:
        files = list(custom_sounds_dir().glob("*.wav"))
    except OSError:
        return
    for path in files:
        if path.resolve() not in kept:
            try:
                path.unlink()
            except OSError:
                pass
