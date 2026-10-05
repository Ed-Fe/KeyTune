"""O que o player rápido entrega à janela principal para a mídia seguir tocando sem corte."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AdoptedPlayback:
    """O MPV do player rápido, ainda tocando, e o que ele estava tocando ao ser entregue."""

    player: Any
    instance: Any
    # A mídia que toca é a primeira; as demais são as que viriam depois dela.
    paths: list[str] = field(default_factory=list)
    volume: int = 0
    playback_rate: float = 1.0
    paused: bool = False
    # Preenchido se a faixa acabar enquanto a janela principal ainda sobe.
    ended: bool = False
