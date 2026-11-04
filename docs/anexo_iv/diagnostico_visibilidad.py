"""
Script auxiliar del Anexo IV (no forma parte de la aplicación Wynik).

Reproduce el defecto de visibilidad detectado durante la captura de pantallas: los widgets
con `visible: False` al construir la interfaz (clase `vistas.componentes.Ocultable`) se
retiran de su contenedor y, sin otra referencia fuerte, Python los libera; cuando su
condición pasa a ser verdadera ya no pueden volver a mostrarse.

Pasos: arranca la aplicación con un directorio de datos vacío, carga una partitura de
guitarra sin <transpose> (que produce un aviso de importación) y comprueba si la etiqueta
del aviso está en el árbol de widgets de «Preparar la práctica».

Uso (desde la raíz del repositorio; en Linux sin pantalla, anteponer «xvfb-run -a»):
    python docs/anexo_iv/diagnostico_visibilidad.py
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
DATOS = Path(tempfile.mkdtemp(prefix="wynik_visibilidad_"))
os.environ["WYNIK_DATOS"] = str(DATOS)
os.environ["KIVY_HOME"] = str(DATOS)
os.environ["KIVY_NO_ARGS"] = "1"
sys.path.insert(0, str(AQUI.parent.parent))

from kivy.config import Config  # noqa: E402

Config.set("graphics", "width", "412")
Config.set("graphics", "height", "915")

from kivy.clock import Clock  # noqa: E402

from vistas import WynikApp  # noqa: E402

ODA = str(AQUI / "partituras" / "oda_a_la_alegria_guitarra.musicxml")
app = WynikApp()


def recorrer(widget):
    yield widget
    for hijo in widget.children:
        yield from recorrer(hijo)


def cargar(_dt):
    app._partitura_seleccionada(ODA)
    Clock.schedule_once(comprobar, 1.5)


def comprobar(_dt):
    pantalla = app.root.get_screen("ajustes_inicio")
    en_arbol = [w for w in recorrer(pantalla) if "no indica si suena" in str(getattr(w, "text", ""))]
    print(f"Pantalla actual: {app.root.current}")
    print(f"app.avisos_partitura no vacío: {bool(app.avisos_partitura)}")
    print(f"app.convencion_elegible: {app.convencion_elegible}")
    print(f"app.texto_afinacion: {app.texto_afinacion!r}")
    print(f"Etiquetas del aviso presentes en el árbol de widgets: {len(en_arbol)}")
    try:
        pantalla.ids.texto_avisos.text
        print("ids.texto_avisos: accesible")
    except ReferenceError as error:
        print(f"ids.texto_avisos: ReferenceError ({error})")
    app.stop()


Clock.schedule_once(cargar, 1.0)
app.run()
shutil.rmtree(DATOS, ignore_errors=True)
