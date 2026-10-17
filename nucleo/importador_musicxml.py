"""
Importador de MusicXML (.musicxml, .xml y .mxl) al modelo de `nucleo.musica`.

- music21 se importa solo al leer un archivo: importar este módulo no lo carga.
- Conserva partes, pentagramas, voces, silencios, duraciones, ligaduras, acordes, notas de
  adorno y cambios de tempo. No expande repeticiones: el orden es el escrito.
- Altura sonora = altura escrita + transposición declarada con <transpose> (music21 la
  guarda en el instrumento de la parte). La clave con cambio de octava (por ejemplo, sol
  octava baja) solo indica cómo se dibuja: nunca se aplica como transposición, para no
  transponer dos veces.
- Guitarra sin <transpose>: el archivo no dice si está escrita una octava por encima de como
  suena. Si solo una de las dos lecturas cabe en el rango sonoro de la guitarra, se usa esa;
  si caben las dos, se conservan las alturas del archivo y se avisa, salvo que el perfil
  indique la convención (parámetro `convencion_guitarra`, que la interfaz ofrece como una
  elección sencilla; el texto de los avisos nunca nombra el parámetro).
"""

from __future__ import annotations

import os
import re
from typing import Dict, Iterator, List, Optional, Tuple

from nucleo.instrumentos import GUITARRA, perfil_por_nombre
from nucleo.musica import (Altura, Armadura, CambioTempo, Clave, Compas, Evento, Ligadura, MapaTempo, NotaEvento,
                           OrigenTransposicion, Parte, Partitura, Transposicion)

EXTENSIONES = (".musicxml", ".xml", ".mxl")
CONVENCIONES_GUITARRA = ("auto", "sonora", "escrita_octava_alta")

_LIGADURAS = {"start": Ligadura.INICIO, "continue": Ligadura.CONTINUACION, "stop": Ligadura.FIN}
_PENTAGRAMA_EN_ID = re.compile(r"^(.*)-Staff(\d+)$")


class ErrorPartitura(ValueError):
    """El archivo no tiene un formato admitido o no se puede interpretar como MusicXML."""


def extension_admitida(ruta: str) -> bool:
    return bool(ruta) and os.path.splitext(ruta.lower())[1] in EXTENSIONES


def importar_musicxml(ruta: str, convencion_guitarra: str = "auto",
                      bpm_por_defecto: float = 120.0) -> Partitura:
    """Lee un archivo MusicXML y devuelve la `Partitura` estructurada.

    - `convencion_guitarra`: 'auto' (decidir por el archivo y el rango), 'sonora' (las alturas
      del archivo ya son las que suenan) o 'escrita_octava_alta' (suenan una octava más abajo).
      Solo se usa en partes de guitarra sin <transpose>.
    - `bpm_por_defecto`: tempo en negras por minuto si la partitura no lo indica.

    Errores: `FileNotFoundError` si el archivo no existe; `ErrorPartitura` si la extensión no
    es admitida o el contenido no se puede interpretar.
    """
    if convencion_guitarra not in CONVENCIONES_GUITARRA:
        raise ValueError(f"Convención de guitarra no válida: {convencion_guitarra!r}")
    if not ruta or not os.path.isfile(ruta):
        raise FileNotFoundError(f"No se encontró el archivo de partitura: {ruta}")
    nombre = os.path.basename(ruta)
    if not extension_admitida(ruta):
        raise ErrorPartitura(f"«{nombre}»: formato no admitido; se esperan .musicxml, .xml o .mxl")
    try:
        from music21 import converter
        puntuacion = converter.parse(ruta, forceSource=True)
    except Exception as error:  # music21 lanza tipos distintos según el fallo
        raise ErrorPartitura(f"No se pudo leer «{nombre}» como MusicXML ({_resumen(error)})") from error
    if getattr(puntuacion, "parts", None) is None:
        raise ErrorPartitura(f"«{nombre}» no contiene una partitura MusicXML")
    try:
        return _convertir(puntuacion, ruta, convencion_guitarra, bpm_por_defecto)
    except ErrorPartitura:
        raise
    except Exception as error:
        raise ErrorPartitura(f"No se pudo interpretar «{nombre}» ({_resumen(error)})") from error


def _resumen(error: Exception) -> str:
    texto = " ".join(str(error).split())
    return f"{type(error).__name__}: {texto[:200]}" if texto else type(error).__name__


# ---------------------------------------------------------------------------------------------
#  Conversión
# ---------------------------------------------------------------------------------------------

