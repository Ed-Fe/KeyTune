"""Auto DJ — beat/tempo-aware automatic mixing (experimental prototype).

This subpackage is intentionally isolated from the playback core. It provides:

- :mod:`analysis` — offline BPM/beat-grid analysis of local audio files, backed
  by ``librosa`` (an *optional* dependency) and cached to disk. When ``librosa``
  is not installed, :func:`analysis.is_available` returns ``False`` and the whole
  feature degrades to a no-op so nothing else breaks.
- :mod:`planner` — pure functions that decide how to connect two tracks
  (tempo-match ratio, transition length in beats). No I/O, easy to unit test.

The UI wiring lives in ``frames/playback/autodj.py`` (``AutoDjMixin``); it reuses
the existing dual-player crossfade machinery to actually overlap the two tracks.
"""

from . import analysis, planner

__all__ = ["analysis", "planner"]
