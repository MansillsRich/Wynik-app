"""
Avisos emergentes de Wynik (snackbar).

KivyMD 2.0.0 crea el búfer del efecto de pulsación (`init_fbos`) con el tamaño del widget
antes de que tenga uno. En macOS (OpenGL sobre Metal) un Fbo de alto 0 es «incompleto» y el
snackbar fallaba al construirse: ningún aviso llegaba a verse. `SnackbarWynik` repite el mismo
`init_fbos` con un tamaño mínimo de 1×1; no cambia nada más del componente.
"""

from kivy.graphics import ClearBuffers, ClearColor, Color, Fbo, Rectangle
from kivy.metrics import dp
from kivymd.uix.snackbar import MDSnackbar, MDSnackbarSupportingText


class SnackbarWynik(MDSnackbar):
    """MDSnackbar que se puede construir aunque todavía no tenga tamaño."""

    def init_fbos(self):
        self._phase = 0.0
        self.ripple_pos = (0, 0)
        self.fbo = Fbo(size=self._clamp_size(*self.size), group="m3_ripple_behavior")
        self.set_shader(self.fbo)
        with self.fbo:
            ClearColor(0, 0, 0, 0)
            ClearBuffers()
            Color(1, 1, 1, 1)
            self.rect = Rectangle(pos=(0, 0), size=self.size)


def mostrar_aviso(texto: str) -> None:
    """Muestra `texto` en un snackbar (varias líneas si hace falta). Propaga cualquier error:
    quien llama decide cómo registrarlo."""
    SnackbarWynik(
        MDSnackbarSupportingText(text=texto, padding=(dp(16), dp(14))),
        y=dp(24), pos_hint={"center_x": 0.5}, size_hint_x=0.92,
    ).open()
