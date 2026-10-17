"""
Analizador: convierte bloques de audio en eventos de interpretación.

No abre dispositivos ni crea hilos: recibe bloques (de la captura real, de una prueba o de
un archivo) con `alimentar` y devuelve los eventos que producen. `audio.escucha` lo ejecuta
en un hilo propio, separado del callback del micrófono.

Por cada salto de 10 ms calcula:
- el nivel RMS (dBFS) del salto y un nivel «largo» en una ventana de 1,5 periodos de la nota
  más grave del instrumento (máximo 60 ms), que no oscila con las notas graves;
- el flujo espectral (ventana de Hann de 20 ms, magnitud comprimida con log10(1 + 1000·|X|),
  filtro de máximos de 3 bandas y diferencia con el espectro de 20 ms antes);
- la altura y la aperiodicidad con YIN (`audio.estimador_yin`) sobre la trama que termina
  en ese salto, en el rango de búsqueda del perfil de instrumento.

Los instantes de los eventos se calculan a partir del número de muestra (sin acumular el
desfase de los callbacks): t = t_ref + muestra / frecuencia_de_muestreo, donde t_ref es la
cota inferior de (t_captura − muestras_recibidas / fs) de los bloques recibidos. Si faltan
muestras (bloques descartados), el análisis se reinicia en lugar de unir audio discontinuo.

Solo usa numpy y el núcleo musical.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Callable, List, Optional

import numpy as np

from nucleo.eventos import EventoInterpretacion
from nucleo.instrumentos import PerfilInstrumento
from nucleo.musica import LA4_HZ, midi_a_frecuencia

from .estimador_yin import EstimadorYin, _potencia_de_2, refinar_fundamental
from .segmentador import Segmentador, Trama
from .senal import NIVEL_MINIMO_REPRESENTABLE_DBFS, PerfilDeRuido, es_interferencia

DURACION_SALTO_S = 0.010
COMPRESION_FLUJO = 1000.0
FRECUENCIA_MAXIMA_FLUJO_HZ = 10000.0
RETARDO_FLUJO_SALTOS = 2


class Analizador:
    """Bloques de audio (mono, float) → eventos de interpretación."""

    def __init__(self, frecuencia_muestreo: float, perfil: PerfilInstrumento,
                 ruido: Optional[PerfilDeRuido] = None, la4: float = LA4_HZ,
                 al_evento: Optional[Callable[[EventoInterpretacion], None]] = None,
                 sesion: int = 0):
        self.frecuencia_muestreo = float(frecuencia_muestreo)
        self.perfil = perfil
        self.la4 = float(la4)
        p = perfil.deteccion
        self.ruido = ruido or PerfilDeRuido.por_defecto(p.nivel_silencio_dbfs, p.nivel_minimo_dbfs)
        self.al_evento = al_evento
        self.sesion = sesion
        f_min, f_max = perfil.rango_busqueda_hz(self.la4, self.frecuencia_muestreo)
        self.estimador = EstimadorYin(self.frecuencia_muestreo, f_min, f_max, umbral=p.umbral_yin)
        self.salto = max(1, int(round(DURACION_SALTO_S * self.frecuencia_muestreo)))
        self.ventana_flujo = 2 * self.salto
        self._nfft_flujo = _potencia_de_2(self.ventana_flujo)
        self._hann = np.hanning(self.ventana_flujo)
        self._escala_flujo = 2.0 / self._hann.sum()
        bandas = np.fft.rfftfreq(self._nfft_flujo, 1.0 / self.frecuencia_muestreo)
        self._bandas_flujo = max(4, int(np.searchsorted(bandas, FRECUENCIA_MAXIMA_FLUJO_HZ)))
        # Además del nivel en 10 ms se mide un nivel «largo», en una ventana de 1,5 periodos de
        # la nota más grave del instrumento (máximo 60 ms): con 10 ms, un A0 (36 ms de
        # periodo) oscila dentro de la ventana y cada cresta parecería un ataque.
        f_grave = midi_a_frecuencia(perfil.midi_min, self.la4)
        self.ventana_nivel_largo = int(min(max(self.salto, round(1.5 * self.frecuencia_muestreo / f_grave)),
                                           round(0.060 * self.frecuencia_muestreo)))
        self.longitud_historia = max(self.estimador.longitud_trama, self.ventana_flujo,
                                     self.ventana_nivel_largo)
        self.segmentador = Segmentador(
            p, self.ruido.umbral_silencio_dbfs, self.ruido.umbral_minimo_dbfs,
            perfil.midi_min, perfil.midi_max, self.estimador.duracion_trama_s, self.la4,
            es_interferencia=lambda f, nivel, con_ataque=False: es_interferencia(
                f, nivel, self.ruido, p.frecuencias_interferencia_hz,
                p.tolerancia_interferencia_cents, con_ataque))
        # Estadísticas para las pruebas y las mediciones
        self.saltos_procesados = 0
        self.discontinuidades = 0
        self.segundos_de_calculo = 0.0
        self.reiniciar(0)

    @property
    def latencia_minima_s(self) -> float:
        """Audio necesario tras un ataque para poder confirmarlo (trama YIN + confirmación)."""
        return self.estimador.duracion_trama_s + self.perfil.deteccion.tramas_confirmacion * DURACION_SALTO_S

    def reiniciar(self, indice_muestra: int = 0) -> None:
        """Olvida el audio anterior (inicio, o hueco en la captura)."""
        self._historia = np.zeros(self.longitud_historia, dtype=np.float64)
        self._pendiente = np.zeros(0, dtype=np.float64)
        self._indice_siguiente = int(indice_muestra)   # índice de la próxima muestra que llegará
        self._indice_procesado = int(indice_muestra)   # índice de la primera muestra pendiente
        self._espectros = deque(maxlen=RETARDO_FLUJO_SALTOS)
        self.segmentador.reiniciar()

    def configurar_ruido(self, ruido: PerfilDeRuido) -> None:
        self.ruido = ruido
        self.segmentador.umbral_silencio = ruido.umbral_silencio_dbfs
        self.segmentador.umbral_minimo = ruido.umbral_minimo_dbfs

    # ------------------------------------------------------------------------------------
    def alimentar(self, muestras, indice_inicial: Optional[int] = None,
                  t_captura: Optional[float] = None) -> List[EventoInterpretacion]:
        """Procesa un bloque. `indice_inicial`: número de su primera muestra en la captura;
        `t_captura`: instante (reloj de la sesión) en que terminó de capturarse."""
        inicio_calculo = time.perf_counter()
        x = np.asarray(muestras, dtype=np.float64).reshape(-1)
        if indice_inicial is None:
            indice_inicial = self._indice_siguiente
        if indice_inicial != self._indice_siguiente:
            self.discontinuidades += 1
            self.reiniciar(indice_inicial)
        self._indice_siguiente = indice_inicial + len(x)
        if t_captura is not None:
            self._actualizar_referencia(t_captura)
        eventos = self._procesar(x)
        self.segundos_de_calculo += time.perf_counter() - inicio_calculo
        return eventos

    _t_ref: Optional[float] = None

    def _actualizar_referencia(self, t_captura: float) -> None:
        """t_ref = instante de la muestra 0. Se toma del primer bloque y se corrige hacia
        atrás con los bloques que llegan antes de lo previsto, pero solo si la captura va a
        ritmo real: si los bloques llegan más deprisa que el audio que contienen (archivos,
        pruebas), el reloj de llegada no dice nada sobre el instante de las muestras."""
        referencia = t_captura - self._indice_siguiente / self.frecuencia_muestreo
        if self._t_ref is None:
            self._t_ref = referencia
            self._ref_llegada = t_captura
            self._ref_indice = self._indice_siguiente
        elif referencia < self._t_ref:
            transcurrido = t_captura - self._ref_llegada
            audio = (self._indice_siguiente - self._ref_indice) / self.frecuencia_muestreo
            if transcurrido >= 0.5 * audio:
                self._t_ref = referencia

    def _procesar(self, x: np.ndarray) -> List[EventoInterpretacion]:
        self._pendiente = np.concatenate([self._pendiente, x]) if self._pendiente.size else x
        salto = self.salto
        n = len(self._pendiente) // salto
        if n == 0:
            return []
        nuevos = self._pendiente[: n * salto]
        datos = np.concatenate([self._historia, nuevos])
        base = len(self._historia)
        fines = base + salto * (np.arange(n) + 1)
        longitud = self.estimador.longitud_trama
        ventanas_yin = np.lib.stride_tricks.sliding_window_view(datos, longitud)[fines - longitud]
        frecuencias, aperiodicidades = self.estimador.estimar_lote(ventanas_yin)
        if self.perfil.deteccion.refinar_fundamental:
            frecuencias = refinar_fundamental(ventanas_yin, frecuencias, self.frecuencia_muestreo)
        acumulada = np.concatenate([[0.0], np.cumsum(datos * datos)])
        niveles = _niveles_db(acumulada, fines, salto)
        niveles_largos = _niveles_db(acumulada, fines, self.ventana_nivel_largo)
        ventanas_flujo = np.lib.stride_tricks.sliding_window_view(
            datos, self.ventana_flujo)[fines - self.ventana_flujo] * self._hann
        magnitudes = np.abs(np.fft.rfft(ventanas_flujo, n=self._nfft_flujo, axis=1))
        espectros = np.log10(1.0 + COMPRESION_FLUJO * self._escala_flujo
                             * magnitudes[:, : self._bandas_flujo])

        t_ref = self._t_ref if self._t_ref is not None else 0.0
        sr = self.frecuencia_muestreo
        eventos: List[EventoInterpretacion] = []
        for k in range(n):
            espectro = espectros[k]
            if len(self._espectros) == RETARDO_FLUJO_SALTOS:
                referencia = self._espectros[0]
                filtrada = np.maximum(np.maximum(referencia[:-2], referencia[1:-1]), referencia[2:])
                filtrada = np.concatenate([referencia[:1], filtrada, referencia[-1:]])
                flujo = float(np.sum(np.maximum(espectro - filtrada, 0.0)))
            else:
                flujo = float(np.sum(espectro))
            self._espectros.append(espectro)
            indice_fin = self._indice_procesado + (k + 1) * salto
            t = t_ref + indice_fin / sr
            trama = Trama(t=t, duracion_salto=salto / sr, nivel_dbfs=float(niveles[k]),
                          nivel_largo_dbfs=float(niveles_largos[k]), flujo=flujo, frecuencia_hz=float(frecuencias[k]),
                          aperiodicidad=float(aperiodicidades[k]),
                          inicio_trama=t - longitud / sr)
            for evento in self.segmentador.procesar(trama):
                if self.sesion:
                    evento = evento.con_sesion(self.sesion)
                eventos.append(evento)
                if self.al_evento is not None:
                    self.al_evento(evento)
        self.saltos_procesados += n
        self._indice_procesado += n * salto
        self._historia = datos[-self.longitud_historia:].copy()
        self._pendiente = self._pendiente[n * salto:]
        return eventos

    def analizar_senal(self, y, tam_bloque: int = 1024) -> List[EventoInterpretacion]:
        """Analiza una señal completa en bloques (pruebas, archivos)."""
        y = np.asarray(y, dtype=np.float64).reshape(-1)
        eventos: List[EventoInterpretacion] = []
        for i in range(0, len(y), tam_bloque):
            eventos.extend(self.alimentar(y[i:i + tam_bloque]))
        return eventos


def _niveles_db(acumulada: np.ndarray, fines: np.ndarray, ventana: int) -> np.ndarray:
    potencias = (acumulada[fines] - acumulada[fines - ventana]) / ventana
    with np.errstate(divide="ignore", invalid="ignore"):
        niveles = 10.0 * np.log10(np.maximum(potencias, 0.0))
    return np.maximum(np.nan_to_num(niveles, nan=NIVEL_MINIMO_REPRESENTABLE_DBFS,
                                    neginf=NIVEL_MINIMO_REPRESENTABLE_DBFS),
                      NIVEL_MINIMO_REPRESENTABLE_DBFS)
