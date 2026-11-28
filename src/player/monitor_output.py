"""Copy a Windows WASAPI render endpoint to another output."""

from array import array
from collections import deque
from contextlib import ExitStack
import sys
from threading import Condition, Event, Thread

from .i18n import _
from .log import get_logger


_logger = get_logger(__name__)
_ENDPOINT_PREFIX = "{0.0.0.00000000}."
_FRAMES = 512
_MONITOR_RETRY_SECONDS = 2.0
_CLOSE_TIMEOUT_SECONDS = 3.0
_GAIN_TABLES = {}
_GAIN_BIAS = 32768


def wasapi_endpoint_id(device_id):
    driver, _, endpoint = str(device_id or "").strip().casefold().partition("/")
    return endpoint.removeprefix(_ENDPOINT_PREFIX) if driver == "wasapi" else ""


def default_wasapi_device_id():
    """Read the multimedia default, the same endpoint role used by mpv."""
    if sys.platform != "win32":
        return ""

    import ctypes as c
    from uuid import UUID

    ole = c.WinDLL("ole32")
    # These interfaces are used entirely on the calling thread.
    apartment = ole.CoInitializeEx(None, 0)
    if apartment < 0 and apartment != -2147417850:  # RPC_E_CHANGED_MODE
        return ""
    enumerator = c.c_void_p()
    device = c.c_void_p()
    endpoint = c.c_void_p()

    def method(obj, slot, result, *args):
        table = c.cast(obj, c.POINTER(c.POINTER(c.c_void_p)))[0]
        return c.WINFUNCTYPE(result, c.c_void_p, *args)(table[slot])

    try:
        clsid = UUID("bcde0395-e52f-467c-8e3d-c4579291692e").bytes_le
        iid = UUID("a95664d2-9614-4f35-a746-de8db63617e6").bytes_le
        if ole.CoCreateInstance(clsid, None, 1, iid, c.byref(enumerator)) < 0:
            return ""
        get_default = method(enumerator, 4, c.c_long, c.c_int, c.c_int, c.POINTER(c.c_void_p))
        if get_default(enumerator, 0, 1, c.byref(device)) < 0:  # eRender, eMultimedia
            return ""
        get_id = method(device, 5, c.c_long, c.POINTER(c.c_void_p))
        if get_id(device, c.byref(endpoint)) < 0:
            return ""
        return "wasapi/" + c.wstring_at(endpoint)
    finally:
        if endpoint:
            ole.CoTaskMemFree(endpoint)
        for obj in (device, enumerator):
            if obj:
                method(obj, 2, c.c_ulong)(obj)  # IUnknown::Release
        if apartment >= 0:
            ole.CoUninitialize()


def same_monitor_device(source_id, monitor_id):
    source = wasapi_endpoint_id(source_id or default_wasapi_device_id())
    return bool(source and source == wasapi_endpoint_id(monitor_id))


def monitor_conflict_message():
    return _("A monitoração e a transmissão precisam usar dispositivos diferentes.")


class _MonitorError(Exception):
    pass


def _prepare_gain_table(volume):
    """Build the int16 lookup for one monitor volume outside the audio callback."""
    try:
        volume = int(volume)
    except (TypeError, ValueError):
        return
    if volume <= 0 or volume >= 100 or volume in _GAIN_TABLES:
        return
    _GAIN_TABLES[volume] = array(
        "h",
        (round(sample * volume / 100) for sample in range(-_GAIN_BIAS, _GAIN_BIAS)),
    )


def _apply_gain(data, volume):
    """Attenuate 16-bit PCM with a prepared table. No per-sample rounding."""
    try:
        volume = int(volume)
    except (TypeError, ValueError):
        return data if isinstance(data, (bytes, bytearray)) else bytes(data)
    if not data or volume >= 100:
        return data if isinstance(data, (bytes, bytearray)) else bytes(data)
    if volume <= 0:
        return b""
    table = _GAIN_TABLES.get(volume)
    if table is None:
        _prepare_gain_table(volume)
        table = _GAIN_TABLES.get(volume)
    if table is None:
        return data if isinstance(data, (bytes, bytearray)) else bytes(data)
    payload = bytes(data)
    if len(payload) < 2:
        return b""
    if len(payload) % 2:
        payload = payload[:-1]
    samples = array("h")
    samples.frombytes(payload)
    gained = array("h", (table[sample + _GAIN_BIAS] for sample in samples))
    return gained.tobytes()


