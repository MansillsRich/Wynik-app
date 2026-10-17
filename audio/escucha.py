"""
Motor de escucha: captura + cola acotada + analizador en un hilo independiente.

    micrófono ─► callback (copia y encola) ─► ColaDeBloques ─► hilo de análisis
                                                                 │  Analizador
                                                                 ▼
                                               al_evento(EventoInterpretacion)

- `iniciar()` abre la captura y arranca el hilo; `detener()` cierra la captura, para el
  hilo y descarta los bloques pendientes: nada de una sesión cerrada llega a la siguiente.
- Cada motor tiene un número de `sesion` con el que se marcan sus eventos.
- `calibrar(segundos)` mide el ruido de fondo con la misma captura antes de analizar.
- `procesar_pendientes()` es el trabajo de una vuelta del hilo; las pruebas y las
  simulaciones lo llaman directamente para ser deterministas (`usar_hilo=False`).

Un error dentro del análisis no detiene la captura ni bloquea la interfaz: se guarda en
`ultimo_error` y se cuenta.
"""

from __future__ import annotations

import threading
import time
import traceback
from typing import Callable, List, Optional

import numpy as np

from nucleo.eventos import EventoInterpretacion
from nucleo.instrumentos import PerfilInstrumento
from nucleo.musica import LA4_HZ

from .analizador import Analizador
from .captura import CapturaBase, CapturaSounddevice
from .senal import PerfilDeRuido, calibrar

INTERVALO_HILO_S = 0.005


