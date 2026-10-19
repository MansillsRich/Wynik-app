"""
Utilidades de dibujo para los widgets de Wynik: texto con la fuente de símbolos musicales y
colores de estado (siempre acompañados de un símbolo: el color nunca es la única señal).
"""

from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Rectangle

from .. import tema
from ..fuentes import FUENTE_TEXTO, registrar_fuentes

registrar_fuentes()

TINTA = tema.TINTA
TINTA_SUAVE = tema.TINTA_SUAVE
PAPEL = tema.SUPERFICIE
FONDO_SUAVE = tema.SUPERFICIE_2
ACTUAL = tema.PRIMARIO
ACTUAL_SUAVE = tema.PRIMARIO_SUAVE
ACENTO = tema.ACENTO
CORRECTO = tema.CORRECTO
DESAFINADO = tema.DESAFINADO
INCORRECTO = tema.ERROR
SIN_DATOS = tema.NEUTRO

# estado de nucleo.sesion.EstadoNota → (color, símbolo)
ESTILO_ESTADO = {
    "correcta": (CORRECTO, "✓"),
    "desafinada": (DESAFINADO, "≈"),
    "nota_incorrecta": (INCORRECTO, "✗"),
    "octava_incorrecta": (INCORRECTO, "✗"),
    "omitida": (SIN_DATOS, "–"),
    "senal_insuficiente": (SIN_DATOS, "?"),
    "baja_confianza": (SIN_DATOS, "?"),
    "fuera_de_rango": (INCORRECTO, "!"),
    "sin_evaluar": (SIN_DATOS, "○"),
}

_texturas = {}


def textura(texto: str, tam: float, negrita: bool = False):
    from kivy.metrics import Metrics
    tam_real = tam * getattr(Metrics, "fontscale", 1.0)
    clave = (texto, round(tam_real, 1), negrita)
    if clave not in _texturas:
        etiqueta = CoreLabel(text=texto, font_size=tam_real, font_name=FUENTE_TEXTO, bold=negrita)
        etiqueta.refresh()
        _texturas[clave] = etiqueta.texture
        if len(_texturas) > 512:
            _texturas.pop(next(iter(_texturas)))
    return _texturas[clave]


def texto(cadena: str, x: float, y: float, tam: float, color=TINTA, ancla: str = "centro",
          negrita: bool = False) -> None:
    """Dibuja `cadena` en el canvas activo. `ancla`: centro, izquierda o derecha (vertical
    siempre centrada en y)."""
    if not cadena:
        return
    tex = textura(cadena, tam, negrita)
    ancho, alto = tex.size
    if ancla == "izquierda":
        x0 = x
    elif ancla == "derecha":
        x0 = x - ancho
    else:
        x0 = x - ancho / 2
    Color(*color)
    Rectangle(texture=tex, pos=(x0, y - alto / 2), size=(ancho, alto))
