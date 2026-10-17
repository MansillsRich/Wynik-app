"""
Diálogos de Wynik: confirmaciones, errores, resumen de la práctica y selector de archivos.

Todos comparten el mismo aspecto (`mostrar_dialogo`): tarjeta centrada sobre un velo, título
con icono, mensaje y botones. Atrás (Esc) los cierra como «cancelar»; ver `WynikApp._tecla`.

Las importaciones de Kivy están dentro de las funciones: este módulo se importa también en
las simulaciones sin interfaz, que nunca abren un diálogo.
"""

import os
from typing import Callable, Optional, Sequence, Tuple

from . import tema

_abiertos = []


def dialogo_abierto():
    """El diálogo visible más reciente (o None)."""
    return _abiertos[-1] if _abiertos else None


def cerrar_dialogo() -> bool:
    vista = dialogo_abierto()
    if vista is None:
        return False
    vista.dismiss()
    return True


def mostrar_dialogo(titulo: str, mensaje: str = "", icono: str = "", color_icono=None,
                    botones: Sequence[Tuple[str, str, Optional[Callable[[], None]]]] = (("Entendido", "primario", None),),
                    contenido=None, ancho_max_dp: float = 460, al_cerrar: Optional[Callable[[], None]] = None):
    """Abre un diálogo modal. `botones`: (texto, variante de `Boton`, acción o None); cada
    botón ejecuta su acción y cierra el diálogo. Devuelve la ModalView."""
    from kivy.core.window import Window
    from kivy.metrics import dp, sp
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.modalview import ModalView

    from .componentes import Boton, Etiqueta, Icono, Superficie

    vista = ModalView(size_hint=(None, None), auto_dismiss=True, background="",
                      background_color=(0, 0, 0, 0), overlay_color=tema.VELO)
    tarjeta = Superficie(orientation="vertical", padding=[dp(22), dp(20), dp(22), dp(16)],
                         spacing=dp(14), size_hint=(None, None), sombra=True, radio=dp(22))

    cabecera = BoxLayout(spacing=dp(12), size_hint_y=None)
    if icono:
        cabecera.add_widget(Icono(icono=icono, font_size=sp(26), size_hint=(None, None),
                                  size=(dp(32), dp(32)), pos_hint={"center_y": 0.5},
                                  color=color_icono or tema.PRIMARIO))
    rotulo = Etiqueta(text=titulo, font_name=tema.FUENTE_TEXTO, bold=True, font_size=sp(tema.T_TITULO),
                      pos_hint={"center_y": 0.5})
    cabecera.add_widget(rotulo)
    rotulo.bind(height=lambda *_: setattr(cabecera, "height", max(dp(32), rotulo.height)))
    tarjeta.add_widget(cabecera)
    if mensaje:
        tarjeta.add_widget(Etiqueta(text=mensaje, color=tema.TINTA_SUAVE, font_size=sp(tema.T_CUERPO)))
    if contenido is not None:
        tarjeta.add_widget(contenido)

    fila = BoxLayout(spacing=dp(10), size_hint_y=None, height=dp(tema.ALTO_BOTON))
    apilar = len(botones) > 2
    if apilar:
        fila.orientation = "vertical"
        fila.height = len(botones) * dp(tema.ALTO_BOTON) + (len(botones) - 1) * dp(8)
        fila.spacing = dp(8)

    def accion(funcion):
        def pulsar(*_):
            try:
                if funcion is not None:
                    funcion()
            finally:
                vista.dismiss()
        return pulsar

    for texto, variante, funcion in botones:
        fila.add_widget(Boton(texto=texto, variante=variante, on_release=accion(funcion)))
    tarjeta.add_widget(fila)

    def medir(*_):
        ancho = min(Window.width - dp(32), dp(ancho_max_dp))
        tarjeta.width = ancho
        vista.size = (ancho, min(tarjeta.minimum_height, Window.height - dp(24)))
        tarjeta.height = vista.height
    tarjeta.bind(minimum_height=medir)
    Window.bind(size=medir)
    vista.add_widget(tarjeta)
    medir()

    def cerrada(*_):
        Window.unbind(size=medir)
        if vista in _abiertos:
            _abiertos.remove(vista)
        if al_cerrar is not None:
            al_cerrar()
    vista.bind(on_dismiss=cerrada)
    _abiertos.append(vista)
    vista.open()
    return vista


def abrir_selector_de_archivo(callback_ruta_seleccionada: Callable[[Optional[str]], None]) -> None:
    """
    Abre el selector de archivos MusicXML (.xml, .musicxml, .mxl).
    Llama a `callback_ruta_seleccionada` con la ruta absoluta o None si se cancela.
    """
    from kivy.core.window import Window
    from kivy.metrics import dp
    from kivy.uix.filechooser import FileChooserListView

    from .componentes import Superficie

    elegido = {"ruta": None, "hecho": False}
    panel = Superficie(size_hint_y=None, height=min(dp(380), max(dp(160), Window.height * 0.5)),
                       padding=dp(6), fondo=list(tema.TINTA), borde=list(tema.TINTA), radio=dp(14))
    selector = FileChooserListView(filters=["*.xml", "*.musicxml", "*.mxl"], path=os.path.expanduser("~"))
    panel.add_widget(selector)

    def aceptar():
        seleccion = selector.selection
        elegido["ruta"] = seleccion[0] if seleccion else None

    def cerrar():
        if not elegido["hecho"]:
            elegido["hecho"] = True
            callback_ruta_seleccionada(elegido["ruta"])

    vista = mostrar_dialogo("Importar partitura", "Elige un archivo MusicXML (.musicxml, .xml o .mxl).",
                            icono="file-music-outline",
                            botones=(("Cancelar", "texto", None), ("Abrir", "primario", aceptar)),
                            contenido=panel, ancho_max_dp=640, al_cerrar=cerrar)

    def doble_toque(_selector, seleccion, _toque):
        if seleccion:
            elegido["ruta"] = seleccion[0]
            vista.dismiss()
    selector.bind(on_submit=doble_toque)
