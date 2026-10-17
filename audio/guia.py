"""
Síntesis de la guía de audio desde el modelo temporal de la partitura (C11).

Cada ataque suena en su instante (`inicio_s`, con los cambios de tempo de la partitura) y
durante su duración (con las ligaduras ya sumadas); los silencios son los huecos entre
ataques; las notas simultáneas (acordes, dos pentagramas) suenan a la vez. La frecuencia sale
del número MIDI del modelo, nunca de reinterpretar un nombre.

Las notas fuera del rango audible (< 20 Hz) o por encima del 45 % de la frecuencia de
muestreo no se sintetizan (se cuentan en `GuiaSintetizada.omitidas`).

Timbres (`timbre`): «seno» (por defecto, un seno puro por nota), «piano» (parciales
ligeramente inarmónicos que se apagan antes cuanto más agudos) y «guitarra» (cuerda pulsada:
parciales según el punto de pulsación, más brillante al principio y con caída rápida). Son
aproximaciones para distinguir de oído la referencia de cada instrumento, no muestras reales.

Solo usa numpy y la biblioteca estándar (`wave` para escribir el archivo).
"""

from __future__ import annotations

import wave
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np

from nucleo.musica import Altura, ErrorAltura, midi_a_frecuencia

FRECUENCIA_GUIA = 22050
FRECUENCIA_AUDIBLE_MINIMA_HZ = 20.0
ATAQUE_S = 0.005
RELAJACION_S = 0.010
AMPLITUD = 0.5
TIMBRES = ("seno", "piano", "guitarra")
PARCIALES = 10
INARMONICIDAD_PIANO = 0.0004      # B de f_n = n·f·√(1 + B·n²), valor típico de registro medio
PUNTO_PULSACION = 0.18            # fracción de la cuerda desde el puente


@dataclass(frozen=True)
class SonidoGuia:
    inicio_s: float
    duracion_s: float
    frecuencias_hz: Tuple[float, ...]


@dataclass
class GuiaSintetizada:
    muestras: np.ndarray
    frecuencia_muestreo: int
    sonidos: List[SonidoGuia] = field(default_factory=list)
    omitidas: int = 0

    @property
    def duracion_s(self) -> float:
        return len(self.muestras) / self.frecuencia_muestreo


def _frecuencias_de_nota(nota: dict) -> Tuple[float, ...]:
    alturas = nota.get("alturas_midi")
    if alturas:
        todas = list(alturas) + list(nota.get("acompanamiento_midi") or ())
        return tuple(midi_a_frecuencia(m) for m in todas)
    try:
        if nota.get("frecuencia_hz"):
            return (float(nota["frecuencia_hz"]),)
        if nota.get("midi") is not None:
            return (midi_a_frecuencia(nota["midi"]),)
        return (Altura.desde_nombre(nota["nombre"]).frecuencia,)
    except (ErrorAltura, KeyError, TypeError, ValueError):
        return ()


def sonidos_de_notas(notas: Iterable[dict], bpm: Optional[float] = None,
                     factor_tempo: float = 1.0) -> List[SonidoGuia]:
    """Sonidos de la lista de `cargar_partitura`.

    - Con `bpm`, tempo constante: inicio = offset_beats·60/bpm (los silencios se conservan
      porque cuentan las posiciones, no la suma de duraciones).
    - Sin `bpm`, se usan `inicio_s`/`duracion_s` (tempo de la partitura y sus cambios) y, si
      faltan, 120 negras por minuto. `factor_tempo` > 1 acelera."""
    if factor_tempo <= 0:
        raise ValueError("El factor de tempo debe ser positivo")
    resultado = []
    for nota in notas:
        if bpm is None and nota.get("inicio_s") is not None and nota.get("duracion_s") is not None:
            inicio, duracion = float(nota["inicio_s"]), float(nota["duracion_s"])
        else:
            spb = 60.0 / max(float(bpm or 120.0), 1.0)
            inicio = float(nota["offset_beats"]) * spb
            duracion = float(nota["duracion_beats"]) * spb
        resultado.append(SonidoGuia(inicio / factor_tempo, duracion / factor_tempo,
                                    _frecuencias_de_nota(nota)))
    return resultado


