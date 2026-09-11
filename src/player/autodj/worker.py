from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import sys

from player.autodj.librosa_analyzer import LibrosaAnalyzer


_WORKER_ENVIRONMENT_DEFAULTS = {
    "NUMBA_THREADING_LAYER": "workqueue",
    "NUMBA_NUM_THREADS": "1",
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
}


def main(argv=None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 4:
        return 2
    managed_environment = ("KEYTUNE_AUTODJ_ANALYZER_WORKER", *_WORKER_ENVIRONMENT_DEFAULTS)
    previous_environment = {name: os.environ.get(name) for name in managed_environment}
    os.environ["KEYTUNE_AUTODJ_ANALYZER_WORKER"] = "1"
    for name, value in _WORKER_ENVIRONMENT_DEFAULTS.items():
        os.environ[name] = value
    result_path = Path(arguments[3])
    try:
        try:
            analyzer = LibrosaAnalyzer(
                sample_rate=int(arguments[1]),
                maximum_duration_seconds=int(arguments[2]),
            )
            result = analyzer._analyze_in_process(arguments[0])
            payload = {"ok": True, "result": asdict(result)}
            exit_code = 0
        except Exception as exc:
            payload = {"ok": False, "error": str(exc) or exc.__class__.__name__}
            exit_code = 1
    finally:
        for name, previous_value in previous_environment.items():
            if previous_value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = previous_value
    try:
        result_path.write_text(
            json.dumps(payload, ensure_ascii=True, separators=(",", ":")),
            encoding="utf-8",
        )
    except OSError:
        # The main application may be closing while this isolated process is
        # still finishing. Its temporary result directory is then gone and
        # there is no caller left to consume a result; avoid an unhandled
        # traceback from the child process during shutdown.
        return exit_code or 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
