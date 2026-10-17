"""
Estado del reproductor de la guía de audio, sin depender de Kivy.

`ReproductorGuia` envuelve el objeto de sonido que devuelve `SoundLoader` (o uno de prueba) y
decide qué puede mostrar la interfaz sin inventar nada:

- La duración sale del sonido (`length`) o del WAV.
- Posición y búsqueda solo se ofrecen si el reproductor las implementa de verdad
  (`admite_busqueda`). El reproductor SDL2 de Kivy en escritorio no lo hace: `get_pos()`
  devuelve siempre 0 y `seek()` no hace nada. En ese caso la posición que se muestra es el
  tiempo transcurrido desde que empezó a sonar (siempre empieza desde el principio), y la
  interfaz la presenta como una barra de solo lectura, sin pausa ni búsqueda.
- El fin natural del audio se detecta con el evento `on_stop` del sonido, si existe, y, como
  respaldo, cuando el tiempo transcurrido supera la duración: la interfaz no se queda
  mostrando «sonando» con el audio ya parado.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

DETENIDO = "detenido"
SONANDO = "sonando"
PAUSADO = "pausado"

# Margen tras la duración nominal antes de dar el audio por terminado (respaldo de on_stop).
MARGEN_FIN_S = 0.25


def admite_busqueda(sonido) -> bool:
    """True si el reproductor implementa `seek` y `get_pos` (no los métodos vacíos de la clase
    base de Kivy)."""
    if sonido is None:
        return False
    try:
        from kivy.core.audio import Sound
    except Exception:  # noqa: BLE001 - sin Kivy (pruebas)
        Sound = None
    if isinstance(Sound, type) and isinstance(sonido, Sound):
        clase = type(sonido)
        if getattr(clase, "get_pos", None) is getattr(Sound, "get_pos", None):
            return False
        # SoundSDL2 (escritorio, Kivy 2.3.1) hereda los dos métodos vacíos: no llega aquí.
        return getattr(clase, "seek", None) is not getattr(Sound, "seek", None)
    return callable(getattr(sonido, "seek", None)) and callable(getattr(sonido, "get_pos", None))


class ReproductorGuia:
    def __init__(self, sonido, duracion_s: Optional[float] = None,
                 reloj: Callable[[], float] = time.monotonic,
                 al_terminar: Optional[Callable[[], None]] = None):
        self.sonido = sonido
        self.reloj = reloj
        self.al_terminar = al_terminar
        self.duracion_s = float(getattr(sonido, "length", 0) or duracion_s or 0.0)
        self.admite_busqueda = admite_busqueda(sonido)
        self.estado = DETENIDO
        self._inicio = None          # instante (reloj) en que empezó a sonar desde _base
        self._base = 0.0             # posición desde la que empezó a sonar
        self._pausa_en = 0.0
        self._ignorar_parada = False
        enlazar = getattr(sonido, "bind", None)
        if callable(enlazar):
            try:
                enlazar(on_stop=self._parada_del_sonido)
            except Exception:  # noqa: BLE001 - un sonido sin eventos usa solo el reloj
                pass

    # ------------------------------------------------------------------ capacidades
    @property
    def admite_pausa(self) -> bool:
        """Pausar exige reanudar en el mismo punto, es decir, búsqueda real."""
        return self.admite_busqueda

    @property
    def sonando(self) -> bool:
        return self.estado == SONANDO

    # ------------------------------------------------------------------ acciones
    def reproducir(self) -> None:
        if self.sonido is None or self.estado == SONANDO:
            return
        base = self._pausa_en if (self.estado == PAUSADO and self.admite_busqueda) else 0.0
        self.sonido.play()
        if base and self.admite_busqueda:
            self.sonido.seek(base)
        self._base = base
        self._inicio = self.reloj()
        self.estado = SONANDO

    def pausar(self) -> None:
        """Con búsqueda: pausa real. Sin ella, equivale a detener (vuelve al principio)."""
        if self.estado != SONANDO:
            return
        if not self.admite_pausa:
            self.detener()
            return
        posicion = self.posicion()
        self._parar_sonido()
        self._pausa_en = posicion
        self.estado = PAUSADO

    def detener(self) -> None:
        if self.sonido is not None:
            self._parar_sonido()
            if self.admite_busqueda:
                try:
                    self.sonido.seek(0)
                except Exception:  # noqa: BLE001
                    pass
        self.estado = DETENIDO
        self._pausa_en = 0.0
        self._inicio = None

    def buscar(self, segundos: float) -> bool:
        """Mueve la reproducción. False (y nada cambia) si el reproductor no lo admite."""
        if not self.admite_busqueda or self.sonido is None:
            return False
        segundos = max(0.0, min(float(segundos), self.duracion_s))
        if self.estado == SONANDO:
            self.sonido.seek(segundos)
            self._base, self._inicio = segundos, self.reloj()
        else:
            self._pausa_en = segundos
            if self.estado == DETENIDO and segundos > 0:
                self.estado = PAUSADO
        return True

    # ------------------------------------------------------------------ consulta
    def posicion(self) -> float:
        if self.estado == PAUSADO:
            return self._pausa_en
        if self.estado != SONANDO or self._inicio is None:
            return 0.0
        if self.admite_busqueda:
            try:
                pos = float(self.sonido.get_pos() or 0.0)
            except Exception:  # noqa: BLE001
                pos = 0.0
            if pos > 0:
                return min(pos, self.duracion_s) if self.duracion_s else pos
        transcurrido = self._base + (self.reloj() - self._inicio)
        return min(transcurrido, self.duracion_s) if self.duracion_s else transcurrido

    def actualizar(self) -> bool:
        """Llamar periódicamente mientras suena. True si el audio acaba de terminar solo."""
        if self.estado != SONANDO:
            return False
        estado_sonido = getattr(self.sonido, "state", "play")
        inicio = self._inicio if self._inicio is not None else self.reloj()
        transcurrido = self._base + (self.reloj() - inicio)
        if estado_sonido == "stop" or (self.duracion_s and transcurrido >= self.duracion_s + MARGEN_FIN_S):
            self._fin_natural()
            return True
        return False

    # ------------------------------------------------------------------ interno
    def _parar_sonido(self):
        self._ignorar_parada = True
        try:
            self.sonido.stop()
        finally:
            self._ignorar_parada = False

    def _parada_del_sonido(self, *args):
        if self._ignorar_parada or self.estado != SONANDO:
            return
        self._fin_natural()

    def _fin_natural(self):
        self.estado = DETENIDO
        self._inicio = None
        self._pausa_en = 0.0
        if self.al_terminar is not None:
            self.al_terminar()
