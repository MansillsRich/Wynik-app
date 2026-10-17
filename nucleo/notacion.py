"""
Maquetación de la partitura: de los datos importados (`nucleo.musica.Parte`) a primitivas
geométricas listas para dibujar. Sin Kivy ni dibujo: solo calcula posiciones, de modo que se
pueden probar sin abrir la interfaz.

Unidades y ejes
- Todas las distancias están en «espacios» de pentagrama (la distancia entre dos líneas).
- `x` crece hacia la derecha desde el inicio de la parte; `y` crece hacia ARRIBA y vale 0 en la
  línea central del primer pentagrama. Los pentagramas siguientes están `SEPARACION` espacios
  más abajo. Una posición vertical `pos` se cuenta en medios espacios desde la línea central
  (+1 = el espacio superior contiguo, +4 = la línea de arriba, −4 = la de abajo).
- La posición de una nota sale de su altura ESCRITA (la sonora puede diferir: guitarra, o un
  instrumento transpositor) y de la clave del pentagrama, incluido su cambio de octava.

Qué se dibuja (y qué no)
- Pentagramas, claves (y sus cambios), armadura, indicación de compás, barras de compás,
  cabezas llenas o huecas, plicas, corchetes (banderas), puntillos, silencios, ligaduras de
  unión, líneas adicionales y alteraciones (♯ ♭ ♮) según la armadura y el compás.
- Las notas se alinean verticalmente por instante entre pentagramas (las dos manos del piano).
- No se dibujan: notas de adorno, barras de corchea (se usan banderas), tresillos y otros
  grupos irregulares, ligaduras de expresión, matices, repeticiones ni cambios de compás
  irregulares (se dibujan, pero el espaciado no los distingue). Lo que el archivo no declara no
  se inventa: sin clave declarada se usa sol y se anota en `Disposicion.avisos`.

Solo usa la biblioteca estándar.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

from .musica import Altura, Clave, Evento, Ligadura, NotaEvento, Parte

SEPARACION = 12.0          # distancia entre las líneas centrales de dos pentagramas
ANCHO_CABEZA = 1.3
ALTO_CABEZA = 1.0
LARGO_PLICA = 3.5
MARGEN_INICIAL = 0.6
ANCHO_ALTERACION = 1.2
ANCHO_CLAVE = 3.2
ANCHO_CIFRA = 2.2
ANCHO_ARMADURA = 1.1
ESPACIO_BARRA = 1.4

_PASO = {"C": 0, "D": 1, "E": 2, "F": 3, "G": 4, "A": 5, "B": 6}
# Nota que define cada clave: (letra, octava de la nota que está en su línea)
_NOTA_DE_CLAVE = {"G": ("G", 4), "F": ("F", 3), "C": ("C", 4)}
CLAVE_POR_OMISION = Clave(0.0, 1, "G", 2, 0)

# Posiciones (en medios espacios desde la línea central) de los sostenidos y bemoles de la
# armadura, en el orden del círculo de quintas.
_ARMADURA_SOL = {"s": (4, 1, 5, 2, -1, 3, 0), "b": (0, 3, -1, 2, -2, 1, -3)}
_ARMADURA_FA = {"s": (2, -1, 3, 0, -3, 1, -2), "b": (-2, 1, -3, 0, -4, -1, -5)}
_ORDEN_SOSTENIDOS = "FCGDAEB"
_ORDEN_BEMOLES = "BEADGCF"

_FIGURAS = {"whole": (4.0, False, 0), "half": (2.0, True, 0), "quarter": (1.0, True, 0),
            "eighth": (0.5, True, 1), "16th": (0.25, True, 2), "32nd": (0.125, True, 3),
            "64th": (0.0625, True, 4), "breve": (8.0, False, 0)}


@dataclass(frozen=True)
class Elemento:
    """Una primitiva de dibujo. Qué campos usa cada `tipo`:

    - `linea_adicional`: de (x, y) a (x2, y).
    - `cabeza`: centro (x, y); `relleno`; `inicio` (instante) y `pentagrama`.
    - `plica`: de (x, y) a (x, y2).
    - `corchete`: nace en (x, y), `n` banderas, `direccion` +1 (plica hacia arriba) o −1.
    - `puntillo`: centro (x, y).
    - `alteracion`: texto '♯', '♭', '♮', '♯♯' o '♭♭' centrado en (x, y).
    - `silencio`: texto = figura, centro (x, y).
    - `ligadura`: arco de (x, y) a (x2, y2) hacia `direccion` (+1 arriba, −1 abajo).
    - `barra_compas`: de (x, y) a (x, y2); `texto` = número del compás.
    - `clave`: texto = signo ('G', 'F', 'C'); (x, y) = línea de la clave; `n` = cambio de octava.
    - `armadura`: texto '♯' o '♭' centrado en (x, y).
    - `cifra`: texto = numerador o denominador, centrado en (x, y).
    """

    tipo: str
    x: float
    y: float
    x2: float = 0.0
    y2: float = 0.0
    texto: str = ""
    n: int = 0
    direccion: int = 0
    relleno: bool = True
    inicio: Optional[float] = None
    pentagrama: int = 1
    desplazada: bool = False


@dataclass
class Disposicion:
    elementos: List[Elemento] = field(default_factory=list)
    ancho: float = 0.0
    pentagramas: int = 1
    columnas: Dict[float, float] = field(default_factory=dict)  # instante (negras) → x de la cabeza
    avisos: List[str] = field(default_factory=list)
    _prefijos: Dict[float, Tuple[Tuple[Elemento, ...], float]] = field(default_factory=dict)

    def y_central(self, pentagrama: int) -> float:
        return -(pentagrama - 1) * SEPARACION

    @property
    def y_max(self) -> float:
        return max([e.y for e in self.elementos] + [e.y2 for e in self.elementos if e.tipo in ("plica", "barra_compas")]
                   + [2.0])

    @property
    def y_min(self) -> float:
        return min([e.y for e in self.elementos] + [e.y2 for e in self.elementos if e.tipo in ("plica", "barra_compas")]
                   + [self.y_central(self.pentagramas) - 2.0])

    def visibles(self, x_desde: float, x_hasta: float) -> List[Elemento]:
        """Elementos que tocan [x_desde, x_hasta]."""
        return [e for e in self.elementos
                if max(e.x, e.x2) >= x_desde and min(e.x, e.x2 if e.x2 else e.x) <= x_hasta]

    def contexto(self, inicio_negras: float) -> Tuple[Tuple[Elemento, ...], float]:
        """Claves, armadura y compás vigentes en `inicio_negras`, con x desde 0, y su ancho. Es lo
        que se dibuja al margen izquierdo cuando la vista no empieza al principio."""
        vigentes = [t for t in self._prefijos if t <= inicio_negras + 1e-9]
        return self._prefijos[max(vigentes)] if vigentes else self._prefijos[min(self._prefijos)]


# ---------------------------------------------------------------------------------------
#  Alturas y claves
# ---------------------------------------------------------------------------------------

def paso_diatonico(altura: Altura) -> int:
    return altura.octava * 7 + _PASO[altura.paso]


def posicion_en_clave(altura: Altura, clave: Clave) -> int:
    """Medios espacios sobre (+) o bajo (−) la línea central del pentagrama para una nota
    ESCRITA con esa clave. La línea `clave.linea` (1 = la de abajo) tiene la nota de referencia
    de la clave (sol4, fa3 o do4), una octava más grave si hay cambio de octava de −1."""
    letra, octava = _NOTA_DE_CLAVE[clave.signo]
    referencia = (octava + clave.cambio_octava) * 7 + _PASO[letra]
    posicion_linea = 2 * (clave.linea - 3)
    return paso_diatonico(altura) - referencia + posicion_linea


def clave_vigente(parte: Parte, pentagrama: int, inicio: float) -> Optional[Clave]:
    vigente = None
    for c in parte.claves:
        if c.pentagrama == pentagrama and c.inicio_negras <= inicio + 1e-9:
            vigente = c
    return vigente


def _quintas_en(parte: Parte, inicio: float) -> int:
    quintas = 0
    for a in parte.armaduras:
        if a.inicio_negras <= inicio + 1e-9:
            quintas = a.quintas
    return quintas


def alteraciones_de_armadura(quintas: int) -> Dict[str, int]:
    """Alteración que la armadura impone a cada letra: {'F': 1, 'C': 1…} o {'B': −1…}."""
    if quintas > 0:
        return {letra: 1 for letra in _ORDEN_SOSTENIDOS[:min(quintas, 7)]}
    if quintas < 0:
        return {letra: -1 for letra in _ORDEN_BEMOLES[:min(-quintas, 7)]}
    return {}


def posiciones_de_armadura(quintas: int, clave: Clave) -> List[int]:
    """Posición de cada alteración de la armadura (en el orden en que se escriben)."""
    tabla = _ARMADURA_FA if clave.signo == "F" else _ARMADURA_SOL
    posiciones = list(tabla["s" if quintas > 0 else "b"][:min(abs(quintas), 7)])
    if clave.signo == "C":  # do: la de sol, un sexto más abajo (se mantiene en el pentagrama)
        posiciones = [p - 6 if p + 6 > 5 else p + 1 for p in posiciones]
    if clave.signo == "G" and clave.cambio_octava:
        pass  # las alteraciones de la armadura se dibujan igual con 8va
    return posiciones


def figura_de(evento: Evento) -> Tuple[str, int]:
    """(figura, puntillos): lo que dice el archivo; si no consta, la que corresponde a la
    duración (sin tuplets: una duración irregular se dibuja con la figura menor más cercana)."""
    if evento.figura in _FIGURAS:
        return evento.figura, max(0, int(evento.puntillos))
    d = evento.duracion_negras
    for nombre, (valor, _, _) in sorted(_FIGURAS.items(), key=lambda kv: -kv[1][0]):
        if d + 1e-9 >= valor:
            resto = d - valor
            puntillos = 1 if abs(resto - valor / 2) < 1e-6 else 0
            return nombre, puntillos
    return "64th", 0


def _simbolo(alteracion: int) -> str:
    return {1: "♯", -1: "♭", 0: "♮", 2: "♯♯", -2: "♭♭"}.get(alteracion, "♮")


# ---------------------------------------------------------------------------------------
#  Maquetación
# ---------------------------------------------------------------------------------------

@dataclass
class _Cabeza:
    nota: NotaEvento
    pos: int
    simbolo: str = ""
    columna: int = 0
    desplazada: bool = False


@dataclass
class _Colocado:
    evento: Evento
    figura: str
    puntillos: int
    cabezas: List[_Cabeza]
    direccion: int = 1
    dx: float = 0.0


def _ancho_de_espaciado(duracion: float) -> float:
    duracion = max(duracion, 0.125)
    return max(3.0, 3.6 + 1.6 * math.log2(duracion))


def disponer(parte: Parte) -> Disposicion:
    """Maqueta toda la parte. Si faltan datos (claves, armadura, compases), usa valores por
    omisión y lo anota en `avisos`."""
    disp = Disposicion(pentagramas=max(1, parte.pentagramas))
    eventos = [e for e in parte.eventos if not e.adorno]
    if not eventos:
        disp._prefijos[0.0] = ((), MARGEN_INICIAL)
        return disp

    claves_faltan = [p for p in range(1, disp.pentagramas + 1) if clave_vigente(parte, p, 0.0) is None]
    if claves_faltan:
        disp.avisos.append("La partitura no declara clave en el pentagrama "
                           + ", ".join(map(str, claves_faltan)) + ": se usa la clave de sol.")

    def clave(p: int, t: float) -> Clave:
        return clave_vigente(parte, p, t) or CLAVE_POR_OMISION

    inicios_compas = [i for _, i in parte.inicios_compas]
    numeros = {i: n for n, i in parte.inicios_compas}
    cambios_clave: Dict[float, List[Clave]] = {}
    for c in parte.claves:
        if c.inicio_negras > 1e-9:
            cambios_clave.setdefault(round(c.inicio_negras, 6), []).append(c)
    cambios_armadura = {round(a.inicio_negras, 6): a.quintas for a in parte.armaduras if a.inicio_negras > 1e-9}
    cambios_compas = {round(c.inicio_negras, 6): c for c in parte.compases if c.inicio_negras > 1e-9}

    def prefijo(t: float, con_compas: bool = True) -> Tuple[List[Elemento], float]:
        """Claves, armadura y compás vigentes en t, desde x = MARGEN_INICIAL."""
        elementos: List[Elemento] = []
        x = MARGEN_INICIAL
        quintas = _quintas_en(parte, t)
        ancho_claves = ANCHO_CLAVE
        for p in range(1, disp.pentagramas + 1):
            c = clave(p, t)
            elementos.append(Elemento("clave", x, disp.y_central(p) + (c.linea - 3), texto=c.signo,
                                      n=c.cambio_octava, inicio=t, pentagrama=p))
        x += ancho_claves
        if quintas:
            for p in range(1, disp.pentagramas + 1):
                for k, pos in enumerate(posiciones_de_armadura(quintas, clave(p, t))):
                    elementos.append(Elemento("armadura", x + k * ANCHO_ARMADURA, disp.y_central(p) + pos / 2.0,
                                              texto="♯" if quintas > 0 else "♭", inicio=t, pentagrama=p))
            x += abs(quintas) * ANCHO_ARMADURA + 0.8
        if con_compas:
            vigente = None
            for c in parte.compases:
                if c.inicio_negras <= t + 1e-9:
                    vigente = c
            if vigente is not None:
                for p in range(1, disp.pentagramas + 1):
                    elementos.append(Elemento("cifra", x + ANCHO_CIFRA / 2, disp.y_central(p) + 1.0,
                                              texto=str(vigente.numerador), inicio=t, pentagrama=p))
                    elementos.append(Elemento("cifra", x + ANCHO_CIFRA / 2, disp.y_central(p) - 1.0,
                                              texto=str(vigente.denominador), inicio=t, pentagrama=p))
                x += ANCHO_CIFRA + 0.6
        return elementos, x

    inicial, x = prefijo(0.0)
    disp.elementos.extend(inicial)
    disp._prefijos[0.0] = (tuple(inicial), x)

    # Instantes: notas, silencios, cambios y barras.
    instantes: Set[float] = {round(e.inicio_negras, 6) for e in eventos}
    cambios_en: Set[float] = set(cambios_clave) | set(cambios_armadura) | set(cambios_compas)
    barras = {round(i, 6) for i in inicios_compas if i > 1e-9}
    todos = sorted(instantes | barras | cambios_en)
    por_instante: Dict[float, List[Evento]] = {}
    for e in eventos:
        por_instante.setdefault(round(e.inicio_negras, 6), []).append(e)
    siguientes = {t: (todos[i + 1] if i + 1 < len(todos) else None) for i, t in enumerate(todos)}
    fin_total = max(e.fin_negras for e in eventos)

    memoria: Dict[int, Dict[Tuple[str, int], int]] = {}
    compas_de_memoria: Dict[int, float] = {}
    notas_ligables: Dict[Tuple[int, str, float], Tuple[float, float, float, int]] = {}
    ligaduras_abiertas: Dict[Tuple[int, str, float], Tuple[float, float, int]] = {}

    def inicio_del_compas(t: float) -> float:
        anteriores = [i for i in inicios_compas if i <= t + 1e-9]
        return max(anteriores) if anteriores else 0.0

    for t in todos:
        siguiente_t = siguientes[t]
        es_barra = t in barras
        hay_cambio = t in cambios_en
        if es_barra:
            disp.elementos.append(Elemento("barra_compas", x, 2.0, y2=disp.y_central(disp.pentagramas) - 2.0,
                                           texto=str(numeros.get(next((n for n, i in parte.inicios_compas
                                                                       if abs(i - t) < 1e-6), 0), "")),
                                           inicio=t))
            x += ESPACIO_BARRA
        if hay_cambio:
            if t in cambios_clave:
                for c in cambios_clave[t]:
                    disp.elementos.append(Elemento("clave", x, disp.y_central(c.pentagrama) + (c.linea - 3),
                                                   texto=c.signo, n=c.cambio_octava, inicio=t,
                                                   pentagrama=c.pentagrama))
                x += ANCHO_CLAVE * 0.8
            if t in cambios_armadura:
                quintas = cambios_armadura[t]
                for p in range(1, disp.pentagramas + 1):
                    for k, pos in enumerate(posiciones_de_armadura(quintas, clave(p, t))):
                        disp.elementos.append(Elemento("armadura", x + k * ANCHO_ARMADURA,
                                                       disp.y_central(p) + pos / 2.0,
                                                       texto="♯" if quintas > 0 else "♭", inicio=t, pentagrama=p))
                x += abs(quintas) * ANCHO_ARMADURA + 0.8
            if t in cambios_compas:
                c = cambios_compas[t]
                for p in range(1, disp.pentagramas + 1):
                    disp.elementos.append(Elemento("cifra", x + ANCHO_CIFRA / 2, disp.y_central(p) + 1.0,
                                                   texto=str(c.numerador), inicio=t, pentagrama=p))
                    disp.elementos.append(Elemento("cifra", x + ANCHO_CIFRA / 2, disp.y_central(p) - 1.0,
                                                   texto=str(c.denominador), inicio=t, pentagrama=p))
                x += ANCHO_CIFRA + 0.6
            elementos_nuevos, ancho = prefijo(t)
            disp._prefijos[t] = (tuple(elementos_nuevos), ancho)
        if t not in instantes:
            continue

        # --- colocar los eventos de este instante, pentagrama por pentagrama
        mem_compas = inicio_del_compas(t)
        colocados: List[_Colocado] = []
        for e in sorted(por_instante[t], key=lambda e: (e.pentagrama, e.voz)):
            figura, puntillos = figura_de(e)
            cabezas: List[_Cabeza] = []
            if e.notas:
                c = clave(e.pentagrama, t)
                recuerdo = memoria.setdefault(e.pentagrama, {})
                if compas_de_memoria.get(e.pentagrama) != mem_compas:
                    recuerdo.clear()
                    compas_de_memoria[e.pentagrama] = mem_compas
                armadura = alteraciones_de_armadura(_quintas_en(parte, t))
                for nota in sorted(e.notas, key=lambda n: posicion_en_clave(n.escrita, c)):
                    altura = nota.escrita
                    alteracion = int(round(altura.alteracion))
                    clave_mem = (altura.paso, altura.octava)
                    vigente = recuerdo.get(clave_mem, armadura.get(altura.paso, 0))
                    simbolo = ""
                    continua = nota.ligadura in (Ligadura.FIN, Ligadura.CONTINUACION)
                    if alteracion != vigente and not continua:
                        simbolo = _simbolo(alteracion)
                    recuerdo[clave_mem] = alteracion
                    cabezas.append(_Cabeza(nota, posicion_en_clave(altura, c), simbolo))
            colocados.append(_Colocado(e, figura, puntillos, cabezas))

        # direcciones de plica y desplazamiento de segundas
        voces_por_pentagrama: Dict[int, List[str]] = {}
        for e in eventos:
            voces_por_pentagrama.setdefault(e.pentagrama, [])
            if e.voz not in voces_por_pentagrama[e.pentagrama]:
                voces_por_pentagrama[e.pentagrama].append(e.voz)
        for cab in colocados:
            if not cab.cabezas:
                continue
            voces = sorted(voces_por_pentagrama.get(cab.evento.pentagrama, []))
            if len(voces) > 1:
                cab.direccion = 1 if voces.index(cab.evento.voz) % 2 == 0 else -1
            else:
                extremo = max((h.pos for h in cab.cabezas), key=abs)
                cab.direccion = 1 if extremo < 0 else -1
            _desplazar_segundas(cab)

        # columnas de alteraciones: arriba abajo, la primera columna libre
        ancho_alteraciones = 0.0
        for cab in colocados:
            usadas: List[Tuple[int, int]] = []
            for h in sorted(cab.cabezas, key=lambda h: -h.pos):
                if not h.simbolo:
                    continue
                columna = 0
                while any(c == columna and abs(p - h.pos) <= 5 for p, c in usadas):
                    columna += 1
                h.columna = columna
                usadas.append((h.pos, columna))
            if usadas:
                ancho_alteraciones = max(ancho_alteraciones, (max(c for _, c in usadas) + 1) * ANCHO_ALTERACION + 0.3)
        x_cabeza = x + ancho_alteraciones + ANCHO_CABEZA / 2
        disp.columnas[t] = x_cabeza

        # voces que se pisan en un mismo pentagrama
        _separar_voces(colocados)

        mayor_ancho_post = 0.0
        for cab in colocados:
            _emitir(disp, cab, x_cabeza + cab.dx, t, ligaduras_abiertas, clave(cab.evento.pentagrama, t), parte)
            extra = cab.puntillos * 0.9 + (ANCHO_CABEZA if any(h.desplazada for h in cab.cabezas) else 0)
            mayor_ancho_post = max(mayor_ancho_post, extra + cab.dx)
        duracion = ((siguiente_t - t) if siguiente_t is not None else (fin_total - t))
        if siguiente_t is not None and siguiente_t in barras and siguiente_t not in instantes:
            duracion = siguiente_t - t
        x = x_cabeza + max(_ancho_de_espaciado(duracion), 1.8 + mayor_ancho_post)

    # ligaduras que quedaron abiertas hasta el final: no se dibujan (no hay destino)
    disp.ancho = x + 1.0
    return disp


def _desplazar_segundas(cab: _Colocado) -> None:
    """Segundas (notas contiguas): la cabeza que molesta pasa al otro lado de la plica."""
    cabezas = sorted(cab.cabezas, key=lambda h: h.pos, reverse=cab.direccion < 0)
    anterior = None
    for h in cabezas:
        if anterior is not None and abs(h.pos - anterior.pos) == 1 and not anterior.desplazada:
            h.desplazada = True
        anterior = h


def _separar_voces(colocados: List[_Colocado]) -> None:
    """Dos voces de un pentagrama en el mismo instante: si sus cabezas se tocan, la segunda se
    corre a la derecha."""
    por_pentagrama: Dict[int, List[_Colocado]] = {}
    for cab in colocados:
        if cab.cabezas:
            por_pentagrama.setdefault(cab.evento.pentagrama, []).append(cab)
    for lista in por_pentagrama.values():
        for i, cab in enumerate(lista[1:], start=1):
            posiciones_previas = [h.pos for otra in lista[:i] for h in otra.cabezas]
            if any(abs(h.pos - p) <= 1 for h in cab.cabezas for p in posiciones_previas):
                cab.dx = ANCHO_CABEZA * 1.1


def _emitir(disp: Disposicion, cab: _Colocado, x: float, t: float, abiertas, clave: Clave,
            parte: Parte) -> None:
    e = cab.evento
    y0 = disp.y_central(e.pentagrama)
    figura = cab.figura
    if not cab.cabezas:  # silencio
        desplazamiento = 0.0
        voces = sorted({o.voz for o in parte.eventos if o.pentagrama == e.pentagrama})
        if len(voces) > 1:
            desplazamiento = 2.0 if voces.index(e.voz) % 2 == 0 else -2.0
        disp.elementos.append(Elemento("silencio", x, y0 + desplazamiento, texto=figura, inicio=t,
                                       pentagrama=e.pentagrama))
        for k in range(cab.puntillos):
            disp.elementos.append(Elemento("puntillo", x + 1.1 + 0.7 * k, y0 + desplazamiento + 0.5, inicio=t,
                                           pentagrama=e.pentagrama))
        return
    _, con_plica, banderas = _FIGURAS[figura]
    relleno = figura not in ("whole", "half", "breve")
    posiciones = [h.pos for h in cab.cabezas]
    lineas: Set[int] = set()
    for h in cab.cabezas:
        if h.pos >= 6:
            lineas.update(range(6, h.pos + 1, 2))
        if h.pos <= -6:
            lineas.update(range(-6, h.pos - 1, -2))
    for pos in sorted(lineas):
        disp.elementos.append(Elemento("linea_adicional", x - 0.95, y0 + pos / 2.0, x2=x + 0.95 + (ANCHO_CABEZA if
                                       any(h.desplazada for h in cab.cabezas) else 0.0),
                                       inicio=t, pentagrama=e.pentagrama))
    for h in cab.cabezas:
        xh = x
        if h.desplazada:
            xh = x + (ANCHO_CABEZA if cab.direccion > 0 else -ANCHO_CABEZA) * 1.0
        yh = y0 + h.pos / 2.0
        disp.elementos.append(Elemento("cabeza", xh, yh, relleno=relleno, inicio=t, pentagrama=e.pentagrama,
                                       desplazada=h.desplazada))
        if h.simbolo:
            disp.elementos.append(Elemento("alteracion", x - ANCHO_CABEZA / 2 - 0.85 - h.columna * ANCHO_ALTERACION,
                                           yh, texto=h.simbolo, inicio=t, pentagrama=e.pentagrama))
        for k in range(cab.puntillos):
            pos_punto = h.pos if h.pos % 2 else h.pos + 1  # el punto va en un espacio, no en una línea
            disp.elementos.append(Elemento("puntillo", xh + ANCHO_CABEZA / 2 + 0.6 + 0.7 * k,
                                           y0 + pos_punto / 2.0, inicio=t, pentagrama=e.pentagrama))
    if con_plica:
        if cab.direccion > 0:
            xp = x + ANCHO_CABEZA / 2 - 0.05
            y_base = y0 + min(posiciones) / 2.0
            y_fin = y0 + max(max(posiciones) / 2.0 + LARGO_PLICA, 0.0)
        else:
            xp = x - ANCHO_CABEZA / 2 + 0.05
            y_base = y0 + max(posiciones) / 2.0
            y_fin = y0 + min(min(posiciones) / 2.0 - LARGO_PLICA, 0.0)
        disp.elementos.append(Elemento("plica", xp, y_base, y2=y_fin, inicio=t, pentagrama=e.pentagrama,
                                       direccion=cab.direccion))
        if banderas:
            disp.elementos.append(Elemento("corchete", xp, y_fin, n=banderas, direccion=cab.direccion,
                                           inicio=t, pentagrama=e.pentagrama))
    # ligaduras de unión: se abren en la nota que empieza y se cierran en la siguiente igual
    for h in cab.cabezas:
        clave_lig = (e.pentagrama, e.voz, float(h.nota.midi))
        xh = x + (((ANCHO_CABEZA if cab.direccion > 0 else -ANCHO_CABEZA) * 1.0) if h.desplazada else 0.0)
        yh = y0 + h.pos / 2.0
        if clave_lig in abiertas:
            x_ini, y_ini, dir_ini = abiertas.pop(clave_lig)
            disp.elementos.append(Elemento("ligadura", x_ini + 0.7, y_ini + dir_ini * 0.55, x2=xh - 0.7,
                                           y2=yh + dir_ini * 0.55, direccion=dir_ini, inicio=t,
                                           pentagrama=e.pentagrama))
        if h.nota.ligadura in (Ligadura.INICIO, Ligadura.CONTINUACION):
            abiertas[clave_lig] = (xh, yh, -cab.direccion)


def altura_total(disp: Disposicion, x_desde: float, x_hasta: float) -> Tuple[float, float]:
    """(y_max, y_min) de lo que se dibuja entre x_desde y x_hasta, incluidos los pentagramas."""
    visibles = disp.visibles(x_desde, x_hasta)
    arriba = [2.0] + [e.y for e in visibles if e.tipo not in ("barra_compas",)] \
        + [e.y2 for e in visibles if e.tipo == "plica"]
    abajo = [disp.y_central(disp.pentagramas) - 2.0] + [e.y for e in visibles if e.tipo not in ("barra_compas",)] \
        + [e.y2 for e in visibles if e.tipo == "plica"]
    return max(arriba), min(abajo)



FRACCION_ANTES = 0.30   # de lo visible, lo que queda a la izquierda de la nota actual


def tramo_visible(disp, tiempo, ancho_espacios):
    """(izquierda, derecha, contexto, ancho_contexto) del fragmento que rodea a `tiempo`.

    - La nota de ese instante queda a `FRACCION_ANTES` del ancho visible, y se ve la anterior.
    - Si el tramo empieza al principio de la parte, se dibuja todo desde el principio y no hay
      contexto aparte. Si no, el contexto son las claves, armadura y compás vigentes (que se
      dibujan al margen izquierdo) y `ancho_contexto` lo que ocupan.
    """
    if disp is None:
        return 0.0, ancho_espacios, (), 0.0
    clave = min(disp.columnas, key=lambda t: abs(t - tiempo)) if disp.columnas else None
    x_actual = disp.columnas.get(clave, 0.0) if clave is not None else 0.0
    inicial, ancho_inicial = disp.contexto(0.0)
    izquierda = x_actual - FRACCION_ANTES * ancho_espacios
    if izquierda <= ancho_inicial * 0.5:
        return 0.0, ancho_espacios, (), 0.0
    tiempos_antes = [t for t, x in disp.columnas.items() if x <= izquierda]
    t_ref = max(tiempos_antes) if tiempos_antes else 0.0
    contexto, ancho = disp.contexto(t_ref)
    return izquierda, izquierda + ancho_espacios - ancho, contexto, ancho


__all__ = ["CLAVE_POR_OMISION", "Disposicion", "Elemento", "SEPARACION", "alteraciones_de_armadura",
           "altura_total", "clave_vigente", "disponer", "figura_de", "paso_diatonico",
           "posicion_en_clave", "posiciones_de_armadura", "tramo_visible"]
