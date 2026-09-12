"""Shared AutoDJ analysis service for local files and resolved online streams."""

from __future__ import annotations

from dataclasses import asdict
from collections import OrderedDict
from http.client import IncompleteRead
import os
import re
from pathlib import Path
import tempfile
import threading
import time
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from ..i18n import _
from ..log import get_logger
from .cache import AnalysisCache
from .librosa_analyzer import AutoDJAnalysisCancelled, LibrosaAnalyzer

MAX_REMOTE_AUDIO_BYTES = 120 * 1024 * 1024
REMOTE_DOWNLOAD_ATTEMPTS = 3
REMOTE_DOWNLOAD_RETRY_DELAY_SECONDS = 0.5
REMOTE_DOWNLOAD_MAX_REQUESTS = 128
REMOTE_DOWNLOAD_TIMEOUT_SECONDS = 180
_logger = get_logger(__name__)


class AutoDJService:
    # Scientific analysis can briefly consume hundreds of megabytes. Keep one
    # analyzer process active per service to prevent PyInstaller installations
    # from being terminated under memory pressure.
    max_parallel_analyses = 1
    supports_analysis_deadline = True

    def __init__(self, cache_path, *, remote_resolver=None, remote_retry_handler=None,
                 remote_fallback_resolver=None, analyzer=None):
        self.cache = AnalysisCache(cache_path)
        self.remote_resolver = remote_resolver
        self.remote_retry_handler = remote_retry_handler
        self.remote_fallback_resolver = remote_fallback_resolver
        self.analyzer = analyzer or LibrosaAnalyzer()
        self._analysis_lock = threading.Lock()
        self._status_lock = threading.Lock()
        self._analysis_statuses = OrderedDict()

    def get_analysis_status(self, media_path: str) -> str:
        """Return the last observed result, without implying a queued track is analyzed."""
        with self._status_lock:
            return self._analysis_statuses.get(str(media_path or "").strip(), "unknown")

    def _set_analysis_status(self, media_path: str, status: str) -> None:
        with self._status_lock:
            self._analysis_statuses[media_path] = status
            self._analysis_statuses.move_to_end(media_path)
            while len(self._analysis_statuses) > 512:
                self._analysis_statuses.popitem(last=False)

    def _run_analyzer(self, media_path, *, cancel_event=None, deadline=None):
        kwargs = {}
        if getattr(self.analyzer, "supports_analysis_deadline", False) is True:
            kwargs.update(cancel_event=cancel_event, deadline=deadline)
        return self.analyzer.analyze(media_path, **kwargs)

    def get_cached(self, media_path):
        normalized = str(media_path or "").strip()
        if not normalized:
            return None
        if os.path.isfile(normalized):
            cached = self.cache.get(normalized, self.analyzer.analysis_version)
        else:
            cached = self.cache.get_remote(normalized, self.analyzer.analysis_version)
        return asdict(cached) if cached is not None else None

    @staticmethod
    def _check_cancelled(cancel_event=None, deadline=None):
        if (
            (cancel_event is not None and cancel_event.is_set())
            or (deadline is not None and time.monotonic() >= deadline)
        ):
            raise AutoDJAnalysisCancelled(
                _("A análise do AutoDJ foi cancelada porque o resultado não é mais necessário.")
            )

    def analyze(self, media_path, *, remote_resolver=None, cancel_event=None, deadline=None):
        normalized = str(media_path or "").strip()
        while not self._analysis_lock.acquire(timeout=0.1):
            self._check_cancelled(cancel_event, deadline)
        try:
            self._check_cancelled(cancel_event, deadline)
            self._set_analysis_status(normalized, "pending")
            try:
                result = self._analyze_serialized(
                    normalized,
                    remote_resolver=remote_resolver,
                    cancel_event=cancel_event,
                    deadline=deadline,
                )
            except AutoDJAnalysisCancelled:
                self._set_analysis_status(normalized, "unknown")
                raise
            except IncompleteRead as exc:
                self._set_analysis_status(normalized, "failed")
                raise RuntimeError(_("O áudio baixado está incompleto. Não foi possível analisar a faixa.")) from exc
            except Exception:
                self._set_analysis_status(normalized, "failed")
                raise
            self._set_analysis_status(normalized, "ready")
            return result
        finally:
            self._analysis_lock.release()

    def _analyze_serialized(
        self, media_path, *, remote_resolver=None, cancel_event=None, deadline=None
    ):
        normalized = str(media_path or "").strip()
        if not normalized:
            raise ValueError("O caminho da mídia é obrigatório.")
        if os.path.isfile(normalized):
            cached = self.cache.get(normalized, self.analyzer.analysis_version)
            if cached is None:
                cached = self._run_analyzer(
                    normalized, cancel_event=cancel_event, deadline=deadline
                )
                self.cache.put(normalized, cached, self.analyzer.analysis_version)
            return asdict(cached)
        resolver = remote_resolver or self.remote_resolver
        if not callable(resolver):
            raise ValueError("A mídia não é local e nenhum resolvedor remoto está disponível.")
        cached = self.cache.get_remote(normalized, self.analyzer.analysis_version)
        if cached is not None:
            return asdict(cached)
        with tempfile.TemporaryDirectory(prefix="keytune-autodj-") as temporary:
            target = Path(temporary) / "audio"
            retry_handler = self.remote_retry_handler if remote_resolver is None else None
            try:
                downloaded_path = self._download_remote(
                    normalized,
                    resolver,
                    target,
                    retry_handler=retry_handler,
                    cancel_event=cancel_event,
                    deadline=deadline,
                )
            except (OSError, IncompleteRead, ValueError) as exc:
                if remote_resolver is not None or not callable(self.remote_fallback_resolver):
                    raise
                _logger.warning("AutoDJ download failed (%s); trying an alternate stream", type(exc).__name__)
                # Never append bytes from a different representation to the first file.
                downloaded_path = self._download_remote(
                    normalized,
                    self.remote_fallback_resolver,
                    Path(temporary) / "alternative",
                    cancel_event=cancel_event,
                    deadline=deadline,
                )
            analysis = self._run_analyzer(
                downloaded_path, cancel_event=cancel_event, deadline=deadline
            )
        self.cache.put_remote(normalized, analysis, self.analyzer.analysis_version)
        return asdict(analysis)

    def _download_remote(
        self,
        media_path,
        resolver,
        target,
        *,
        retry_handler=None,
        cancel_event=None,
        deadline=None,
    ):
        last_error = None
        playback = None
        failures = 0
        previous_size = 0
        started_at = time.monotonic()
        for request_index in range(REMOTE_DOWNLOAD_MAX_REQUESTS):
            self._check_cancelled(cancel_event, deadline)
            if time.monotonic() - started_at >= REMOTE_DOWNLOAD_TIMEOUT_SECONDS:
                raise TimeoutError(_("O download do áudio para análise excedeu o tempo limite."))
            try:
                if playback is None:
                    playback = resolver(media_path)
                stream_url = str(getattr(playback, "stream_url", "") or "").strip()
                if not stream_url:
                    raise ValueError(_("O resolvedor remoto não retornou uma URL reproduzível."))
                download_kwargs = {"resume": request_index > 0}
                if cancel_event is not None or deadline is not None:
                    download_kwargs.update(cancel_event=cancel_event, deadline=deadline)
                return self._download(
                    stream_url,
                    target,
                    playback.http_headers or {},
                    **download_kwargs,
                )
            except (ConnectionError, IncompleteRead, TimeoutError, URLError, OSError) as exc:
                last_error = exc
                paths = list(Path(target).parent.glob(f"{Path(target).name}.*"))
                if Path(target).is_file():
                    paths.append(Path(target))
                current_size = max((path.stat().st_size for path in paths if path.is_file()), default=0)
                progressing = isinstance(exc, IncompleteRead) and current_size > previous_size
                previous_size = current_size
                if progressing:
                    # Some media servers end a response after 1 MiB, even when
                    # its headers advertise the whole file. Fetch the next range
                    # from the same stream; partial audio must never be analyzed.
                    failures = 0
                    continue
                failures += 1
                if failures >= REMOTE_DOWNLOAD_ATTEMPTS:
                    raise
                if callable(retry_handler):
                    retry_handler(media_path, exc)
                playback = None
                retry_delay = REMOTE_DOWNLOAD_RETRY_DELAY_SECONDS * failures
                if deadline is not None:
                    retry_delay = min(retry_delay, max(0.0, deadline - time.monotonic()))
                if cancel_event is not None:
                    cancel_event.wait(retry_delay)
                else:
                    time.sleep(retry_delay)
                self._check_cancelled(cancel_event, deadline)
        raise last_error or RuntimeError("Não foi possível baixar a faixa para análise.")

    @staticmethod
    def _download(
        url, target, headers, *, resume=False, cancel_event=None, deadline=None
    ):
        parsed_url = urlsplit(str(url or "").strip())
        if parsed_url.scheme.casefold() not in {"http", "https"} or not parsed_url.hostname:
            raise ValueError(_("O resolvedor remoto retornou uma URL de mídia inválida."))
        request_headers = {str(key): str(value) for key, value in headers.items()}
        partial_paths = []
        if resume:
            partial_paths = list(Path(target).parent.glob(f"{Path(target).name}.*"))
            if Path(target).is_file():
                partial_paths.append(Path(target))
        existing_path = max(partial_paths, key=lambda path: path.stat().st_size, default=None)
        existing_size = existing_path.stat().st_size if existing_path is not None else 0
        # YouTube may return only the first 1 MiB without an explicit Range.
        request_headers = {key: value for key, value in request_headers.items() if key.lower() != "range"}
        request_headers["Range"] = f"bytes={existing_size}-"

        request = Request(url, headers=request_headers)
        AutoDJService._check_cancelled(cancel_event, deadline)
        remaining_seconds = 30.0 if deadline is None else max(0.1, deadline - time.monotonic())
        with urlopen(request, timeout=min(30.0, remaining_seconds)) as response:
            content_type = str(response.headers.get("Content-Type", "")).split(";", 1)[0].strip().lower()
            if content_type.startswith("text/") or content_type in {"application/json", "application/xml"}:
                raise ValueError(_("O servidor remoto não retornou uma mídia de áudio válida."))
            suffix = {"audio/mp4": ".m4a", "audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mpeg": ".mp3", "audio/flac": ".flac"}.get(content_type, "")
            if not suffix and existing_path is not None:
                suffix = existing_path.suffix
            output_path = Path(target).with_suffix(suffix)
            response_status = int(getattr(response, "status", 200) or 200)
            can_resume = existing_path == output_path and existing_size > 0 and response_status == 206
            total = existing_size if can_resume else 0
            range_size = None
            expected_total = None
            if response_status == 206:
                content_range = re.fullmatch(
                    r"bytes (\d+)-(\d+)/(\d+)",
                    str(response.headers.get("Content-Range", "")).strip(),
                )
                if content_range is None:
                    raise ValueError(_("O servidor retornou um intervalo de áudio inválido."))
                start, end, expected_total = map(int, content_range.groups())
                if start != total or not start <= end < expected_total:
                    raise ValueError(_("O servidor retornou um intervalo de áudio inválido."))
                range_size = end - start + 1
                if expected_total > MAX_REMOTE_AUDIO_BYTES:
                    raise ValueError(_("A faixa online excede o limite de análise de 120 MB."))
            try:
                response_size = int(response.headers.get("Content-Length", "") or 0)
            except (TypeError, ValueError):
                response_size = 0
            if response_size > 0 and total + response_size > MAX_REMOTE_AUDIO_BYTES:
                raise ValueError(_("A faixa online excede o limite de análise de 120 MB."))
            if range_size is not None and response_size > 0 and response_size != range_size:
                raise ValueError(_("O servidor retornou um intervalo de áudio inválido."))
            expected_response_size = range_size if range_size is not None else response_size
            initial_size = total
            output = output_path.open("ab" if can_resume else "wb")
            try:
                while chunk := response.read(256 * 1024):
                    AutoDJService._check_cancelled(cancel_event, deadline)
                    total += len(chunk)
                    if total > MAX_REMOTE_AUDIO_BYTES:
                        raise ValueError(_("A faixa online excede o limite de análise de 120 MB."))
                    output.write(chunk)
            finally:
                output.close()
            received_size = total - initial_size
            if expected_response_size and received_size < expected_response_size:
                raise IncompleteRead(b"", expected_response_size - received_size)
            if expected_response_size and received_size > expected_response_size:
                raise ValueError(_("O servidor retornou um intervalo de áudio inválido."))
            if expected_total is not None and total < expected_total:
                raise IncompleteRead(b"", expected_total - total)
        return output_path
