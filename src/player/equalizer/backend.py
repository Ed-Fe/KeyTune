import math

from .models import (
    BUILTIN_PRESET_DESCRIPTIONS,
    BUILTIN_PRESET_LABELS,
    BUILTIN_PRESET_TABLE,
    FALLBACK_EQUALIZER_FREQUENCIES_HZ,
    EqualizerCatalog,
    EqualizerPreset,
    PRESET_SOURCE_BUILTIN,
    build_builtin_preset_id,
    clamp_gain_db,
    normalize_band_gains,
    normalize_builtin_preset_key,
)


def load_equalizer_catalog():
    frequencies = list(FALLBACK_EQUALIZER_FREQUENCIES_HZ)
    builtin_presets = []
    for preset_key, preset_data in BUILTIN_PRESET_TABLE.items():
        normalized_key = normalize_builtin_preset_key(preset_key)
        builtin_presets.append(
            EqualizerPreset(
                preset_id=build_builtin_preset_id(normalized_key),
                name=BUILTIN_PRESET_LABELS.get(normalized_key, str(preset_key).title()),
                preamp_db=clamp_gain_db(preset_data.get("preamp_db", 0.0)),
                band_gains_db=normalize_band_gains(
                    list(preset_data.get("band_gains_db", [])),
                    expected_count=len(frequencies),
                ),
                source=PRESET_SOURCE_BUILTIN,
                builtin_key=normalized_key,
                description=BUILTIN_PRESET_DESCRIPTIONS.get(
                    normalized_key,
                    f"Preset embutido do equalizador: {preset_key}.",
                ),
            )
        )

    return EqualizerCatalog(band_frequencies_hz=frequencies, builtin_presets=builtin_presets)


def _band_width_octaves(band_frequencies_hz, index):
    if not band_frequencies_hz:
        return 1.0

    current_frequency = float(band_frequencies_hz[index])
    previous_frequency = float(band_frequencies_hz[index - 1]) if index > 0 else current_frequency / math.sqrt(2.0)
    next_frequency = (
        float(band_frequencies_hz[index + 1])
        if index + 1 < len(band_frequencies_hz)
        else current_frequency * math.sqrt(2.0)
    )

    previous_frequency = max(1.0, previous_frequency)
    next_frequency = max(current_frequency + 1.0, next_frequency)
    return max(0.25, round(0.5 * math.log2(next_frequency / previous_frequency), 3))


def _safe_preamp_db(preamp_db, band_gains_db):
    requested_preamp_db = clamp_gain_db(preamp_db)
    highest_boost_db = max([0.0, *band_gains_db]) if band_gains_db else 0.0
    if highest_boost_db <= 0.0:
        return requested_preamp_db

    # Reserva apenas metade do maior boost como headroom: cada banda usa um
    # filtro peaking com cerca de uma oitava de largura, então o conteúdo
    # real do áudio raramente atinge o pico de todas as bandas
    # simultaneamente. Subtrair o valor inteiro do boost (pior caso teórico)
    # derruba o loudness percebido sem necessidade.
    required_headroom_db = clamp_gain_db(-highest_boost_db / 2.0)
    return min(requested_preamp_db, required_headroom_db)


def build_mpv_equalizer_filter(preset, *, band_frequencies_hz):
    if preset is None:
        return ""

    normalized_band_gains = normalize_band_gains(
        preset.band_gains_db,
        expected_count=len(band_frequencies_hz),
    )
    filter_parts = [f"volume=volume={_safe_preamp_db(preset.preamp_db, normalized_band_gains):.1f}dB"]
    for band_index, frequency_hz in enumerate(band_frequencies_hz):
        filter_parts.append(
            "equalizer="
            f"f={float(frequency_hz):.1f}:"
            f"t=o:w={_band_width_octaves(band_frequencies_hz, band_index):.3f}:"
            f"g={clamp_gain_db(normalized_band_gains[band_index]):.1f}"
        )

    # Limiter de segurança: se um preset personalizado ainda assim somar
    # picos suficientes para estourar (acima de ~−0,3 dBFS), o alimiter
    # corta o pico sem distorcer o restante da música.
    filter_parts.append("alimiter=limit=0.97:attack=5:release=50:level=disabled")

    return f"lavfi=[{','.join(filter_parts)}]"

