"""
Modelo musical de Wynik.

Representa alturas, eventos, partes, tempo y partituras con valores numéricos inequívocos
(número MIDI, hercios, pulsos y segundos) y conserva por separado la grafía original
(letra y alteración) para mostrar sostenidos y bemoles tal como están escritos.

Solo usa la biblioteca estándar: importarlo no carga Kivy, librosa, sounddevice, numpy
ni music21.

Convenciones
- Octava en notación científica: C4 = do central = MIDI 60; A4 = 440 Hz = MIDI 69.
- Los cálculos usan `Altura.midi` y `Altura.frecuencia`; el texto solo sirve para mostrar
  o para leer nombres que llegan de otros componentes. `Altura.desde_nombre` acepta la
  notación de music21 ('B-4', 'E--4', 'F##4'), la de librosa ('A♯4', 'B♭3'), ASCII
  ('Bb4', 'C#4') y Unicode ('C𝄪4', 'D𝄫4'). La octava de un nombre debe ser un entero >= 0:
  un '-' entre la letra y la octava es siempre un bemol, como en music21.
- Tolerancias de afinación aprobadas (independientes de la octava y del tiempo):
  hasta 25 cents, afinada; más de 25 y hasta 50 cents, la misma nota pero desafinada;
  más de 50 cents, se evalúa la nota más cercana y se clasifica su identidad real.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterator, List, Optional, Tuple, Union

LA4_HZ = 440.0
MIDI_LA4 = 69
TOLERANCIA_AFINADA_CENTS = 25.0
TOLERANCIA_IDENTIDAD_CENTS = 50.0
# Margen numérico para que una desviación calculada de exactamente 25 o 50 cents no cambie de
# categoría por errores de redondeo en coma flotante.
_MARGEN_CENTS = 1e-6

PASOS = ("C", "D", "E", "F", "G", "A", "B")
_SEMITONOS_PASO = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_SOLFEO = {"C": "Do", "D": "Re", "E": "Mi", "F": "Fa", "G": "Sol", "A": "La", "B": "Si"}
_ALTERACION_DE_TEXTO = {"#": 1, "♯": 1, "x": 2, "𝄪": 2,
                        "b": -1, "♭": -1, "-": -1, "𝄫": -2, "n": 0, "♮": 0}
_PATRON_NOMBRE = re.compile(r"^\s*([A-Ga-g])([#♯x𝄪b♭\-𝄫n♮]*)(\d+)\s*$")
_SIMBOLOS = {2: "♯♯", 1: "♯", 0: "", -1: "♭", -2: "♭♭"}
_ASCII = {2: "##", 1: "#", 0: "", -1: "b", -2: "bb"}
_DESDE_MIDI_SOSTENIDOS = (("C", 0), ("C", 1), ("D", 0), ("D", 1), ("E", 0), ("F", 0),
                          ("F", 1), ("G", 0), ("G", 1), ("A", 0), ("A", 1), ("B", 0))
_DESDE_MIDI_BEMOLES = (("C", 0), ("D", -1), ("D", 0), ("E", -1), ("E", 0), ("F", 0),
                       ("G", -1), ("G", 0), ("A", -1), ("A", 0), ("B", -1), ("B", 0))

Numero = Union[int, float]


class ErrorAltura(ValueError):
    """Nombre, número MIDI o frecuencia que no representa una altura válida."""


def _es_numero_finito(valor) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)


def _entero_si_exacto(valor: float) -> Numero:
    return int(valor) if float(valor).is_integer() else valor


# ---------------------------------------------------------------------------------------------
#  Conversiones numéricas
# ---------------------------------------------------------------------------------------------

def midi_a_frecuencia(midi: Numero, la4: float = LA4_HZ) -> float:
    """Frecuencia en hercios de un número MIDI (admite valores fraccionarios)."""
    if not _es_numero_finito(midi):
        raise ErrorAltura(f"Número MIDI no válido: {midi!r}")
    return la4 * 2.0 ** ((midi - MIDI_LA4) / 12.0)


def frecuencia_a_midi(frecuencia_hz: Numero, la4: float = LA4_HZ) -> float:
    """Número MIDI fraccionario de una frecuencia (69,5 está 50 cents por encima de A4)."""
    if not _es_numero_finito(frecuencia_hz) or frecuencia_hz <= 0:
        raise ErrorAltura(f"Frecuencia no válida: {frecuencia_hz!r}")
    return MIDI_LA4 + 12.0 * math.log2(frecuencia_hz / la4)


def cents_entre(frecuencia_hz: Numero, referencia_hz: Numero) -> float:
    """Distancia en cents de `frecuencia_hz` respecto de `referencia_hz` (positiva si es más aguda)."""
    for valor in (frecuencia_hz, referencia_hz):
        if not _es_numero_finito(valor) or valor <= 0:
            raise ErrorAltura(f"Frecuencia no válida: {valor!r}")
    return 1200.0 * math.log2(frecuencia_hz / referencia_hz)


def midi_mas_cercano(midi: Numero) -> int:
    """Semitono más cercano. Un empate exacto (medio semitono) se resuelve hacia arriba."""
    if not _es_numero_finito(midi):
        raise ErrorAltura(f"Número MIDI no válido: {midi!r}")
    return math.floor(midi + 0.5)


# ---------------------------------------------------------------------------------------------
#  Altura
# ---------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Altura:
    """Altura con su grafía: letra (`paso`), alteración en semitonos y octava científica.

    Dos alturas enarmónicas (A♯3 y B♭3) son objetos distintos, porque se escriben distinto,
    pero tienen el mismo `midi` y la misma `frecuencia`: compárense con `misma_altura_sonora`.
    """

    paso: str
    alteracion: Numero = 0
    octava: int = 4

    def __post_init__(self):
        if self.paso not in _SEMITONOS_PASO:
            raise ErrorAltura(f"Letra de nota no válida: {self.paso!r}")
        if not isinstance(self.octava, int) or isinstance(self.octava, bool):
            raise ErrorAltura(f"Octava no válida: {self.octava!r}")
        if not _es_numero_finito(self.alteracion) or abs(self.alteracion) > 3:
            raise ErrorAltura(f"Alteración no válida: {self.alteracion!r}")
        object.__setattr__(self, "alteracion", _entero_si_exacto(self.alteracion))

    # --- valores numéricos -------------------------------------------------------------------

    @property
    def midi(self) -> Numero:
        """Número MIDI (entero salvo microtonos): C4 = 60, B♭4 = 70, C♭4 = 59."""
        return _entero_si_exacto(12 * (self.octava + 1) + _SEMITONOS_PASO[self.paso] + self.alteracion)

    @property
    def midi_entero(self) -> int:
        return midi_mas_cercano(self.midi)

    @property
    def frecuencia(self) -> float:
        """Frecuencia en hercios con A4 = 440 Hz."""
        return midi_a_frecuencia(self.midi)

    def frecuencia_con(self, la4: float) -> float:
        return midi_a_frecuencia(self.midi, la4)

    @property
    def clase(self) -> int:
        """Clase de altura (0 = do, 11 = si), sin octava."""
        return self.midi_entero % 12

    @property
    def paso_diatonico(self) -> int:
        """Posición vertical en el pentagrama: depende de la letra y la octava escritas."""
        return self.octava * 7 + PASOS.index(self.paso)

    def misma_altura_sonora(self, otra: "Altura") -> bool:
        return self.midi == otra.midi

    # --- grafía ------------------------------------------------------------------------------

    @property
    def simbolo_alteracion(self) -> str:
        if self.alteracion in _SIMBOLOS:
            return _SIMBOLOS[self.alteracion]
        return f"({self.alteracion:+g})"

    @property
    def nombre(self) -> str:
        """Nombre para mostrar con la alteración original: 'B♭4', 'C♯4', 'E♭♭4'."""
        return f"{self.paso}{self.simbolo_alteracion}{self.octava}"

    @property
    def nombre_ascii(self) -> str:
        """Nombre en ASCII ('Bb4', 'C#4'), útil para registros e intercambio."""
        alteracion = _ASCII.get(self.alteracion, f"({self.alteracion:+g})")
        return f"{self.paso}{alteracion}{self.octava}"

    @property
    def nombre_solfeo(self) -> str:
        """Nombre en solfeo con la alteración original: 'Si♭4', 'Do♯4'."""
        return f"{_SOLFEO[self.paso]}{self.simbolo_alteracion}{self.octava}"

    def __str__(self) -> str:
        return self.nombre

    # --- construcción ------------------------------------------------------------------------

    @classmethod
    def desde_nombre(cls, texto: str) -> "Altura":
        """Lee un nombre de nota de music21, librosa, ASCII o Unicode (ver el módulo)."""
        if not isinstance(texto, str):
            raise ErrorAltura(f"Nombre de nota no válido: {texto!r}")
        coincidencia = _PATRON_NOMBRE.match(texto)
        if not coincidencia:
            raise ErrorAltura(f"Nombre de nota no reconocido: {texto!r}")
        letra, alteraciones, octava = coincidencia.groups()
        alteracion = sum(_ALTERACION_DE_TEXTO[c] for c in alteraciones)
        return cls(letra.upper(), alteracion, int(octava))

    @classmethod
    def desde_midi(cls, midi: int, preferir_bemoles: bool = False) -> "Altura":
        """Altura de un número MIDI entero, escrita con sostenidos (o bemoles si se prefiere)."""
        if not _es_numero_finito(midi) or not float(midi).is_integer() or midi < 0:
            raise ErrorAltura(f"Número MIDI no válido para escribir una nota: {midi!r}")
        midi = int(midi)
        tabla = _DESDE_MIDI_BEMOLES if preferir_bemoles else _DESDE_MIDI_SOSTENIDOS
        paso, alteracion = tabla[midi % 12]
        return cls(paso, alteracion, midi // 12 - 1)


def a_midi(valor: Union[Altura, Numero, str]) -> Numero:
    """Número MIDI de una `Altura`, de un número MIDI o de un nombre de nota."""
    if isinstance(valor, Altura):
        return valor.midi
    if isinstance(valor, str):
        return Altura.desde_nombre(valor).midi
    if _es_numero_finito(valor):
        return valor
    raise ErrorAltura(f"No es una altura: {valor!r}")


# ---------------------------------------------------------------------------------------------
#  Comparación de alturas con las tolerancias aprobadas
# ---------------------------------------------------------------------------------------------

class EstadoAltura(str, Enum):
    """Resultado de comparar la altura tocada con la esperada (sin considerar el tiempo)."""

    CORRECTA = "correcta"                    # misma nota y octava, a ±25 cents o menos
    DESAFINADA = "desafinada"                # misma nota y octava, a más de 25 y hasta 50 cents
    OCTAVA_INCORRECTA = "octava_incorrecta"  # misma nota en otra octava
    NOTA_INCORRECTA = "nota_incorrecta"      # otra nota


@dataclass(frozen=True)
class ResultadoAltura:
    """Comparación de una altura detectada con la esperada.

    - `midi_identificado`: la nota que realmente sonó (la esperada si la desviación es de
      50 cents o menos; si no, la más cercana).
    - `cents`: desviación respecto de `midi_identificado`, o `None` si la entrada ya era una
      nota sin afinación (por ejemplo, un nombre).
    """

    estado: EstadoAltura
    midi_esperado: Numero
    midi_identificado: int
    cents: Optional[float] = None

    @property
    def es_acierto(self) -> bool:
        """Nota y octava correctas (afinada o no). Es lo que exige el modo normal."""
        return self.estado in (EstadoAltura.CORRECTA, EstadoAltura.DESAFINADA)

    @property
    def afinada(self) -> Optional[bool]:
        if self.cents is None:
            return None
        return abs(self.cents) <= TOLERANCIA_AFINADA_CENTS + _MARGEN_CENTS

    @property
    def diferencia_semitonos(self) -> int:
        return self.midi_identificado - midi_mas_cercano(self.midi_esperado)

    @property
    def diferencia_octavas(self) -> Optional[int]:
        if self.estado is not EstadoAltura.OCTAVA_INCORRECTA:
            return None
        return self.diferencia_semitonos // 12

    @property
    def altura_identificada(self) -> Altura:
        return Altura.desde_midi(self.midi_identificado)


def comparar_frecuencia(frecuencia_hz: Numero, esperada: Union[Altura, Numero, str],
                        la4: float = LA4_HZ) -> ResultadoAltura:
    """Compara una frecuencia medida con la altura esperada aplicando las tolerancias aprobadas.

    - |desviación| <= 25 cents respecto de la esperada: CORRECTA.
    - 25 < |desviación| <= 50 cents: DESAFINADA (misma nota y octava).
    - |desviación| > 50 cents: se identifica la nota más cercana a la frecuencia y se
      clasifica como OCTAVA_INCORRECTA (misma clase de altura) o NOTA_INCORRECTA.
    """
    midi_esperado = a_midi(esperada)
    midi_medido = frecuencia_a_midi(frecuencia_hz, la4)
    referencia = midi_mas_cercano(midi_esperado)
    desviacion = (midi_medido - midi_esperado) * 100.0
    if abs(desviacion) <= TOLERANCIA_IDENTIDAD_CENTS + _MARGEN_CENTS:
        afinada = abs(desviacion) <= TOLERANCIA_AFINADA_CENTS + _MARGEN_CENTS
        estado = EstadoAltura.CORRECTA if afinada else EstadoAltura.DESAFINADA
        return ResultadoAltura(estado, midi_esperado, referencia, desviacion)
    identificado = midi_mas_cercano(midi_medido)
    cents = (midi_medido - identificado) * 100.0
    if identificado == referencia:  # solo posible si la altura esperada es microtonal
        estado = EstadoAltura.DESAFINADA
    elif (identificado - referencia) % 12 == 0:
        estado = EstadoAltura.OCTAVA_INCORRECTA
    else:
        estado = EstadoAltura.NOTA_INCORRECTA
    return ResultadoAltura(estado, midi_esperado, identificado, cents)


def comparar_alturas(detectada: Union[Altura, Numero, str],
                     esperada: Union[Altura, Numero, str]) -> ResultadoAltura:
    """Compara dos alturas ya identificadas (nombres, `Altura` o MIDI), sin afinación.

    Las notas enarmónicas coinciden (A♯3 = B♭3); la octava debe ser la misma.
    """
    identificado = midi_mas_cercano(a_midi(detectada))
    midi_esperado = a_midi(esperada)
    referencia = midi_mas_cercano(midi_esperado)
    if identificado == referencia:
        estado = EstadoAltura.CORRECTA
    elif (identificado - referencia) % 12 == 0:
        estado = EstadoAltura.OCTAVA_INCORRECTA
    else:
        estado = EstadoAltura.NOTA_INCORRECTA
    return ResultadoAltura(estado, midi_esperado, identificado, None)


# ---------------------------------------------------------------------------------------------
#  Eventos, partes y tempo
# ---------------------------------------------------------------------------------------------

class Ligadura(str, Enum):
    """Papel de una nota en una ligadura de prolongación."""

    INICIO = "inicio"
    CONTINUACION = "continuacion"
    FIN = "fin"


@dataclass(frozen=True)
class NotaEvento:
    """Una cabeza de nota: altura escrita, altura sonora y ligadura."""

    escrita: Altura
    sonora: Altura
    ligadura: Optional[Ligadura] = None

    @property
    def midi(self) -> Numero:
        """MIDI sonoro: el que debe oír el micrófono."""
        return self.sonora.midi

    @property
    def frecuencia(self) -> float:
        return self.sonora.frecuencia


@dataclass(frozen=True)
class Evento:
    """Lo que empieza en un instante dentro de una voz: nota, acorde o silencio.

    - `notas` vacío: silencio. Más de una nota: acorde (notas simultáneas de la misma voz).
    - Tiempos en negras desde el inicio de la partitura y, si se conoce el tempo, en segundos.
    """

    inicio_negras: float
    duracion_negras: float
    notas: Tuple[NotaEvento, ...] = ()
    parte_id: str = "P1"
    pentagrama: int = 1
    voz: str = "1"
    compas: Optional[int] = None
    adorno: bool = False
    inicio_s: Optional[float] = None
    duracion_s: Optional[float] = None
    figura: str = ""      # tipo de figura de MusicXML ('quarter', 'eighth'…); '' o 'complex': no consta
    puntillos: int = 0

    @property
    def fin_negras(self) -> float:
        return self.inicio_negras + self.duracion_negras

    @property
    def es_silencio(self) -> bool:
        return not self.notas

    @property
    def es_acorde(self) -> bool:
        return len(self.notas) > 1


@dataclass(frozen=True)
class CambioTempo:
    """Tempo en negras por minuto a partir de un instante (en negras)."""

    inicio_negras: float
    negras_por_minuto: float


@dataclass(frozen=True)
class MapaTempo:
    """Tempo de la partitura a lo largo del tiempo.

    Sin cambios (`explicito` falso) o antes del primer cambio se usa `por_defecto`.
    """

    cambios: Tuple[CambioTempo, ...] = ()
    por_defecto: float = 120.0

    def __post_init__(self):
        if not _es_numero_finito(self.por_defecto) or self.por_defecto <= 0:
            raise ValueError(f"Tempo por defecto no válido: {self.por_defecto!r}")
        unicos: Dict[float, CambioTempo] = {}
        for cambio in self.cambios:
            if not _es_numero_finito(cambio.negras_por_minuto) or cambio.negras_por_minuto <= 0:
                raise ValueError(f"Tempo no válido: {cambio.negras_por_minuto!r}")
            unicos[float(cambio.inicio_negras)] = cambio
        object.__setattr__(self, "cambios", tuple(unicos[k] for k in sorted(unicos)))

    @property
    def explicito(self) -> bool:
        return bool(self.cambios)

    def _tramos(self) -> List[Tuple[float, float]]:
        tramos: List[Tuple[float, float]] = []
        if not self.cambios or self.cambios[0].inicio_negras > 0:
            tramos.append((0.0, self.por_defecto))
        tramos.extend((c.inicio_negras, c.negras_por_minuto) for c in self.cambios)
        return tramos

    def negras_por_minuto_en(self, negras: float) -> float:
        actual = self._tramos()[0][1]
        for inicio, bpm in self._tramos():
            if inicio <= negras + 1e-9:
                actual = bpm
        return actual

    def segundos(self, negras: float) -> float:
        """Instante en segundos del pulso `negras`, integrando los cambios de tempo."""
        total = 0.0
        tramos = self._tramos()
        for i, (inicio, bpm) in enumerate(tramos):
            fin = tramos[i + 1][0] if i + 1 < len(tramos) else math.inf
            if negras <= inicio:
                break
            total += (min(negras, fin) - inicio) * 60.0 / bpm
        return total

    def duracion_segundos(self, inicio_negras: float, duracion_negras: float) -> float:
        return self.segundos(inicio_negras + duracion_negras) - self.segundos(inicio_negras)


class OrigenTransposicion(str, Enum):
    """De dónde sale la diferencia entre altura escrita y altura sonora de una parte."""

    DECLARADA = "declarada"                    # elemento <transpose> del archivo
    SIN_TRANSPOSICION = "sin_transposicion"    # el archivo no declara transposición
    DEDUCIDA_POR_RANGO = "deducida_por_rango"  # guitarra sin indicación: solo una lectura cabe en su rango
    CONFIGURADA = "configurada"                # impuesta por la configuración del perfil
    INDETERMINADA = "indeterminada"            # guitarra sin indicación y dos lecturas posibles


@dataclass(frozen=True)
class Transposicion:
    """Semitonos que se suman a la altura escrita para obtener la sonora, y su origen."""

    semitonos: int = 0
    origen: OrigenTransposicion = OrigenTransposicion.SIN_TRANSPOSICION
    detalle: str = ""


@dataclass(frozen=True)
class Clave:
    """Clave vigente en un pentagrama desde `inicio_negras`: signo ('G', 'F', 'C'), línea (1 =
    la de abajo) y cambio de octava (−1 = sol octava baja, la de la guitarra)."""

    inicio_negras: float
    pentagrama: int
    signo: str
    linea: int
    cambio_octava: int = 0


@dataclass(frozen=True)
class Armadura:
    """Armadura desde `inicio_negras`: > 0 sostenidos, < 0 bemoles (círculo de quintas)."""

    inicio_negras: float
    quintas: int


@dataclass(frozen=True)
class Compas:
    """Indicación de compás desde `inicio_negras`."""

    inicio_negras: float
    numerador: int
    denominador: int


@dataclass(frozen=True)
class Parte:
    """Una parte de la partitura (un instrumento), con todos sus pentagramas y voces."""

    id: str
    nombre: str
    eventos: Tuple[Evento, ...]
    pentagramas: int = 1
    transposicion: Transposicion = field(default_factory=Transposicion)
    perfil: Optional[str] = None
    clave_cambio_octava: int = 0
    claves: Tuple[Clave, ...] = ()
    armaduras: Tuple[Armadura, ...] = ()
    compases: Tuple[Compas, ...] = ()                    # indicaciones de compás (3/4, 6/8…)
    inicios_compas: Tuple[Tuple[int, float], ...] = ()   # (número, inicio en negras) de cada barra

    @property
    def notas(self) -> Iterator[NotaEvento]:
        for evento in self.eventos:
            yield from evento.notas

    @property
    def voces(self) -> Tuple[Tuple[int, str], ...]:
        """Pares (pentagrama, voz) presentes en la parte."""
        return tuple(sorted({(e.pentagrama, e.voz) for e in self.eventos}))


@dataclass(frozen=True)
class Ataque:
    """Lo que se espera tocar a partir de un instante en la práctica nota a nota.

    Reúne todas las notas que empiezan juntas en la parte (acordes y voces simultáneas),
    con las ligaduras ya sumadas. `principal` es la más aguda (altura sonora): la única que
    evalúa el modo monofónico. Las demás se conservan para no perder el acorde.

    En una parte de varios pentagramas (piano) cada mano es un ataque distinto: `notas` son las
    del pentagrama principal en ese instante (el de número menor que suena: la mano derecha) y
    las de los demás pentagramas son `acompanamiento` (suenan y se muestran, pero no forman
    parte del acorde que se evalúa).
    """

    inicio_negras: float
    duracion_negras: float
    notas: Tuple[NotaEvento, ...]
    parte_id: str
    compas: Optional[int] = None
    inicio_s: float = 0.0
    duracion_s: float = 0.0
    acompanamiento: Tuple[NotaEvento, ...] = ()
    pentagrama: int = 1

    @property
    def todas_las_notas(self) -> Tuple[NotaEvento, ...]:
        return self.notas + self.acompanamiento
    @property
    def principal(self) -> NotaEvento:
        return self.notas[-1]

    @property
    def es_acorde(self) -> bool:
        return len(self.notas) > 1


@dataclass(frozen=True)
class Partitura:
    """Partitura completa: partes, tempo y avisos de importación."""

    partes: Tuple[Parte, ...]
    tempo: MapaTempo = field(default_factory=MapaTempo)
    titulo: str = ""
    ruta: Optional[str] = None
    avisos: Tuple[str, ...] = ()

    def parte(self, parte_id: str) -> Parte:
        for parte in self.partes:
            if parte.id == parte_id:
                return parte
        raise KeyError(parte_id)

    def eventos(self) -> List[Evento]:
        """Todos los eventos de todas las partes, ordenados por instante."""
        orden = {p.id: i for i, p in enumerate(self.partes)}
        todos = [e for p in self.partes for e in p.eventos]
        return sorted(todos, key=lambda e: (e.inicio_negras, orden[e.parte_id], e.pentagrama, e.voz))

    @property
    def total_notas(self) -> int:
        return sum(len(e.notas) for p in self.partes for e in p.eventos)

    @property
    def duracion_negras(self) -> float:
        return max((e.fin_negras for p in self.partes for e in p.eventos), default=0.0)

    @property
    def duracion_s(self) -> float:
        return self.tempo.segundos(self.duracion_negras)

    def linea_de_practica(self, parte_id: Optional[str] = None) -> Tuple[Ataque, ...]:
        """Secuencia de ataques de una parte (por defecto, la primera) para practicar nota a nota.

        - Las notas ligadas se suman en un único ataque.
        - Las notas que empiezan juntas en un mismo pentagrama (acordes o voces) forman un
          solo ataque. En un piano de dos pentagramas, las del pentagrama principal forman el
          ataque y las de los otros son su `acompanamiento`: las dos manos no se funden en un
          acorde por sonar a la vez.
        - Los silencios no generan ataques: quedan como huecos entre `inicio_negras`.
        - Las notas de adorno no se incluyen (no tienen duración propia).
        """
        if not self.partes:
            return ()
        parte = self.parte(parte_id) if parte_id is not None else self.partes[0]
        return tuple(_ataques_de_parte(parte, self.tempo))


@dataclass
class _Sonido:
    inicio: float
    fin: float
    nota: NotaEvento
    compas: Optional[int]
    pentagrama: int = 1


def _ataques_de_parte(parte: Parte, tempo: MapaTempo) -> List[Ataque]:
    eventos = sorted((e for e in parte.eventos if e.notas and not e.adorno),
                     key=lambda e: (e.inicio_negras, e.pentagrama, e.voz))
    sonidos: List[_Sonido] = []
    abiertas: Dict[Tuple[int, str, Numero], int] = {}
    for evento in eventos:
        for nota in evento.notas:
            clave = (evento.pentagrama, evento.voz, nota.midi)
            if nota.ligadura in (Ligadura.CONTINUACION, Ligadura.FIN):
                indice = _ligadura_abierta(abiertas, sonidos, clave, evento.inicio_negras)
                if indice is not None:
                    sonidos[indice].fin = evento.fin_negras
                    if nota.ligadura is Ligadura.FIN:
                        abiertas = {k: v for k, v in abiertas.items() if v != indice}
                    continue
            sonidos.append(_Sonido(evento.inicio_negras, evento.fin_negras, nota, evento.compas,
                                   evento.pentagrama))
            # Una continuación sin inicio encontrado también liga con la nota siguiente.
            if nota.ligadura in (Ligadura.INICIO, Ligadura.CONTINUACION):
                abiertas[clave] = len(sonidos) - 1

    grupos: Dict[float, List[_Sonido]] = {}
    for sonido in sonidos:
        grupos.setdefault(round(sonido.inicio, 9), []).append(sonido)
    ataques = []
    for inicio in sorted(grupos):
        pentagrama = min(s.pentagrama for s in grupos[inicio])
        orden = lambda s: (s.nota.sonora.midi, s.nota.escrita.midi)  # noqa: E731
        grupo = sorted((s for s in grupos[inicio] if s.pentagrama == pentagrama), key=orden)
        resto = sorted((s for s in grupos[inicio] if s.pentagrama != pentagrama), key=orden)
        principal = grupo[-1]
        duracion = principal.fin - principal.inicio
        ataques.append(Ataque(
            inicio_negras=principal.inicio,
            duracion_negras=duracion,
            notas=tuple(s.nota for s in grupo),
            parte_id=parte.id,
            compas=principal.compas,
            inicio_s=tempo.segundos(principal.inicio),
            duracion_s=tempo.duracion_segundos(principal.inicio, duracion),
            acompanamiento=tuple(s.nota for s in resto),
            pentagrama=pentagrama,
        ))
    return ataques


def _ligadura_abierta(abiertas, sonidos, clave, inicio) -> Optional[int]:
    """Ligadura abierta que termina justo en `inicio`: primero en la misma voz y, si no, en
    cualquier voz del mismo pentagrama con la misma altura."""
    candidatos = [abiertas[clave]] if clave in abiertas else []
    candidatos += [i for (pentagrama, _, midi), i in abiertas.items()
                   if pentagrama == clave[0] and midi == clave[2] and i not in candidatos]
    for indice in candidatos:
        if abs(sonidos[indice].fin - inicio) < 1e-6:
            return indice
    return None
