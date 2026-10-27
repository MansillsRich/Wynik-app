"""
Wynik 🎵
Punto de entrada de la aplicación de práctica musical con reconocimiento en tiempo real.
"""

import sys
from pathlib import Path

# Garantiza que el directorio raíz del proyecto forme parte de sys.path
RAIZ_PROYECTO = Path(__file__).resolve().parent
if str(RAIZ_PROYECTO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROYECTO))

from kivy.utils import platform

ESCRITORIO = platform not in ("android", "ios")

if ESCRITORIO:
    # Tamaño inicial de escritorio (antes de crear la ventana). La ventana se puede
    # redimensionar; la interfaz se adapta desde 360 × 340 (teléfono, apaisado).
    from kivy.config import Config
    Config.set("graphics", "width", "1040")
    Config.set("graphics", "height", "720")
    Config.set("graphics", "resizable", "1")

    # En Linux/escritorio, inicializar los proveedores de audio antes de crear la ventana
    # evita un interbloqueo (GIL deadlock) entre el filtro de eventos SDL2 de Kivy
    # y la detección de dispositivos de PulseAudio/PipeWire al cargar la guía de audio.
    from kivy.core.audio import SoundLoader  # noqa: E402
    for _cls in getattr(SoundLoader, "_classes", []):
        try:
            _cls.extensions()
        except Exception:
            pass

from kivy.core.window import Window  # noqa: E402
from vistas import WynikApp  # noqa: E402

if ESCRITORIO:
    Window.minimum_width, Window.minimum_height = 360, 340


def main():
    """Inicializa y ejecuta la aplicación Wynik."""
    app = WynikApp()
    app.run()


if __name__ == "__main__":
    main()