def _convertir(puntuacion, ruta: str, convencion: str, bpm: float) -> Partitura:
    avisos: List[str] = []
    grupos: Dict[str, List] = {}
    nombres: Dict[str, str] = {}
    for indice, m21_parte in enumerate(puntuacion.parts):
        parte_id = _id_de_parte(m21_parte, indice)
        grupos.setdefault(parte_id, []).append(m21_parte)
        instrumento = m21_parte.getInstrument(returnDefault=False)
        nombres.setdefault(parte_id, m21_parte.partName
                           or getattr(instrumento, "instrumentName", None) or parte_id)

    mapa = _mapa_tempo(puntuacion, bpm, avisos)
    partes = tuple(_convertir_parte(pid, nombres[pid], pentagramas, mapa, convencion, avisos)
                   for pid, pentagramas in grupos.items())
    if len(partes) > 1:
        avisos.append(f"La partitura tiene {len(partes)} partes; la práctica nota a nota usa "
                      f"por defecto la primera («{partes[0].nombre}»).")
    metadatos = getattr(puntuacion, "metadata", None)
    titulo = (getattr(metadatos, "title", None) or getattr(metadatos, "movementName", None) or "")
    return Partitura(partes, mapa, str(titulo), os.path.abspath(ruta), tuple(avisos))


def _id_de_parte(m21_parte, indice: int) -> str:
    """Identificador de la parte en el MusicXML: los pentagramas de un piano comparten id."""
    instrumento = m21_parte.getInstrument(returnDefault=False)
    if getattr(instrumento, "partId", None):
        return str(instrumento.partId)
    coincidencia = _PENTAGRAMA_EN_ID.match(str(m21_parte.id))
    if coincidencia:
        return coincidencia.group(1)
    return str(m21_parte.id) if m21_parte.id is not None else f"P{indice + 1}"


def _mapa_tempo(puntuacion, bpm: float, avisos: List[str]) -> MapaTempo:
    from music21 import tempo as m21_tempo

    cambios: Dict[float, CambioTempo] = {}
    sin_numero = 0
    for marca in puntuacion.recurse().getElementsByClass(m21_tempo.MetronomeMark):
        valor = marca.number if marca.number is not None and not marca.numberImplicit else None
        if valor is None:
            valor = getattr(marca, "numberSounding", None)
        if not valor or valor <= 0:
            sin_numero += 1
            continue
        referente = getattr(marca, "referent", None)
        negras_por_pulso = float(referente.quarterLength) if referente is not None else 1.0
        inicio = float(marca.getOffsetInHierarchy(puntuacion))
        cambios.setdefault(round(inicio, 9), CambioTempo(inicio, float(valor) * negras_por_pulso))
    if sin_numero:
        avisos.append(f"{sin_numero} indicaciones de tempo sin valor numérico no se usaron.")
    if not cambios:
        avisos.append(f"La partitura no indica el tempo; se usan {bpm:g} negras por minuto.")
    return MapaTempo(tuple(cambios.values()), bpm)


