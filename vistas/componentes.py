"""
Componentes visuales reutilizables de Wynik (Kivy puro + la fuente de iconos de KivyMD).

Su aspecto está en `componentes.kv`; aquí, el comportamiento que no cabe en KV:

- `Pulsable`: respuesta al toque animada (capa de estado de 0 a 1) para botones y tarjetas.
- `Boton`, `BotonIcono`, `Opcion`: controles con área mínima de pulsación de 44 dp. El texto
  de `Boton` se ajusta a su ancho (nunca se sale ni se superpone al icono).
- `GrupoOpciones`: rejilla cuyas columnas dependen del ancho disponible y cuyas filas tienen la
  altura de la opción más alta (todas iguales).
- `Columnas`: una o dos columnas según el ancho (cada columna alineada arriba).
- `DisposicionPractica`: reparte la pantalla de práctica según el tamaño de la ventana
  (vertical, horizontal amplia o apaisada baja) sin que nada desaparezca: si no cabe, crece y
  la pantalla se desplaza.
- `TiraResultados`, `MedidorCents`, `AnilloProgreso`, `GraficoSesiones`: dibujos de estado.

Los dibujos se rehacen solo cuando cambian sus datos o su tamaño: nada se anima mientras se
escucha salvo transiciones cortas de color al cambiar el resultado.
"""

from __future__ import annotations

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.properties import (BooleanProperty, ListProperty, NumericProperty, ObjectProperty,
                             OptionProperty, StringProperty)
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.layout import Layout
from kivy.uix.widget import Widget

from . import tema
from .widgets import dibujo

try:
    from kivymd.icon_definitions import md_icons
except Exception:  # noqa: BLE001
    md_icons = {}


def glifo(nombre: str) -> str:
    """Carácter de la fuente de iconos de KivyMD («Icons») para `nombre`."""
    return md_icons.get(nombre, "") if nombre else ""


def mezcla(a, b, t):
    t = max(0.0, min(1.0, float(t)))
    return [a[i] + (b[i] - a[i]) * t for i in range(4)]


# ------------------------------------------------------------------------------ visibilidad
class Ocultable:
    """`visible=False` saca el widget de su contenedor (no ocupa sitio ni deja el hueco del
    espaciado, a diferencia de alto 0 + opacidad 0); `visible=True` lo devuelve a su sitio."""
    visible = BooleanProperty(True)

    def on_visible(self, *args):
        if not hasattr(self, "_aplicar_visible"):
            self._aplicar_visible = Clock.create_trigger(self._colocar, -1)
        self._aplicar_visible()

    def on_parent(self, *args):
        if self.parent is not None and not self.visible:
            self.on_visible()

    def _colocar(self, *args):
        if not self.visible:
            padre = self.parent
            if padre is None:
                return
            self._padre_original = padre
            self._orden_original = list(padre.children)
            padre.remove_widget(self)
            return
        padre = getattr(self, "_padre_original", None)
        if padre is None or self.parent is not None:
            return
        orden = self._orden_original
        posicion = orden.index(self) if self in orden else 0
        indice = sum(1 for w in orden[:posicion] if w.parent is padre)
        padre.add_widget(self, index=indice)


class Bloque(Ocultable, BoxLayout):
    """BoxLayout que se puede ocultar (ver `Ocultable`)."""


# ------------------------------------------------------------------------------ texto e iconos
class Etiqueta(Ocultable, Label):
    """Texto que ocupa el ancho disponible, se parte en líneas y toma la altura de su contenido.
    `lineas` > 0 limita las líneas (lo que no cabe termina en «…»)."""
    lineas = NumericProperty(0)


class Icono(Label):
    icono = StringProperty("")


class IconoCirculo(Icono):
    fondo = ListProperty(list(tema.PRIMARIO_SUAVE))


# ------------------------------------------------------------------------------ pulsación
class Pulsable(ButtonBehavior):
    """Capa de estado animada al pulsar (`capa` va de 0 a 1)."""
    capa = NumericProperty(0)

    def on_state(self, _instancia, estado):
        Animation.cancel_all(self, "capa")
        if estado == "down":
            Animation(capa=1, d=0.06, t="out_quad").start(self)
        else:
            Animation(capa=0, d=0.25, t="out_quad").start(self)


