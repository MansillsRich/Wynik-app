"""
Controlador de la práctica: une la escucha (`audio.escucha`), la sesión (`nucleo.sesion`) y
la secuencia de inicio, sin depender de Kivy.

Secuencia al pulsar «Empezar»
1. Si sonaba la guía, la interfaz la detiene antes (la guía y la escucha nunca coinciden).
2. Se abre el micrófono con un número de sesión nuevo.
3. Calibración (opcional, 1 s): se mide el ruido de fondo; el usuario no toca.
4. Cuenta previa visual (opcional, sin sonido para que el micrófono no la capte).
5. La sesión empieza: su instante cero es el final de la cuenta.

La interfaz llama a `actualizar()` periódicamente (en el hilo de la interfaz). Los eventos
del hilo de análisis llegan por `encolar_evento` a una cola segura entre hilos y solo se
procesan si pertenecen a la sesión vigente. Los que llegan durante la cuenta se retienen y
se entregan a la sesión cuando empieza: quien se adelanta un poco al final de la cuenta
(dentro de la tolerancia) no pierde la primera nota por que el detector la confirme antes de
que la cuenta termine; la sesión descarta los que empezaron antes de t0 − tolerancia.
"""

from __future__ import annotations

import math
import queue
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence

from audio.captura import CapturaBase, CapturaSounddevice, MicrofonoNoDisponibleError
from audio.escucha import MotorDeEscucha
from audio.senal import PerfilDeRuido
from nucleo.eventos import EventoInterpretacion, TipoEvento
from nucleo.instrumentos import PIANO, PerfilInstrumento
from nucleo.sesion import (Cambio, ConfiguracionSesion, ModoPractica, NotaEsperada,
                           SesionDePractica, notas_esperadas)

DURACION_CALIBRACION_S = 1.0
MAX_EVENTOS_RETENIDOS = 64  # eventos de la cuenta previa que se guardan para la sesión

LISTA = "lista"
CALIBRANDO = "calibrando"
CUENTA = "cuenta"
ESCUCHANDO = "escuchando"
PAUSADA = "pausada"
TERMINADA = "terminada"


@dataclass(frozen=True)
class OpcionesPractica:
    perfil: PerfilInstrumento = PIANO
    la4: float = 440.0
    modo: ModoPractica = ModoPractica.SEGUIR_TEMPO
    factor_tempo: float = 1.0
    tolerancia_s: float = 0.150
    bpm_por_defecto: float = 120.0
    calibrar: bool = True
    pulsos_cuenta: int = 3
    segundos_por_pulso: float = 0.5
    dispositivo: object = None


@dataclass
class EventoProcesado:
    """Un evento de la sesión vigente y los cambios que produjo."""

    evento: EventoInterpretacion
    cambios: List[Cambio] = field(default_factory=list)


@dataclass
class Actualizacion:
    estado: str
    estado_cambiado: bool = False
    eventos: List[EventoProcesado] = field(default_factory=list)
    cambios: List[Cambio] = field(default_factory=list)
    indice_actual: int = 0
    indice_cambiado: bool = False
    cuenta_restante: int = 0
    terminada: bool = False