def _convertir_parte(parte_id: str, nombre: str, pentagramas_m21: List, mapa: MapaTempo,
                     convencion: str, avisos: List[str]) -> Parte:
    from music21 import chord, clef, note

    instrumento = pentagramas_m21[0].getInstrument(returnDefault=False)
    perfil = perfil_por_nombre(nombre, getattr(instrumento, "instrumentName", None),
                               getattr(instrumento, "instrumentSound", None))

    # Primera pasada: alturas escritas, transposición declarada y estructura.
    crudos = []  # (inicio, duración, [(escrita, sonora_declarada, ligadura)], pentagrama, voz, compás, adorno)
    semitonos_declarados: List[int] = []
    clave_cambio_octava = 0
    sin_altura = 0
    for pentagrama, m21_parte in enumerate(pentagramas_m21, start=1):
        intervalos = _intervalos_declarados(m21_parte)
        for c in m21_parte.recurse().getElementsByClass(clef.Clef):
            if getattr(c, "octaveChange", 0) and not clave_cambio_octava:
                clave_cambio_octava = int(c.octaveChange)
        for compas, inicio, voz, elemento in _recorrer(m21_parte):
            adorno = bool(elemento.duration.isGrace)
            duracion = 0.0 if adorno else float(elemento.quarterLength)
            figura = (str(elemento.duration.type or ""), int(elemento.duration.dots or 0))
            if isinstance(elemento, note.Rest):
                crudos.append((inicio, duracion, [], pentagrama, voz, compas, adorno, figura))
                continue
            if isinstance(elemento, chord.Chord):
                cabezas = [(n.pitch, n.tie or elemento.tie) for n in elemento.notes
                           if getattr(n, "pitch", None) is not None]
            elif isinstance(elemento, note.Note):
                cabezas = [(elemento.pitch, elemento.tie)]
            else:
                cabezas = []
            if not cabezas:  # percusión sin altura
                sin_altura += 1
                continue
            intervalo = _intervalo_en(intervalos, inicio)
            notas = []
            for pitch, tie in cabezas:
                escrita = _altura(pitch)
                sonora = None
                if intervalo is not None and intervalo.semitones != 0:
                    sonora = _altura(pitch.transpose(intervalo))
                    semitonos = int(round(intervalo.semitones))
                    if semitonos not in semitonos_declarados:
                        semitonos_declarados.append(semitonos)
                notas.append((escrita, sonora, _LIGADURAS.get(getattr(tie, "type", None))))
            crudos.append((inicio, duracion, notas, pentagrama, voz, compas, adorno, figura))
    if sin_altura:
        avisos.append(f"Parte «{nombre}»: {sin_altura} notas de percusión sin altura no se importaron.")

    # Transposición de la parte.
    if semitonos_declarados:
        lista = ", ".join(f"{s:+d}" for s in semitonos_declarados)
        transposicion = Transposicion(semitonos_declarados[0], OrigenTransposicion.DECLARADA,
                                      f"<transpose> del archivo ({lista} semitonos)")
        extra = 0
    elif perfil is GUITARRA:
        escritas = [n[0].midi for c in crudos for n in c[2]]
        transposicion = _transposicion_guitarra(escritas, convencion, clave_cambio_octava)
        extra = transposicion.semitonos
        if transposicion.origen is OrigenTransposicion.INDETERMINADA:
            avisos.append(f"Parte «{nombre}»: {transposicion.detalle}")
    else:
        transposicion = Transposicion()
        extra = 0

    # Segunda pasada: eventos con altura sonora y tiempo en segundos.
    eventos = []
    for inicio, duracion, notas, pentagrama, voz, compas, adorno, (figura, puntillos) in crudos:
        notas_evento = tuple(
            NotaEvento(escrita, sonora if sonora is not None else _desplazar_octavas(escrita, extra), ligadura)
            for escrita, sonora, ligadura in notas)
        eventos.append(Evento(inicio, duracion, notas_evento, parte_id, pentagrama, voz, compas, adorno,
                              mapa.segundos(inicio), mapa.duracion_segundos(inicio, duracion),
                              figura, puntillos))
    eventos.sort(key=lambda e: (e.inicio_negras, e.pentagrama, e.voz))
    claves, armaduras, compases, inicios_compas = _estructura_de_notacion(pentagramas_m21)
    return Parte(parte_id, nombre, tuple(eventos), len(pentagramas_m21), transposicion,
                 perfil.clave if perfil else None, clave_cambio_octava,
                 claves, armaduras, compases, inicios_compas)


def _estructura_de_notacion(pentagramas_m21: List):
    """Claves (por pentagrama), armaduras, indicaciones de compás y barras de la parte, tal
    como están en el archivo. Si el archivo no declara una clave no se inventa ninguna: el
    dibujo elige una por defecto y lo dice."""
    from music21 import clef, key, meter, stream

    claves: List[Clave] = []
    armaduras: Dict[float, int] = {}
    compases: Dict[float, Tuple[int, int]] = {}
    inicios: Dict[int, float] = {}
    for pentagrama, m21_parte in enumerate(pentagramas_m21, start=1):
        for c in m21_parte.recurse().getElementsByClass(clef.Clef):
            if getattr(c, "sign", None) in ("G", "F", "C") and getattr(c, "line", None):
                claves.append(Clave(float(c.getOffsetInHierarchy(m21_parte)), pentagrama, c.sign,
                                    int(c.line), int(getattr(c, "octaveChange", 0) or 0)))
        for k in m21_parte.recurse().getElementsByClass(key.KeySignature):
            armaduras.setdefault(float(k.getOffsetInHierarchy(m21_parte)), int(k.sharps))
        for m in m21_parte.recurse().getElementsByClass(meter.TimeSignature):
            compases.setdefault(float(m.getOffsetInHierarchy(m21_parte)), (int(m.numerator), int(m.denominator)))
        for medida in m21_parte.getElementsByClass(stream.Measure):
            if isinstance(medida.number, int):
                inicios.setdefault(medida.number, float(medida.getOffsetBySite(m21_parte)))
    # Una armadura o un compás repetido igual en cada compás o pentagrama no es un cambio.
    def sin_repetidos(mapa):
        resultado, anterior = [], None
        for inicio in sorted(mapa):
            if mapa[inicio] != anterior:
                resultado.append((inicio, mapa[inicio]))
            anterior = mapa[inicio]
        return resultado
    return (tuple(sorted(set(claves), key=lambda c: (c.inicio_negras, c.pentagrama))),
            tuple(Armadura(i, q) for i, q in sin_repetidos(armaduras)),
            tuple(Compas(i, n, d) for i, (n, d) in sin_repetidos(compases)),
            tuple(sorted(((n, i) for n, i in inicios.items()), key=lambda x: x[1])))


