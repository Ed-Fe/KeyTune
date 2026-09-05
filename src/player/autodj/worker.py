from __future__ import annotations

from dataclasses import asdict
import json
import os
import sys

from player.autodj.librosa_analyzer import LibrosaAnalyzer, _WORKER_RESULT_PREFIX


def main() -> int:
    if len(sys.argv) != 4:
        return 2
    os.environ["KEYTUNE_AUTODJ_ANALYZER_WORKER"] = "1"
    os.environ.setdefault("NUMBA_THREADING_LAYER", "workqueue")
    analyzer = LibrosaAnalyzer(
        sample_rate=int(sys.argv[2]),
        maximum_duration_seconds=int(sys.argv[3]),
    )
    result = analyzer._analyze_in_process(sys.argv[1])
    print(_WORKER_RESULT_PREFIX + json.dumps(asdict(result), ensure_ascii=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
