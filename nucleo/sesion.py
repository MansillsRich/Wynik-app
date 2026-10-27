"""
Sesión de práctica: compara los eventos de interpretación con la partitura en el tiempo.

Independiente de Kivy y del audio: recibe `EventoInterpretacion` (de `audio.analizador` o de
una prueba) y la línea de práctica de la partitura, y decide el estado de cada nota.

Modos
- SEGUIR_TEMPO: la partitura avanza sola con el tempo. Cada nota tiene una ventana de
  ±`tolerancia_s` (150 ms) alrededor de su inicio esperado.
- ESPERAR_NOTA: la partitura espera en cada nota hasta que se toca la correcta.

Alineación (C8)
- Antes del primer ataque, la sesión no sabe cuándo empezará el usuario: la primera nota
  admite ataques hasta `alineacion_inicial_max_s` (500 ms) tarde. El primer ataque fija el
  desfase entre el reloj y la partitura (por ejemplo, 200 ms de tiempo de reacción) y todas
  las ventanas siguientes se desplazan con él; las tolerancias no se amplían.
- Después, si los tres últimos ataques asignados llegan desplazados en el mismo sentido (el
  intérprete va algo más lento o más rápido que la partitura), el desfase se corrige con la
  media de esos tres errores. Las desviaciones alternas (imprecisión de cada nota) no lo
  mueven: una nota que estaba dentro de la tolerancia no sale de su ventana por las notas
  vecinas. Con negras a 120 por minuto sigue desviaciones de tempo de hasta ≈ 7 %.

Latencia de entrega (DET-01)
- Un evento lleva el instante del ATAQUE (`t`, reloj de captura), pero llega a la sesión más
  tarde: el detector necesita audio posterior para confirmarlo (hasta `confirmacion_max_s`
  más la trama), el hilo de análisis lo procesa y la interfaz lo recoge en su siguiente tick.
  Cerrar la ventana de una nota con el reloj actual en `esperado + tolerancia` descartaba como
  «no se tocó» ataques correctos y dentro de la tolerancia que aún iban de camino. La
  tolerancia se aplica al instante del ataque y no cambia; la ventana solo se cierra cuando
  ya no puede llegar ningún evento cuyo ataque cayera dentro (`margen_cierre_s`).
- La alineación (C8) solo la fijan y la corrigen los aciertos (DET-02): un sonido espurio, o
  una nota equivocada, no dice cuándo empezó el intérprete.

Política de estados (C9)
- Un acierto (nota y octava correctas, afinada o desafinada) es definitivo: ningún evento
  posterior lo cambia.
- Un error de altura es provisional mientras la ventana de la nota está abierta: si el
  usuario se corrige dentro de la ventana, la nota pasa a acierto (y se cuenta el intento
  fallido). Al cerrarse la ventana, el error es definitivo.
- Los eventos sin altura fiable (señal débil, baja confianza, inestable) y los de fuera de
  rango nunca cambian un estado ni hacen avanzar la partitura: solo explican por qué una
  nota quedó sin tocar (OMITIDA, SENAL_INSUFICIENTE, BAJA_CONFIANZA o FUERA_DE_RANGO).
- Un evento se asigna a una sola nota. Los eventos de otra sesión de captura (`sesion`
  distinto) o anteriores al inicio se descartan (C10).

Acordes (DET-03): el detector es monofónico y ante varias notas a la vez devuelve la fundamental
común, un subarmónico o una altura sin sentido, así que no puede decir si un acorde está bien o
mal. Un acorde queda en `SIN_EVALUAR`: ni acierto ni fallo (no cuenta en la precisión) y sin
sonido que lo puntúe. Con tempo se cierra con su ventana y los eventos que caen más cerca de él
que de otra nota se descartan, para que su rasgueo no puntúe a las notas vecinas. En «esperar
cada nota» el acorde avanza con el primer ataque que se oye (de cualquier altura) y, durante
`refractario_acorde_s`, se ignoran los eventos que le siguen: así un solo rasgueo no avanza dos
veces. Las notas del acorde se muestran como referencia visual.

Dudas del detector (DET-05): un evento con `confianza` por debajo de `confianza_min_error` que
no coincide con la nota esperada no se declara «nota equivocada»: se anota como detección poco
fiable. Un acierto cuenta siempre, sea cual sea su confianza: el umbral nunca quita notas
válidas, solo evita acusar de error a un sonido dudoso (voz, ruido con altura).

Solo usa la biblioteca estándar.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .eventos import EventoInterpretacion, TipoEvento
from .musica import LA4_HZ, EstadoAltura, ResultadoAltura, comparar_frecuencia


# Cuánto después de `esperado + tolerancia` se cierra la ventana de una nota. Componentes de la
# latencia máxima de entrega de un ataque: confirmación (`confirmacion_max_s` = 0,15 s) + trama
# del estimador (≈ 0,04 s en guitarra, hasta ≈ 0,08 s en los graves del piano) + hilo de análisis y tick de la interfaz (≈ 0,1 s). Es un
# criterio de diseño, no una medida con micrófono real; `tests/test_22_sincronizacion.py`
# comprueba que cubre el peor caso del detector. Se puede ajustar por sesión.
MARGEN_CIERRE_S = 0.35


class ModoPractica(str, Enum):
    SEGUIR_TEMPO = "seguir_tempo"
    ESPERAR_NOTA = "esperar_nota"


class EstadoNota(str, Enum):
    PENDIENTE = "pendiente"
    CORRECTA = "correcta"                    # nota y octava correctas, afinada (≤ 25 cents)
    DESAFINADA = "desafinada"                # nota y octava correctas, 25–50 cents
    NOTA_INCORRECTA = "nota_incorrecta"
    OCTAVA_INCORRECTA = "octava_incorrecta"
    OMITIDA = "omitida"                      # ningún ataque en la ventana
    SENAL_INSUFICIENTE = "senal_insuficiente"  # solo ataques por debajo del nivel mínimo
    BAJA_CONFIANZA = "baja_confianza"        # solo ataques sin altura fiable
    FUERA_DE_RANGO = "fuera_de_rango"        # altura estable fuera del rango del instrumento
    SIN_EVALUAR = "sin_evaluar"              # acorde: el detector monofónico no puede evaluarlo

    @property
    def es_acierto(self) -> bool:
        return self in (EstadoNota.CORRECTA, EstadoNota.DESAFINADA)

    @property
    def es_error(self) -> bool:
        return self not in (EstadoNota.PENDIENTE, EstadoNota.SIN_EVALUAR) and not self.es_acierto


_DE_ALTURA = {
    EstadoAltura.CORRECTA: EstadoNota.CORRECTA,
    EstadoAltura.DESAFINADA: EstadoNota.DESAFINADA,
    EstadoAltura.NOTA_INCORRECTA: EstadoNota.NOTA_INCORRECTA,
    EstadoAltura.OCTAVA_INCORRECTA: EstadoNota.OCTAVA_INCORRECTA,
}
# Prioridad para explicar una nota sin ataque válido, de mayor a menor.
_DIAGNOSTICOS = (
    (TipoEvento.FUERA_DE_RANGO, EstadoNota.FUERA_DE_RANGO),
    (TipoEvento.BAJA_CONFIANZA, EstadoNota.BAJA_CONFIANZA),
    (TipoEvento.INESTABLE, EstadoNota.BAJA_CONFIANZA),
    (TipoEvento.SENAL_DEBIL, EstadoNota.SENAL_INSUFICIENTE),
)


@dataclass(frozen=True)
class NotaEsperada:
    """Una nota (o ataque) de la línea de práctica, con tiempos en segundos de partitura."""

    indice: int
    inicio_s: float
    duracion_s: float
    midi: float
    alturas_midi: Tuple[float, ...] = ()
    nombre: str = ""

    @property
    def es_acorde(self) -> bool:
        return len(self.alturas_midi) > 1


@dataclass
class ResultadoNota:
    """Estado de una nota y la evidencia que lo decide."""

    estado: EstadoNota = EstadoNota.PENDIENTE
    definitivo: bool = False
    evento: Optional[EventoInterpretacion] = None
    comparacion: Optional[ResultadoAltura] = None
    desfase_s: Optional[float] = None
    intentos_fallidos: int = 0
    diagnosticos: List[TipoEvento] = field(default_factory=list)

    @property
    def es_acierto(self) -> bool:
        return self.estado.es_acierto

    @property
    def midi_detectado(self) -> Optional[float]:
        return None if self.evento is None else self.evento.midi

    @property
    def cents(self) -> Optional[float]:
        """Desviación respecto de la nota identificada (la esperada si es un acierto)."""
        return None if self.comparacion is None else self.comparacion.cents


@dataclass(frozen=True)
class ConfiguracionSesion:
    modo: ModoPractica = ModoPractica.SEGUIR_TEMPO
    tolerancia_s: float = 0.150
    alineacion_inicial_max_s: float = 0.500
    margen_cierre_s: float = MARGEN_CIERRE_S
    confianza_min_error: float = 0.90   # por debajo, un evento dudoso no acusa de nota equivocada
    refractario_acorde_s: float = 0.30  # tras avanzar un acorde (esperar), se ignora lo que siga
    la4: float = LA4_HZ


@dataclass(frozen=True)
class Cambio:
    """Una nota cuyo resultado cambió (para actualizar la interfaz)."""

    indice: int
    resultado: ResultadoNota


class SesionDePractica:
    """Evalúa una interpretación frente a la línea de práctica de una partitura."""

    def __init__(self, notas: Sequence[NotaEsperada],
                 configuracion: ConfiguracionSesion = ConfiguracionSesion(), sesion: int = 1):
        self.notas: Tuple[NotaEsperada, ...] = tuple(notas)
        self.config = configuracion
        self.sesion = sesion
        self.resultados: List[ResultadoNota] = [ResultadoNota() for _ in self.notas]
        self.t0: Optional[float] = None
        self.desfase_s = 0.0
        self.alineada = False
        self.indice_actual = 0
        self.detenida = False
        self.eventos_fuera_de_ventana: List[EventoInterpretacion] = []
        self._errores_recientes: List[float] = []
        self.ultimo_evento: Optional[EventoInterpretacion] = None
        self.ultima_comparacion: Optional[ResultadoAltura] = None
        self.eventos_de_acorde: List[EventoInterpretacion] = []
        self._ignorar_hasta = float("-inf")
        # La ventana inicial ampliada y la alineación se aplican a la primera nota que se evalúa.
        self._primera = next((n.indice for n in self.notas if not n.es_acorde), 0)

    # ------------------------------------------------------------------------------------
    @property
    def modo(self) -> ModoPractica:
        return self.config.modo

    @property
    def iniciada(self) -> bool:
        return self.t0 is not None

    @property
    def terminada(self) -> bool:
        return bool(self.notas) and all(r.definitivo for r in self.resultados)

    @property
    def estados_booleanos(self) -> List[Optional[bool]]:
        """True (acierto), False (error) o None (pendiente), como la interfaz anterior."""
        return [None if r.estado in (EstadoNota.PENDIENTE, EstadoNota.SIN_EVALUAR)
                else r.estado.es_acierto for r in self.resultados]

    def iniciar(self, t0: float) -> None:
        """Fija el instante (reloj de captura) que corresponde al inicio de la partitura."""
        self.t0 = float(t0)
        self.detenida = False

    def detener(self) -> None:
        """El usuario detiene la sesión: no se procesan más eventos."""
        self.detenida = True

    def inicio_esperado(self, indice: int) -> float:
        """Instante esperado (reloj de captura) del ataque de una nota, con la alineación."""
        return self.t0 + self.desfase_s + self.notas[indice].inicio_s

    def ventana(self, indice: int) -> Tuple[float, float]:
        esperado = self.inicio_esperado(indice)
        tolerancia = self.config.tolerancia_s
        if indice == self._primera and not self.alineada:
            return esperado - tolerancia, esperado + max(tolerancia, self.config.alineacion_inicial_max_s)
        return esperado - tolerancia, esperado + tolerancia

    # ------------------------------------------------------------------------------------
    def procesar(self, evento: EventoInterpretacion) -> List[Cambio]:
        """Incorpora un evento de interpretación. Devuelve las notas que cambiaron."""
        if (self.t0 is None or self.detenida or not self.notas
                or (evento.sesion and evento.sesion != self.sesion)
                or evento.tipo is TipoEvento.FIN
                or evento.t < self.t0 - self.config.tolerancia_s):
            return []
        self.ultimo_evento = evento
        if self.modo is ModoPractica.ESPERAR_NOTA:
            return self._procesar_esperando(evento)
        return self._procesar_con_tempo(evento)

    def actualizar(self, t: float) -> List[Cambio]:
        """Avanza el reloj: cierra las ventanas vencidas y mueve la nota actual."""
        if self.t0 is None or self.detenida or self.modo is ModoPractica.ESPERAR_NOTA:
            return []
        cambios = []
        for i, resultado in enumerate(self.resultados):
            if resultado.definitivo:
                continue
            if t > self.ventana(i)[1] + self.config.margen_cierre_s:
                cambios.append(self._cerrar(i))
            else:
                break
        nuevo = self.indice_actual
        while nuevo + 1 < len(self.notas) and t >= self.inicio_esperado(nuevo + 1):
            nuevo += 1
        self.indice_actual = max(self.indice_actual, nuevo)
        return cambios

    # ------------------------------------------------------------------------------------
    def _comparar(self, evento: EventoInterpretacion, indice: int) -> ResultadoAltura:
        return comparar_frecuencia(evento.frecuencia_hz, self.notas[indice].midi, self.config.la4)

    def _con_dudas(self, evento: EventoInterpretacion) -> bool:
        return evento.tipo is TipoEvento.NOTA and evento.confianza < self.config.confianza_min_error

    def _procesar_con_tempo(self, evento: EventoInterpretacion) -> List[Cambio]:
        candidatas = self._candidatas(evento.t)
        if candidatas:
            cercana = min(candidatas, key=lambda i: abs(evento.t - self.inicio_esperado(i)))
            if self.notas[cercana].es_acorde:
                self.eventos_de_acorde.append(evento)  # el rasgueo no puntúa a las notas vecinas
                return []
            candidatas = [i for i in candidatas if not self.notas[i].es_acorde]
        if not candidatas:
            if evento.tipo is TipoEvento.NOTA:
                self.eventos_fuera_de_ventana.append(evento)
            return []
        if evento.tipo is not TipoEvento.NOTA:
            # Diagnóstico: explica la nota más cercana que aún no tiene ataque.
            sin_ataque = [i for i in candidatas if self.resultados[i].evento is None]
            if sin_ataque:
                indice = min(sin_ataque, key=lambda i: abs(evento.t - self.inicio_esperado(i)))
                self.resultados[indice].diagnosticos.append(evento.tipo)
            return []
        comparaciones = {i: self._comparar(evento, i) for i in candidatas}
        aciertos = [i for i in candidatas if comparaciones[i].es_acierto]
        if not aciertos and self._con_dudas(evento):
            sin_ataque = [i for i in candidatas if self.resultados[i].evento is None]
            if sin_ataque:
                indice = min(sin_ataque, key=lambda i: abs(evento.t - self.inicio_esperado(i)))
                self.resultados[indice].diagnosticos.append(TipoEvento.BAJA_CONFIANZA)
            return []
        if aciertos:
            indice = min(aciertos, key=lambda i: abs(evento.t - self.inicio_esperado(i)))
        elif (not self.alineada and self.resultados[self._primera].evento is None
              and candidatas[0] == self._primera):
            # Antes del primer ataque, una nota equivocada es el intento de empezar: se asigna
            # a la primera nota, no a la que esté más cerca en el tiempo nominal. Solo la
            # primera: con la ventana inicial ampliada, los siguientes ataques equivocados
            # siguen su propia nota (no alinean la sesión, así que la ventana sigue abierta).
            indice = self._primera
        else:
            sin_ataque = [i for i in candidatas if self.resultados[i].evento is None]
            grupo = sin_ataque or candidatas
            indice = min(grupo, key=lambda i: abs(evento.t - self.inicio_esperado(i)))
        comparacion = comparaciones[indice]
        self.ultima_comparacion = comparacion
        cambio = self._asignar(indice, evento, comparacion)
        if comparacion.es_acierto:  # solo un acierto indica cuándo toca el intérprete
            self._alinear(indice, evento)
        return [cambio]

    def _candidatas(self, t: float) -> List[int]:
        """Notas sin resultado definitivo cuya ventana contiene `t`, en orden."""
        resultado = []
        for i, nota_resultado in enumerate(self.resultados):
            if nota_resultado.definitivo:
                continue
            inicio, fin = self.ventana(i)
            if inicio > t:
                break
            if t <= fin:
                resultado.append(i)
        return resultado

    def _asignar(self, indice: int, evento: EventoInterpretacion,
                 comparacion: ResultadoAltura) -> Cambio:
        resultado = self.resultados[indice]
        if not comparacion.es_acierto:
            resultado.intentos_fallidos += 1
        resultado.evento = evento
        resultado.comparacion = comparacion
        resultado.estado = _DE_ALTURA[comparacion.estado]
        resultado.desfase_s = evento.t - self.inicio_esperado(indice)
        if comparacion.es_acierto:
            resultado.definitivo = True
        return Cambio(indice, resultado)

    def _alinear(self, indice: int, evento: EventoInterpretacion) -> None:
        error = evento.t - self.inicio_esperado(indice)
        if not self.alineada:
            self.desfase_s += error
            self.alineada = True
            return
        if abs(error) > self.config.tolerancia_s:
            return
        self._errores_recientes = (self._errores_recientes + [error])[-3:]
        recientes = self._errores_recientes
        if len(recientes) == 3 and (all(e > 0 for e in recientes) or all(e < 0 for e in recientes)):
            self.desfase_s += sum(recientes) / 3
            self._errores_recientes = []

    def _cerrar(self, indice: int) -> Cambio:
        resultado = self.resultados[indice]
        if self.notas[indice].es_acorde:
            resultado.estado = EstadoNota.SIN_EVALUAR
        elif resultado.estado is EstadoNota.PENDIENTE:
            resultado.estado = EstadoNota.OMITIDA
            for tipo, estado in _DIAGNOSTICOS:
                if tipo in resultado.diagnosticos:
                    resultado.estado = estado
                    break
        resultado.definitivo = True
        return Cambio(indice, resultado)

    # ------------------------------------------------------------------------------------
    def _procesar_esperando(self, evento: EventoInterpretacion) -> List[Cambio]:
        if self.indice_actual >= len(self.notas):
            return []
        if evento.t < self._ignorar_hasta:
            return []  # lo que sigue al rasgueo de un acorde ya avanzado
        indice = self.indice_actual
        resultado = self.resultados[indice]
        if self.notas[indice].es_acorde:
            if evento.tipo is TipoEvento.SENAL_DEBIL:
                resultado.diagnosticos.append(evento.tipo)
                return []
            resultado.estado = EstadoNota.SIN_EVALUAR
            resultado.definitivo = True
            self.indice_actual += 1
            self._ignorar_hasta = evento.t + self.config.refractario_acorde_s
            return [Cambio(indice, resultado)]
        if evento.tipo is not TipoEvento.NOTA:
            resultado.diagnosticos.append(evento.tipo)
            return []
        comparacion = self._comparar(evento, indice)
        self.ultima_comparacion = comparacion
        if not comparacion.es_acierto and self._con_dudas(evento):
            resultado.diagnosticos.append(TipoEvento.BAJA_CONFIANZA)
            return []
        if comparacion.es_acierto:
            cambio = self._asignar(indice, evento, comparacion)
            self.indice_actual += 1
            return [cambio]
        resultado.intentos_fallidos += 1
        resultado.evento = evento
        resultado.comparacion = comparacion
        resultado.estado = _DE_ALTURA[comparacion.estado]
        return [Cambio(indice, resultado)]

    # ------------------------------------------------------------------------------------
    def resumen(self) -> Dict[str, object]:
        conteo: Dict[str, int] = {estado.value: 0 for estado in EstadoNota}
        for r in self.resultados:
            conteo[r.estado.value] += 1
        aciertos = sum(1 for r in self.resultados if r.es_acierto)
        evaluables = sum(1 for n in self.notas if not n.es_acorde)
        evaluadas = sum(1 for r in self.resultados
                        if r.estado not in (EstadoNota.PENDIENTE, EstadoNota.SIN_EVALUAR))
        cents = [abs(r.cents) for r in self.resultados if r.es_acierto and r.cents is not None]
        desfases = [abs(r.desfase_s) for r in self.resultados
                    if r.es_acierto and r.desfase_s is not None]
        return {
            "total": len(self.notas),
            "evaluables": evaluables,   # sin los acordes, que no se evalúan
            "evaluadas": evaluadas,
            "aciertos": aciertos,
            "precision": aciertos / evaluables if evaluables else 0.0,
            "estados": conteo,
            "intentos_fallidos": sum(r.intentos_fallidos for r in self.resultados),
            "cents_medios": sum(cents) / len(cents) if cents else None,
            "desfase_medio_s": sum(desfases) / len(desfases) if desfases else None,
            "alineacion_s": self.desfase_s,
            "eventos_fuera_de_ventana": len(self.eventos_fuera_de_ventana),
        }


def notas_esperadas(notas: Iterable[dict], bpm: float = 120.0, factor_tempo: float = 1.0
                    ) -> List[NotaEsperada]:
    """Convierte la lista de `cargar_partitura` en notas esperadas.

    Usa `inicio_s`/`duracion_s` (tempo de la partitura, cambios incluidos) cuando existen y,
    si no, `offset_beats`/`duracion_beats` a `bpm`. `factor_tempo` > 1 acelera la práctica."""
    if factor_tempo <= 0:
        raise ValueError("El factor de tempo debe ser positivo")
    resultado = []
    segundos_por_negra = 60.0 / max(float(bpm), 1e-6)
    for i, nota in enumerate(notas):
        if nota.get("inicio_s") is not None and nota.get("duracion_s") is not None:
            inicio, duracion = float(nota["inicio_s"]), float(nota["duracion_s"])
        else:
            inicio = float(nota["offset_beats"]) * segundos_por_negra
            duracion = float(nota["duracion_beats"]) * segundos_por_negra
        midi = nota.get("midi")
        if midi is None:
            from .musica import a_midi
            midi = a_midi(nota["nombre"])
        alturas = tuple(nota.get("alturas_midi") or (midi,))
        resultado.append(NotaEsperada(i, inicio / factor_tempo, duracion / factor_tempo,
                                      float(midi), alturas, nota.get("nombre", "")))
    return resultado


def describir_estado(estado: EstadoNota) -> str:
    """Texto breve para la interfaz (sin depender de colores)."""
    return {
        EstadoNota.PENDIENTE: "Pendiente",
        EstadoNota.CORRECTA: "Correcta",
        EstadoNota.DESAFINADA: "Correcta, pero desafinada",
        EstadoNota.NOTA_INCORRECTA: "Nota equivocada",
        EstadoNota.OCTAVA_INCORRECTA: "Octava incorrecta",
        EstadoNota.OMITIDA: "No se tocó",
        EstadoNota.SENAL_INSUFICIENTE: "Señal insuficiente",
        EstadoNota.BAJA_CONFIANZA: "Detección poco fiable",
        EstadoNota.FUERA_DE_RANGO: "Fuera del rango del instrumento",
        EstadoNota.SIN_EVALUAR: "Acorde: no se evalúa",
    }[estado]


@dataclass
class SesionProgreso:
    """Clase formal POO de dominio que modela el resultado de una sesión de práctica."""
    partitura: str
    instrumento: str = "piano"
    modo: str = "seguir_tempo"
    factor_tempo: float = 1.0
    total: int = 0
    aciertos: int = 0
    precision: float = 0.0
    fecha: str = field(
        default_factory=lambda: datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    )
    estados: Dict[str, int] = field(default_factory=dict)
    cents_medios: Optional[float] = None
    desfase_medio_s: Optional[float] = None

    # Propiedades semánticas (compatibilidad con la nomenclatura del informe técnico), hola
    @property
    def nombre_partitura(self) -> str:
        return self.partitura

    @property
    def precision_media(self) -> float:
        return self.precision

    @property
    def notas_correctas(self) -> int:
        return self.aciertos

    @property
    def total_notas(self) -> int:
        return self.total

    @property
    def timestamp(self) -> str:
        return self.fecha

    def to_dict(self) -> Dict[str, Any]:
        """Serializa la instancia POO a un diccionario primitivo para persistencia JSON."""
        return {
            "fecha": self.fecha,
            "partitura": self.partitura,
            "instrumento": self.instrumento,
            "modo": self.modo,
            "factor_tempo": self.factor_tempo,
            "total": self.total,
            "aciertos": self.aciertos,
            "precision": round(float(self.precision), 4),
            "estados": dict(self.estados),
            "cents_medios": self.cents_medios,
            "desfase_medio_s": self.desfase_medio_s,
        }

    @classmethod
    def from_dict(cls, datos: Dict[str, Any]) -> "SesionProgreso":
        """Reconstruye una instancia POO de dominio a partir de un diccionario cargado de JSON."""
        return cls(
            fecha=str(datos.get("fecha", "")),
            partitura=str(datos.get("partitura", "?")),
            instrumento=str(datos.get("instrumento", "piano")),
            modo=str(datos.get("modo", "seguir_tempo")),
            factor_tempo=float(datos.get("factor_tempo", 1.0)),
            total=int(datos.get("total", 0)),
            aciertos=int(datos.get("aciertos", 0)),
            precision=float(datos.get("precision", 0.0)),
            estados=dict(datos.get("estados", {})),
            cents_medios=float(datos["cents_medios"]) if datos.get("cents_medios") is not None else None,
            desfase_medio_s=float(datos["desfase_medio_s"]) if datos.get("desfase_medio_s") is not None else None,
        )


__all__ = ["Cambio", "ConfiguracionSesion", "EstadoNota", "ModoPractica", "NotaEsperada",
           "ResultadoNota", "SesionDePractica", "SesionProgreso", "describir_estado", "notas_esperadas"]
