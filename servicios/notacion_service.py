"""
Servicio de notación: fachada de compatibilidad sobre `nucleo.musica`.

Mantiene las funciones que usa la interfaz (nombres para mostrar, posición en el pentagrama
y comparación de notas), pero todas las conversiones se hacen con números (MIDI) a partir de
`Altura.desde_nombre`, que entiende los nombres de music21 ('B-4') y de librosa ('A♯4').
No depende de Kivy, librosa ni sounddevice.
"""

from typing import Optional

from nucleo.musica import Altura, ErrorAltura, comparar_alturas


def paso_diatonico(nombre_nota: str) -> int:
    """Posición vertical de una nota en el pentagrama (letra y octava escritas).

    Ejemplo: 'C4' -> 4 * 7 + 0 = 28. La alteración no cambia la posición: 'B-3' y 'B3'
    ocupan la misma línea.
    """
    return Altura.desde_nombre(nombre_nota).paso_diatonico


PASO_B4 = paso_diatonico("B4")  # Línea 3 (central) en clave de sol


def nombre_para_mostrar(nombre_nota: Optional[str], usar_solfeo: bool) -> str:
    """Nombre legible con la alteración original: 'B-3' -> 'B♭3' o, en solfeo, 'Si♭3'.

    Un texto que no es un nombre de nota se devuelve sin cambios.
    """
    if not nombre_nota:
        return ""
    try:
        altura = Altura.desde_nombre(nombre_nota)
    except ErrorAltura:
        return nombre_nota
    return altura.nombre_solfeo if usar_solfeo else altura.nombre


def nota_coincide(nota_detectada: Optional[str], nota_esperada: Optional[str],
                  tolerancia_semitonos: int = 0) -> bool:
    """True si la nota detectada es la esperada: misma altura y misma octava.

    Las notas enarmónicas coinciden (A♯3 = B♭3). `tolerancia_semitonos` admite una distancia
    de hasta ese número de semitonos (0 por defecto, el modo normal); se limita a 11 para no
    equiparar nunca dos octavas. Para comparar frecuencias con la tolerancia de afinación en
    cents, véase `nucleo.musica.comparar_frecuencia`.
    """
    if nota_detectada is None or nota_esperada is None:
        return False
    try:
        resultado = comparar_alturas(nota_detectada, nota_esperada)
    except ErrorAltura:
        return False
    if tolerancia_semitonos <= 0:
        return resultado.es_acierto
    return abs(resultado.diferencia_semitonos) <= min(tolerancia_semitonos, 11)