TRANSPARENTE = (0, 0, 0, 0)
# variante → (fondo, texto, borde)
COLORES_BOTON = {
    "primario": (tema.PRIMARIO, tema.SOBRE_PRIMARIO, TRANSPARENTE),
    "tonal": (tema.PRIMARIO_SUAVE, tema.PRIMARIO_OSCURO, TRANSPARENTE),
    "contorno": (TRANSPARENTE, tema.PRIMARIO, tema.BORDE_FUERTE),
    "texto": (TRANSPARENTE, tema.PRIMARIO, TRANSPARENTE),
    "claro": (tema.SUPERFICIE, tema.PRIMARIO_OSCURO, TRANSPARENTE),
    "acento": (tema.ACENTO, tema.SOBRE_PRIMARIO, TRANSPARENTE),
}
COLORES_BOTON_ICONO = {
    "plano": (TRANSPARENTE, tema.TINTA_SUAVE, TRANSPARENTE),
    "tonal": (tema.SUPERFICIE_2, tema.TINTA, TRANSPARENTE),
    "contorno": (tema.SUPERFICIE, tema.TINTA, tema.BORDE),
    "primario": (tema.PRIMARIO, tema.SOBRE_PRIMARIO, TRANSPARENTE),
    "claro": (tema.con_alfa(tema.SOBRE_PRIMARIO, 0.18), tema.SOBRE_PRIMARIO, TRANSPARENTE),
}


class _Coloreado:
    """`fondo`, `tinta` y `borde` según `variante` (y `activo`, si lo hay)."""
    fondo = ListProperty(list(TRANSPARENTE))
    tinta = ListProperty(list(tema.TINTA))
    borde = ListProperty(list(TRANSPARENTE))
    _TABLA = {}

    def on_kv_post(self, *args):
        self._colorear()

    def on_variante(self, *args):
        self._colorear()

    def _colorear(self, *args):
        fondo, tinta, borde = self._TABLA[self.variante]
        if getattr(self, "activo", False):
            fondo, tinta, borde = tema.PRIMARIO_SUAVE, tema.PRIMARIO, tema.PRIMARIO
        self.fondo, self.tinta, self.borde = list(fondo), list(tinta), list(borde)


class Boton(_Coloreado, Pulsable, Label):
    """Botón con icono opcional y texto en una misma etiqueta (marcado de Kivy): el icono y el
    texto no pueden solaparse. El texto se parte en líneas dentro del ancho que tenga el botón
    (el alto crece si hace falta); `BotonAjustado` toma el ancho de su contenido."""
    texto = StringProperty("")
    icono = StringProperty("")
    variante = OptionProperty("primario", options=tuple(COLORES_BOTON))
    relleno_x = NumericProperty(dp(20))
    ajustar = BooleanProperty(False)
    _TABLA = COLORES_BOTON

    def contenido(self, texto, icono, tam_icono):
        partes = []
        if icono and glifo(icono):
            partes.append(f"[font=Icons][size={int(tam_icono)}]{glifo(icono)}[/size][/font]")
        if texto:
            partes.append(texto.replace("&", "&amp;").replace("[", "&bl;").replace("]", "&br;"))
        return "  ".join(partes)


class BotonIcono(Ocultable, _Coloreado, Pulsable, Label):
    icono = StringProperty("")
    variante = OptionProperty("plano", options=tuple(COLORES_BOTON_ICONO))
    activo = BooleanProperty(False)
    _TABLA = COLORES_BOTON_ICONO

    def on_activo(self, *args):
        self._colorear()


