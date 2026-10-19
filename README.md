# Wynik 🎵

Aplicación de práctica musical hecha con Kivy y KivyMD. Carga una partitura MusicXML, muestra la nota esperada (pentagrama, diapasón de guitarra o teclado de piano) y, con el micrófono, comprueba en tiempo real si tocas la nota correcta y a tiempo.

## Instalación (escritorio)

Requiere Python 3.13 y un micrófono.

```bash
python3.13 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-escritorio.txt
```

## Ejecución

```bash
python main.py o ./.venv/bin/python main.py
```

Los datos del usuario (historial, ajustes, progreso) se guardan junto a la aplicación; `WYNIK_DATOS=<carpeta>` cambia dónde.

## Limitaciones conocidas

- Guitarra y piano, una nota cada vez. Los acordes se muestran como referencia y no se evalúan. La flauta es experimental.
- La precisión con instrumentos reales todavía no está validada.
- Solo probada en macOS (escritorio). Android y Windows sin verificar.
- El reproductor de referencia no admite pausa ni búsqueda con el audio de escritorio de Kivy (SDL2).
