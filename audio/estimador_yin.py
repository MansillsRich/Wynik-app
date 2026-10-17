"""
Estimador de frecuencia fundamental YIN (de Cheveigné y Kawahara, 2002) con NumPy.

Pasos del artículo implementados:
  2. Función de diferencia d(τ), calculada con FFT (correlación cruzada) y sumas acumuladas.
  3. Diferencia media acumulada normalizada d'(τ) (CMND).
  4. Umbral absoluto: el primer mínimo local de d'(τ) por debajo de `umbral`; si no hay
     ninguno, el mínimo global (con su aperiodicidad alta, para que el llamador lo descarte).
  5. Interpolación parabólica alrededor del mínimo elegido.

Comprobación de subarmónicos: cuando la fundamental es débil (graves de piano), el primer
mínimo puede estar en la mitad del periodo (error de una octava hacia arriba). Si d'(2τ) o
d'(3τ) es claramente menor que d'(τ), se toma el periodo largo. Solo se aplica a candidatos
por debajo de 1 kHz (ver FRECUENCIA_MAXIMA_SUBARMONICO_HZ).

El rango de búsqueda (f_min, f_max) se fija al construir el estimador, antes de estimar.
La trama necesaria es `longitud_trama` muestras: una ventana de integración de τ_max
muestras más τ_max de desplazamiento máximo.

Solo usa numpy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

import numpy as np

# d'(kτ) debe ser menor que FACTOR_SUBARMONICO · d'(τ) para preferir el periodo k veces mayor;
# y d'(τ) debe superar APERIODICIDAD_MINIMA_SUBARMONICO (una señal limpia y periódica tiene
# d'(τ) ≈ d'(2τ) ≈ 0 y no debe cambiar de octava).
FACTOR_SUBARMONICO = 0.5
APERIODICIDAD_MINIMA_SUBARMONICO = 0.005
# La comprobación solo se aplica si el candidato está por debajo de esta frecuencia: las
# fundamentales débiles son un problema de los graves, y con periodos muy cortos (pocas
# muestras) la interpolación parabólica subestima la profundidad del mínimo y la
# comprobación bajaría una octava notas agudas correctas.
FRECUENCIA_MAXIMA_SUBARMONICO_HZ = 1000.0


def _potencia_de_2(n: int) -> int:
    return 1 << (int(n) - 1).bit_length()


@dataclass(frozen=True)
class EstimacionAltura:
    """Resultado de una trama: frecuencia (nan si no hay periodo) y aperiodicidad d'(τ)."""

    frecuencia_hz: float
    aperiodicidad: float

    @property
    def confianza(self) -> float:
        return float(min(1.0, max(0.0, 1.0 - self.aperiodicidad)))

    @property
    def tiene_altura(self) -> bool:
        return not math.isnan(self.frecuencia_hz)


NFFT_REFINAMIENTO = 65536
BUSQUEDA_REFINAMIENTO_CENTS = (-60.0, 15.0)   # la inarmonicidad solo sube la estimación de YIN
PROMINENCIA_REFINAMIENTO = 0.1                # el pico debe ser ≥ −20 dB del mayor de 0,8·f a 8·f
FRECUENCIA_MINIMA_REFINAMIENTO_HZ = 25.0      # se prueba en todo el rango; la validación descarta lo dudoso


