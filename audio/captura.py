"""
Captura de audio desacoplada del análisis.

El callback del micrófono solo copia el bloque, anota el instante y su número de muestra y
lo deja en una cola acotada (`ColaDeBloques`). Ningún cálculo de altura se hace dentro del
callback: el análisis corre en otro hilo (`audio.escucha.MotorDeEscucha`).

- Si la cola se llena (el análisis no da abasto), se descarta el bloque más antiguo y se
  cuenta: el analizador detecta el hueco por el número de muestra y se reinicia en lugar
  de unir audio discontinuo.
- Los desbordes que informa el sistema de audio (`status` de PortAudio) se cuentan.
- La frecuencia de muestreo es la real del flujo abierto, no una constante.

`CapturaSounddevice` es el adaptador de escritorio (macOS, Windows y Linux) e importa
sounddevice solo al abrir el micrófono. Android necesitará un adaptador propio
(AudioRecord con pyjnius) con la misma interfaz: `abrir`, `cerrar`, `activa`,
`frecuencia_muestreo`, `cola` y `estadisticas`.
"""

from __future__ import annotations

import statistics
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Deque, List, Optional

import numpy as np

TAM_BLOQUE = 1024
CAPACIDAD_COLA_BLOQUES = 64  # ≈ 1,4 s de audio a 48 kHz con bloques de 1024 muestras


class MicrofonoNoDisponibleError(Exception):
    """No se pudo abrir el dispositivo de entrada de audio."""


@dataclass(frozen=True)
class BloqueAudio:
    """Bloque capturado: muestras mono (copia), número de su primera muestra en la captura,
    instante (reloj de la sesión) en que se recibió y estado del sistema de audio."""

    muestras: np.ndarray
    indice_inicial: int
    t_captura: float
    estado: str = ""


class ColaDeBloques:
    """Cola acotada y segura entre hilos. Llena, descarta el bloque más antiguo."""

    def __init__(self, capacidad: int = CAPACIDAD_COLA_BLOQUES):
        if capacidad < 1:
            raise ValueError("La capacidad de la cola debe ser al menos 1")
        self.capacidad = capacidad
        self._bloques: Deque[BloqueAudio] = deque()
        self._cerrojo = threading.Lock()
        self.recibidos = 0
        self.descartados = 0

    def poner(self, bloque: BloqueAudio) -> bool:
        """Añade un bloque. Devuelve False si tuvo que descartar uno antiguo."""
        with self._cerrojo:
            descartado = False
            if len(self._bloques) >= self.capacidad:
                self._bloques.popleft()
                self.descartados += 1
                descartado = True
            self._bloques.append(bloque)
            self.recibidos += 1
            return not descartado

    def sacar_todos(self) -> List[BloqueAudio]:
        with self._cerrojo:
            bloques = list(self._bloques)
            self._bloques.clear()
            return bloques

    def vaciar(self) -> int:
        with self._cerrojo:
            n = len(self._bloques)
            self._bloques.clear()
            return n

    def __len__(self) -> int:
        with self._cerrojo:
            return len(self._bloques)


class EstadisticasCaptura:
    """Coste del callback y continuidad del flujo (para pruebas y mediciones de hardware)."""

    def __init__(self, maximo_muestras: int = 100_000):
        self.tiempos_callback_s: Deque[float] = deque(maxlen=maximo_muestras)
        self.bloques = 0
        self.tramas = 0
        self.desbordes = 0
        self.estados: Deque[str] = deque(maxlen=50)
        self.errores: Deque[str] = deque(maxlen=50)

    def resumen(self) -> dict:
        tiempos = sorted(self.tiempos_callback_s)

        def percentil(p):
            if not tiempos:
                return None
            return round(1000 * tiempos[min(len(tiempos) - 1, int(round(p * (len(tiempos) - 1))))], 4)

        return {
            "bloques": self.bloques,
            "tramas": self.tramas,
            "desbordes": self.desbordes,
            "estados": list(self.estados)[:20],
            "errores": list(self.errores)[:20],
            "callback_mediana_ms": round(1000 * statistics.median(tiempos), 4) if tiempos else None,
            "callback_p99_ms": percentil(0.99),
            "callback_max_ms": round(1000 * tiempos[-1], 4) if tiempos else None,
        }


