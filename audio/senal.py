"""
Nivel de señal, perfil de ruido de fondo y calibración.

La calibración mide el ruido de fondo de la sala con el micrófono real (el usuario en
silencio) en lugar de bajar un umbral fijo hasta que cualquier cosa produzca una nota:

- `nivel_fondo_dbfs`: mediana del nivel RMS en ventanas de 10 ms.
- `umbral_silencio_dbfs`: por debajo, silencio (fondo + 6 dB).
- `umbral_minimo_dbfs`: nivel mínimo para evaluar una nota (fondo + 12 dB, y nunca por
  debajo del percentil 95 del fondo + 6 dB, para que los picos del ruido no cuenten).
- `tonos_estacionarios`: componentes periódicas estables del fondo (zumbido de red,
  ventiladores, un frigorífico…). Un tono detectado a ±20 cents de una de ellas solo se
  acepta como nota si supera su nivel en 10 dB.

Sin calibrar se usan los niveles por defecto del perfil de instrumento.

Solo usa numpy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence, Tuple

import numpy as np

NIVEL_MINIMO_REPRESENTABLE_DBFS = -120.0
MARGEN_SILENCIO_DB = 6.0
MARGEN_NOTA_DB = 12.0
MARGEN_SOBRE_TONO_ESTACIONARIO_DB = 10.0


def nivel_dbfs(muestras) -> float:
    """Nivel RMS en dBFS (0 dBFS = valor RMS 1,0). Devuelve −120 si la señal es nula."""
    x = np.asarray(muestras, dtype=np.float64)
    if x.size == 0:
        return NIVEL_MINIMO_REPRESENTABLE_DBFS
    rms = math.sqrt(float(np.mean(x * x)))
    if rms <= 10 ** (NIVEL_MINIMO_REPRESENTABLE_DBFS / 20):
        return NIVEL_MINIMO_REPRESENTABLE_DBFS
    return 20.0 * math.log10(rms)


def niveles_por_ventana(muestras, tam_ventana: int) -> np.ndarray:
    """Nivel RMS (dBFS) de cada ventana consecutiva de `tam_ventana` muestras."""
    x = np.asarray(muestras, dtype=np.float64)
    n = len(x) // tam_ventana
    if n == 0:
        return np.zeros(0)
    potencia = np.mean(x[: n * tam_ventana].reshape(n, tam_ventana) ** 2, axis=1)
    with np.errstate(divide="ignore"):
        niveles = 10.0 * np.log10(potencia)
    return np.maximum(niveles, NIVEL_MINIMO_REPRESENTABLE_DBFS)


@dataclass(frozen=True)
class TonoEstacionario:
    frecuencia_hz: float
    nivel_dbfs: float


@dataclass(frozen=True)
class PerfilDeRuido:
    """Niveles de referencia de la captura. `calibrado` indica si salen de una medición."""

    nivel_fondo_dbfs: float
    umbral_silencio_dbfs: float
    umbral_minimo_dbfs: float
    tonos_estacionarios: Tuple[TonoEstacionario, ...] = field(default_factory=tuple)
    calibrado: bool = False
    duracion_medida_s: float = 0.0
    frecuencia_muestreo: Optional[float] = None

    @classmethod
    def por_defecto(cls, nivel_silencio_dbfs: float = -65.0, nivel_minimo_dbfs: float = -50.0
                    ) -> "PerfilDeRuido":
        return cls(nivel_fondo_dbfs=nivel_silencio_dbfs - MARGEN_SILENCIO_DB,
                   umbral_silencio_dbfs=nivel_silencio_dbfs,
                   umbral_minimo_dbfs=nivel_minimo_dbfs)

    def como_diccionario(self) -> dict:
        return {
            "nivel_fondo_dbfs": round(self.nivel_fondo_dbfs, 1),
            "umbral_silencio_dbfs": round(self.umbral_silencio_dbfs, 1),
            "umbral_minimo_dbfs": round(self.umbral_minimo_dbfs, 1),
            "tonos_estacionarios": [(round(t.frecuencia_hz, 2), round(t.nivel_dbfs, 1))
                                    for t in self.tonos_estacionarios],
            "calibrado": self.calibrado,
            "duracion_medida_s": round(self.duracion_medida_s, 2),
        }


def cents(f: float, referencia: float) -> float:
    return 1200.0 * math.log2(f / referencia)


def es_interferencia(frecuencia_hz: float, nivel: float, ruido: PerfilDeRuido,
                     frecuencias_red: Iterable[float] = (), tolerancia_cents: float = 20.0,
                     con_ataque: bool = False) -> bool:
    """True si un tono estable coincide con el zumbido de red o con un tono del fondo.

    - Las frecuencias de red solo cuentan como interferencia si el tono aparece sin ataque
      (`con_ataque=False`): un zumbido es estacionario. Una nota tocada con ataque a esa
      altura se evalúa normalmente; por ejemplo, un Sol2 con La4 = 444 Hz suena a 19 cents
      de 100 Hz y un Sol2 afinado 15 cents alto con La4 = 440 Hz, a 20 cents.
    - Los tonos del fondo medidos en la calibración cuentan con o sin ataque, salvo que la
      señal los supere en 10 dB o más (una nota tocada a esa misma altura)."""
    if not frecuencia_hz or not math.isfinite(frecuencia_hz) or frecuencia_hz <= 0:
        return False
    for f_red in () if con_ataque else frecuencias_red:
        if abs(cents(frecuencia_hz, f_red)) <= tolerancia_cents:
            return True
    for tono in ruido.tonos_estacionarios:
        if (abs(cents(frecuencia_hz, tono.frecuencia_hz)) <= tolerancia_cents
                and nivel < tono.nivel_dbfs + MARGEN_SOBRE_TONO_ESTACIONARIO_DB):
            return True
    return False


def calibrar(muestras, frecuencia_muestreo: float, estimador=None,
             nivel_minimo_absoluto_dbfs: float = -70.0) -> PerfilDeRuido:
    """Perfil de ruido a partir de una grabación del fondo (el usuario no toca).

    `estimador` (opcional, con `estimar_lote` y `longitud_trama`) se usa para detectar tonos
    estacionarios: si al menos el 60 % de las tramas son periódicas con la misma altura
    (±15 cents), esa altura se guarda como tono del fondo.
    """
    x = np.asarray(muestras, dtype=np.float64)
    sr = float(frecuencia_muestreo)
    ventana = max(1, int(round(0.010 * sr)))
    niveles = niveles_por_ventana(x, ventana)
    if niveles.size == 0:
        raise ValueError("La grabación de calibración es demasiado corta")
    fondo = float(np.median(niveles))
    p95 = float(np.percentile(niveles, 95))
    silencio = max(fondo + MARGEN_SILENCIO_DB, NIVEL_MINIMO_REPRESENTABLE_DBFS + MARGEN_SILENCIO_DB)
    minimo = max(fondo + MARGEN_NOTA_DB, p95 + MARGEN_SILENCIO_DB, nivel_minimo_absoluto_dbfs)
    silencio = min(silencio, minimo - 3.0)
    tonos = tuple(_tonos_estacionarios(x, sr, estimador)) if estimador is not None else ()
    return PerfilDeRuido(nivel_fondo_dbfs=fondo, umbral_silencio_dbfs=silencio,
                         umbral_minimo_dbfs=minimo, tonos_estacionarios=tonos, calibrado=True,
                         duracion_medida_s=len(x) / sr, frecuencia_muestreo=sr)


def _tonos_estacionarios(x: np.ndarray, sr: float, estimador) -> Sequence[TonoEstacionario]:
    longitud = estimador.longitud_trama
    salto = max(1, int(round(0.020 * sr)))
    inicios = range(0, len(x) - longitud + 1, salto)
    if len(inicios) < 5:
        return []
    tramas = np.stack([x[i:i + longitud] for i in inicios])
    frecuencias, aperiodicidades = estimador.estimar_lote(tramas)
    validas = np.isfinite(frecuencias) & (aperiodicidades <= 0.25)
    if np.count_nonzero(validas) < 0.6 * len(frecuencias):
        return []
    f = frecuencias[validas]
    mediana = float(np.median(f))
    desviacion = 1200.0 * np.abs(np.log2(f / mediana))
    if np.percentile(desviacion, 80) > 15.0:
        return []
    nivel = nivel_dbfs(x)
    return [TonoEstacionario(mediana, nivel)]