def refinar_fundamental(tramas: np.ndarray, frecuencias: np.ndarray, frecuencia_muestreo: float
                        ) -> np.ndarray:
    """Corrige la estimación de YIN con la posición real de la fundamental en el espectro.

    Para cada trama con frecuencia YIN `f`, busca el pico espectral en [f − 60 cents, f + 15
    cents] (interpolación parabólica del logaritmo de la magnitud con ventana de Hann). Solo lo
    acepta si es un máximo local, no está en el borde de la búsqueda y alcanza el 10 % del
    mayor pico entre 0,8·f y 8·f: si la fundamental falta o es muy débil (graves del piano),
    no hay nada que refinar y se conserva la estimación de YIN. Las tramas sin frecuencia
    (nan) o por debajo de 100 Hz se devuelven sin cambios."""
    x = np.asarray(tramas, dtype=np.float64)
    resultado = np.array(frecuencias, dtype=np.float64, copy=True)
    if x.ndim != 2 or not x.shape[0]:
        return resultado
    ventana = np.hanning(x.shape[1])
    ancho_bin = frecuencia_muestreo / NFFT_REFINAMIENTO
    for i, f in enumerate(frecuencias):
        if not np.isfinite(f) or f < FRECUENCIA_MINIMA_REFINAMIENTO_HZ:
            continue
        magnitud = np.abs(np.fft.rfft((x[i] - x[i].mean()) * ventana, n=NFFT_REFINAMIENTO))
        desde = int(np.ceil(f * 2 ** (BUSQUEDA_REFINAMIENTO_CENTS[0] / 1200) / ancho_bin))
        hasta = int(np.floor(f * 2 ** (BUSQUEDA_REFINAMIENTO_CENTS[1] / 1200) / ancho_bin))
        if hasta - desde < 2 or hasta + 2 >= len(magnitud):
            continue
        k = desde + int(np.argmax(magnitud[desde: hasta + 1]))
        if k <= desde or k >= hasta:  # pico en el borde: es la ladera de otro
            continue
        if not (magnitud[k] >= magnitud[k - 1] and magnitud[k] >= magnitud[k + 1]) or magnitud[k] <= 0:
            continue
        banda = magnitud[int(0.8 * f / ancho_bin): int(8 * f / ancho_bin) + 1]
        if magnitud[k] < PROMINENCIA_REFINAMIENTO * banda.max():
            continue
        a, b, c = (np.log(max(magnitud[k + d], 1e-300)) for d in (-1, 0, 1))
        denominador = a - 2 * b + c
        desplazamiento = 0.5 * (a - c) / denominador if denominador < 0 else 0.0
        resultado[i] = (k + max(-0.5, min(0.5, desplazamiento))) * ancho_bin
    return resultado


