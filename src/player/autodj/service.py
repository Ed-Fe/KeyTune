"""Shared AutoDJ analysis service for local files and resolved online streams."""

from __future__ import annotations

from dataclasses import asdict
from http.client import IncompleteRead
import os
from pathlib import Path
import tempfile
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

from .cache import AnalysisCache
from .librosa_analyzer import LibrosaAnalyzer

MAX_REMOTE_AUDIO_BYTES = 120 * 1024 * 1024
REMOTE_DOWNLOAD_ATTEMPTS = 3
REMOTE_DOWNLOAD_RETRY_DELAY_SECONDS = 0.5


class AutoDJService:
    def __init__(self, cache_path, *, remote_resolver=None, remote_retry_handler=None, analyzer=None):
        self.cache = AnalysisCache(cache_path)
        self.remote_resolver = remote_resolver
        self.remote_retry_handler = remote_retry_handler
        self.analyzer = analyzer or LibrosaAnalyzer()

    def get_cached(self, media_path):
        normalized = str(media_path or "").strip()
        if not normalized:
            return None
        if os.path.isfile(normalized):
            cached = self.cache.get(normalized, self.analyzer.analysis_version)
        else:
            cached = self.cache.get_remote(normalized, self.analyzer.analysis_version)
        return asdict(cached) if cached is not None else None

    def analyze(self, media_path, *, remote_resolver=None):
        normalized = str(media_path or "").strip()
        if not normalized:
            raise ValueError("O caminho da mídia é obrigatório.")
        if os.path.isfile(normalized):
            cached = self.cache.get(normalized, self.analyzer.analysis_version)
            if cached is None:
                cached = self.analyzer.analyze(normalized)
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
            downloaded_path = self._download_remote(normalized, resolver, target, retry_handler=retry_handler)
            analysis = self.analyzer.analyze(downloaded_path)
        self.cache.put_remote(normalized, analysis, self.analyzer.analysis_version)
        return asdict(analysis)

    def _download_remote(self, media_path, resolver, target, *, retry_handler=None):
        last_error = None
        for attempt in range(REMOTE_DOWNLOAD_ATTEMPTS):
            try:
                playback = resolver(media_path)
                return self._download(
                    playback.stream_url,
                    target,
                    playback.http_headers or {},
                    resume=attempt > 0,
                )
            except (ConnectionError, IncompleteRead, TimeoutError, URLError, OSError) as exc:
                last_error = exc
                if attempt + 1 >= REMOTE_DOWNLOAD_ATTEMPTS:
                    raise
                if callable(retry_handler):
                    retry_handler(media_path, exc)
                time.sleep(REMOTE_DOWNLOAD_RETRY_DELAY_SECONDS * (attempt + 1))
        raise last_error or RuntimeError("Não foi possível baixar a faixa para análise.")

    @staticmethod
    def _download(url, target, headers, *, resume=False):
        request_headers = {str(key): str(value) for key, value in headers.items()}
        partial_paths = []
        if resume:
            partial_paths = list(Path(target).parent.glob(f"{Path(target).name}.*"))
            if Path(target).is_file():
                partial_paths.append(Path(target))
        existing_path = max(partial_paths, key=lambda path: path.stat().st_size, default=None)
        existing_size = existing_path.stat().st_size if existing_path is not None else 0
        if existing_size > 0:
            request_headers["Range"] = f"bytes={existing_size}-"

        request = Request(url, headers=request_headers)
        with urlopen(request, timeout=30) as response:
            content_type = str(response.headers.get("Content-Type", "")).split(";", 1)[0].strip().lower()
            suffix = {"audio/mp4": ".m4a", "audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mpeg": ".mp3", "audio/flac": ".flac"}.get(content_type, "")
            if not suffix and existing_path is not None:
                suffix = existing_path.suffix
            output_path = Path(target).with_suffix(suffix)
            response_status = int(getattr(response, "status", 200) or 200)
            can_resume = existing_path == output_path and existing_size > 0 and response_status == 206
            total = existing_size if can_resume else 0
            output = output_path.open("ab" if can_resume else "wb")
            try:
                while chunk := response.read(256 * 1024):
                    total += len(chunk)
                    if total > MAX_REMOTE_AUDIO_BYTES:
                        raise ValueError("A faixa online excede o limite de análise de 120 MB.")
                    output.write(chunk)
            finally:
                output.close()
        return output_path
