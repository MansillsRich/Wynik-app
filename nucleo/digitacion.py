"""
Guía visual para tocar una nota o un acorde: posiciones en la guitarra y teclas del piano.

Todo se calcula a partir de alturas sonoras (MIDI) y de la afinación configurada, de forma
verificable: la cuerda c al aire más el traste t suena exactamente afinacion[c] + t.

Guitarra
- `posiciones_guitarra`: todas las posiciones (cuerda, traste) que producen una altura.
- `posicion_sugerida`: sin contexto, la del traste más bajo; con la posición anterior, la
  más cercana a ella. Un dedo solo se indica cuando la convención es inequívoca: cuerda al
  aire (0) o primera posición, un dedo por traste (trastes 1–4 → dedos 1–4). En otras
  posiciones depende de la mano y no se inventa.
- `acorde_guitarra`: si las alturas coinciden exactamente con una forma abierta estándar
  (afinación estándar) o con una forma móvil con cejilla (Mi y La, mayor, menor y séptima,
  del traste 1 al 12), se devuelve con su digitación habitual y su cejilla (`validado=True`).
  Una forma móvil solo se acepta si las alturas que produce, calculadas con la afinación, son
  exactamente las del acorde: la digitación viene de una tabla curada, nunca se deduce. Si no,
  se busca una colocación tocable (una nota por cuerda, cuerdas contiguas, a lo sumo cuatro
  dedos y ≤ 3 trastes de apertura) sin digitación (`validado=False`). Si no existe, `None`:
  la interfaz muestra las notas y avisa de que no hay propuesta validada.

Piano
- `rango_teclado`: teclas que conviene dibujar para ver las notas en su octava.
- `digitacion_piano`: solo para tríadas en posición fundamental y cerrada (1-3-5 con la mano
  derecha, 5-3-1 con la izquierda), la digitación de los métodos de iniciación. En los demás
  casos no se propone ninguna.

Solo usa la biblioteca estándar.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from .instrumentos import AFINACIONES_GUITARRA
from .musica import Altura, midi_mas_cercano

TRASTES_GUITARRA = 19
APERTURA_MAXIMA_TRASTES = 3  # traste más alto − más bajo (sin contar cuerdas al aire)
MAXIMO_DEDOS = 4             # una colocación calculada sin cejilla no pide más dedos que la mano


@dataclass(frozen=True)
class PosicionGuitarra:
    cuerda: int          # 1 = la más aguda, 6 = la más grave
    traste: int          # 0 = al aire
    midi: int
    dedo: Optional[int] = None  # 0 al aire, 1–4, o None si no se puede determinar

    @property
    def al_aire(self) -> bool:
        return self.traste == 0

    def descripcion(self) -> str:
        if self.al_aire:
            return f"Cuerda {self.cuerda} al aire"
        texto = f"Cuerda {self.cuerda}, traste {self.traste}"
        if self.dedo:
            texto += f" (dedo {self.dedo})"
        return texto


def _afinacion(afinacion) -> Tuple[int, ...]:
    if isinstance(afinacion, str):
        return AFINACIONES_GUITARRA[afinacion]
    return tuple(int(m) for m in afinacion)


def posiciones_guitarra(midi, afinacion="estandar", trastes: int = TRASTES_GUITARRA
                        ) -> List[PosicionGuitarra]:
    """Posiciones que producen la altura sonora `midi`, del traste más bajo al más alto."""
    objetivo = midi_mas_cercano(midi)
    resultado = []
    for cuerda, al_aire in enumerate(_afinacion(afinacion), start=1):
        traste = objetivo - al_aire
        if 0 <= traste <= trastes:
            resultado.append(PosicionGuitarra(cuerda, traste, objetivo))
    return sorted(resultado, key=lambda p: (p.traste, p.cuerda))


def _con_dedo(posicion: PosicionGuitarra, primera_posicion: bool) -> PosicionGuitarra:
    if posicion.traste == 0:
        dedo = 0
    elif posicion.traste <= 4 and primera_posicion:
        dedo = posicion.traste
    else:
        dedo = None
    return PosicionGuitarra(posicion.cuerda, posicion.traste, posicion.midi, dedo)


def posicion_sugerida(midi, afinacion="estandar", trastes: int = TRASTES_GUITARRA,
                      anterior: Optional[PosicionGuitarra] = None) -> Optional[PosicionGuitarra]:
    """La posición más sencilla (traste más bajo) o, si se conoce la anterior, la más
    cercana a ella. None si la nota no existe en la guitarra con esa afinación."""
    candidatas = posiciones_guitarra(midi, afinacion, trastes)
    if not candidatas:
        return None
    if anterior is None or anterior.traste == 0:
        elegida = candidatas[0]
    else:
        elegida = min(candidatas, key=lambda p: (abs(p.traste - anterior.traste) if p.traste else 99,
                                                 p.traste, p.cuerda))
    primera = elegida.traste <= 4 and (anterior is None or anterior.traste <= 4)
    return _con_dedo(elegida, primera)


def alternativas_guitarra(midi, afinacion="estandar", trastes: int = TRASTES_GUITARRA,
                          elegida: Optional[PosicionGuitarra] = None) -> List[PosicionGuitarra]:
    return [p for p in posiciones_guitarra(midi, afinacion, trastes)
            if elegida is None or (p.cuerda, p.traste) != (elegida.cuerda, elegida.traste)]


# ---------------------------------------------------------------------------------------------
#  Acordes de guitarra
# ---------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Cejilla:
    """Un dedo que pisa varias cuerdas contiguas en el mismo traste (de la más grave, `desde`, a
    la más aguda, `hasta`; la 6.ª es la más grave)."""

    traste: int
    cuerda_desde: int
    cuerda_hasta: int
    dedo: int = 1

    def cubre(self, cuerda: int, traste: int) -> bool:
        return traste == self.traste and self.cuerda_hasta <= cuerda <= self.cuerda_desde


@dataclass(frozen=True)
class DiagramaAcorde:
    """Trastes y dedos por cuerda, de la 6.ª (grave) a la 1.ª (aguda). None = no se toca.

    - `cejillas`: las cejillas de la digitación (vacío si no hay o si no se conocen).
    - `traste_base`: el traste más bajo que se pisa (None si todo es al aire).
    - `fuente`: 'forma_abierta' y 'forma_movil' (tabla curada, con digitación), o 'calculada'
      (solo posiciones: no se afirma que sea la digitación habitual ni que esté verificada).
    """

    nombre: str
    trastes: Tuple[Optional[int], ...]
    dedos: Optional[Tuple[Optional[int], ...]]
    validado: bool
    cejillas: Tuple[Cejilla, ...] = ()
    traste_base: Optional[int] = None
    fuente: str = "calculada"

    def alturas(self, afinacion="estandar") -> List[int]:
        cuerdas = list(reversed(_afinacion(afinacion)))  # 6.ª … 1.ª
        return [cuerdas[i] + t for i, t in enumerate(self.trastes) if t is not None]

    @property
    def origen(self) -> str:
        if not self.validado:
            return "posiciones calculadas"
        return "forma móvil con cejilla" if self.fuente == "forma_movil" else "forma estándar"

    def dedos_necesarios(self) -> int:
        """Dedos distintos que pide la digitación (una cejilla cuenta como uno)."""
        if self.dedos is not None:
            return len({d for d in self.dedos if d})
        return sum(1 for t in self.trastes if t)


# Formas abiertas en afinación estándar con su digitación habitual (6.ª → 1.ª; None: no se
# toca; dedo 0: al aire). Son las de cualquier método de iniciación.
FORMAS_ABIERTAS: Dict[str, Tuple[Tuple[Optional[int], ...], Tuple[Optional[int], ...]]] = {
    "Do mayor (C)": ((None, 3, 2, 0, 1, 0), (None, 3, 2, 0, 1, 0)),
    "La mayor (A)": ((None, 0, 2, 2, 2, 0), (None, 0, 1, 2, 3, 0)),
    "Sol mayor (G)": ((3, 2, 0, 0, 0, 3), (2, 1, 0, 0, 0, 3)),
    "Mi mayor (E)": ((0, 2, 2, 1, 0, 0), (0, 2, 3, 1, 0, 0)),
    "Re mayor (D)": ((None, None, 0, 2, 3, 2), (None, None, 0, 1, 3, 2)),
    "La menor (Am)": ((None, 0, 2, 2, 1, 0), (None, 0, 2, 3, 1, 0)),
    "Mi menor (Em)": ((0, 2, 2, 0, 0, 0), (0, 2, 3, 0, 0, 0)),
    "Re menor (Dm)": ((None, None, 0, 2, 3, 1), (None, None, 0, 2, 3, 1)),
    "Mi séptima (E7)": ((0, 2, 0, 1, 0, 0), (0, 2, 0, 1, 0, 0)),
    "La séptima (A7)": ((None, 0, 2, 0, 2, 0), (None, 0, 2, 0, 3, 0)),
    "Re séptima (D7)": ((None, None, 0, 2, 1, 2), (None, None, 0, 2, 1, 3)),
    "Sol séptima (G7)": ((3, 2, 0, 0, 0, 1), (3, 2, 0, 0, 0, 1)),
    "Do séptima (C7)": ((None, 3, 2, 3, 1, 0), (None, 3, 2, 4, 1, 0)),
    "Si séptima (B7)": ((None, 2, 1, 2, 0, 2), (None, 2, 1, 3, 0, 4)),
}


# Formas móviles con cejilla (6.ª → 1.ª). Los trastes son relativos al de la cejilla (0 = el
# traste de la cejilla); `dedos` es la digitación habitual de los métodos de iniciación;
# `cuerda_desde` es la cuerda más grave que cubre la cejilla (1.er dedo). La calidad y el
# traste dan el nombre; la raíz sale de la cuerda grave de la forma.
FORMAS_MOVILES: Dict[str, Tuple[Tuple[Optional[int], ...], Tuple[Optional[int], ...], int, int, str]] = {
    "mayor, forma de Mi": ((0, 2, 2, 1, 0, 0), (1, 3, 4, 2, 1, 1), 6, 6, "mayor"),
    "menor, forma de Mi": ((0, 2, 2, 0, 0, 0), (1, 3, 4, 1, 1, 1), 6, 6, "menor"),
    "séptima, forma de Mi": ((0, 2, 0, 1, 0, 0), (1, 3, 1, 2, 1, 1), 6, 6, "séptima"),
    "mayor, forma de La": ((None, 0, 2, 2, 2, 0), (None, 1, 2, 3, 4, 1), 5, 5, "mayor"),
    "menor, forma de La": ((None, 0, 2, 2, 1, 0), (None, 1, 3, 4, 2, 1), 5, 5, "menor"),
    "séptima, forma de La": ((None, 0, 2, 0, 2, 0), (None, 1, 3, 1, 4, 1), 5, 5, "séptima"),
}
_NOMBRES_RAIZ = {0: "Do", 1: "Re♭", 2: "Re", 3: "Mi♭", 4: "Mi", 5: "Fa", 6: "Fa♯", 7: "Sol", 8: "La♭", 9: "La",
                 10: "Si♭", 11: "Si"}
TRASTE_MAXIMO_FORMA_MOVIL = 12


def formas_moviles(afinacion="estandar") -> List[DiagramaAcorde]:
    """Todas las formas móviles con cejilla (traste 1 al 12) que caben en el mástil. Cada una
    lleva su cejilla y su digitación; las alturas se calculan con la afinación dada."""
    cuerdas = list(reversed(_afinacion(afinacion)))  # 6.ª … 1.ª
    resultado = []
    for nombre_forma, (relativos, dedos, cuerda_raiz, cuerda_desde, calidad) in FORMAS_MOVILES.items():
        for traste in range(1, TRASTE_MAXIMO_FORMA_MOVIL + 1):
            absolutos = tuple(None if r is None else traste + r for r in relativos)
            if max(t for t in absolutos if t is not None) > TRASTES_GUITARRA:
                continue
            raiz = (cuerdas[6 - cuerda_raiz] + traste) % 12
            nombre = f"{_NOMBRES_RAIZ[raiz]} {calidad} ({nombre_forma.split(', ')[1]}, cejilla en el traste {traste})"
            cejilla = Cejilla(traste, cuerda_desde, 1, 1)
            resultado.append(DiagramaAcorde(nombre, absolutos, dedos, True, (cejilla,), traste, "forma_movil"))
    return resultado


def acorde_guitarra(midis: Sequence[float], afinacion="estandar",
                    trastes: int = TRASTES_GUITARRA) -> Optional[DiagramaAcorde]:
    """Diagrama para tocar exactamente estas alturas sonoras, o None si no hay uno tocable."""
    objetivo = sorted(midi_mas_cercano(m) for m in midis)
    if not objetivo or len(objetivo) > 6:
        return None
    if _afinacion(afinacion) == AFINACIONES_GUITARRA["estandar"]:
        for nombre, (forma, dedos) in FORMAS_ABIERTAS.items():
            diagrama = DiagramaAcorde(nombre, forma, dedos, True, fuente="forma_abierta")
            if sorted(diagrama.alturas(afinacion)) == objetivo:
                return diagrama
    for diagrama in formas_moviles(afinacion):  # del traste más bajo al más alto
        if sorted(diagrama.alturas(afinacion)) == objetivo:
            return diagrama
    return _colocacion_calculada(objetivo, afinacion, trastes)


def _colocacion_calculada(objetivo: List[int], afinacion, trastes: int) -> Optional[DiagramaAcorde]:
    opciones = [posiciones_guitarra(m, afinacion, trastes) for m in objetivo]
    if any(not o for o in opciones):
        return None
    mejor, mejor_clave = None, None
    for combinacion in itertools.product(*opciones):
        cuerdas = [p.cuerda for p in combinacion]
        if len(set(cuerdas)) != len(cuerdas):
            continue
        pisadas = [p.traste for p in combinacion if p.traste > 0]
        apertura = (max(pisadas) - min(pisadas)) if pisadas else 0
        if apertura > APERTURA_MAXIMA_TRASTES or len(pisadas) > MAXIMO_DEDOS:
            continue
        usadas = sorted(cuerdas)  # una cuerda interior sin tocar obligaría a silenciarla con otro dedo
        if usadas[-1] - usadas[0] + 1 != len(usadas):
            continue
        # Notas graves en cuerdas graves (orden natural), apertura y altura en el mástil mínimas.
        desorden = sum(1 for a, b in zip(combinacion, combinacion[1:]) if a.cuerda < b.cuerda)
        clave = (desorden, max(pisadas, default=0), apertura, sum(cuerdas))
        if mejor_clave is None or clave < mejor_clave:
            mejor, mejor_clave = combinacion, clave
    if mejor is None:
        return None
    por_cuerda: List[Optional[int]] = [None] * 6
    for p in mejor:
        por_cuerda[6 - p.cuerda] = p.traste
    nombres = " ".join(Altura.desde_midi(m).nombre for m in objetivo)
    pisados = [t for t in por_cuerda if t]
    return DiagramaAcorde(nombres, tuple(por_cuerda), None, False, (), min(pisados) if pisados else None)


# ---------------------------------------------------------------------------------------------
#  Piano
# ---------------------------------------------------------------------------------------------

_NEGRAS = {1, 3, 6, 8, 10}
PIANO_MIDI_MIN, PIANO_MIDI_MAX = 21, 108


def es_tecla_negra(midi: int) -> bool:
    return midi_mas_cercano(midi) % 12 in _NEGRAS


def rango_teclado(midis: Sequence[float], octavas_minimas: int = 2) -> Tuple[int, int]:
    """Primera y última tecla (MIDI) a dibujar: de un Do a un Si, con las notas dentro y al
    menos `octavas_minimas` octavas, sin salir del piano (A0–C8)."""
    alturas = [midi_mas_cercano(m) for m in midis] or [60]
    bajo = (min(alturas) // 12) * 12
    alto = (max(alturas) // 12) * 12 + 11
    while (alto - bajo + 1) < 12 * octavas_minimas:
        margen_abajo, margen_arriba = min(alturas) - bajo, alto - max(alturas)
        if margen_abajo <= margen_arriba and bajo - 12 >= 12:
            bajo -= 12
        elif alto + 12 <= 131:
            alto += 12
        else:
            bajo -= 12
    return max(bajo, PIANO_MIDI_MIN), min(alto, PIANO_MIDI_MAX)


_TRIADAS_FUNDAMENTAL = {(4, 7), (3, 7), (3, 6), (4, 8)}


def digitacion_piano(midis: Sequence[float], mano: str = "derecha") -> Optional[Tuple[int, ...]]:
    """Dedos (1 = pulgar … 5 = meñique) para las notas ordenadas de grave a aguda, solo si es
    una tríada cerrada en posición fundamental; None en cualquier otro caso."""
    alturas = sorted(set(midi_mas_cercano(m) for m in midis))
    if len(alturas) != 3:
        return None
    intervalos = (alturas[1] - alturas[0], alturas[2] - alturas[0])
    if intervalos not in _TRIADAS_FUNDAMENTAL:
        return None
    return (1, 3, 5) if mano == "derecha" else (5, 3, 1)
