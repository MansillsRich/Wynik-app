"""
Segmentación: convierte las estimaciones sucesivas (tramas de 10 ms) en eventos de
interpretación (`nucleo.eventos.EventoInterpretacion`).

Un evento NOTA no depende de que cambie el nombre de la nota: cada ataque nuevo se confirma
por separado, aunque tenga la misma altura que el anterior (reataque).

Cómo empieza un evento (candidato)
- Ataque por energía: el nivel sube `subida_ataque_db` respecto del mínimo de los 50 ms
  anteriores (nota tras silencio, articulación, cuerda pulsada de nuevo).
- Ataque por flujo espectral: el espectro gana energía de forma brusca y en banda ancha
  (martillo de piano, púa), aunque el nivel apenas suba (al menos 1,5 dB) o, si la cuerda se
  detiene y se pulsa de nuevo más suave, aunque baje de golpe (6 dB en 10 ms). El flujo se calcula con un
  filtro de máximos en frecuencia (SuperFlux simplificado, Böck y Widmer 2013) para que el
  vibrato no lo dispare.
- Sin ataque: aparece una altura estable cuando no sonaba nada (ataque lento), o la altura
  cambia al menos `histeresis_semitonos` (legato). Un salto de 12, 19 o 24 semitonos sin
  ataque se trata como un error de octava del estimador y no inicia otra nota.

Cómo se confirma
- Con un ataque, solo cuentan las tramas YIN que empiezan después del ataque (las
  anteriores contienen el sonido previo).
- `tramas_confirmacion` tramas periódicas seguidas dentro de ±50 cents de su mediana.
- La altura confirmada se clasifica: zumbido o tono del fondo (se ignora), señal por debajo
  del nivel mínimo (SENAL_DEBIL), fuera del rango del instrumento (FUERA_DE_RANGO) o NOTA.
- Si no se confirma en `confirmacion_max_s` (más la duración de la trama), un ataque se
  informa como SENAL_DEBIL, BAJA_CONFIANZA (sin periodicidad) o INESTABLE (altura que no se
  estabiliza). Como mucho un diagnóstico cada 300 ms, y uno por segundo si es del mismo
  tipo: el ruido continuo no produce un flujo de eventos.

Cómo termina una nota: 40 ms de silencio o 120 ms sin periodicidad (evento FIN).

Solo usa la biblioteca estándar y el núcleo musical.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from statistics import median
from typing import Callable, Deque, List, Optional

from nucleo.eventos import EventoInterpretacion, TipoEvento
from nucleo.instrumentos import ParametrosDeteccion
from nucleo.musica import LA4_HZ, frecuencia_a_midi, midi_a_frecuencia

NIVEL_INICIAL_DBFS = -120.0
SEPARACION_DIAGNOSTICOS_S = 0.3
SEPARACION_DIAGNOSTICOS_IGUALES_S = 1.0
SUBIDA_MINIMA_FLUJO_DB = 1.5
SUBIDA_SOBRE_CANDIDATO_DB = 3.0
CAIDA_BRUSCA_DB = 6.0
FRECUENCIA_NIVEL_CORTO_HZ = 150.0
SILENCIO_FIN_S = 0.04
APERIODICIDAD_FIN_S = 0.12
SALTOS_ARMONICOS = (12.0, 19.0, 24.0)


@dataclass(frozen=True)
class Trama:
    """Características de un salto de análisis.

    - `t`: fin del salto; `duracion_salto`: su duración (10 ms).
    - `nivel_dbfs`: nivel RMS del salto (10 ms); `nivel_largo_dbfs`: nivel en una ventana de
      1,5 periodos de la nota más grave del instrumento; `flujo`: flujo espectral.
    - `frecuencia_hz`, `aperiodicidad`: YIN sobre la trama que termina en `t` y empieza en
      `inicio_trama`.
    """

    t: float
    duracion_salto: float
    nivel_dbfs: float
    nivel_largo_dbfs: float
    flujo: float
    frecuencia_hz: float
    aperiodicidad: float
    inicio_trama: float

    @property
    def inicio_salto(self) -> float:
        return self.t - self.duracion_salto


@dataclass
class _Candidato:
    t_inicio: float
    motivo: str  # "ataque", "altura" o "cambio"
    t_limite: float
    # Ataque en la primera trama tras (re)iniciar: no había nivel anterior con el que
    # comparar, así que no se sabe si el sonido empezó ahí o ya sonaba (un zumbido).
    sin_referencia: bool = False
    alturas: List[float] = field(default_factory=list)
    aperiodicidades: List[float] = field(default_factory=list)
    niveles: List[float] = field(default_factory=list)
    tramas_validas: int = 0


@dataclass
class _NotaActiva:
    midi: float
    t_inicio: float
    tipo: Optional[TipoEvento]  # None: interferencia (zumbido) que se ignora


class Segmentador:
    """Máquina de estados de ataques y notas. No guarda audio: solo características."""

    def __init__(self, parametros: ParametrosDeteccion, umbral_silencio_dbfs: float,
                 umbral_minimo_dbfs: float, midi_min: float, midi_max: float,
                 duracion_trama_s: float, la4: float = LA4_HZ,
                 es_interferencia: Optional[Callable[[float, float, bool], bool]] = None):
        self.p = parametros
        self.umbral_silencio = umbral_silencio_dbfs
        self.umbral_minimo = umbral_minimo_dbfs
        self.midi_min = midi_min
        self.midi_max = midi_max
        self.duracion_trama = duracion_trama_s
        self.la4 = la4
        # es_interferencia(frecuencia, nivel, con_ataque) -> True si el tono es un zumbido
        self._es_interferencia = es_interferencia or (lambda f, nivel, con_ataque=False: False)
        self.reiniciar()

    def reiniciar(self) -> None:
        self._niveles: Deque[float] = deque(maxlen=5)
        self._niveles_largos: Deque[float] = deque(maxlen=5)
        self._flujos: Deque[float] = deque(maxlen=30)
        self._ultimo_ataque = -math.inf
        self._ultimo_diagnostico = -math.inf
        self._tipo_ultimo_diagnostico: Optional[TipoEvento] = None
        self._candidato: Optional[_Candidato] = None
        self._activa: Optional[_NotaActiva] = None
        self._saltos_silencio = 0
        self._saltos_aperiodicos = 0

    # ------------------------------------------------------------------------------------
    def procesar(self, tr: Trama) -> List[EventoInterpretacion]:
        p = self.p
        eventos: List[EventoInterpretacion] = []
        periodica = (math.isfinite(tr.frecuencia_hz) and tr.frecuencia_hz > 0
                     and tr.aperiodicidad <= p.aperiodicidad_max)
        midi = frecuencia_a_midi(tr.frecuencia_hz, self.la4) if periodica else None

        sin_referencia = not self._niveles
        ataque = self._es_ataque(tr)
        if ataque:
            self._ultimo_ataque = tr.t
            self._candidato = _Candidato(
                t_inicio=tr.inicio_salto, motivo="ataque",
                t_limite=tr.t + self.duracion_trama + p.confirmacion_max_s,
                sin_referencia=sin_referencia)
        elif (self._candidato is None and midi is not None
              and max(tr.nivel_dbfs, tr.nivel_largo_dbfs) >= self.umbral_silencio):
            activa = self._activa
            if activa is None:
                self._candidato = _Candidato(t_inicio=tr.inicio_trama, motivo="altura",
                                             t_limite=tr.t + p.confirmacion_max_s)
            elif (abs(midi - activa.midi) >= p.histeresis_semitonos
                  and not _salto_armonico(midi, activa.midi)):
                self._candidato = _Candidato(t_inicio=tr.t - 0.5 * self.duracion_trama,
                                             motivo="cambio", t_limite=tr.t + p.confirmacion_max_s)

        if self._candidato is not None:
            eventos.extend(self._avanzar_candidato(self._candidato, tr, midi))
        else:
            eventos.extend(self._seguir_nota(tr, periodica, midi))
        return eventos

    # ------------------------------------------------------------------------------------
    def _es_ataque(self, tr: Trama) -> bool:
        p = self.p
        previo_corto = min(self._niveles) if self._niveles else NIVEL_INICIAL_DBFS
        previo_largo = min(self._niveles_largos) if self._niveles_largos else NIVEL_INICIAL_DBFS
        anterior = self._niveles[-1] if self._niveles else NIVEL_INICIAL_DBFS
        media_flujo = sum(self._flujos) / len(self._flujos) if self._flujos else 0.0
        self._niveles.append(tr.nivel_dbfs)
        self._niveles_largos.append(tr.nivel_largo_dbfs)
        self._flujos.append(tr.flujo)
        if max(tr.nivel_dbfs, tr.nivel_largo_dbfs) < self.umbral_silencio:
            return False
        if tr.t - self._ultimo_ataque < p.separacion_minima_s:
            return False
        # Con una nota grave sonando (por debajo de 150 Hz, periodo > 6,7 ms) el nivel de
        # 10 ms oscila con la forma de onda: se usa el nivel largo.
        referencia = self._activa.midi if self._activa is not None else None
        if self._candidato is not None and self._candidato.alturas:
            referencia = self._candidato.alturas[-1]
        grave = referencia is not None and midi_a_frecuencia(referencia, self.la4) < FRECUENCIA_NIVEL_CORTO_HZ
        nivel, previo = ((tr.nivel_largo_dbfs, previo_largo) if grave
                         else (tr.nivel_dbfs, previo_corto))
        por_energia = nivel - previo >= p.subida_ataque_db
        # Mientras se confirma un ataque, otro solo lo sustituye si es claramente más fuerte
        # (las crestas de una onda grave no son ataques nuevos).
        candidato = self._candidato
        if por_energia and candidato is not None and candidato.motivo == "ataque" and candidato.niveles:
            por_energia = nivel >= max(candidato.niveles) + SUBIDA_SOBRE_CANDIDATO_DB
        # Un golpe nuevo añade energía: un pico de flujo con el nivel bajando poco a poco es la
        # cola de la nota anterior, no un ataque. Una caída brusca (≥ 6 dB en 10 ms) con flujo
        # sí lo es: la cuerda se detiene y se pulsa de nuevo, más suave.
        subida_corta = tr.nivel_dbfs - previo_corto
        caida_brusca = anterior - tr.nivel_dbfs >= CAIDA_BRUSCA_DB
        por_flujo = (tr.flujo >= max(p.flujo_minimo, p.flujo_relativo * media_flujo)
                     and (subida_corta >= SUBIDA_MINIMA_FLUJO_DB or caida_brusca))
        return por_energia or por_flujo

    def _avanzar_candidato(self, c: _Candidato, tr: Trama, midi: Optional[float]):
        p = self.p
        c.niveles.append(max(tr.nivel_dbfs, tr.nivel_largo_dbfs))
        # Con un ataque, las tramas que empiezan antes contienen el sonido anterior.
        valida = c.motivo != "ataque" or tr.inicio_trama >= c.t_inicio - 0.5 * tr.duracion_salto
        if valida:
            c.tramas_validas += 1
            if midi is not None:
                c.alturas.append(midi)
                c.aperiodicidades.append(tr.aperiodicidad)
                n = p.tramas_confirmacion
                if len(c.alturas) >= n:
                    ultimas = c.alturas[-n:]
                    centro = median(ultimas)
                    if max(abs(a - centro) for a in ultimas) <= 0.5:
                        return self._confirmar(c, centro, tr)
        if tr.t > c.t_limite:
            return self._expirar(c, tr)
        return []

    def _confirmar(self, c: _Candidato, midi: float, tr: Trama) -> List[EventoInterpretacion]:
        self._candidato = None
        frecuencia = midi_a_frecuencia(midi, self.la4)
        nivel = max(c.niveles)
        n = self.p.tramas_confirmacion
        confianza = max(0.0, min(1.0, 1.0 - sum(c.aperiodicidades[-n:]) / n))
        activa = self._activa
        # Para decidir si el tono es un zumbido cuenta el nivel de las tramas que confirman la
        # altura: tras una caída brusca, las primeras tramas del candidato aún contienen la
        # nota anterior.
        nivel_tono = max(c.niveles[-n:])
        if self._es_interferencia(frecuencia, nivel_tono, c.motivo == "ataque" and not c.sin_referencia):
            self._activa = _NotaActiva(midi, c.t_inicio, None)
            return []
        if (c.motivo != "ataque" and activa is not None and activa.tipo is not None
                and abs(midi - activa.midi) < self.p.histeresis_semitonos):
            return []  # la altura volvió a la de la nota que sonaba: no es otra nota
        if nivel < self.umbral_minimo:
            tipo = TipoEvento.SENAL_DEBIL
        elif not (self.midi_min - 0.5 <= midi <= self.midi_max + 0.5):
            tipo = TipoEvento.FUERA_DE_RANGO
        else:
            tipo = TipoEvento.NOTA
        repeticion = (c.motivo == "ataque" and activa is not None and activa.tipo is not None
                      and abs(midi - activa.midi) < 0.5)
        self._activa = _NotaActiva(midi, c.t_inicio, tipo)
        self._saltos_silencio = self._saltos_aperiodicos = 0
        if tipo is not TipoEvento.NOTA:
            self._ultimo_diagnostico = tr.t
            self._tipo_ultimo_diagnostico = tipo
        return [EventoInterpretacion(tipo, c.t_inicio, frecuencia_hz=frecuencia, la4=self.la4,
                                     confianza=confianza, nivel_dbfs=nivel, t_confirmacion=tr.t,
                                     repeticion=repeticion)]

    def _expirar(self, c: _Candidato, tr: Trama) -> List[EventoInterpretacion]:
        self._candidato = None
        if c.motivo != "ataque" or tr.t - self._ultimo_diagnostico < SEPARACION_DIAGNOSTICOS_S:
            return []
        nivel = max(c.niveles) if c.niveles else NIVEL_INICIAL_DBFS
        if nivel < self.umbral_minimo:
            tipo = TipoEvento.SENAL_DEBIL
        elif len(c.alturas) < 0.3 * max(1, c.tramas_validas):
            tipo = TipoEvento.BAJA_CONFIANZA
        else:
            tipo = TipoEvento.INESTABLE
        if (tipo is self._tipo_ultimo_diagnostico
                and tr.t - self._ultimo_diagnostico < SEPARACION_DIAGNOSTICOS_IGUALES_S):
            return []
        self._ultimo_diagnostico = tr.t
        self._tipo_ultimo_diagnostico = tipo
        frecuencia = midi_a_frecuencia(median(c.alturas), self.la4) if c.alturas else None
        confianza = (1.0 - sum(c.aperiodicidades) / len(c.aperiodicidades)) if c.aperiodicidades else 0.0
        return [EventoInterpretacion(tipo, c.t_inicio, frecuencia_hz=frecuencia, la4=self.la4,
                                     confianza=max(0.0, confianza), nivel_dbfs=nivel,
                                     t_confirmacion=tr.t)]

    def _seguir_nota(self, tr: Trama, periodica: bool, midi: Optional[float]):
        activa = self._activa
        if activa is None:
            return []
        silencio = max(tr.nivel_dbfs, tr.nivel_largo_dbfs) < self.umbral_silencio
        self._saltos_silencio = self._saltos_silencio + 1 if silencio else 0
        self._saltos_aperiodicos = 0 if periodica else self._saltos_aperiodicos + 1
        if (self._saltos_silencio * tr.duracion_salto >= SILENCIO_FIN_S
                or self._saltos_aperiodicos * tr.duracion_salto >= APERIODICIDAD_FIN_S):
            self._activa = None
            self._saltos_silencio = self._saltos_aperiodicos = 0
            if activa.tipo is TipoEvento.NOTA:
                return [EventoInterpretacion(TipoEvento.FIN, tr.t, la4=self.la4,
                                             frecuencia_hz=midi_a_frecuencia(activa.midi, self.la4),
                                             nivel_dbfs=tr.nivel_dbfs, t_confirmacion=tr.t)]
        return []


def _salto_armonico(midi: float, referencia: float) -> bool:
    diferencia = abs(midi - referencia)
    return any(abs(diferencia - salto) < 0.5 for salto in SALTOS_ARMONICOS)
