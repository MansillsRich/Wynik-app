"""
Wynik 🎵
Punto de entrada de la aplicación de práctica musical con reconocimiento en tiempo real.
"""

from kivy.utils import platform

ESCRITORIO = platform not in ("android", "ios")

if ESCRITORIO:
    # Tamaño inicial de escritorio (antes de crear la ventana). La ventana se puede
    # redimensionar; la interfaz se adapta desde 360 × 340 (teléfono, apaisado).
    from kivy.config import Config
    Config.set("graphics", "width", "1040")
    Config.set("graphics", "height", "720")
    Config.set("graphics", "resizable", "1")

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