def _transposicion_guitarra(escritas: List, convencion: str, clave_cambio_octava: int) -> Transposicion:
    """Transposición de una guitarra cuyo archivo no tiene <transpose>."""
    if convencion == "sonora":
        return Transposicion(0, OrigenTransposicion.CONFIGURADA,
                             "configuración: las alturas del archivo ya son las que suenan")
    if convencion == "escrita_octava_alta":
        return Transposicion(GUITARRA.transposicion_escritura, OrigenTransposicion.CONFIGURADA,
                             "configuración: escrita una octava por encima de como suena")
    if clave_cambio_octava:
        return Transposicion(0, OrigenTransposicion.SIN_TRANSPOSICION,
                             "clave con cambio de octava y sin <transpose>: las alturas del archivo "
                             "son las que indica la clave")
    if not escritas:
        return Transposicion(0, OrigenTransposicion.SIN_TRANSPOSICION, "sin notas")
    tal_cual = all(GUITARRA.contiene(m) for m in escritas)
    octava_abajo = all(GUITARRA.contiene(m + GUITARRA.transposicion_escritura) for m in escritas)
    grave, agudo = Altura.desde_midi(int(min(escritas))).nombre, Altura.desde_midi(int(max(escritas))).nombre
    if tal_cual and not octava_abajo:
        return Transposicion(0, OrigenTransposicion.DEDUCIDA_POR_RANGO,
                             f"sin <transpose>; {grave}–{agudo} solo cabe en el rango de la guitarra "
                             "tal como está escrito")
    if octava_abajo and not tal_cual:
        return Transposicion(GUITARRA.transposicion_escritura, OrigenTransposicion.DEDUCIDA_POR_RANGO,
                             f"sin <transpose>; {grave}–{agudo} solo cabe en el rango de la guitarra "
                             "una octava más abajo")
    return Transposicion(0, OrigenTransposicion.INDETERMINADA,
                         f"La partitura de guitarra ({grave}–{agudo}) no indica si suena una octava más "
                         "grave de lo escrito, que es lo habitual en guitarra. Se usan las notas tal como "
                         "están escritas; si no coinciden con lo que tocas, elige «Una octava abajo» al "
                         "preparar la práctica.")


def _desplazar_octavas(altura: Altura, semitonos: int) -> Altura:
    if not semitonos:
        return altura
    return Altura(altura.paso, altura.alteracion, altura.octava + semitonos // 12)


def _altura(pitch) -> Altura:
    octava = pitch.octave if pitch.octave is not None else pitch.implicitOctave
    return Altura(pitch.step, float(pitch.alter), int(octava))


def _intervalos_declarados(m21_parte) -> List[Tuple[float, object]]:
    """Intervalos de transposición (<transpose>) de la parte, con su instante de inicio."""
    from music21 import instrument

    if m21_parte.atSoundingPitch is True:
        return []
    intervalos = []
    for inst in m21_parte.recurse().getElementsByClass(instrument.Instrument):
        intervalos.append((float(inst.getOffsetInHierarchy(m21_parte)), inst.transposition))
    return sorted(intervalos, key=lambda x: x[0])


def _intervalo_en(intervalos: List[Tuple[float, object]], inicio: float):
    vigente = None
    for desde, intervalo in intervalos:
        if desde <= inicio + 1e-9:
            vigente = intervalo
    return vigente


def _recorrer(m21_parte) -> Iterator[Tuple[Optional[int], float, str, object]]:
    """(compás, inicio en negras, voz, elemento) de cada nota, acorde o silencio de la parte."""
    from music21 import stream

    compases = list(m21_parte.getElementsByClass(stream.Measure))
    if not compases:
        for elemento in m21_parte.flatten().notesAndRests:
            yield None, float(elemento.offset), "1", elemento
        return
    for medida in compases:
        inicio_compas = float(medida.getOffsetBySite(m21_parte))
        numero = medida.number if isinstance(medida.number, int) else None
        for elemento in medida.notesAndRests:
            yield numero, inicio_compas + float(elemento.offset), "1", elemento
        for orden, voz in enumerate(medida.voices, start=1):
            identificador = str(voz.id)
            if not (identificador.isdigit() and len(identificador) <= 3):
                identificador = str(orden)
            base = inicio_compas + float(voz.offset)
            for elemento in voz.notesAndRests:
                yield numero, base + float(elemento.offset), identificador, elemento
