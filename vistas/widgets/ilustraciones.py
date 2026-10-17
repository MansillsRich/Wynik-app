"""
Ilustraciones de Wynik dibujadas con el canvas de Kivy (sin imágenes ni recursos remotos).

- `DibujoInstrumento`: guitarra, piano o partitura en pequeño (tarjetas de elección, filas
  de la biblioteca). `instrumento` elige el dibujo y `color` la tinta.
- `IlustracionPortada`: pentagrama con notas, guitarra y teclado para la tarjeta principal del
  inicio. Las notas flotan suavemente solo mientras `animar` es True (el inicio está a la
  vista); en la práctica no hay ninguna animación continua.
"""

import math

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import (Color, Ellipse, Line, PopMatrix, PushMatrix, Rectangle, Rotate,
                           RoundedRectangle)
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, StringProperty
from kivy.uix.widget import Widget

from .. import tema


def _nota(cx, cy, r, color, plica=True, arriba=True, grosor=None):
    """Cabeza de nota inclinada con plica."""
    Color(*color)
    PushMatrix()
    Rotate(angle=-20, origin=(cx, cy))
    Ellipse(pos=(cx - r * 1.25, cy - r * 0.9), size=(r * 2.5, r * 1.8))
    PopMatrix()
    if plica:
        x = cx + r * 1.12 if arriba else cx - r * 1.12
        Line(points=[x, cy, x, cy + (r * 6 if arriba else -r * 6)], width=grosor or max(1.0, r * 0.22))


class _Ilustracion(Widget):
    color = ListProperty(list(tema.PRIMARIO))

    def __init__(self, **kwargs):
        self._redibujar = Clock.create_trigger(self.redibujar, -1)
        super().__init__(**kwargs)
        self.bind(pos=self._redibujar, size=self._redibujar, color=self._redibujar)

    def redibujar(self, *args):
        pass


class DibujoInstrumento(_Ilustracion):
    instrumento = StringProperty("partitura")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(instrumento=self._redibujar)

    def redibujar(self, *args):
        self.canvas.clear()
        lado = min(self.width, self.height)
        if lado < dp(16):
            return
        x0, y0 = self.center_x - lado / 2, self.center_y - lado / 2
        with self.canvas:
            getattr(self, f"_{self.instrumento}", self._partitura)(x0, y0, lado)

    def _guitarra(self, x0, y0, s):
        c = self.color
        # cuerpo: dos óvalos, boca y puente; mástil inclinado
        PushMatrix()
        Rotate(angle=-35, origin=(x0 + s / 2, y0 + s / 2))
        Color(*c)
        Ellipse(pos=(x0 + s * 0.22, y0 + s * 0.04), size=(s * 0.46, s * 0.40))
        Ellipse(pos=(x0 + s * 0.27, y0 + s * 0.33), size=(s * 0.36, s * 0.31))
        RoundedRectangle(pos=(x0 + s * 0.465, y0 + s * 0.55), size=(s * 0.07, s * 0.36), radius=[s * 0.02])
        RoundedRectangle(pos=(x0 + s * 0.44, y0 + s * 0.86), size=(s * 0.12, s * 0.12), radius=[s * 0.03])
        Color(*tema.SUPERFICIE)
        Ellipse(pos=(x0 + s * 0.43, y0 + s * 0.36), size=(s * 0.14, s * 0.14))
        Rectangle(pos=(x0 + s * 0.40, y0 + s * 0.15), size=(s * 0.20, s * 0.035))
        Color(*tema.con_alfa(tema.SUPERFICIE, 0.7))
        for k in (-1, 0, 1):
            Line(points=[x0 + s * (0.5 + 0.018 * k), y0 + s * 0.17, x0 + s * (0.5 + 0.018 * k), y0 + s * 0.95],
                 width=max(0.6, s * 0.006))
        PopMatrix()

    def _piano(self, x0, y0, s):
        c = self.color
        ancho, alto = s * 0.9, s * 0.62
        x, y = x0 + (s - ancho) / 2, y0 + (s - alto) / 2
        Color(*c)
        RoundedRectangle(pos=(x - s * 0.03, y - s * 0.03), size=(ancho + s * 0.06, alto + s * 0.06), radius=[s * 0.06])
        Color(*tema.SUPERFICIE)
        n = 7
        w = ancho / n
        for i in range(n):
            RoundedRectangle(pos=(x + i * w + s * 0.008, y), size=(w - s * 0.016, alto), radius=[0, 0, s * 0.02, s * 0.02])
        Color(*c)
        for i in (1, 2, 4, 5, 6):
            Rectangle(pos=(x + i * w - w * 0.3, y + alto * 0.4), size=(w * 0.6, alto * 0.6))

    def _flauta(self, x0, y0, s):
        PushMatrix()
        Rotate(angle=35, origin=(x0 + s / 2, y0 + s / 2))
        Color(*self.color)
        RoundedRectangle(pos=(x0 + s * 0.05, y0 + s * 0.45), size=(s * 0.9, s * 0.1), radius=[s * 0.05])
        Color(*tema.SUPERFICIE)
        for i in range(5):
            Ellipse(pos=(x0 + s * (0.32 + i * 0.11), y0 + s * 0.475), size=(s * 0.05, s * 0.05))
        PopMatrix()

    def _partitura(self, x0, y0, s):
        c = self.color
        Color(*tema.con_alfa(c, 0.55))
        for k in range(5):
            y = y0 + s * (0.3 + 0.1 * k)
            Line(points=[x0 + s * 0.05, y, x0 + s * 0.95, y], width=max(0.8, s * 0.012))
        _nota(x0 + s * 0.32, y0 + s * 0.35, s * 0.065, c)
        _nota(x0 + s * 0.62, y0 + s * 0.50, s * 0.065, c)


