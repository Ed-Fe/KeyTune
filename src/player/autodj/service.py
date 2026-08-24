"""Shared AutoDJ analysis service for local files and resolved online streams."""

from __future__ import annotations

from dataclasses import asdict
import os
from pathlib import Path
import tempfile
from urllib.request import Request, urlopen

from .cache import AnalysisCache
from .librosa_analyzer import LibrosaAnalyzer

MAX_REMOTE_AUDIO_BYTES = 120 * 1024 * 1024


class AutoDJService:
    def __init__(self, cache_path, *, remote_resolver=None, analyzer=None):
        self.cache = AnalysisCache(cache_path)
        self.remote_resolver = remote_resolver
        self.analyzer = analyzer or LibrosaAnalyzer()

    def analyze(self, media_path):
        normalized = str(media_path or "").strip()
        if not normalized:
            raise ValueError("O caminho da mídia é obrigatório.")
        if os.path.isfile(normalized):
            cached = self.cache.get(normalized, self.analyzer.analysis_version)
            if cached is None:
                cached = self.analyzer.analyze(normalized)
                self.cache.put(normalized, cached, self.analyzer.analysis_version)
            return asdict(cached)
        if not callable(self.remote_resolver):
            raise ValueError("A mídia não é local e nenhum resolvedor remoto está disponível.")
        cached = self.cache.get_remote(normalized, self.analyzer.analysis_version)
        if cached is not None:
            return asdict(cached)
        playback = self.remote_resolver(normalized)
        with tempfile.TemporaryDirectory(prefix="keytune-autodj-") as temporary:
            target = Path(temporary) / "audio"
            downloaded_path = self._download(playback.stream_url, target, playback.http_headers or {})
            analysis = self.analyzer.analyze(downloaded_path)
        self.cache.put_remote(normalized, analysis, self.analyzer.analysis_version)
        return asdict(analysis)

    @staticmethod
    def _download(url, target, headers):
        request = Request(url, headers={str(key): str(value) for key, value in headers.items()})
        total = 0
        with urlopen(request, timeout=30) as response:
            content_type = str(response.headers.get("Content-Type", "")).split(";", 1)[0].strip().lower()
            suffix = {"audio/mp4": ".m4a", "audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mpeg": ".mp3", "audio/flac": ".flac"}.get(content_type, "")
            output_path = Path(target).with_suffix(suffix)
            output = output_path.open("wb")
            try:
                while chunk := response.read(256 * 1024):
                    total += len(chunk)
                    if total > MAX_REMOTE_AUDIO_BYTES:
                        raise ValueError("A faixa online excede o limite de análise de 120 MB.")
                    output.write(chunk)
            finally:
                output.close()
        return output_path