class CapturaBase:
    """Lógica común de captura: el callback y la cola. Las subclases abren el dispositivo."""

    def __init__(self, cola: Optional[ColaDeBloques] = None,
                 reloj: Callable[[], float] = time.monotonic, tam_bloque: int = TAM_BLOQUE):
        self.cola = cola if cola is not None else ColaDeBloques()
        self.reloj = reloj
        self.tam_bloque = int(tam_bloque)
        self.frecuencia_muestreo: Optional[float] = None
        self.estadisticas = EstadisticasCaptura()
        self._indice = 0
        self._dc_estimado: Optional[float] = None

    def _callback(self, indata, frames, time_info, status) -> None:
        """Callback del flujo de entrada: copiar, anotar y encolar. Nada más."""
        inicio = time.perf_counter()
        t = self.reloj()
        datos = indata[:, 0] if getattr(indata, "ndim", 1) == 2 else indata
        copia = np.array(datos, dtype=np.float32, copy=True)
        if len(copia):
            media = float(np.mean(copia))
            if self._dc_estimado is None:
                self._dc_estimado = media
            else:
                alpha = min(0.05, len(copia) / (self.frecuencia_muestreo or 48000.0) * 2.0)
                self._dc_estimado = (1.0 - alpha) * self._dc_estimado + alpha * media
            copia -= np.float32(self._dc_estimado)
        estado = str(status) if status else ""
        if estado:
            self.estadisticas.desbordes += 1
            self.estadisticas.estados.append(estado)
        self.cola.poner(BloqueAudio(copia, self._indice, t, estado))
        self._indice += len(copia)
        self.estadisticas.bloques += 1
        self.estadisticas.tramas += len(copia)
        self.estadisticas.tiempos_callback_s.append(time.perf_counter() - inicio)

    def reiniciar_indices(self) -> None:
        self._indice = 0
        self._dc_estimado = None

    def abrir(self) -> None:  # pragma: no cover - lo implementan las subclases
        raise NotImplementedError

    def cerrar(self) -> None:  # pragma: no cover
        raise NotImplementedError

    @property
    def activa(self) -> bool:  # pragma: no cover
        return False


class CapturaManual(CapturaBase):
    """Captura sin dispositivo: los bloques llegan llamando a `_callback` (pruebas,
    simulaciones, archivos)."""

    def __init__(self, frecuencia_muestreo: float, **kwargs):
        super().__init__(**kwargs)
        self.frecuencia_muestreo = float(frecuencia_muestreo)
        self._abierta = False

    def abrir(self) -> None:
        self._abierta = True

    def cerrar(self) -> None:
        self._abierta = False

    @property
    def activa(self) -> bool:
        return self._abierta


class CapturaSounddevice(CapturaBase):
    """Micrófono de escritorio con sounddevice (PortAudio)."""

    def __init__(self, dispositivo=None, frecuencia_muestreo: Optional[float] = None,
                 modulo_sounddevice=None, **kwargs):
        super().__init__(**kwargs)
        self.dispositivo = dispositivo
        self.frecuencia_solicitada = frecuencia_muestreo
        self._sd = modulo_sounddevice
        self._flujo = None
        self.nombre_dispositivo: Optional[str] = None

    def _modulo(self):
        if self._sd is None:
            import sounddevice  # importación diferida: solo al abrir el micrófono
            self._sd = sounddevice
        return self._sd

    def abrir(self) -> None:
        try:
            sd = self._modulo()
            info = sd.query_devices(self.dispositivo, "input")
            frecuencia = float(self.frecuencia_solicitada or info["default_samplerate"])
            self.nombre_dispositivo = info.get("name") if hasattr(info, "get") else None
            self.reiniciar_indices()
            flujo = sd.InputStream(device=self.dispositivo, channels=1, samplerate=frecuencia,
                                   blocksize=self.tam_bloque, dtype="float32",
                                   callback=self._callback)
            flujo.start()
        except Exception as error:  # noqa: BLE001 - cualquier fallo del sistema de audio
            self._flujo = None
            self.estadisticas.errores.append(f"{type(error).__name__}: {error}")
            raise MicrofonoNoDisponibleError(f"No se pudo abrir el micrófono ({error}).") from error
        self._flujo = flujo
        self.frecuencia_muestreo = float(getattr(flujo, "samplerate", frecuencia) or frecuencia)

    def cerrar(self) -> None:
        flujo, self._flujo = self._flujo, None
        if flujo is None:
            return
        for metodo in ("stop", "close"):
            try:
                getattr(flujo, metodo)()
            except Exception as error:  # noqa: BLE001 - el dispositivo puede haber desaparecido
                self.estadisticas.errores.append(f"{metodo}: {type(error).__name__}: {error}")

    @property
    def activa(self) -> bool:
        flujo = self._flujo
        if flujo is None:
            return False
        return bool(getattr(flujo, "active", True))


def dispositivos_de_entrada(modulo_sounddevice=None) -> List[dict]:
    """Dispositivos con canales de entrada: índice, nombre, frecuencia y si es el
    predeterminado. Lista vacía si el sistema de audio no está disponible."""
    try:
        sd = modulo_sounddevice
        if sd is None:
            import sounddevice as sd  # noqa: F811
        dispositivos = sd.query_devices()
        predeterminado = sd.default.device[0] if hasattr(sd, "default") else None
    except Exception:  # noqa: BLE001
        return []
    import re
    descartes = ("playback", "speaker", "altavoz", "sink", "output", "salida", "monitor", "loopback")
    resultado = []
    for indice, info in enumerate(dispositivos):
        if info.get("max_input_channels", 0) <= 0:
            continue
        nombre = info.get("name", f"Entrada {indice}")
        nombre_lower = nombre.lower()
        if any(palabra in nombre_lower for palabra in descartes):
            continue
        if re.search(r"\[.*\]", nombre):
            continue
        resultado.append({"indice": indice, "nombre": nombre,
                          "frecuencia": info.get("default_samplerate"),
                          "predeterminado": indice == predeterminado})
    return resultado
