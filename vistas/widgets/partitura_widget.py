"""
Pentagrama con la partitura alrededor de la nota actual.

El widget solo dibuja: toda la geometría (posición de las notas según su clave, alteraciones,
armadura, figuras, silencios, barras, ligaduras, las dos manos del piano alineadas) la calcula
`nucleo.notacion.disponer`, que se prueba sin Kivy. Aquí se elige el tramo visible, se escala
en dp y se traducen las primitivas a instrucciones gráficas.

- La altura dibujada es la ESCRITA con la clave de cada pentagrama (la guitarra se escribe una
  octava por encima de como suena; la evaluación usa la sonora).
- El estado de cada nota evaluada se indica con color y con un símbolo bajo el pentagrama
  (✓ correcta, ≈ desafinada, ✗ equivocada, – no tocada, ? sin señal fiable, ! fuera de rango,
  ○ acorde sin evaluar); la nota actual se marca con ▲, no solo con color.
- Solo se colorean las notas del pentagrama que se evalúa; la otra mano se dibuja en tinta.
- Las claves se dibujan con trazos propios: la fuente de la interfaz no tiene los símbolos
  musicales de clave ni de silencio. Es una versión simplificada hasta contar con una fuente
  musical (SMuFL).
"""

import math

from kivy.graphics import (Color, Ellipse, Line, Rectangle, RoundedRectangle, StencilPop, StencilPush,
                           StencilUnUse, StencilUse)
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, ObjectProperty
from kivy.uix.widget import Widget

from nucleo.notacion import altura_total, tramo_visible

from . import dibujo

ESPACIO_MIN_DP = 5.0
ESPACIO_MAX_DP = 13.0
MARGEN_VERTICAL = 3.2       # espacios libres arriba y abajo (el símbolo de estado va abajo)