def _resolve_devices(audio, wasapi, source_id, monitor_id, devices):
    source = wasapi_endpoint_id(source_id)
    monitor = wasapi_endpoint_id(monitor_id)
    if source and source == monitor:
        raise _MonitorError(monitor_conflict_message())

    # PyAudioWPatch exposes PortAudio indices and names, while mpv exposes
    # endpoint IDs. Require a unique exact name in both lists and in the
    # loopback list so that ambiguous devices can never form a feedback loop.
    outputs = [
        info for info in audio.get_device_info_generator_by_host_api(host_api_type=wasapi)
        if info["maxOutputChannels"] and not info["isLoopbackDevice"]
    ]

    def resolve(endpoint, unavailable):
        name = dict(devices).get(endpoint)
        if name is None:
            raise _MonitorError(unavailable)
        matches = [info for info in outputs if info["name"].strip() == name]
        if len(matches) > 1 or sum(label == name for _, label in devices) > 1:
            raise _MonitorError(_("Há dispositivos de áudio com o mesmo nome. Renomeie-os ou escolha outra saída."))
        if not matches:
            raise _MonitorError(unavailable)
        return matches[0]

    source_missing = _("Saída de transmissão indisponível para a monitoração. Confira o dispositivo de áudio.")
    headphones_missing = _("Saída de monitoração indisponível. Confira a conexão do fone ou das caixas.")
    source_output = resolve(source, source_missing)
    headphones = resolve(monitor, headphones_missing)
    expected_name = source_output["name"] + " [Loopback]"
    loopbacks = [info for info in audio.get_loopback_device_info_generator() if info["name"] == expected_name]
    if len(loopbacks) != 1:
        raise _MonitorError(_("Não foi possível capturar o áudio da saída de transmissão."))
    return loopbacks[0], headphones