class ControladorPractica:
    """Estado de una práctica (una partitura con unas opciones)."""

    def __init__(self, notas: Sequence[dict], opciones: OpcionesPractica = OpcionesPractica(),
                 fabrica_captura: Optional[Callable[[], CapturaBase]] = None,
                 reloj: Callable[[], float] = time.monotonic, usar_hilo: bool = True,
                 ruido: Optional[PerfilDeRuido] = None, primera_sesion: int = 1):
        self.notas = list(notas)
        self.opciones = opciones
        self.fabrica_captura = fabrica_captura or (lambda: CapturaSounddevice(dispositivo=opciones.dispositivo))
        self.reloj = reloj
        self.usar_hilo = usar_hilo
        self.ruido = ruido
        self.estado = LISTA
        self.sesion: Optional[SesionDePractica] = None
        self.motor: Optional[MotorDeEscucha] = None
        self.esperadas: List[NotaEsperada] = notas_esperadas(
            self.notas, opciones.bpm_por_defecto, opciones.factor_tempo)
        self._numero_sesion = primera_sesion - 1
        self._eventos: "queue.SimpleQueue[EventoInterpretacion]" = queue.SimpleQueue()
        self._retenidos: List[EventoInterpretacion] = []
        self._fin_cuenta: Optional[float] = None
        self._pulsos_en_cuenta = 0
        self._inicio_pausa: Optional[float] = None
        self._indice_mostrado = 0
        self.ultimo_evento: Optional[EventoInterpretacion] = None

    # ------------------------------------------------------------------------------------
    @property
    def escuchando(self) -> bool:
        return self.motor is not None and self.motor.activo

    @property
    def indice_actual(self) -> int:
        return self.sesion.indice_actual if self.sesion is not None else 0

    @property
    def numero_sesion(self) -> int:
        return self._numero_sesion

    def iniciar(self) -> None:
        """Abre el micrófono y empieza la secuencia (calibración, cuenta, sesión).
        Lanza MicrofonoNoDisponibleError si no hay micrófono."""
        self.detener()
        self._numero_sesion += 1
        self.sesion = SesionDePractica(
            self.esperadas,
            ConfiguracionSesion(modo=self.opciones.modo, tolerancia_s=self.opciones.tolerancia_s,
                                la4=self.opciones.la4),
            sesion=self._numero_sesion)
        self._indice_mostrado = 0
        self._vaciar_eventos()
        motor = MotorDeEscucha(self.opciones.perfil, self.opciones.la4, self.ruido,
                               captura=self.fabrica_captura(), al_evento=self.encolar_evento,
                               sesion=self._numero_sesion, usar_hilo=self.usar_hilo)
        motor.iniciar()  # puede lanzar MicrofonoNoDisponibleError
        self.motor = motor
        if self.opciones.calibrar and self.ruido is None:
            motor.calibrar(DURACION_CALIBRACION_S)
            self.estado = CALIBRANDO
        else:
            self._empezar_cuenta()

    def _empezar_cuenta(self, ahora: Optional[float] = None) -> None:
        """`ahora`: instante de la actualización que la empieza (el mismo con el que se calcula
        lo que falta; con el reloj real, otra lectura sería unos microsegundos posterior y la
        cuenta mostraría un pulso de más)."""
        ahora = self.reloj() if ahora is None else ahora
        pulsos = max(0, int(self.opciones.pulsos_cuenta))
        if pulsos == 0:
            self._empezar_sesion(ahora)
            return
        self._pulsos_en_cuenta = pulsos
        self._fin_cuenta = ahora + pulsos * self.opciones.segundos_por_pulso
        self.estado = CUENTA

    def _empezar_sesion(self, t0: float) -> None:
        self._fin_cuenta = None
        self.sesion.iniciar(t0)
        self.estado = ESCUCHANDO

    def detener(self) -> None:
        """Cierra el micrófono. La sesión conserva sus resultados pero no admite más eventos."""
        if self.motor is not None:
            self.motor.detener()
            self.motor = None
        if self.sesion is not None:
            self.sesion.detener()
        self._vaciar_eventos()
        if self.estado in (CALIBRANDO, CUENTA, ESCUCHANDO, PAUSADA):
            self.estado = LISTA
        self._fin_cuenta = None
        self._inicio_pausa = None

    def pausar(self) -> None:
        if self.estado != ESCUCHANDO:
            return
        self._inicio_pausa = self.reloj()
        if self.motor is not None:
            self.motor.detener()
            self.motor = None
        self._vaciar_eventos()
        self.estado = PAUSADA

    def reanudar(self) -> None:
        """Vuelve a abrir el micrófono (otra sesión de captura). Con tempo, la partitura se
        desplaza lo que duró la pausa más una cuenta corta."""
        if self.estado != PAUSADA or self.sesion is None:
            return
        self._numero_sesion += 1
        self.sesion.sesion = self._numero_sesion
        motor = MotorDeEscucha(self.opciones.perfil, self.opciones.la4, self.ruido,
                               captura=self.fabrica_captura(), al_evento=self.encolar_evento,
                               sesion=self._numero_sesion, usar_hilo=self.usar_hilo)
        motor.iniciar()
        self.motor = motor
        ahora = self.reloj()
        self._pulsos_en_cuenta = max(1, int(self.opciones.pulsos_cuenta))
        cuenta = self._pulsos_en_cuenta * self.opciones.segundos_por_pulso
        if self.sesion.t0 is not None and self._inicio_pausa is not None:
            self.sesion.t0 += (ahora - self._inicio_pausa) + cuenta
        self.sesion.detenida = False
        self._inicio_pausa = None
        self._fin_cuenta = ahora + cuenta
        self.estado = CUENTA

    # ------------------------------------------------------------------------------------
    def encolar_evento(self, evento: EventoInterpretacion) -> None:
        """Llamado desde el hilo de análisis."""
        self._eventos.put(evento)

    def _vaciar_eventos(self) -> None:
        self._retenidos = []
        while True:
            try:
                self._eventos.get_nowait()
            except queue.Empty:
                return

    def actualizar(self) -> Actualizacion:
        """Procesa los eventos pendientes y el paso del tiempo (hilo de la interfaz)."""
        estado_anterior = self.estado
        indice_anterior = self._indice_mostrado
        resultado = Actualizacion(estado=self.estado)
        ahora = self.reloj()
        if self.estado == CALIBRANDO and self.motor is not None and not self.motor.calibrando:
            self.ruido = self.motor.ruido
            self._empezar_cuenta(ahora)
        if self.estado == CUENTA and self._fin_cuenta is not None and ahora >= self._fin_cuenta:
            if self.sesion.t0 is None:
                self._empezar_sesion(self._fin_cuenta)
            else:
                self._fin_cuenta = None
                self.estado = ESCUCHANDO
        if self.estado == ESCUCHANDO and self._retenidos:
            retenidos, self._retenidos = self._retenidos, []
            for evento in retenidos:
                cambios = self.sesion.procesar(evento)
                resultado.eventos.append(EventoProcesado(evento, cambios))
                resultado.cambios.extend(cambios)
        while True:
            try:
                evento = self._eventos.get_nowait()
            except queue.Empty:
                break
            if self.sesion is None or (evento.sesion and evento.sesion != self.sesion.sesion):
                continue  # evento de una sesión de captura anterior
            self.ultimo_evento = evento
            if self.estado == CUENTA:
                # Se entrega a la sesión cuando empiece (ver el docstring del módulo).
                self._retenidos = (self._retenidos + [evento])[-MAX_EVENTOS_RETENIDOS:]
                continue
            cambios = self.sesion.procesar(evento) if self.estado == ESCUCHANDO else []
            resultado.eventos.append(EventoProcesado(evento, cambios))
            resultado.cambios.extend(cambios)
        if self.estado == ESCUCHANDO and self.sesion is not None:
            resultado.cambios.extend(self.sesion.actualizar(ahora))
            if self.sesion.terminada:
                self.estado = TERMINADA
                resultado.terminada = True
                if self.motor is not None:
                    self.motor.detener()
                    self.motor = None
        self._indice_mostrado = self.indice_actual
        resultado.estado = self.estado
        resultado.estado_cambiado = self.estado != estado_anterior
        resultado.indice_actual = self._indice_mostrado
        resultado.indice_cambiado = self._indice_mostrado != indice_anterior
        if self.estado == CUENTA and self._fin_cuenta is not None:
            restante = self._fin_cuenta - ahora
            pulsos = math.ceil(restante / self.opciones.segundos_por_pulso - 1e-6)
            resultado.cuenta_restante = min(max(1, int(pulsos)), max(1, self._pulsos_en_cuenta))
        return resultado

    def resumen(self) -> dict:
        datos = self.sesion.resumen() if self.sesion is not None else {}
        if self.motor is not None:
            datos["captura"] = self.motor.estadisticas()
        return datos


__all__ = ["CALIBRANDO", "CUENTA", "ESCUCHANDO", "LISTA", "PAUSADA", "TERMINADA",
           "Actualizacion", "ControladorPractica", "EventoProcesado", "MicrofonoNoDisponibleError",
           "OpcionesPractica", "TipoEvento"]
