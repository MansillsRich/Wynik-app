"""
Servicio de partituras: fachada de compatibilidad sobre `nucleo.importador_musicxml`.

- `cargar_partitura_estructurada` devuelve el modelo completo (`nucleo.musica.Partitura`):
  partes, pentagramas, voces, silencios, ligaduras, acordes y tempo.
- `cargar_partitura` mantiene la lista de notas que usa la interfaz actual, calculada desde
  ese modelo con `Partitura.linea_de_practica` (práctica nota a nota de la primera parte).

Formato de cada elemento de `cargar_partitura`:
    nombre          altura sonora con su alteración original ('B♭4'): la que debe oírse
    offset_beats    inicio en negras desde el principio de la partitura
    duracion_beats  duración en negras, con las ligaduras ya sumadas
    midi, frecuencia_hz         altura sonora en número MIDI y en hercios
    nombre_escrito, midi_escrito  altura escrita (posición en el pentagrama)
    es_acorde, alturas_midi     si empiezan varias notas a la vez en el pentagrama que se evalúa y
                                todas sus alturas sonoras
    acompanamiento_midi         notas de los demás pentagramas (la otra mano del piano) que suenan
                                con el ataque: se oyen y se muestran, pero no se evalúan
    pentagrama                  pentagrama del ataque (1 = mano derecha en el piano)
    nombres, nombres_escritos, alturas_escritas_midi   grafía sonora y escrita de cada nota
    inicio_s, duracion_s        tiempos en segundos según el tempo de la partitura
    compas                      número de compás
"""

import os
from typing import Any, Dict, List, Optional

from nucleo.importador_musicxml import EXTENSIONES, ErrorPartitura, importar_musicxml
from nucleo.musica import Ataque, Partitura

EXTENSIONES_PERMITIDAS = set(EXTENSIONES)

__all__ = ["EXTENSIONES_PERMITIDAS", "ErrorPartitura", "ataque_a_nota", "cargar_partitura",
           "cargar_partitura_estructurada", "validar_extension_partitura"]


def validar_extension_partitura(ruta_archivo: str) -> bool:
    """Verifica si la ruta corresponde a un formato de partitura soportado."""
    if not ruta_archivo:
        return False
    _, extension = os.path.splitext(ruta_archivo.lower())
    return extension in EXTENSIONES_PERMITIDAS


def cargar_partitura_estructurada(ruta_archivo: str, **opciones) -> Partitura:
    """Partitura completa (ver `nucleo.importador_musicxml.importar_musicxml`)."""
    return importar_musicxml(ruta_archivo, **opciones)


def ataque_a_nota(ataque: Ataque) -> Dict[str, Any]:
    """Convierte un ataque de la línea de práctica al diccionario que usa la interfaz."""
    principal = ataque.principal
    return {
        "nombre": principal.sonora.nombre,
        "offset_beats": float(ataque.inicio_negras),
        "duracion_beats": float(ataque.duracion_negras),
        "midi": principal.sonora.midi,
        "frecuencia_hz": principal.sonora.frecuencia,
        "nombre_escrito": principal.escrita.nombre,
        "midi_escrito": principal.escrita.midi,
        "es_acorde": ataque.es_acorde,
        "alturas_midi": [n.sonora.midi for n in ataque.notas],
        "nombres": [n.sonora.nombre for n in ataque.notas],
        "nombres_escritos": [n.escrita.nombre for n in ataque.notas],
        "alturas_escritas_midi": [n.escrita.midi for n in ataque.notas],
        "acompanamiento_midi": [n.sonora.midi for n in ataque.acompanamiento],
        "acompanamiento_nombres": [n.sonora.nombre for n in ataque.acompanamiento],
        "pentagrama": ataque.pentagrama,
        "inicio_s": ataque.inicio_s,
        "duracion_s": ataque.duracion_s,
        "compas": ataque.compas,
    }


def cargar_partitura(ruta_archivo: str, parte_id: Optional[str] = None, **opciones) -> List[Dict[str, Any]]:
    """Lee un MusicXML (.xml, .musicxml, .mxl) y devuelve las notas para practicar una a una.

    Lanza `FileNotFoundError` si el archivo no existe y `ErrorPartitura` si no se puede leer.
    Una partitura sin notas devuelve una lista vacía.
    """
    partitura = importar_musicxml(ruta_archivo, **opciones)
    return [ataque_a_nota(a) for a in partitura.linea_de_practica(parte_id)]
