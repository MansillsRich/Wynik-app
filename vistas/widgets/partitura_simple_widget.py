"""
Widget de partitura simplificada para la práctica musical.

Muestra las notas musicales en una cinta o línea de tiempo interactiva centrada
en la nota actual, con retroalimentación visual inmediata por estado (correcta,
desafinada, equivocada, omitida) y avance continuo.
"""

import math

from kivy.graphics import (
    Color, Line, Rectangle, RoundedRectangle,
    StencilPop, StencilPush, StencilUnUse, StencilUse
)
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty
from kivy.uix.widget import Widget

from servicios import nombre_para_mostrar
from .. import tema
from . import dibujo


class PartituraSimpleWidget(Widget):
    """
    Widget de visualización simplificada de partitura.

    Presenta:
    - Cinta deslizante de notas musicales centrada en la nota actual a tocar.
    - Notación configurable (Do Re Mi Fa... o C D E F...).
    - Distinción visual con colores y símbolos estándar de Wynik para notas pasadas.
    - Vista anticipada de notas próximas.
    - Mini barra de progreso superior.
    """

    notas = ListProperty([])          # Lista de diccionarios de notas de la partitura
    estados = ListProperty([])        # Lista de estados de evaluación de cada nota
    indice = NumericProperty(0)       # Índice de la nota actual
    solfeo = BooleanProperty(False)   # Notación en solfeo (Do Re Mi) o cifrado (C D E)
    escala_fuente = NumericProperty(1.0) # Escala de tamaño de fuente

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(
            pos=self._redibujar,
            size=self._redibujar,
            notas=self._redibujar,
            estados=self._redibujar,
            indice=self._redibujar,
            solfeo=self._redibujar,
            escala_fuente=self._redibujar,
        )

    def _redibujar(self, *args):
        """Redibuja el widget con la cinta de notas y el progreso actual."""
        self.canvas.clear()
        if self.width < 40 or self.height < 40:
            return

        with self.canvas:
            # Fondo de tarjeta redondeada con borde suave
            Color(*tema.SUPERFICIE)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(14)])
            Color(*tema.BORDE)
            Line(rounded_rectangle=[self.x, self.y, self.width, self.height, dp(14)], width=1.0)

            total = len(self.notas)
            if total == 0:
                dibujo.texto("Elige una partitura para practicar", self.center_x, self.center_y, dp(13), dibujo.TINTA_SUAVE)
                return

            actual = min(max(int(self.indice), 0), total - 1)

            # ------------------------------------------------------------------
            # Barra y datos de progreso superior
            # ------------------------------------------------------------------
            y_cabecera = self.top - dp(18)
            texto_avance = f"Nota {actual + 1} de {total}"
            dibujo.texto(texto_avance, self.x + dp(16), y_cabecera, dp(11), dibujo.TINTA_SUAVE, ancla="izquierda", negrita=True)

            porcentaje = int(round((actual / max(total - 1, 1)) * 100)) if total > 1 else 0
            dibujo.texto(f"{porcentaje} %", self.right - dp(16), y_cabecera, dp(11), dibujo.TINTA_SUAVE, ancla="derecha")

            x_barra = self.x + dp(16)
            w_barra = max(self.width - dp(32), 10)
            y_barra = self.top - dp(26)
            h_barra = dp(4)

            Color(*tema.SUPERFICIE_2)
            RoundedRectangle(pos=(x_barra, y_barra), size=(w_barra, h_barra), radius=[dp(2)])

            fraccion = min(actual / max(total - 1, 1), 1.0) if total > 1 else (1.0 if actual > 0 else 0.0)
            if fraccion > 0:
                Color(*tema.PRIMARIO)
                RoundedRectangle(pos=(x_barra, y_barra), size=(max(w_barra * fraccion, dp(4)), h_barra), radius=[dp(2)])

            # ------------------------------------------------------------------
            # Cinta deslizante de notas
            # ------------------------------------------------------------------
            StencilPush()
            Rectangle(pos=(self.x + dp(2), self.y + dp(2)), size=(self.width - dp(4), self.height - dp(4)))
            StencilUse()

            cx = self.center_x
            cy = self.y + (self.height - dp(30)) / 2
            factor = max(0.8, min(float(self.escala_fuente), 1.5))
            espacio = dp(66) * factor

            ancho_act = dp(58) * factor
            alto_act = dp(62) * factor
            ancho_nor = dp(48) * factor
            alto_nor = dp(52) * factor

            # Guía horizontal central
            Color(*tema.BORDE)
            Line(points=[self.x + dp(6), cy, self.right - dp(6), cy], width=1.0)

            # Rango de notas visibles
            alcance = int(math.ceil((self.width / 2.0) / espacio)) + 1
            i_min = max(0, actual - alcance)
            i_max = min(total, actual + alcance + 1)

            for i in range(i_min, i_max):
                pos_x = cx + (i - actual) * espacio
                nota_info = self.notas[i]
                nombre_crudo = nota_info.get("nombre", "") if isinstance(nota_info, dict) else str(nota_info)
                nombre = nombre_para_mostrar(nombre_crudo, self.solfeo)
                estado = self.estados[i] if i < len(self.estados) else "pendiente"

                if i == actual:
                    # Nota actual a tocar
                    Color(*tema.PRIMARIO_SUAVE)
                    RoundedRectangle(
                        pos=(pos_x - ancho_act / 2, cy - alto_act / 2),
                        size=(ancho_act, alto_act),
                        radius=[dp(12)],
                    )
                    Color(*tema.PRIMARIO)
                    Line(
                        rounded_rectangle=[pos_x - ancho_act / 2, cy - alto_act / 2, ancho_act, alto_act, dp(12)],
                        width=2.0,
                    )
                    # Flecha / indicador triangular superior
                    Line(
                        points=[
                            pos_x - dp(6) * factor, cy + alto_act / 2 + dp(8) * factor,
                            pos_x, cy + alto_act / 2 + dp(2) * factor,
                            pos_x + dp(6) * factor, cy + alto_act / 2 + dp(8) * factor
                        ],
                        width=1.8,
                    )
                    dibujo.texto(nombre, pos_x, cy + dp(4) * factor, dp(17) * factor, dibujo.ACTUAL, ancla="centro", negrita=True)
                    dibujo.texto("TOCA", pos_x, cy - dp(18) * factor, dp(8) * factor, dibujo.ACTUAL, ancla="centro", negrita=True)

                elif i < actual:
                    # Nota ya tocada con su evaluación
                    color_estado, simbolo = dibujo.ESTILO_ESTADO.get(estado, (tema.NEUTRO, "–"))
                    if estado == "correcta":
                        bg_color = tema.CORRECTO_SUAVE
                    elif estado == "desafinada":
                        bg_color = tema.DESAFINADO_SUAVE
                    elif estado in ("nota_incorrecta", "octava_incorrecta", "fuera_de_rango"):
                        bg_color = tema.ERROR_SUAVE
                    else:
                        bg_color = tema.NEUTRO_SUAVE

                    Color(*bg_color)
                    RoundedRectangle(
                        pos=(pos_x - ancho_nor / 2, cy - alto_nor / 2),
                        size=(ancho_nor, alto_nor),
                        radius=[dp(10)],
                    )
                    Color(*color_estado)
                    Line(
                        rounded_rectangle=[pos_x - ancho_nor / 2, cy - alto_nor / 2, ancho_nor, alto_nor, dp(10)],
                        width=1.0,
                    )
                    dibujo.texto(simbolo, pos_x, cy + dp(11) * factor, dp(13) * factor, color_estado, ancla="centro", negrita=True)
                    dibujo.texto(nombre, pos_x, cy - dp(9) * factor, dp(12) * factor, color_estado, ancla="centro")

                else:
                    # Nota futura
                    if i == actual + 1:
                        # Próxima nota inmediata: más visible
                        Color(*tema.SUPERFICIE)
                        RoundedRectangle(
                            pos=(pos_x - ancho_nor / 2, cy - alto_nor / 2),
                            size=(ancho_nor, alto_nor),
                            radius=[dp(10)],
                        )
                        Color(*tema.BORDE_FUERTE)
                        Line(
                            rounded_rectangle=[pos_x - ancho_nor / 2, cy - alto_nor / 2, ancho_nor, alto_nor, dp(10)],
                            width=1.2,
                        )
                        dibujo.texto(nombre, pos_x, cy, dp(14) * factor, dibujo.TINTA, ancla="centro", negrita=True)
                    else:
                        # Notas futuras posteriores
                        Color(*tema.SUPERFICIE_2)
                        RoundedRectangle(
                            pos=(pos_x - ancho_nor / 2, cy - alto_nor / 2),
                            size=(ancho_nor, alto_nor),
                            radius=[dp(10)],
                        )
                        Color(*tema.BORDE)
                        Line(
                            rounded_rectangle=[pos_x - ancho_nor / 2, cy - alto_nor / 2, ancho_nor, alto_nor, dp(10)],
                            width=0.8,
                        )
                        dibujo.texto(nombre, pos_x, cy, dp(13) * factor, dibujo.TINTA_SUAVE, ancla="centro")

            StencilUnUse()
            Rectangle(pos=(self.x + dp(2), self.y + dp(2)), size=(self.width - dp(4), self.height - dp(4)))
            StencilPop()