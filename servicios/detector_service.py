"""
Servicio de detección de notas: fachada de compatibilidad sobre `audio.escucha`.

La interfaz anterior (`DetectorDeNotas(callback_nota)`, `iniciar`, `detener`,
`frecuencia_a_nota`) se conserva, pero el trabajo ya no se hace dentro del callback del
micrófono:

- `_procesar_bloque(indata, frames, time_info, status)` es el callback de sounddevice: copia
  el bloque y lo encola (`audio.captura`).
- `procesar_pendientes()` analiza lo encolado (YIN, segmentación en eventos). Con el
  micrófono abierto lo ejecuta un hilo propio; las pruebas lo llaman directamente.

`callback_nota(nombre, frecuencia)` recibe cada ataque confirmado (evento NOTA), también las
notas repetidas. `callback_evento(evento)` recibe además los diagnósticos: señal débil,
baja confianza, altura inestable y fuera de rango.

El perfil por defecto es el de piano (A0–C8), el rango más amplio entre los instrumentos
soportados; la aplicación pasa el perfil del instrumento elegido.
"""

from typing import Callable, Optional

from audio.captura import (
    TAM_BLOQUE,
    CapturaSounddevice,
    MicrofonoNoDisponibleError,
)
from audio.escucha import MotorDeEscucha
from audio.senal import PerfilDeRuido
from nucleo.eventos import EventoInterpretacion, TipoEvento
from nucleo.instrumentos import PIANO, PerfilInstrumento
from nucleo.musica import LA4_HZ, Altura, ErrorAltura, frecuencia_a_midi, midi_mas_cercano

SAMPLE_RATE = 22050  # frecuencia de la guía de audio (la captura usa la del dispositivo)
BLOCK_SIZE = TAM_BLOQUE
# El umbral RMS fijo de 0,15 (≈ −16,5 dBFS) se sustituyó por niveles relativos al ruido de
# fondo (audio.senal.PerfilDeRuido); se conserva el nombre para el código anterior.
UMBRAL_RMS_SILENCIO = None

__all__ = ["BLOCK_SIZE", "SAMPLE_RATE", "UMBRAL_RMS_SILENCIO", "DetectorDeNotas",
           "MicrofonoNoDisponibleError", "frecuencia_a_nota"]


def frecuencia_a_nota(frecuencia_hz: Optional[float], la4: float = LA4_HZ) -> Optional[str]:
    """Nota más cercana a una frecuencia en notación científica con sostenidos ('A♯4')."""
    try:
        midi = frecuencia_a_midi(frecuencia_hz, la4)
    except (ErrorAltura, TypeError):
        return None
    return Altura.desde_midi(midi_mas_cercano(midi)).nombre


def _ruido_desde_umbral_rms(umbral_rms: Optional[float]) -> Optional[PerfilDeRuido]:
    import math
    if not umbral_rms or umbral_rms <= 0:
        return None
    minimo = 20.0 * math.log10(umbral_rms)
    return PerfilDeRuido.por_defecto(nivel_silencio_dbfs=minimo - 15.0, nivel_minimo_dbfs=minimo)


class DetectorDeNotas:
    """Escucha el micrófono y notifica cada nota tocada (incluidas las repetidas)."""

    def __init__(self, callback_nota: Callable[[str, float], None], device=None,
                 umbral_rms: Optional[float] = None, perfil: PerfilInstrumento = PIANO,
                 la4: float = LA4_HZ,
                 callback_evento: Optional[Callable[[EventoInterpretacion], None]] = None,
                 ruido: Optional[PerfilDeRuido] = None):
        self.callback_nota = callback_nota
        self.callback_evento = callback_evento
        self.device = device
        self.samplerate: float = 48000
        self.perfil = perfil
        self.la4 = la4
        self.ruido = ruido or _ruido_desde_umbral_rms(umbral_rms)
        self._motor = MotorDeEscucha(perfil, la4, self.ruido,
                                     captura=CapturaSounddevice(dispositivo=device),
                                     al_evento=self._entregar, usar_hilo=True)
        self.stream = None

    @property
    def motor(self) -> MotorDeEscucha:
        return self._motor

    def _entregar(self, evento: EventoInterpretacion) -> None:
        if self.callback_evento is not None:
            self.callback_evento(evento)
        if evento.tipo is TipoEvento.NOTA:
            self.callback_nota(evento.nombre, evento.frecuencia_hz)

    def _procesar_bloque(self, indata, frames, time_info, status):
        """Callback del micrófono: solo copia y encola el bloque."""
        self._motor.captura._callback(indata, frames, time_info, status)

    def procesar_pendientes(self):
        """Analiza los bloques encolados (lo hace el hilo de análisis con el micrófono abierto)."""
        analizador = self._motor.analizador
        if analizador is None or analizador.frecuencia_muestreo != float(self.samplerate):
            self._motor.captura.frecuencia_muestreo = float(self.samplerate)
            self._motor.preparar(self.samplerate)
        return self._motor.procesar_pendientes()

    def iniciar(self):
        """Abre el micrófono y empieza a analizar en segundo plano."""
        self._motor.iniciar()
        self.samplerate = self._motor.captura.frecuencia_muestreo
        self.stream = self._motor.captura

    def detener(self):
        """Detiene la captura y el análisis."""
        self._motor.detener()
        self.stream = None
