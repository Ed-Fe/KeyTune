from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import sys

from player.autodj.librosa_analyzer import LibrosaAnalyzer


def main(argv=None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 4:
        return 2
    previous_worker_value = os.environ.get("KEYTUNE_AUTODJ_ANALYZER_WORKER")
    os.environ["KEYTUNE_AUTODJ_ANALYZER_WORKER"] = "1"
    os.environ.setdefault("NUMBA_THREADING_LAYER", "workqueue")
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
        if previous_worker_value is None:
            os.environ.pop("KEYTUNE_AUTODJ_ANALYZER_WORKER", None)
        else:
            os.environ["KEYTUNE_AUTODJ_ANALYZER_WORKER"] = previous_worker_value
    result_path.write_text(
        json.dumps(payload, ensure_ascii=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