class MotorDeEscucha:
    """Escucha en segundo plano y entrega eventos de interpretación."""

    def __init__(self, perfil: PerfilInstrumento, la4: float = LA4_HZ,
                 ruido: Optional[PerfilDeRuido] = None,
                 captura: Optional[CapturaBase] = None,
                 al_evento: Optional[Callable[[EventoInterpretacion], None]] = None,
                 al_calibrar: Optional[Callable[[PerfilDeRuido], None]] = None,
                 sesion: int = 1, usar_hilo: bool = True, dispositivo=None):
        self.perfil = perfil
        self.la4 = float(la4)
        self.ruido = ruido
        self.captura = captura if captura is not None else CapturaSounddevice(dispositivo=dispositivo)
        self.al_evento = al_evento
        self.al_calibrar = al_calibrar
        self.sesion = int(sesion)
        self.usar_hilo = usar_hilo
        self.analizador: Optional[Analizador] = None
        self.ultimo_error: Optional[str] = None
        self.errores = 0
        self.segundos_analizados = 0.0
        self._activo = False
        self._detener = threading.Event()
        self._hilo: Optional[threading.Thread] = None
        self._cerrojo = threading.Lock()
        self._calibracion: Optional[list] = None
        self._muestras_calibracion = 0

    # ------------------------------------------------------------------------------------
    @property
    def activo(self) -> bool:
        return self._activo

    @property
    def calibrando(self) -> bool:
        return self._calibracion is not None

    def preparar(self, frecuencia_muestreo: float) -> Analizador:
        """Crea el analizador para una frecuencia de muestreo (sin abrir dispositivos)."""
        self.analizador = Analizador(frecuencia_muestreo, self.perfil, self.ruido, self.la4,
                                     sesion=self.sesion)
        return self.analizador

    def iniciar(self) -> None:
        """Abre el micrófono y empieza a analizar. Lanza MicrofonoNoDisponibleError."""
        self.captura.cola.vaciar()
        self.captura.abrir()
        self.preparar(self.captura.frecuencia_muestreo)
        self._activo = True
        self._detener.clear()
        if self.usar_hilo:
            self._hilo = threading.Thread(target=self._bucle, name=f"wynik-analisis-{self.sesion}",
                                          daemon=True)
            self._hilo.start()

    def detener(self) -> None:
        """Cierra la captura y el hilo. Los bloques pendientes se descartan."""
        self._activo = False
        self._detener.set()
        self.captura.cerrar()
        hilo, self._hilo = self._hilo, None
        if hilo is not None and hilo is not threading.current_thread():
            hilo.join(timeout=2.0)
        self.captura.cola.vaciar()
        self._calibracion = None

    def calibrar(self, segundos: float) -> None:
        """Las próximas `segundos` de audio se usan para medir el fondo, no para analizar."""
        with self._cerrojo:
            self._calibracion = []
            self._muestras_calibracion = int(round(segundos * (self.captura.frecuencia_muestreo or 48000)))

    # ------------------------------------------------------------------------------------
    def procesar_pendientes(self) -> List[EventoInterpretacion]:
        """Analiza los bloques encolados y entrega sus eventos. Devuelve los eventos."""
        bloques = self.captura.cola.sacar_todos()
        if not bloques:
            return []
        if self.analizador is None:
            self.preparar(self.captura.frecuencia_muestreo or 48000)
        eventos: List[EventoInterpretacion] = []
        for bloque in bloques:
            if self._calibracion is not None:
                self._acumular_calibracion(bloque)
                # El analizador sigue el número de muestra aunque no analice.
                self.analizador.reiniciar(bloque.indice_inicial + len(bloque.muestras))
                continue
            try:
                eventos.extend(self.analizador.alimentar(bloque.muestras, bloque.indice_inicial,
                                                         bloque.t_captura))
            except Exception as error:  # noqa: BLE001 - un fallo no debe parar la captura
                self.errores += 1
                self.ultimo_error = f"{type(error).__name__}: {error}"
                self.analizador.reiniciar(bloque.indice_inicial + len(bloque.muestras))
                traceback.print_exc()
            self.segundos_analizados += len(bloque.muestras) / self.analizador.frecuencia_muestreo
        if self.al_evento is not None:
            for evento in eventos:
                self.al_evento(evento)
        return eventos

    def _acumular_calibracion(self, bloque) -> None:
        with self._cerrojo:
            if self._calibracion is None:
                return
            self._calibracion.append(np.asarray(bloque.muestras, dtype=np.float64))
            if sum(len(b) for b in self._calibracion) < self._muestras_calibracion:
                return
            muestras = np.concatenate(self._calibracion)
        try:
            perfil = calibrar(muestras, self.analizador.frecuencia_muestreo, self.analizador.estimador)
        except Exception as error:  # noqa: BLE001
            self.errores += 1
            self.ultimo_error = f"Calibración: {type(error).__name__}: {error}"
            perfil = None
        if perfil is not None:
            self.ruido = perfil
            self.analizador.configurar_ruido(perfil)
        # La calibración termina cuando el perfil ya está asignado: otro hilo que vea
        # `calibrando == False` encuentra `ruido` actualizado.
        with self._cerrojo:
            self._calibracion = None
        if perfil is not None and self.al_calibrar is not None:
            self.al_calibrar(perfil)

    def _bucle(self) -> None:
        while not self._detener.is_set():
            inicio = time.perf_counter()
            self.procesar_pendientes()
            if time.perf_counter() - inicio < INTERVALO_HILO_S:
                self._detener.wait(INTERVALO_HILO_S)

    def estadisticas(self) -> dict:
        resumen = self.captura.estadisticas.resumen()
        resumen.update({
            "frecuencia_muestreo": self.captura.frecuencia_muestreo,
            "bloques_descartados": self.captura.cola.descartados,
            "discontinuidades": self.analizador.discontinuidades if self.analizador else 0,
            "segundos_analizados": round(self.segundos_analizados, 3),
            "segundos_de_calculo": round(self.analizador.segundos_de_calculo, 4) if self.analizador else 0.0,
            "errores_analisis": self.errores,
            "ultimo_error": self.ultimo_error,
            "ruido": self.ruido.como_diccionario() if self.ruido else None,
        })
        if self.segundos_analizados:
            resumen["carga_analisis"] = round(resumen["segundos_de_calculo"] / self.segundos_analizados, 4)
        return resumen