class _PCMConverter:
    """Convert native 16-bit capture to the monitor's sample rate and channels."""

    def __init__(self, input_rate, output_rate, input_channels, output_channels):
        self.input_rate = input_rate
        self.output_rate = output_rate
        self.input_channels = input_channels
        self.output_channels = output_channels
        self.previous = array("h")
        self.position = 0

    def convert(self, data):
        channels = self.output_channels
        if self.input_rate == self.output_rate and self.input_channels == channels:
            return data
        samples = array("h", data)
        if self.input_channels != channels:
            converted = array("h")
            for offset in range(0, len(samples), self.input_channels):
                frame = samples[offset:offset + self.input_channels]
                if channels == 1:
                    converted.append(sum(frame) // len(frame))
                elif len(frame) == 1:
                    converted.extend((frame[0], frame[0]))
                else:
                    # Keep front left/right distinct and fold the extra
                    # channels into both sides when monitoring in stereo.
                    extra = sum(frame[2:]) / (2 * (len(frame) - 2))
                    converted.extend((int(0.5 * frame[0] + extra), int(0.5 * frame[1] + extra)))
            samples = converted
        if self.input_rate == self.output_rate or not samples:
            return samples.tobytes()

        samples = self.previous + samples
        limit = (len(samples) // channels - 1) * self.output_rate
        position = self.position
        output = array("h")
        while position < limit:
            frame, remainder = divmod(position, self.output_rate)
            start = frame * channels
            for channel in range(start, start + channels):
                sample = samples[channel]
                output.append(sample + (samples[channel + channels] - sample) * remainder // self.output_rate)
            position += self.input_rate
        self.previous = samples[-channels:]
        self.position = position - limit
        return output.tobytes()


def _stream_audio(pa, source_id, monitor_id, devices, stopped, get_volume, route_changed, on_started=None):
    """Copy loopback audio. Resampling stays off the PortAudio thread.

    The playback callback only applies a prepared gain table. Either callback
    turns an unexpected error into silence and ``paContinue`` so one bad buffer
    cannot tear the stream down.
    """
    with pa.PyAudio() as audio, ExitStack() as streams:
        capture_device, playback_device = _resolve_devices(audio, pa.paWASAPI, source_id, monitor_id, devices)
        input_rate = int(capture_device["defaultSampleRate"])
        output_rate = int(playback_device["defaultSampleRate"])
        input_channels = capture_device["maxInputChannels"]
        output_channels = playback_device["maxOutputChannels"]
        if input_channels != output_channels:
            output_channels = min(2, output_channels)
        passthrough = input_rate == output_rate and input_channels == output_channels
        converter = None if passthrough else _PCMConverter(input_rate, output_rate, input_channels, output_channels)
        pending = deque(maxlen=6)
        incoming = deque(maxlen=6)
        wake = Condition()
        resample_finished = Event()
        remainder = b""
        callback_error_logged = False
        _prepare_gain_table(get_volume())

        def log_callback_error():
            nonlocal callback_error_logged
            if callback_error_logged:
                return
            callback_error_logged = True
            _logger.exception("WASAPI monitoring callback failed")

        def enqueue_raw(data):
            block = bytes(data)
            if not block:
                return
            if passthrough:
                pending.append(block)
                return
            with wake:
                incoming.append(block)
                wake.notify()

        def convert_loop():
            while not resample_finished.is_set():
                with wake:
                    if resample_finished.is_set():
                        return
                    while not incoming and not resample_finished.is_set():
                        wake.wait()
                    if resample_finished.is_set() or not incoming:
                        return
                    block = incoming.popleft()
                try:
                    pending.append(converter.convert(block))
                except Exception:
                    log_callback_error()

        converter_thread = None
        if converter is not None:
            converter_thread = Thread(target=convert_loop, name="wasapi-monitor-convert", daemon=True)
            converter_thread.start()

        def capture(data, _frames, _time, _status):
            try:
                if stopped.is_set():
                    return None, pa.paAbort
                if data:
                    enqueue_raw(data)
                return None, pa.paContinue
            except Exception:
                log_callback_error()
                return None, pa.paContinue

        def play(_data, frames, _time, _status):
            nonlocal remainder
            try:
                if stopped.is_set():
                    return None, pa.paAbort
                size = frames * output_channels * 2
                data = remainder
                while len(data) < size:
                    try:
                        data += pending.popleft()
                    except IndexError:
                        break
                remainder = data[size:]
                block = data[:size]
                volume = get_volume()
                if volume == 0:
                    block = b""
                elif volume != 100:
                    block = _apply_gain(block, volume)
                return block.ljust(size, b"\x00"), pa.paContinue
            except Exception:
                log_callback_error()
                try:
                    silence = b"\x00" * (frames * output_channels * 2)
                except Exception:
                    silence = b""
                return silence, pa.paContinue

        try:
            if stopped.is_set():
                return
            capture_error = _("Não foi possível capturar o áudio da saída de transmissão.")
            playback_error = _("Saída de monitoração indisponível. Confira a conexão do fone ou das caixas.")
            try:
                capture_stream = streams.enter_context(audio.open(
                    format=pa.paInt16, rate=input_rate, channels=input_channels, frames_per_buffer=_FRAMES,
                    input=True, input_device_index=capture_device["index"], stream_callback=capture, start=False,
                ))
                capture_stream.start_stream()
            except OSError as exc:
                raise _MonitorError(capture_error) from exc

            if stopped.is_set():
                return
            try:
                playback_stream = streams.enter_context(audio.open(
                    format=pa.paInt16, rate=output_rate, channels=output_channels, frames_per_buffer=_FRAMES,
                    output=True, output_device_index=playback_device["index"], stream_callback=play, start=False,
                ))
                playback_stream.start_stream()
            except OSError as exc:
                raise _MonitorError(playback_error) from exc
            notify_started = on_started
            while not stopped.wait(0.5):
                if route_changed():
                    return
                if not playback_stream.is_active():
                    raise _MonitorError(playback_error)
                if not capture_stream.is_active():
                    raise _MonitorError(capture_error)
                if notify_started is not None:
                    callback = notify_started
                    notify_started = None
                    try:
                        callback()
                    except Exception:
                        _logger.exception("WASAPI monitoring recovery notice failed")
        finally:
            resample_finished.set()
            with wake:
                wake.notify_all()
            if converter_thread is not None:
                converter_thread.join(timeout=1.0)
                if converter_thread.is_alive():
                    _logger.warning("WASAPI monitoring resampler did not stop.")


class MonitorOutput:
    """Own the PortAudio streams on one worker, including during device swaps."""

    def __init__(self, volume, on_error):
        _prepare_gain_table(volume)
        self._volume = volume
        self._on_error = on_error
        self._condition = Condition()
        self._request = None
        self._failed = None
        self._stopped = Event()
        self._closed = False
        self._worker = Thread(target=self._run, name="wasapi-monitor", daemon=True)
        self._worker.start()

    def configure(self, source_id, monitor_id, devices, *, retry=False):
        # IDs remain stable across PortAudio enumeration and hotplug.
        endpoints = tuple(sorted({
            endpoint: device.menu_label.strip()
            for device in devices
            if (endpoint := wasapi_endpoint_id(device.device_id))
        }.items()))
        self._set_request((source_id, monitor_id, endpoints), retry=retry)

    def set_volume(self, value):
        _prepare_gain_table(value)
        self._volume = value

    def has_failed(self):
        with self._condition:
            return self._failed is self._stopped

    def stop(self):
        self._set_request(None)

    def close(self):
        with self._condition:
            self._closed = True
            self._stopped.set()
            self._condition.notify()
        self._worker.join(timeout=_CLOSE_TIMEOUT_SECONDS)
        if self._worker.is_alive():
            _logger.warning(
                "WASAPI monitoring did not stop within %.0f seconds.",
                _CLOSE_TIMEOUT_SECONDS,
            )

    def _set_request(self, request, *, retry=False):
        with self._condition:
            if self._closed or (
                request == self._request and not (retry and self._failed is self._stopped)
            ):
                return
            self._stopped.set()
            self._stopped = Event()
            self._failed = None
            self._request = request
            self._condition.notify()

    def _run(self):
        previous = None
        while True:
            with self._condition:
                self._condition.wait_for(lambda: self._closed or (
                    self._request is not None and self._stopped is not previous
                ))
                if self._closed:
                    return
                stopped = self._stopped
                request = self._request
            previous = stopped
            self._monitor(request, stopped)

    def _monitor(self, request, stopped):
        if sys.platform != "win32":
            return
        try:
            import pyaudiowpatch
        except Exception:
            self._report(stopped, _("A monitoração está indisponível porque o componente de áudio do Windows não pôde ser carregado."))
            return

        selected_source, monitor_id, devices = request
        announced_failure = False

        def fail(message, exc):
            nonlocal announced_failure
            if announced_failure:
                _logger.debug("WASAPI monitoring retry after: %s", exc)
                return
            announced_failure = True
            if isinstance(exc, _MonitorError):
                _logger.warning("WASAPI monitoring: %s (%s)", exc, exc.__cause__)
            else:
                _logger.exception("WASAPI monitoring failed")
            self._report(stopped, message)

        def started():
            nonlocal announced_failure
            if not announced_failure:
                return
            announced_failure = False
            self._report_recovery(stopped)

        while not stopped.is_set():
            source_id = selected_source or default_wasapi_device_id()

            def route_changed(source_id=source_id):
                return not selected_source and default_wasapi_device_id() != source_id

            try:
                _stream_audio(
                    pyaudiowpatch,
                    source_id,
                    monitor_id,
                    devices,
                    stopped,
                    lambda: self._volume,
                    route_changed,
                    on_started=started,
                )
            except _MonitorError as exc:
                fail(str(exc), exc)
            except Exception as exc:
                fail(_("A monitoração parou. Confira os dispositivos de áudio."), exc)

            if stopped.is_set():
                return
            # Keep the same request alive. A chosen device retries on a timer;
            # the system default also wakes as soon as that endpoint changes.
            waited = 0.0
            while waited < _MONITOR_RETRY_SECONDS:
                if route_changed():
                    break
                if stopped.wait(0.5):
                    return
                waited += 0.5

    def _mark_failure(self, stopped, failed):
        with self._condition:
            if self._closed or stopped.is_set():
                return False
            # A replaced request sets the old event before the worker reports,
            # so a late report from that generation does not clear a newer one.
            if not failed and self._failed is not None and self._failed is not stopped:
                return False
            self._failed = stopped if failed else None
            return True

    def _report(self, stopped, message):
        if self._mark_failure(stopped, True):
            self._on_error(stopped, message)

    def _report_recovery(self, stopped):
        if self._mark_failure(stopped, False):
            self._on_error(stopped, _("Monitoração retomada."))
