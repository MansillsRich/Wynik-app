"""
Script auxiliar del Anexo IV (no forma parte de la aplicación Wynik).

El repositorio no incluye ninguna partitura MusicXML de ejemplo, así que este script crea
dos partituras sencillas con music21 para ilustrar la documentación:

- partituras/escala_do_mayor.musicxml: escala de Do mayor (C4–C5) en negras, piano,
  compás 4/4 y negra = 80.
- partituras/oda_a_la_alegria_guitarra.musicxml: fragmento de la «Oda a la alegría»
  (L. van Beethoven, dominio público) para guitarra, sin elemento <transpose>, para mostrar
  la pregunta «¿Cómo suena esta guitarra?» de la pantalla de preparación.

Uso (desde la raíz del repositorio, con el entorno virtual activado):
    python docs/anexo_iv/crear_partituras.py
"""

from pathlib import Path

from music21 import instrument, metadata, meter, note, stream, tempo

CARPETA = Path(__file__).resolve().parent / "partituras"


def _partitura(titulo: str, nombre_parte: str, instrumento, bpm: int, notas) -> stream.Score:
    partitura = stream.Score()
    partitura.metadata = metadata.Metadata(title=titulo)
    parte = stream.Part()
    parte.partName = nombre_parte
    parte.insert(0, instrumento)
    parte.append(meter.TimeSignature("4/4"))
    parte.insert(0, tempo.MetronomeMark(number=bpm))
    for nombre, duracion in notas:
        parte.append(note.Note(nombre, quarterLength=duracion))
    partitura.insert(0, parte)
    return partitura.makeNotation()


def main() -> None:
    CARPETA.mkdir(parents=True, exist_ok=True)
    escala = [(n, 1.0) for n in ("C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5")]
    oda = [("E4", 1), ("E4", 1), ("F4", 1), ("G4", 1), ("G4", 1), ("F4", 1), ("E4", 1), ("D4", 1),
           ("C4", 1), ("C4", 1), ("D4", 1), ("E4", 1), ("E4", 1.5), ("D4", 0.5), ("D4", 2)]
    salidas = {
        "escala_do_mayor.musicxml": _partitura("Escala de Do mayor", "Piano", instrument.Piano(), 80, escala),
        "oda_a_la_alegria_guitarra.musicxml": _partitura("Oda a la alegría (fragmento)", "Guitarra",
                                                         instrument.Guitar(), 100, oda),
    }
    for nombre, partitura in salidas.items():
        ruta = CARPETA / nombre
        partitura.write("musicxml", fp=str(ruta))
        print(f"Creada {ruta}")


if __name__ == "__main__":
    main()