class Opcion(Pulsable, BoxLayout):
    """Tarjeta seleccionable: el estado activo se ve en el fondo, el borde, el color del texto
    y una marca ✓ (el color no es la única señal)."""
    texto = StringProperty("")
    detalle = StringProperty("")
    icono = StringProperty("")
    dibujo = StringProperty("")       # «guitarra», «piano»…: ilustración en lugar del icono
    activa = BooleanProperty(False)
    habilitada = BooleanProperty(True)
    t_activa = NumericProperty(0)

    def on_kv_post(self, *args):
        self.t_activa = 1 if self.activa else 0

    def on_activa(self, *args):
        Animation.cancel_all(self, "t_activa")
        Animation(t_activa=1 if self.activa else 0, d=tema.DURACION_ANIMACION, t="out_quad").start(self)

    def on_release(self):
        pass


class GrupoOpciones(GridLayout):
    """Rejilla de `Opcion`: columnas según el ancho (`ancho_minimo` por opción, como mucho
    `max_columnas`) y todas las filas con la altura de la opción más alta."""
    ancho_minimo = NumericProperty(dp(140))
    max_columnas = NumericProperty(0)       # 0: tantas como opciones

    def __init__(self, **kwargs):
        self._aplazado = Clock.create_trigger(self._recalcular, -1)
        super().__init__(**kwargs)
        self.bind(width=self._aplazado, children=self._aplazado, ancho_minimo=self._aplazado)

    def add_widget(self, widget, *args, **kwargs):
        super().add_widget(widget, *args, **kwargs)
        widget.bind(minimum_height=self._aplazado)
        self._aplazado()

    def _recalcular(self, *args):
        n = len(self.children)
        if not n:
            return
        tope = int(self.max_columnas) or n
        hueco = self.spacing[0] if isinstance(self.spacing, (list, tuple)) else self.spacing
        caben = int((self.width + hueco) // (self.ancho_minimo + hueco)) if self.width > 1 else 1
        cols = max(1, min(tope, n, caben))
        # reparto equilibrado: 4 opciones en 3 columnas → 2 + 2
        filas = -(-n // cols)
        cols = -(-n // filas)
        self.cols = cols
        alto = max((getattr(c, "minimum_height", c.height) for c in self.children), default=dp(48))
        self.row_default_height = max(dp(tema.ALTO_TOQUE), alto)


class Columnas(BoxLayout):
    """Dos columnas desde `ancho_corte`; una sola por debajo. Las columnas son hijos con
    `size_hint_y: None` y `height: self.minimum_height`."""
    ancho_corte = NumericProperty(dp(860))
    amplia = BooleanProperty(False)

    def on_width(self, *args):
        self.amplia = self.width >= self.ancho_corte
        self.orientation = "horizontal" if self.amplia else "vertical"


class Superficie(Ocultable, BoxLayout):
    fondo = ListProperty(list(tema.SUPERFICIE))
    borde = ListProperty(list(tema.BORDE))
    radio = NumericProperty(dp(tema.RADIO))
    sombra = BooleanProperty(False)


class TarjetaPulsable(Pulsable, Superficie):
    pass


class FilaPartitura(TarjetaPulsable):
    """Partitura de la biblioteca (se crea desde Python con sus datos)."""
    titulo = StringProperty("")
    detalle = StringProperty("")
    existe = BooleanProperty(True)
    instrumento = StringProperty("partitura")


class FilaSesion(Superficie):
    titulo = StringProperty("")
    detalle = StringProperty("")
    porcentaje = NumericProperty(0)


class FilaPartituraProgreso(Superficie):
    titulo = StringProperty("")
    detalle = StringProperty("")
    mejor = NumericProperty(0)


class Chip(BoxLayout):
    texto = StringProperty("")
    icono = StringProperty("")
    color = ListProperty(list(tema.TINTA_SUAVE))
    fondo = ListProperty(list(tema.SUPERFICIE_2))


class EstadoPildora(Chip):
    """Píldora de estado de evaluación (`clave` de `tema.ESTADOS`) con transición de color."""
    clave = StringProperty("neutro")

    def on_kv_post(self, *args):
        self._aplicar(animar=False)

    def on_clave(self, *args):
        self._aplicar(animar=True)

    def _aplicar(self, animar=True):
        color, fondo, icono, texto = tema.ESTADOS.get(self.clave, tema.ESTADOS["neutro"])
        self.icono, self.texto = icono, texto
        Animation.cancel_all(self, "color", "fondo")
        if animar:
            Animation(color=list(color), fondo=list(fondo), d=tema.DURACION_ANIMACION).start(self)
        else:
            self.color, self.fondo = list(color), list(fondo)


class BarraSuperior(BoxLayout):
    titulo = StringProperty("")
    atras = BooleanProperty(True)
    fuente = StringProperty(tema.FUENTE_ROTULO)

    def on_atras_pulsado(self):
        from kivy.app import App
        App.get_running_app().atras()


# ------------------------------------------------------------------------------ dibujos de estado
class _Dibujo(Ocultable, Widget):
    def __init__(self, **kwargs):
        self._redibujar = Clock.create_trigger(self.redibujar, -1)
        super().__init__(**kwargs)
        self.bind(pos=self._redibujar, size=self._redibujar)

    def redibujar(self, *args):
        pass


class BarraProgreso(_Dibujo):
    """Barra de 0 a 1 con transición suave. Con `buscable`, se puede arrastrar y llama a
    `al_buscar(fraccion)`; sin él es de solo lectura (no aparenta lo que no hace)."""
    valor = NumericProperty(0)
    mostrado = NumericProperty(0)
    color = ListProperty(list(tema.PRIMARIO))
    buscable = BooleanProperty(False)
    al_buscar = ObjectProperty(None, allownone=True)
    animar = BooleanProperty(True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(mostrado=self._redibujar, color=self._redibujar, buscable=self._redibujar)

    def on_valor(self, *args):
        Animation.cancel_all(self, "mostrado")
        destino = max(0.0, min(1.0, float(self.valor)))
        if self.animar and abs(destino - self.mostrado) < 0.5:
            Animation(mostrado=destino, d=0.2, t="out_quad").start(self)
        else:
            self.mostrado = destino

    def redibujar(self, *args):
        self.canvas.clear()
        alto = min(self.height, dp(6))
        y = self.center_y - alto / 2
        with self.canvas:
            Color(*tema.SUPERFICIE_2)
            RoundedRectangle(pos=(self.x, y), size=(self.width, alto), radius=[alto / 2])
            Color(*self.color)
            ancho = self.width * self.mostrado
            if ancho > 0.5:
                RoundedRectangle(pos=(self.x, y), size=(max(alto, ancho), alto), radius=[alto / 2])
            if self.buscable:
                Ellipse(pos=(self.x + ancho - dp(8), self.center_y - dp(8)), size=(dp(16), dp(16)))

    def _buscar(self, toque):
        if self.width > 0 and self.al_buscar is not None:
            fraccion = max(0.0, min(1.0, (toque.x - self.x) / self.width))
            self.valor = fraccion
            self.al_buscar(fraccion)

    def on_touch_down(self, toque):
        if self.buscable and self.collide_point(*toque.pos):
            toque.grab(self)
            self._buscar(toque)
            return True
        return super().on_touch_down(toque)

    def on_touch_move(self, toque):
        if toque.grab_current is self:
            self._buscar(toque)
            return True
        return super().on_touch_move(toque)

    def on_touch_up(self, toque):
        if toque.grab_current is self:
            toque.ungrab(self)
            return True
        return super().on_touch_up(toque)


class TiraResultados(_Dibujo):
    """Una marca por nota de la práctica con el color de su resultado (pendiente: tenue) y la
    posición actual resaltada. Sustituye a una barra de progreso genérica."""
    estados = ListProperty([])
    indice = NumericProperty(0)

    COLORES = {
        "correcta": tema.CORRECTO, "desafinada": tema.DESAFINADO,
        "nota_incorrecta": tema.ERROR, "octava_incorrecta": tema.ERROR, "fuera_de_rango": tema.ERROR,
        "sin_evaluar": tema.BORDE_FUERTE, "omitida": tema.TINTA_TENUE,
        "senal_insuficiente": tema.TINTA_TENUE, "baja_confianza": tema.TINTA_TENUE,
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(estados=self._redibujar, indice=self._redibujar)

    def redibujar(self, *args):
        self.canvas.clear()
        n = len(self.estados)
        alto = min(self.height, dp(8))
        y = self.center_y - alto / 2
        with self.canvas:
            Color(*tema.SUPERFICIE_2)
            RoundedRectangle(pos=(self.x, y), size=(self.width, alto), radius=[alto / 2])
            if not n or self.width < 4:
                return
            paso = self.width / n
            hueco = 1 if paso >= 4 else 0
            # tramos consecutivos del mismo color en un solo rectángulo
            inicio = 0
            for i in range(1, n + 1):
                if i < n and self.estados[i] == self.estados[inicio]:
                    continue
                color = self.COLORES.get(self.estados[inicio])
                if color is not None:
                    Color(*color)
                    Rectangle(pos=(self.x + inicio * paso, y), size=((i - inicio) * paso - hueco, alto))
                inicio = i
            actual = min(max(int(self.indice), 0), n - 1)
            Color(*tema.ACENTO)
            ancho = max(dp(3), paso)
            RoundedRectangle(pos=(self.x + actual * paso + paso / 2 - ancho / 2, y - dp(2)),
                             size=(ancho, alto + dp(4)), radius=[dp(1.5)])


class MedidorCents(_Dibujo):
    """Afinación de la última nota oída: escala de −50 a +50 cents con la zona afinada
    (±25, la tolerancia de la evaluación) marcada. Sin nota oída, solo la escala."""
    cents = ObjectProperty(None, allownone=True)
    tolerancia = NumericProperty(25)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(cents=self._redibujar)

    def redibujar(self, *args):
        self.canvas.clear()
        if self.width < dp(60):
            return
        izq, der = self.x + dp(22), self.right - dp(22)
        ancho = der - izq
        y = self.y + self.height * 0.62

        def x_de(c):
            return izq + (max(-50.0, min(50.0, c)) + 50.0) / 100.0 * ancho

        with self.canvas:
            Color(*tema.SUPERFICIE_2)
            RoundedRectangle(pos=(izq, y - dp(3)), size=(ancho, dp(6)), radius=[dp(3)])
            Color(*tema.CORRECTO_SUAVE)
            RoundedRectangle(pos=(x_de(-self.tolerancia), y - dp(3)),
                             size=(x_de(self.tolerancia) - x_de(-self.tolerancia), dp(6)), radius=[dp(3)])
            Color(*tema.BORDE_FUERTE)
            for c in (-50, -25, 0, 25, 50):
                Line(points=[x_de(c), y - dp(5), x_de(c), y + dp(5)], width=dp(0.6))
            tam = sp(10)
            dibujo.texto("−50", izq - dp(12), y, tam, tema.TINTA_TENUE)
            dibujo.texto("+50", der + dp(12), y, tam, tema.TINTA_TENUE)
            if self.cents is None:
                dibujo.texto("afinación", (izq + der) / 2, self.y + dp(6), tam, tema.TINTA_TENUE)
                return
            c = float(self.cents)
            color = (tema.CORRECTO if abs(c) <= self.tolerancia else
                     tema.DESAFINADO if abs(c) <= 50 else tema.ERROR)
            Color(*color)
            x = x_de(c)
            Ellipse(pos=(x - dp(6), y - dp(6)), size=(dp(12), dp(12)))
            dibujo.texto(f"{c:+.0f} cents", x if izq + dp(30) < x < der - dp(30) else (izq + der) / 2,
                         self.y + dp(6), tam, color, negrita=True)


class AnilloProgreso(_Dibujo):
    """Porcentaje (0–1) como anillo, con el número en el centro."""
    valor = NumericProperty(0)
    mostrado = NumericProperty(0)
    color = ListProperty(list(tema.PRIMARIO))
    grosor = NumericProperty(dp(9))
    rotulo = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(mostrado=self._redibujar, color=self._redibujar, rotulo=self._redibujar)

    def on_valor(self, *args):
        Animation.cancel_all(self, "mostrado")
        Animation(mostrado=float(self.valor), d=0.6, t="out_cubic").start(self)

    def redibujar(self, *args):
        self.canvas.clear()
        r = min(self.width, self.height) / 2 - self.grosor
        if r <= dp(8):
            return
        cx, cy = self.center
        with self.canvas:
            Color(*tema.SUPERFICIE_2)
            Line(circle=(cx, cy, r), width=self.grosor / 2)
            if self.mostrado > 0.001:
                Color(*self.color)
                Line(circle=(cx, cy, r, 0, 360 * min(1.0, self.mostrado)), width=self.grosor / 2, cap="round")
            dibujo.texto(f"{round(100 * self.valor)} %", cx, cy + (dp(7) if self.rotulo else 0),
                         max(sp(14), r * 0.48), tema.TINTA, negrita=True)
            if self.rotulo:
                dibujo.texto(self.rotulo, cx, cy - r * 0.38, max(sp(10), r * 0.2), tema.TINTA_SUAVE)


class GraficoSesiones(_Dibujo):
    """Precisión de las últimas sesiones (barras, de la más antigua a la más reciente) sobre
    una escala fija de 0 a 100 %."""
    valores = ListProperty([])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(valores=self._redibujar)

    def redibujar(self, *args):
        self.canvas.clear()
        if self.width < dp(80) or self.height < dp(60):
            return
        izq, der = self.x + dp(40), self.right - dp(4)
        abajo, arriba = self.y + dp(8), self.top - dp(8)
        alto = arriba - abajo
        with self.canvas:
            for pct in (0, 50, 100):
                y = abajo + alto * pct / 100
                Color(*(tema.BORDE if pct else tema.BORDE_FUERTE))
                Line(points=[izq, y, der, y], width=dp(0.6))
                dibujo.texto(f"{pct} %", self.x + dp(34), y, sp(10), tema.TINTA_TENUE, ancla="derecha")
            n = len(self.valores)
            if not n:
                dibujo.texto("Sin sesiones todavía", (izq + der) / 2, abajo + alto / 2, sp(12), tema.TINTA_SUAVE)
                return
            paso = (der - izq) / max(n, 6)
            ancho = min(paso * 0.62, dp(28))
            for i, v in enumerate(self.valores):
                v = max(0.0, min(1.0, float(v)))
                x = izq + i * paso + (paso - ancho) / 2
                Color(*(tema.PRIMARIO if i == n - 1 else tema.con_alfa(tema.PRIMARIO, 0.45)))
                h = max(dp(2), alto * v)
                RoundedRectangle(pos=(x, abajo), size=(ancho, h), radius=[min(dp(4), ancho / 2), min(dp(4), ancho / 2), 0, 0])
            ultimo = max(0.0, min(1.0, float(self.valores[-1])))
            x = izq + (n - 1) * paso + paso / 2
            dibujo.texto(f"{round(100 * ultimo)} %", x, min(arriba - dp(6), abajo + alto * ultimo + dp(10)),
                         sp(10), tema.PRIMARIO, negrita=True)


# ------------------------------------------------------------------------------ práctica
class DisposicionPractica(Layout):
    """Coloca los cuatro bloques de la práctica (`foco`, `partitura`, `guia`, `pie`) según el
    tamaño disponible. Modos:

    - «vertical» (teléfono, ventana estrecha): foco, partitura, guía y pie apilados.
    - «amplia» (≥ 480 dp de alto y ≥ 900 dp de ancho, o ≥ 720 dp y claramente más ancha que
      alta): partitura arriba a todo el ancho; abajo,
      foco y pie a la izquierda y guía a la derecha.
    - «apaisada» (< 480 dp de alto y más ancha que alta): foco y partitura a la izquierda; guía
      y pie a la derecha.

    Cada bloque tiene una altura mínima; si la ventana no la alcanza, la disposición crece por
    encima del alto visible (`alto_minimo`) y el ScrollView que la contiene se desplaza.
    `pie` y `foco` aportan su altura natural (`height`)."""
    foco = ObjectProperty(None, allownone=True)
    partitura = ObjectProperty(None, allownone=True)
    guia = ObjectProperty(None, allownone=True)
    pie = ObjectProperty(None, allownone=True)
    modo = StringProperty("vertical")
    alto_visible = NumericProperty(0)
    alto_minimo = NumericProperty(0)
    hueco = NumericProperty(dp(10))
    margen = NumericProperty(dp(12))

    MIN_PARTITURA = dp(140)
    MIN_GUIA = dp(120)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._trigger_layout, size=self._trigger_layout, alto_visible=self._trigger_layout)

    def on_pie(self, *args):
        if self.pie is not None:
            self.pie.bind(height=self._trigger_layout)

    def on_foco(self, *args):
        if self.foco is not None:
            self.foco.bind(height=self._trigger_layout)

    def _modo(self, ancho, alto):
        return tema.modo_practica(ancho / dp(1), alto / dp(1))

    def do_layout(self, *args):
        if None in (self.foco, self.partitura, self.guia, self.pie):
            return
        m, g = self.margen, self.hueco
        ancho = self.width - 2 * m
        visible = max(self.alto_visible, dp(100))
        modo = self._modo(self.width, visible)
        self.modo = modo
        h_foco, h_pie = self.foco.height, self.pie.height
        if modo == "vertical":
            necesario = h_foco + h_pie + self.MIN_PARTITURA + self.MIN_GUIA + 3 * g + 2 * m
        elif modo == "amplia":
            necesario = max(self.MIN_PARTITURA + g + max(h_foco + g + h_pie, self.MIN_GUIA), 0) + 2 * m
        else:
            necesario = max(h_foco + g + self.MIN_PARTITURA, self.MIN_GUIA + g + h_pie) + 2 * m
        self.alto_minimo = necesario
        alto_total = max(visible, necesario)
        if abs(self.height - alto_total) > 0.5:
            self.height = alto_total        # vuelve a llamar a do_layout
            return
        x0, y_top = self.x + m, self.top - m
        alto = alto_total - 2 * m
        if modo == "vertical":
            resto = alto - h_foco - h_pie - 3 * g
            h_part = max(self.MIN_PARTITURA, resto * 0.52)
            h_guia = max(self.MIN_GUIA, resto - h_part)
            y = y_top - h_foco
            self._poner(self.foco, x0, y, ancho, h_foco)
            y -= g + h_part
            self._poner(self.partitura, x0, y, ancho, h_part)
            y -= g + h_guia
            self._poner(self.guia, x0, y, ancho, h_guia)
            self._poner(self.pie, x0, self.y + m, ancho, h_pie)
        elif modo == "amplia":
            h_part = max(self.MIN_PARTITURA, min(alto * 0.5, dp(320)))
            self._poner(self.partitura, x0, y_top - h_part, ancho, h_part)
            abajo = alto - h_part - g
            ancho_izq = max(dp(320), min(ancho * 0.42, dp(480)))
            self._poner(self.foco, x0, y_top - h_part - g - h_foco, ancho_izq, h_foco)
            self._poner(self.pie, x0, self.y + m, ancho_izq, h_pie)
            self._poner(self.guia, x0 + ancho_izq + g, self.y + m, ancho - ancho_izq - g, abajo)
        else:
            ancho_izq = ancho * 0.55
            ancho_der = ancho - ancho_izq - g
            self._poner(self.foco, x0, y_top - h_foco, ancho_izq, h_foco)
            self._poner(self.partitura, x0, self.y + m, ancho_izq, alto - h_foco - g)
            self._poner(self.pie, x0 + ancho_izq + g, self.y + m, ancho_der, h_pie)
            self._poner(self.guia, x0 + ancho_izq + g, self.y + m + h_pie + g, ancho_der, alto - h_pie - g)

    @staticmethod
    def _poner(widget, x, y, ancho, alto):
        widget.size_hint = (None, None)
        widget.pos = (x, y)
        widget.size = (max(0, ancho), max(0, alto))