class IlustracionPortada(_Ilustracion):
    """Composición para fondo de color principal: pentagrama con notas, guitarra y teclado."""
    animar = BooleanProperty(False)
    fase = NumericProperty(0)

    def __init__(self, **kwargs):
        self._animacion = None
        super().__init__(**kwargs)
        self.bind(fase=self._redibujar)

    def on_animar(self, *args):
        if self._animacion is not None:
            self._animacion.cancel(self)
            self._animacion = None
        if self.animar:
            self._animacion = Animation(fase=1, d=3.2, t="in_out_sine") + Animation(fase=0, d=3.2, t="in_out_sine")
            self._animacion.repeat = True
            self._animacion.start(self)

    def redibujar(self, *args):
        self.canvas.clear()
        w, h = self.width, self.height
        if w < dp(80) or h < dp(60):
            return
        x0, y0 = self.x, self.y
        claro = tema.con_alfa(tema.SOBRE_PRIMARIO, 0.22)
        medio = tema.con_alfa(tema.SOBRE_PRIMARIO, 0.55)
        fuerte = tema.con_alfa(tema.SOBRE_PRIMARIO, 0.92)
        with self.canvas:
            # pentagrama que cruza la ilustración
            sep = min(h * 0.07, dp(9))
            base = y0 + h * 0.52
            Color(*claro)
            for k in range(5):
                Line(points=[x0, base + k * sep, x0 + w, base + k * sep], width=dp(1))
            # notas que flotan (desfase distinto cada una)
            r = sep * 0.62
            for i, (fx, paso) in enumerate(((0.12, 1), (0.27, 3), (0.42, 5), (0.58, 2), (0.74, 4))):
                desplaz = math.sin((self.fase + i * 0.21) * math.pi * 2) * dp(3)
                _nota(x0 + w * fx, base + paso * sep / 2 + desplaz, r, fuerte if i % 2 == 0 else medio,
                      grosor=dp(1.4))
            # teclado abajo a la derecha
            kx, ky = x0 + w * 0.52, y0 + h * 0.06
            kw, kh = w * 0.46, h * 0.28
            n = 10
            tw = kw / n
            Color(*medio)
            RoundedRectangle(pos=(kx - dp(3), ky - dp(3)), size=(kw + dp(6), kh + dp(6)), radius=[dp(6)])
            Color(*fuerte)
            for i in range(n):
                RoundedRectangle(pos=(kx + i * tw + dp(0.7), ky), size=(tw - dp(1.4), kh), radius=[0, 0, dp(3), dp(3)])
            Color(*tema.PRIMARIO_OSCURO)
            for i in (1, 2, 4, 5, 6, 8, 9):
                Rectangle(pos=(kx + i * tw - tw * 0.3, ky + kh * 0.4), size=(tw * 0.6, kh * 0.6))
            # guitarra a la izquierda, inclinada
            s = min(w * 0.42, h * 0.95)
            gx, gy = x0 + w * 0.02, y0 - s * 0.08
            PushMatrix()
            Rotate(angle=-32, origin=(gx + s / 2, gy + s / 2))
            Color(*fuerte)
            Ellipse(pos=(gx + s * 0.25, gy + s * 0.05), size=(s * 0.42, s * 0.36))
            Ellipse(pos=(gx + s * 0.29, gy + s * 0.31), size=(s * 0.34, s * 0.29))
            RoundedRectangle(pos=(gx + s * 0.44, gy + s * 0.55), size=(s * 0.08, s * 0.40), radius=[s * 0.02])
            Color(*tema.PRIMARIO)
            Ellipse(pos=(gx + s * 0.405, gy + s * 0.32), size=(s * 0.11, s * 0.11))
            Rectangle(pos=(gx + s * 0.39, gy + s * 0.14), size=(s * 0.14, s * 0.03))
            Color(*tema.con_alfa(tema.PRIMARIO, 0.6))
            for k in (-1, 0, 1):
                Line(points=[gx + s * (0.48 + 0.016 * k), gy + s * 0.15, gx + s * (0.48 + 0.016 * k), gy + s * 0.95],
                     width=dp(0.6))
            PopMatrix()
            # acento: un punto ámbar sobre la nota central
            Color(*tema.ACENTO)
            Ellipse(pos=(x0 + w * 0.42 - dp(4), base + 6 * sep + dp(2)), size=(dp(8), dp(8)))
