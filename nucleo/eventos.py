"""
Eventos de interpretación: lo que el análisis de audio entrega a la sesión de práctica.

El analizador (`audio.analizador`) convierte el audio del micrófono en una secuencia de
eventos discretos; la sesión (`nucleo.sesion`) los compara con la partitura. Este módulo es
el contrato entre ambos y solo usa la biblioteca estándar: la sesión, la interfaz y las
pruebas pueden manejar eventos sin cargar numpy ni el análisis de audio.

Tipos de evento
- NOTA: ataque confirmado con una altura estable dentro del rango del instrumento.
- FUERA_DE_RANGO: altura estable fuera del rango configurado. No se convierte en la nota
  más cercana al límite: se informa tal cual.
- SENAL_DEBIL: hubo un ataque, pero por debajo del nivel mínimo evaluable.
- BAJA_CONFIANZA: ataque audible sin periodicidad suficiente (ruido, golpe, roce).
- INESTABLE: hay periodicidad, pero la altura no se estabiliza en el tiempo de confirmación.
- FIN: la nota activa terminó (silencio o pérdida de la altura).

Todos los instantes están en segundos del reloj de captura (el mismo reloj monotónico que
usa la sesión, o el tiempo de muestra en las simulaciones).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from enum import Enum
from typing import Optional

from .musica import LA4_HZ, Altura, ErrorAltura, frecuencia_a_midi, midi_mas_cercano


class TipoEvento(str, Enum):
    NOTA = "nota"
    FUERA_DE_RANGO = "fuera_de_rango"
    SENAL_DEBIL = "senal_debil"
    BAJA_CONFIANZA = "baja_confianza"
    INESTABLE = "inestable"
    FIN = "fin"

    @property
    def tiene_altura(self) -> bool:
        return self in (TipoEvento.NOTA, TipoEvento.FUERA_DE_RANGO)


@dataclass(frozen=True)
class EventoInterpretacion:
    """Un evento detectado en el audio.

    - `t`: inicio del ataque (o del cambio de altura) en segundos del reloj de captura.
    - `t_confirmacion`: instante del audio en que el evento quedó confirmado; la diferencia
      con `t` es la latencia algorítmica del detector (sin contar la interfaz).
    - `frecuencia_hz`: mediana de las estimaciones que confirman el evento (si tiene altura).
    - `la4`: referencia de afinación con la que se calculan `midi` y `cents`.
    - `confianza`: 1 − aperiodicidad media de las tramas de confirmación (0 a 1).
    - `repeticion`: ataque nuevo de la misma altura que la nota que sonaba (reataque).
    - `sesion`: identificador de la sesión de captura que lo produjo; la sesión de práctica
      descarta los eventos de otras sesiones.
    """

    tipo: TipoEvento
    t: float
    frecuencia_hz: Optional[float] = None
    la4: float = LA4_HZ
    confianza: float = 0.0
    nivel_dbfs: float = -math.inf
    t_confirmacion: Optional[float] = None
    repeticion: bool = False
    sesion: int = 0

    @property
    def midi(self) -> Optional[float]:
        """Número MIDI fraccionario de la frecuencia detectada (None si no tiene altura)."""
        if self.frecuencia_hz is None:
            return None
        try:
            return frecuencia_a_midi(self.frecuencia_hz, self.la4)
        except ErrorAltura:
            return None

    @property
    def midi_entero(self) -> Optional[int]:
        midi = self.midi
        return None if midi is None else midi_mas_cercano(midi)

    @property
    def cents(self) -> Optional[float]:
        """Desviación respecto de la nota más cercana, en cents."""
        midi = self.midi
        return None if midi is None else (midi - midi_mas_cercano(midi)) * 100.0

    @property
    def altura(self) -> Optional[Altura]:
        midi = self.midi_entero
        return None if midi is None else Altura.desde_midi(midi)

    @property
    def nombre(self) -> str:
        """Nombre de la nota más cercana ('A♯4'), o '' si el evento no tiene altura."""
        altura = self.altura
        return "" if altura is None else altura.nombre

    @property
    def latencia_s(self) -> Optional[float]:
        if self.t_confirmacion is None:
            return None
        return self.t_confirmacion - self.t

    def con_sesion(self, sesion: int) -> "EventoInterpretacion":
        return replace(self, sesion=sesion)

    def desplazado(self, segundos: float) -> "EventoInterpretacion":
        """El mismo evento con los instantes desplazados (cambio de reloj de referencia)."""
        confirmacion = None if self.t_confirmacion is None else self.t_confirmacion + segundos
        return replace(self, t=self.t + segundos, t_confirmacion=confirmacion)