def _onda(frecuencias: Sequence[float], t: np.ndarray, duracion_s: float, timbre: str,
          sr: int) -> np.ndarray:
    """Suma de las notas simultáneas, cada una con pico ≈ 1 antes de la envolvente común."""
    if timbre == "seno":
        envolvente = np.exp(-3.0 * t / max(duracion_s, 1e-3))
        return envolvente * sum(np.sin(2 * np.pi * f * t) for f in frecuencias)
    total = np.zeros_like(t)
    n = np.arange(1, PARCIALES + 1, dtype=np.float64)
    for f in frecuencias:
        if timbre == "piano":
            fn = n * f * np.sqrt(1.0 + INARMONICIDAD_PIANO * n ** 2)
            amplitudes = 1.0 / n ** 1.15
            caidas = 0.9 + 0.55 * n + f / 900.0           # los agudos se apagan antes
        else:  # guitarra
            fn = n * f
            amplitudes = np.abs(np.sin(np.pi * n * PUNTO_PULSACION)) / n ** 1.2
            caidas = 1.6 + 1.1 * n + f / 600.0
        validos = fn < 0.45 * sr
        amplitudes = amplitudes[validos] / max(float(np.sum(amplitudes[validos])), 1e-9)
        for a, fp, k in zip(amplitudes, fn[validos], caidas[validos]):
            total += a * np.exp(-k * t) * np.sin(2 * np.pi * fp * t)
    return total


def sintetizar(sonidos: Sequence[SonidoGuia], frecuencia_muestreo: int = FRECUENCIA_GUIA,
               duracion_total_s: Optional[float] = None, timbre: str = "seno") -> GuiaSintetizada:
    """Cada sonido con ataque de 5 ms, decaimiento y relajación de 10 ms; `timbre` elige el
    contenido armónico (ver el docstring del módulo)."""
    if timbre not in TIMBRES:
        raise ValueError(f"Timbre desconocido: {timbre}")
    sr = int(frecuencia_muestreo)
    fin = max((s.inicio_s + s.duracion_s for s in sonidos), default=0.0)
    total = max(fin, duracion_total_s or 0.0)
    y = np.zeros(int(round(total * sr)), dtype=np.float64)
    omitidas = 0
    for sonido in sonidos:
        validas = [f for f in sonido.frecuencias_hz
                   if FRECUENCIA_AUDIBLE_MINIMA_HZ <= f < 0.45 * sr]
        omitidas += len(sonido.frecuencias_hz) - len(validas)
        i0 = int(round(sonido.inicio_s * sr))
        n = min(int(round(sonido.duracion_s * sr)), len(y) - i0)
        if not validas or n <= 0:
            continue
        t = np.arange(n) / sr
        envolvente = np.ones(n)
        n_ataque = min(n, int(round(ATAQUE_S * sr)))
        n_relajacion = min(n - n_ataque, int(round(RELAJACION_S * sr)))
        envolvente[:n_ataque] *= np.linspace(0.0, 1.0, n_ataque, endpoint=False)
        if n_relajacion:
            envolvente[n - n_relajacion:] *= np.linspace(1.0, 0.0, n_relajacion)
        amplitud = AMPLITUD / np.sqrt(len(validas))
        onda = _onda(validas, t, sonido.duracion_s, timbre, sr)
        y[i0:i0 + n] += amplitud * onda * envolvente
    pico = float(np.max(np.abs(y))) if y.size else 0.0
    if pico > 0.95:
        y *= 0.95 / pico
    return GuiaSintetizada(y.astype(np.float32), sr, list(sonidos), omitidas)


def escribir_wav(ruta: str, guia: GuiaSintetizada) -> str:
    datos = (np.clip(guia.muestras, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(ruta, "w") as archivo:
        archivo.setnchannels(1)
        archivo.setsampwidth(2)
        archivo.setframerate(guia.frecuencia_muestreo)
        archivo.writeframes(datos.tobytes())
    return ruta