class EstimadorYin:
    """YIN vectorizado. `estimar_lote` procesa varias tramas a la vez (una FFT por lote)."""

    nombre = "yin"

    def __init__(self, frecuencia_muestreo: float, f_min: float, f_max: float,
                 umbral: float = 0.15, ventana_integracion: int = 0):
        if frecuencia_muestreo <= 0:
            raise ValueError("La frecuencia de muestreo debe ser positiva")
        if not 0 < f_min < f_max < frecuencia_muestreo / 2:
            raise ValueError(f"Rango de búsqueda no válido: {f_min}–{f_max} Hz "
                             f"a {frecuencia_muestreo} Hz de muestreo")
        self.frecuencia_muestreo = float(frecuencia_muestreo)
        self.f_min = float(f_min)
        self.f_max = float(f_max)
        self.umbral = float(umbral)
        self.tau_min = max(2, int(math.floor(self.frecuencia_muestreo / self.f_max)))
        self.tau_max = int(math.ceil(self.frecuencia_muestreo / self.f_min)) + 1
        self.integracion = int(ventana_integracion) if ventana_integracion else self.tau_max
        self.longitud_trama = self.integracion + self.tau_max + 1
        self._nfft = _potencia_de_2(self.longitud_trama)
        self._taus = np.arange(self.tau_max + 1)

    @property
    def duracion_trama_s(self) -> float:
        return self.longitud_trama / self.frecuencia_muestreo

    def estimar(self, trama) -> EstimacionAltura:
        f, a = self.estimar_lote(np.asarray(trama, dtype=np.float64)[None, :])
        return EstimacionAltura(float(f[0]), float(a[0]))

    def diferencia_normalizada(self, tramas: np.ndarray) -> np.ndarray:
        """d'(τ) para τ = 0..τ_max de cada trama (filas). Las tramas más largas que
        `longitud_trama` se recortan por el final (se usan las muestras más recientes)."""
        x = np.asarray(tramas, dtype=np.float64)
        if x.ndim == 1:
            x = x[None, :]
        if x.shape[1] < self.longitud_trama:
            relleno = np.zeros((x.shape[0], self.longitud_trama - x.shape[1]))
            x = np.concatenate([relleno, x], axis=1)
        elif x.shape[1] > self.longitud_trama:
            x = x[:, -self.longitud_trama:]
        x = x - x.mean(axis=1, keepdims=True)
        w = self.integracion
        espectro_a = np.fft.rfft(x[:, :w], n=self._nfft, axis=1)
        espectro_x = np.fft.rfft(x, n=self._nfft, axis=1)
        correlacion = np.fft.irfft(np.conj(espectro_a) * espectro_x, n=self._nfft, axis=1)
        correlacion = correlacion[:, : self.tau_max + 1]
        acumulada = np.concatenate([np.zeros((x.shape[0], 1)), np.cumsum(x * x, axis=1)], axis=1)
        energia_0 = acumulada[:, w] - acumulada[:, 0]
        energia_tau = acumulada[:, self._taus + w] - acumulada[:, self._taus]
        d = energia_0[:, None] + energia_tau - 2.0 * correlacion
        d[:, 0] = 0.0
        np.maximum(d, 0.0, out=d)
        suma = np.cumsum(d[:, 1:], axis=1)
        normalizada = np.ones_like(d)
        with np.errstate(divide="ignore", invalid="ignore"):
            cociente = d[:, 1:] * self._taus[1:] / suma
        normalizada[:, 1:] = np.where(suma > 1e-12 * w, cociente, 1.0)
        return normalizada

    def estimar_lote(self, tramas: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Frecuencias (nan si no hay periodo) y aperiodicidades de un lote de tramas."""
        x = np.asarray(tramas, dtype=np.float64)
        if x.ndim == 1:
            x = x[None, :]
        dprima = self.diferencia_normalizada(x)
        energia = np.sum(x[:, -self.longitud_trama:] ** 2, axis=1)
        frecuencias = np.full(x.shape[0], np.nan)
        aperiodicidades = np.ones(x.shape[0])
        for i in range(x.shape[0]):
            if energia[i] <= 1e-12:
                continue
            tau, valor = self._elegir_periodo(dprima[i])
            if tau is None:
                continue
            frecuencias[i] = self.frecuencia_muestreo / tau
            aperiodicidades[i] = valor
        return frecuencias, aperiodicidades

    def _elegir_periodo(self, d: np.ndarray):
        tau_min, tau_max = self.tau_min, self.tau_max - 1
        segmento = d[tau_min: tau_max]
        if segmento.size == 0:
            return None, 1.0
        debajo = np.flatnonzero(segmento < self.umbral)
        if debajo.size:
            tau = tau_min + int(debajo[0])
            while tau + 1 < tau_max and d[tau + 1] < d[tau]:
                tau += 1
        else:
            tau = tau_min + int(np.argmin(segmento))
        return self._comprobar_subarmonicos(d, *self._interpolar(d, tau))

    def _comprobar_subarmonicos(self, d: np.ndarray, tau: float, valor: float):
        """Prefiere 2τ o 3τ si su mínimo (interpolado) es claramente menor que el de τ.

        Se comparan mínimos interpolados, no valores en desplazamientos enteros: con un
        periodo no entero (p. ej. 100,5 muestras) d'(100) y d'(101) son altos, mientras que
        d'(201) es casi nulo, y compararlos directamente bajaría una octava por error."""
        if (valor <= APERIODICIDAD_MINIMA_SUBARMONICO
                or self.frecuencia_muestreo / tau > FRECUENCIA_MAXIMA_SUBARMONICO_HZ):
            return tau, valor
        mejor = (tau, valor)
        for multiplo in (2, 3):
            centro = int(round(multiplo * tau))
            if centro + 2 >= self.tau_max:
                break
            inicio = max(centro - 2, 1)
            local = inicio + int(np.argmin(d[inicio: centro + 3]))
            tau_k, valor_k = self._interpolar(d, local)
            if valor_k < FACTOR_SUBARMONICO * valor and valor_k < mejor[1]:
                mejor = (tau_k, valor_k)
        return mejor

    def _interpolar(self, d: np.ndarray, tau: int):
        if 1 <= tau < len(d) - 1:
            izquierda, centro, derecha = d[tau - 1], d[tau], d[tau + 1]
            denominador = izquierda - 2.0 * centro + derecha
            if denominador > 0:
                desplazamiento = 0.5 * (izquierda - derecha) / denominador
                if abs(desplazamiento) < 1.0:
                    valor = centro - 0.25 * (izquierda - derecha) * desplazamiento
                    return tau + desplazamiento, float(min(max(valor, 0.0), 1.0))
        return float(tau), float(min(max(d[tau], 0.0), 1.0))