class PartituraWidget(Widget):
    """Fragmento de la partitura que rodea a la nota actual."""

    notas = ListProperty([])
    estados = ListProperty([])
    indice = NumericProperty(0)
    solfeo = BooleanProperty(False)
    disposicion = ObjectProperty(None, allownone=True)   # nucleo.notacion.Disposicion

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self.redibujar, size=self.redibujar, notas=self.redibujar,
                  estados=self.redibujar, indice=self.redibujar, disposicion=self.redibujar)

    # ------------------------------------------------------------------------------------
    def tramo(self, ancho_espacios, alto_espacios_max=None):
        """(x_izquierda, x_derecha, contexto, ancho_contexto) del tramo visible, en espacios de
        partitura. Sin Kivy: lo usan las pruebas."""
        return tramo_visible(self.disposicion, self._tiempo_actual(), ancho_espacios)

    def _tiempo_actual(self):
        if not self.notas:
            return 0.0
        i = min(max(int(self.indice), 0), len(self.notas) - 1)
        return float(self.notas[i].get("offset_beats", 0.0))

    def redibujar(self, *args):
        self.canvas.clear()
        if self.width < 40 or self.height < 40:
            return
        with self.canvas:
            Color(*dibujo.PAPEL)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(14)])
            disp = self.disposicion
            if disp is None or not self.notas:
                dibujo.texto("Sin partitura", self.center_x, self.center_y, dp(13), dibujo.TINTA_SUAVE)
                return
            # Nada se dibuja fuera del recuadro (un elemento junto al borde derecho se recorta).
            StencilPush()
            Rectangle(pos=self.pos, size=self.size)
            StencilUse()
            margen_px = dp(8)
            ancho_px = self.width - 2 * margen_px
            # Escala: lo que haya que mostrar debe caber en alto; por debajo del mínimo no se
            # encoge más (se prefiere legible a completo).
            espacio = dp(ESPACIO_MAX_DP)
            for _ in range(2):
                izq, der, contexto, ancho_ctx = tramo_visible(disp, self._tiempo_actual(), ancho_px / espacio)
                arriba, abajo = altura_total(disp, izq, der)
                necesario = (arriba - abajo) + 2 * MARGEN_VERTICAL
                espacio = max(dp(ESPACIO_MIN_DP), min(dp(ESPACIO_MAX_DP), self.height / necesario))
            izq, der, contexto, ancho_ctx = tramo_visible(disp, self._tiempo_actual(), ancho_px / espacio)
            arriba, abajo = altura_total(disp, izq, der)
            # El centro del dibujo en y: reparte el sobrante entre arriba y abajo.
            y_cero = self.y + self.height / 2 - ((arriba + abajo) / 2) * espacio
            x_cero = self.x + margen_px

            def px(x):
                return x_cero + x * espacio

            def py(y):
                return y_cero + y * espacio

            desplazamiento = ancho_ctx - izq if contexto else 0.0   # x de partitura → x de pantalla

            def X(x):
                return px(x + desplazamiento)

            estados_por_tiempo = self._estados_por_tiempo()
            # banda de la posición actual (detrás de todo)
            for tiempo, (indice, _p, _e) in estados_por_tiempo.items():
                x = disp.columnas.get(tiempo)
                if indice == int(self.indice) and x is not None and izq - 0.5 <= x <= der:
                    alto_banda = py(disp.y_central(1) + 3.5) - py(disp.y_central(disp.pentagramas) - 3.5)
                    Color(*dibujo.ACTUAL_SUAVE)
                    RoundedRectangle(pos=(X(x) - 1.6 * espacio, py(disp.y_central(disp.pentagramas) - 3.5)),
                                     size=(3.2 * espacio, alto_banda), radius=[espacio * 0.8])
                    break
            # pentagramas
            Color(*dibujo.TINTA)
            for p in range(1, disp.pentagramas + 1):
                for k in range(-2, 3):
                    y = py(disp.y_central(p) + k)
                    Line(points=[px(0), y, self.right - margen_px, y], width=1.0)
            grosor = max(1.0, espacio * 0.09)
            for e in contexto:
                self._dibujar(e, px, py, espacio, grosor, dibujo.TINTA)
            for e in disp.visibles(izq, der):
                if contexto and e.x < izq and e.tipo in ("clave", "armadura", "cifra"):
                    continue
                color = self._color_de(e, estados_por_tiempo)
                self._dibujar(e, X, py, espacio, grosor, color)
            # símbolo de estado y marca de la nota actual
            y_simbolo = py(disp.y_central(disp.pentagramas) - 4.2)
            for tiempo, (indice, pentagrama, estado) in estados_por_tiempo.items():
                x = disp.columnas.get(tiempo)
                if x is None or not (izq - 0.5 <= x <= der):
                    continue
                color, simbolo = dibujo.ESTILO_ESTADO.get(estado, (None, ""))
                if simbolo:
                    dibujo.texto(simbolo, X(x), y_simbolo, espacio * 1.5, color, negrita=True)
                if indice == int(self.indice):
                    dibujo.texto("▲", X(x), y_simbolo - espacio * 1.4, espacio * 1.1, dibujo.ACENTO)
            StencilUnUse()
            Rectangle(pos=self.pos, size=self.size)
            StencilPop()

    # ------------------------------------------------------------------------------------
    def _estados_por_tiempo(self):
        """{inicio en negras: (índice, pentagrama evaluado, estado)} de la línea de práctica."""
        resultado = {}
        for i, nota in enumerate(self.notas):
            estado = self.estados[i] if i < len(self.estados) else "pendiente"
            resultado[round(float(nota.get("offset_beats", 0.0)), 6)] = (i, int(nota.get("pentagrama", 1)), estado)
        return resultado

    def _color_de(self, e, estados_por_tiempo):
        if e.inicio is None or e.tipo in ("clave", "armadura", "cifra", "barra_compas"):
            return dibujo.TINTA
        datos = estados_por_tiempo.get(round(e.inicio, 6))
        if datos is None or e.pentagrama != datos[1]:
            return dibujo.TINTA
        indice, _, estado = datos
        color, _ = dibujo.ESTILO_ESTADO.get(estado, (None, ""))
        if color is not None:
            return color
        return dibujo.ACTUAL if indice == int(self.indice) else dibujo.TINTA

    def _dibujar(self, e, X, Y, espacio, grosor, color):
        t = e.tipo
        Color(*color)
        if t == "cabeza":
            ancho, alto = 1.3 * espacio, 1.0 * espacio
            if e.relleno:
                Ellipse(pos=(X(e.x) - ancho / 2, Y(e.y) - alto / 2), size=(ancho, alto))
            else:
                Line(ellipse=(X(e.x) - ancho / 2, Y(e.y) - alto / 2, ancho, alto), width=grosor * 1.4)
        elif t == "plica":
            Line(points=[X(e.x), Y(e.y), X(e.x), Y(e.y2)], width=grosor)
        elif t == "corchete":
            sentido = e.direccion
            for k in range(e.n):
                y0 = Y(e.y) - sentido * k * 0.8 * espacio
                Line(bezier=[X(e.x), y0, X(e.x) + 0.2 * espacio, y0 - sentido * 0.6 * espacio,
                             X(e.x) + 1.4 * espacio, y0 - sentido * 1.0 * espacio,
                             X(e.x) + 0.9 * espacio, y0 - sentido * 2.3 * espacio], width=grosor * 1.3)
        elif t == "linea_adicional":
            Line(points=[X(e.x), Y(e.y), X(e.x2), Y(e.y)], width=grosor * 1.2)
        elif t == "puntillo":
            Ellipse(pos=(X(e.x) - 0.2 * espacio, Y(e.y) - 0.2 * espacio), size=(0.4 * espacio, 0.4 * espacio))
        elif t == "alteracion":
            dibujo.texto(e.texto, X(e.x), Y(e.y), espacio * 2.1, color)
        elif t == "armadura":
            dibujo.texto(e.texto, X(e.x), Y(e.y), espacio * 2.0, color)
        elif t == "cifra":
            dibujo.texto(e.texto, X(e.x), Y(e.y), espacio * 2.2, color, negrita=True)
        elif t == "barra_compas":
            Line(points=[X(e.x), Y(e.y), X(e.x), Y(e.y2)], width=grosor)
        elif t == "silencio":
            self._silencio(e, X, Y, espacio, grosor)
        elif t == "ligadura":
            self._ligadura(e, X, Y, espacio, grosor)
        elif t == "clave":
            self._clave(e, X, Y, espacio, grosor)

    def _silencio(self, e, X, Y, espacio, grosor):
        x, y, figura = X(e.x), Y(e.y), e.texto
        if figura in ("whole", "breve"):   # cuelga de la 4.ª línea
            Rectangle(pos=(x - 0.7 * espacio, y + 1.0 * espacio - 0.5 * espacio), size=(1.4 * espacio, 0.5 * espacio))
        elif figura == "half":             # se apoya en la 3.ª línea
            Rectangle(pos=(x - 0.7 * espacio, y), size=(1.4 * espacio, 0.5 * espacio))
        elif figura == "quarter":
            Line(points=[x + 0.3 * espacio, y + 1.7 * espacio, x - 0.4 * espacio, y + 0.8 * espacio,
                         x + 0.4 * espacio, y - 0.1 * espacio, x - 0.4 * espacio, y - 0.8 * espacio,
                         x + 0.3 * espacio, y - 1.5 * espacio], width=grosor * 1.8)
        else:                              # corcheas y menores: trazo con un punto por bandera
            banderas = {"eighth": 1, "16th": 2, "32nd": 3, "64th": 4}.get(figura, 1)
            Line(points=[x + 0.5 * espacio, y + 1.0 * espacio, x - 0.3 * espacio, y - 1.2 * espacio], width=grosor * 1.3)
            for k in range(banderas):
                yk = y + 0.6 * espacio - k * 0.8 * espacio
                Ellipse(pos=(x - 0.7 * espacio + k * 0.1 * espacio, yk - 0.2 * espacio),
                        size=(0.5 * espacio, 0.5 * espacio))

    def _ligadura(self, e, X, Y, espacio, grosor):
        x1, y1, x2, y2 = X(e.x), Y(e.y), X(e.x2), Y(e.y2)
        alto = 0.9 * espacio * e.direccion
        puntos = []
        for k in range(13):
            s = k / 12.0
            puntos += [x1 + (x2 - x1) * s, y1 + (y2 - y1) * s + alto * 4 * s * (1 - s)]
        Line(points=puntos, width=grosor * 1.3)

    def _clave(self, e, X, Y, espacio, grosor):
        x, y = X(e.x), Y(e.y)
        if e.texto == "G":
            # espiral alrededor de la línea de sol, con la vertical que la atraviesa
            puntos = []
            for k in range(0, 41):
                a = math.pi * 2.2 * k / 40
                radio = (0.35 + 1.15 * k / 40) * espacio
                puntos += [x + 0.9 * espacio + radio * math.sin(a) * 0.9, y + 0.1 * espacio + radio * math.cos(a)]
            Line(points=puntos, width=grosor * 1.6)
            Line(points=[x + 0.9 * espacio, y + 4.4 * espacio, x + 0.9 * espacio, y - 2.6 * espacio], width=grosor * 1.6)
            Line(bezier=[x + 0.9 * espacio, y - 2.6 * espacio, x + 0.9 * espacio, y - 3.6 * espacio,
                         x - 0.3 * espacio, y - 3.4 * espacio, x - 0.1 * espacio, y - 2.7 * espacio], width=grosor * 1.6)
            if e.n:
                dibujo.texto(str(8), x + 0.9 * espacio, y - 4.2 * espacio, espacio * 1.2, dibujo.TINTA, negrita=True)
        elif e.texto == "F":
            Ellipse(pos=(x + 0.3 * espacio, y - 0.5 * espacio), size=(1.0 * espacio, 1.0 * espacio))
            Line(bezier=[x + 0.4 * espacio, y + 0.4 * espacio, x + 1.6 * espacio, y + 1.2 * espacio,
                         x + 2.4 * espacio, y - 0.6 * espacio, x + 0.6 * espacio, y - 3.4 * espacio], width=grosor * 1.6)
            for dy in (0.9, -0.9):
                Ellipse(pos=(x + 2.4 * espacio, y + (dy - 0.25) * espacio), size=(0.5 * espacio, 0.5 * espacio))
            if e.n:
                dibujo.texto(str(8), x + 1.2 * espacio, y - 3.6 * espacio, espacio * 1.2, dibujo.TINTA, negrita=True)
        else:  # do: dos barras y dos curvas pequeñas
            Rectangle(pos=(x + 0.2 * espacio, y - 2.0 * espacio), size=(0.5 * espacio, 4.0 * espacio))
            Rectangle(pos=(x + 1.0 * espacio, y - 2.0 * espacio), size=(0.18 * espacio, 4.0 * espacio))
            for dy in (1.0, -1.0):
                Line(circle=(x + 2.0 * espacio, y + dy * espacio, 0.8 * espacio, 0, 180 if dy > 0 else 360), width=grosor * 1.4)
