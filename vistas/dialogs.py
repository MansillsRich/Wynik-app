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


def _abrir_selector_android(callback_ruta_seleccionada: Callable[[Optional[str]], None]) -> bool:
    """Abre el selector nativo de documentos de Android (SAF) mediante PyJNIus."""
    try:
        from android import activity
        from jnius import autoclass
        from kivy.clock import Clock
        from kivymd.app import MDApp

        Intent = autoclass("android.content.Intent")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Activity = autoclass("android.app.Activity")
        FileOutputStream = autoclass("java.io.FileOutputStream")

        CODIGO_SOLICITUD = 7042

        def responder(ruta_resultado: Optional[str]) -> None:
            """Despacha la respuesta al bucle principal de Kivy de forma segura."""
            Clock.schedule_once(lambda _dt: callback_ruta_seleccionada(ruta_resultado), 0)

        def al_recibir_resultado(request_code, result_code, intent_datos):
            if request_code != CODIGO_SOLICITUD:
                return
            activity.unbind(on_activity_result=al_recibir_resultado)
            if result_code == Activity.RESULT_OK and intent_datos is not None:
                uri = intent_datos.getData()
                if uri is not None:
                    try:
                        actividad = PythonActivity.mActivity
                        resolver = actividad.getContentResolver()
                        stream_entrada = resolver.openInputStream(uri)
                        if stream_entrada is None:
                            print(f"[Wynik] No se pudo abrir InputStream para URI: {uri}")
                            responder(None)
                            return

                        nombre_archivo = "partitura_importada.mxl"
                        try:
                            cursor = resolver.query(uri, None, None, None, None)
                            if cursor is not None:
                                if cursor.moveToFirst():
                                    col = cursor.getColumnIndex("_display_name")
                                    if col >= 0:
                                        val = cursor.getString(col)
                                        if val:
                                            nombre_archivo = val
                                cursor.close()
                        except Exception as e_cursor:  # noqa: BLE001
                            print(f"[Wynik] Error obteniendo nombre del archivo: {e_cursor}")

                        # Asegurar extension admitida (.musicxml, .xml o .mxl)
                        extensiones_validas = (".musicxml", ".xml", ".mxl")
                        if not any(nombre_archivo.lower().endswith(ext) for ext in extensiones_validas):
                            nombre_archivo = f"{nombre_archivo}.mxl"

                        app = MDApp.get_running_app()
                        directorio_destino = app.user_data_dir if app else "/data/data/org.wynik.wynik/files"
                        os.makedirs(directorio_destino, exist_ok=True)
                        ruta_destino = os.path.join(directorio_destino, nombre_archivo)

                        stream_salida = None
                        try:
                            stream_salida = FileOutputStream(ruta_destino)
                            copiado = False

                            # Metodo 1: android.os.FileUtils.copy (API 29+, Samsung S24 / Android 14)
                            try:
                                FileUtils = autoclass("android.os.FileUtils")
                                FileUtils.copy(stream_entrada, stream_salida)
                                copiado = True
                            except Exception as e_fu:
                                print(f"[Wynik] FileUtils.copy no disponible o falló: {e_fu}")

                            # Metodo 2: java.nio.file.Files.copy (API 26+)
                            if not copiado:
                                try:
                                    stream_salida.flush()
                                    stream_salida.close()
                                    stream_salida = None
                                    Paths = autoclass("java.nio.file.Paths")
                                    Files = autoclass("java.nio.file.Files")
                                    StandardCopyOption = autoclass("java.nio.file.StandardCopyOption")
                                    Files.copy(stream_entrada, Paths.get(ruta_destino), StandardCopyOption.REPLACE_EXISTING)
                                    copiado = True
                                except Exception as e_nio:
                                    print(f"[Wynik] Files.copy falló: {e_nio}")

                            # Metodo 3: Fallback lectura byte a byte
                            if not copiado:
                                if stream_salida is None:
                                    stream_salida = FileOutputStream(ruta_destino)
                                b = stream_entrada.read()
                                while b != -1:
                                    stream_salida.write(b)
                                    b = stream_entrada.read()

                            if stream_salida is not None:
                                stream_salida.flush()

                            tamano = os.path.getsize(ruta_destino) if os.path.isfile(ruta_destino) else 0
                            print(f"[Wynik] Partitura copiada exitosamente: {ruta_destino} ({tamano} bytes)")
                            if tamano > 0:
                                responder(ruta_destino)
                                return
                            print("[Wynik] Advertencia: Archivo copiado con 0 bytes")
                        finally:
                            if stream_salida is not None:
                                try:
                                    stream_salida.close()
                                except Exception:
                                    pass
                            try:
                                stream_entrada.close()
                            except Exception:
                                pass
                    except Exception as err:  # noqa: BLE001
                        print(f"[Wynik] Error importando archivo desde URI: {err}")

            responder(None)

        activity.bind(on_activity_result=al_recibir_resultado)
        intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
        intent.addCategory(Intent.CATEGORY_OPENABLE)
        intent.setType("*/*")
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        PythonActivity.mActivity.startActivityForResult(intent, CODIGO_SOLICITUD)
        return True
    except Exception as error:  # noqa: BLE001
        print(f"[Wynik] No se pudo lanzar el selector nativo Android: {error}")
        return False


def abrir_selector_de_archivo(callback_ruta_seleccionada: Callable[[Optional[str]], None]) -> None:
    """
    Abre el selector de archivos MusicXML (.xml, .musicxml, .mxl).
    Llama a `callback_ruta_seleccionada` con la ruta absoluta o None si se cancela.
    """
    from kivy.utils import platform
    if platform == "android":
        if _abrir_selector_android(callback_ruta_seleccionada):
            return

    from kivy.core.window import Window
    from kivy.metrics import dp
    from kivy.uix.filechooser import FileChooserListView

    from .componentes import Superficie

    ruta_inicial = os.path.expanduser("~")
    if platform == "android":
        for pos in ("/storage/emulated/0/Download", "/storage/emulated/0/Documents", "/sdcard/Download", "/sdcard"):
            if os.path.isdir(pos):
                ruta_inicial = pos
                break

    elegido = {"ruta": None, "hecho": False}
    panel = Superficie(size_hint_y=None, height=min(dp(380), max(dp(160), Window.height * 0.5)),
                       padding=dp(6), fondo=list(tema.TINTA), borde=list(tema.TINTA), radio=dp(14))
    selector = FileChooserListView(filters=["*.xml", "*.musicxml", "*.mxl"], path=ruta_inicial)
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
