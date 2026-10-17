"""
Servicio de la guía de audio: fachada de compatibilidad sobre `audio.guia`.

- `generar_audio_guia(notas, bpm, ...)` (interfaz anterior): tempo constante `bpm`, pero cada
  nota suena en su posición (`offset_beats`), así que los silencios se conservan; las notas
  simultáneas suenan a la vez y no alargan la guía.
- `generar_guia(notas, ...)`: usa los tiempos de la partitura (`inicio_s`/`duracion_s`, con
  sus cambios de tempo) y un factor de tempo de práctica.

La frecuencia de cada nota sale del modelo musical (`alturas_midi`, `midi`, `frecuencia_hz`
o, si faltan, su nombre leído con `nucleo.musica.Altura`): 'B-4' es Si bemol 4.
"""

import math
from typing import Any, Dict, List, Optional

from audio.guia import (FRECUENCIA_GUIA, _frecuencias_de_nota, escribir_wav, sintetizar,
                        sonidos_de_notas)


def duracion_wav(ruta: str) -> float:
    """Duración en segundos de un WAV según su cabecera (0.0 si no se puede leer). Sirve
    cuando el reproductor del sistema no informa la duración (por ejemplo, sin salida de
    audio)."""
    import wave
    try:
        with wave.open(ruta, "rb") as archivo:
            frecuencia = archivo.getframerate()
            return archivo.getnframes() / frecuencia if frecuencia else 0.0
    except (OSError, EOFError, wave.Error):
        return 0.0


def formatear_tiempo(segundos: Optional[float]) -> str:
    """Formatea una duración en segundos a una cadena MM:SS."""
    if segundos is None or (isinstance(segundos, float) and math.isnan(segundos)) or segundos < 0:
        return "00:00"
    mins = int(segundos // 60)
    secs = int(segundos % 60)
    return f"{mins:02d}:{secs:02d}"


def frecuencia_de_nota(nota: Dict[str, Any]) -> Optional[float]:
    """Frecuencia en hercios de la nota principal (None si no tiene altura válida)."""
    try:
        if nota.get("frecuencia_hz"):
            return float(nota["frecuencia_hz"])
    except (TypeError, ValueError):
        return None
    frecuencias = _frecuencias_de_nota({k: v for k, v in nota.items() if k != "alturas_midi"})
    return frecuencias[0] if frecuencias else None


def generar_audio_guia(notas_partitura: List[Dict[str, Any]], bpm: float,
                       ruta_salida: str = "temp_guia.wav",
                       sample_rate: int = FRECUENCIA_GUIA, timbre: str = "seno") -> Optional[str]:
    """Sintetiza la guía a tempo constante `bpm` y la guarda en `ruta_salida` (WAV)."""
    if not notas_partitura:
        return None
    guia = sintetizar(sonidos_de_notas(notas_partitura, bpm=bpm), sample_rate, timbre=timbre)
    if not len(guia.muestras):
        return None
    return escribir_wav(ruta_salida, guia)


def generar_guia(notas_partitura: List[Dict[str, Any]], ruta_salida: str = "temp_guia.wav",
                 factor_tempo: float = 1.0, duracion_total_s: Optional[float] = None,
                 sample_rate: int = FRECUENCIA_GUIA, timbre: str = "seno") -> Optional[str]:
    """Guía con los tiempos de la partitura (cambios de tempo incluidos). `timbre`: «seno»,
    «piano» o «guitarra» (ver `audio.guia`)."""
    if not notas_partitura:
        return None
    total = None if duracion_total_s is None else duracion_total_s / factor_tempo
    guia = sintetizar(sonidos_de_notas(notas_partitura, factor_tempo=factor_tempo),
                      sample_rate, duracion_total_s=total, timbre=timbre)
    if not len(guia.muestras):
        return None
    return escribir_wav(ruta_salida, guia)
