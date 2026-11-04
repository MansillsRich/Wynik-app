"""
Script auxiliar del Anexo IV (no forma parte de la aplicación Wynik).

Arranca la aplicación real (`vistas.WynikApp`, la misma clase que usa `main.py`) con una
ventana de proporción de teléfono, recorre las pantallas con el ScreenManager mediante
`Clock.schedule_once`/`Clock.schedule_interval` y guarda cada una con `Window.screenshot()`.

- No modifica el código de la aplicación: solo usa su API pública y el atributo
  `WynikApp.fabrica_captura`, previsto para sustituir el micrófono.
- Entrada SIMULADA: para la práctica en curso no se abre el micrófono. Un hilo genera en
  tiempo real ondas senoidales con la frecuencia de cada nota (y una nota equivocada, una
  desafinada y una omitida a propósito) y las entrega a `audio.captura.CapturaManual`, igual
  que lo haría el callback de PortAudio. El análisis (YIN, segmentación, sesión) es el real.
- Los datos (ajustes, historial y progreso) se escriben en `docs/anexo_iv/_datos_demo`
  mediante la variable `WYNIK_DATOS`: no se tocan los JSON del usuario.
- Junto a cada captura se guarda `capturas/cajas/<nombre>.json` con las cajas (en píxeles de
  la imagen) de los elementos que luego numera `anotar_capturas.py`.

Uso (desde la raíz del repositorio, con el entorno virtual activado):
    python docs/anexo_iv/capturar_pantallas.py            # escritorio con pantalla
    xvfb-run -s "-screen 0 1000x2000x24" python docs/anexo_iv/capturar_pantallas.py   # Linux sin pantalla
"""

import json
import math
import os
import shutil
import sys
import threading
import time
from pathlib import Path

# ----------------------------------------------------------------------------- configuración
ANCHO_DP, ALTO_DP = 412, 915          # resolución lógica de un teléfono Android típico
DENSIDAD = 2                          # píxeles por dp de la captura
AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent
PARTITURAS = AQUI / "partituras"
DATOS = AQUI / "_datos_demo"
ORIGINALES = AQUI / "capturas" / "originales"
CAJAS = AQUI / "capturas" / "cajas"
FRECUENCIA_MUESTREO = 48000.0
TAM_BLOQUE = 1024

for carpeta in (ORIGINALES, CAJAS):
    carpeta.mkdir(parents=True, exist_ok=True)
shutil.rmtree(DATOS, ignore_errors=True)
DATOS.mkdir(parents=True)
(DATOS / "kivy_home").mkdir()

os.environ["WYNIK_DATOS"] = str(DATOS)                # datos de la demostración
os.environ["KIVY_HOME"] = str(DATOS / "kivy_home")    # configuración de Kivy aislada
os.environ["HOME"] = str(PARTITURAS)                  # el selector de archivos abre «~»
os.environ["KIVY_METRICS_DENSITY"] = str(DENSIDAD)
os.environ["KIVY_NO_ARGS"] = "1"
sys.path.insert(0, str(RAIZ))

# Ajustes iniciales de la demostración (formato de servicios.ajustes_service.AjustesPractica).
with open(DATOS / "ajustes_wynik.json", "w", encoding="utf-8") as f:
    json.dump({"instrumento": "piano", "modo": "seguir_tempo", "factor_tempo": 1.0,
               "tolerancia_ms": 150, "calibrar_al_empezar": False, "pulsos_cuenta": 3}, f)

from kivy.config import Config  # noqa: E402

Config.set("graphics", "width", str(ANCHO_DP * DENSIDAD))
Config.set("graphics", "height", str(ALTO_DP * DENSIDAD))
Config.set("graphics", "resizable", "0")
Config.set("graphics", "maxfps", "30")

from kivy.clock import Clock  # noqa: E402
from kivy.core.window import Window  # noqa: E402

from audio.captura import CapturaManual  # noqa: E402
from nucleo.musica import midi_a_frecuencia  # noqa: E402
from vistas import (
    WynikApp,  # noqa: E402
    dialogs,  # noqa: E402
)

ESCALA = str(PARTITURAS / "escala_do_mayor.musicxml")
ODA = str(PARTITURAS / "oda_a_la_alegria_guitarra.musicxml")


# ----------------------------------------------------------------------------- entrada simulada
class Alimentador(threading.Thread):
    """Genera audio en tiempo real (bloques de 1024 muestras a 48 kHz) y lo entrega a la
    captura activa con su callback, como haría PortAudio. El contenido depende de la sesión
    de práctica en curso: cada nota suena en su instante esperado salvo las excepciones del
    plan (nota equivocada, desafinada u omitida)."""

    RETRASO_S = 0.04        # el «intérprete» ataca 40 ms tarde (dentro de la tolerancia)
    FRACCION_SONANDO = 0.72  # el resto de la figura es silencio (articulación)
    AMPLITUD = 0.25
    RUIDO = 1e-4            # ruido de fondo ≈ −80 dBFS

    def __init__(self, app, plan):
        super().__init__(daemon=True, name="alimentador-simulado")
        self.app = app
        self.plan = plan        # índice → ("correcta" | "otra:<midi>" | "cents:<c>" | "omitir")
        self.captura = None
        self.detener = threading.Event()
        self.generador = __import__("numpy").random.default_rng(7)

    def nueva_captura(self):
        self.captura = CapturaManual(FRECUENCIA_MUESTREO)
        return self.captura

    def _objetivo(self, t):
        controlador = self.app.controlador
        sesion = getattr(controlador, "sesion", None)
        if sesion is None or sesion.t0 is None:
            return None
        for i, nota in enumerate(sesion.notas):
            inicio = sesion.t0 + nota.inicio_s + self.RETRASO_S
            fin = inicio + self.FRACCION_SONANDO * nota.duracion_s
            if inicio <= t < fin:
                accion = self.plan.get(i, "correcta")
                if accion == "omitir":
                    return None
                midi = nota.midi
                if accion.startswith("otra:"):
                    midi = float(accion.split(":")[1])
                elif accion.startswith("cents:"):
                    midi += float(accion.split(":")[1]) / 100.0
                return midi_a_frecuencia(midi), inicio, fin
        return None

    def run(self):
        """Las muestras son contiguas (contador de muestras), como en un dispositivo real: si
        el hilo se retrasa, los bloques pendientes se entregan seguidos, sin saltos de fase."""
        import numpy as np
        sr, n = FRECUENCIA_MUESTREO, TAM_BLOQUE
        t_base = time.monotonic()
        indice = 0
        captura_actual = None
        while not self.detener.is_set():
            fin_bloque = t_base + (indice + n) / sr
            espera = fin_bloque - time.monotonic()
            if espera > 0:
                time.sleep(espera)
            tiempos = t_base + (indice + np.arange(n)) / sr
            indice += n
            captura = self.captura
            if captura is None or not captura.activa:
                captura_actual = None
                continue
            if captura is not captura_actual:
                captura_actual = captura
            bloque = self.RUIDO * self.generador.standard_normal(n)
            for k in (0, n - 1):  # como mucho, una nota termina y otra empieza en un bloque
                objetivo = self._objetivo(tiempos[k])
                if objetivo is None:
                    continue
                frecuencia, inicio, fin = objetivo
                dentro = (tiempos >= inicio) & (tiempos < fin)
                rel = tiempos[dentro] - inicio
                envolvente = np.minimum(1.0, np.minimum(rel / 0.01, (fin - tiempos[dentro]) / 0.02))
                bloque[dentro] += self.AMPLITUD * envolvente * np.sin(2 * math.pi * frecuencia * rel)
            captura._callback(bloque.astype(np.float32).reshape(-1, 1), n, None, None)


# ----------------------------------------------------------------------------- utilidades
def recorrer(widget):
    yield widget
    for hijo in getattr(widget, "children", []):
        yield from recorrer(hijo)


def texto_de(widget):
    return " ".join(str(getattr(widget, a, "") or "") for a in ("text", "texto", "titulo", "icono", "detalle", "path"))


def buscar(clase=None, contiene=None, raiz=None, todos=False):
    """Widgets visibles de la clase indicada cuyo texto contiene `contiene`."""
    encontrados = []
    for w in recorrer(raiz or Window):
        if clase and type(w).__name__ != clase:
            continue
        if contiene and contiene not in texto_de(w):
            continue
        if getattr(w, "opacity", 1) == 0 or w.width <= 1 or w.height <= 1:
            continue
        encontrados.append(w)
        if not todos:
            break
    return encontrados if todos else (encontrados[0] if encontrados else None)


def caja(widget, margen=4):
    x, y = widget.to_window(*widget.pos)
    alto_ventana = Window.height
    return [round(x - margen), round(alto_ventana - (y + widget.height) - margen),
            round(widget.width + 2 * margen), round(widget.height + 2 * margen)]


class Capturador:
    def __init__(self):
        self.pendiente = None
        Window.bind(on_flip=self._al_dibujar)

    def pedir(self, nombre, objetivos):
        """Captura en el próximo fotograma (en `on_flip`, antes de mostrar el búfer)."""
        self.pendiente = (nombre, objetivos)
        Window.canvas.ask_update()

    def _al_dibujar(self, *_):
        if self.pendiente is None:
            return
        nombre, objetivos = self.pendiente
        self.pendiente = None
        ruta = ORIGINALES / f"{nombre}.png"
        if ruta.exists():
            ruta.unlink()
        generado = Window.screenshot(name=str(ruta))
        if generado and Path(generado) != ruta:
            Path(generado).replace(ruta)
        cajas = []
        for numero, (etiqueta, selector) in enumerate(objetivos, start=1):
            widget = selector() if callable(selector) else selector
            if widget is None:
                print(f"[capturas] {nombre}: no se encontró «{etiqueta}»")
                continue
            cajas.append({"n": numero, "etiqueta": etiqueta, "caja": caja(widget)})
        with open(CAJAS / f"{nombre}.json", "w", encoding="utf-8") as f:
            json.dump({"imagen": ruta.name, "ancho": Window.width, "alto": Window.height,
                       "cajas": cajas}, f, ensure_ascii=False, indent=2)
        print(f"[capturas] {ruta.name} ({Window.width}×{Window.height}) · {len(cajas)} marcas")

    @property
    def ocupado(self):
        return self.pendiente is not None


# ----------------------------------------------------------------------------- guion
def guion(app, cap, alimentador):
    pantalla = lambda nombre: app.root.get_screen(nombre)  # noqa: E731

    def hasta(condicion, maximo_s=20.0):
        limite = time.monotonic() + maximo_s
        return lambda: condicion() or time.monotonic() > limite

    def esperar_captura(nombre, objetivos):
        cap.pedir(nombre, objetivos)
        return lambda: not cap.ocupado

    yield 2.5
    app.fabrica_captura = alimentador.nueva_captura   # sustituye el micrófono

    # 1) Importar la escala de piano con el selector de archivos real de la aplicación
    app.subir_partitura()
    yield 1.5
    buscar("FileChooserListView").selection = [ESCALA]
    yield 0.6
    yield esperar_captura("02_importar_partitura", [
        ("Título e instrucción del diálogo", lambda: buscar("Etiqueta", "Elige un archivo MusicXML")),
        ("Selector de archivos (filtro .musicxml/.xml/.mxl)", lambda: buscar("FileChooserListView")),
        ("Archivo seleccionado", lambda: buscar("FileListEntry", "escala_do_mayor")),
        ("Cancelar", lambda: buscar("Boton", "Cancelar")),
        ("Abrir", lambda: buscar("Boton", "Abrir")),
    ])
    buscar("Boton", "Abrir").dispatch("on_release")
    yield 1.2
    preparar = pantalla("ajustes_inicio")
    yield esperar_captura("04a_preparar_practica", [
        ("Partitura elegida", lambda: preparar.ids.titulo_partitura),
        ("Datos de la partitura", lambda: preparar.ids.datos_partitura),
        ("Escuchar la referencia (guía de audio)", lambda: buscar("Seccion", "Escuchar la referencia").parent.parent.parent),
        ("Instrumento", lambda: buscar("Seccion", "Instrumento").parent),
        ("Practicar", lambda: buscar("Boton", "Practicar")),
    ])
    preparar.ids.desplazamiento_preparar.scroll_y = 0
    yield 0.6
    yield esperar_captura("04b_preparar_modo_tempo", [
        ("Modo de práctica", lambda: buscar("Seccion", "Modo").parent),
        ("Tempo (factor sobre el de la partitura)", lambda: buscar("Paso")),
        ("Nombres de las notas", lambda: buscar("Seccion", "Nombres de las notas").parent),
        ("Vista de partitura", lambda: buscar("Seccion", "Vista de partitura").parent),
        ("Practicar", lambda: buscar("Boton", "Practicar")),
    ])

    # 2) Importar la guitarra (sin <transpose>): evidencia del aviso que no se muestra
    app.subir_partitura()
    yield 1.5
    buscar("FileChooserListView").selection = [ODA]
    yield 0.4
    buscar("Boton", "Abrir").dispatch("on_release")
    yield 1.0
    preparar.ids.desplazamiento_preparar.scroll_y = 1
    yield 0.6
    yield esperar_captura("04c_preparar_guitarra", [
        ("Partitura de guitarra elegida", lambda: preparar.ids.titulo_partitura),
        ("Datos (sin el bloque de avisos)", lambda: preparar.ids.datos_partitura),
        ("Instrumento detectado: guitarra", lambda: buscar("Opcion", "Guitarra")),
    ])
    print("[capturas] avisos_partitura:", bool(app.avisos_partitura),
          "| convencion_elegible:", app.convencion_elegible)

    # 3) Mis partituras (historial_partituras.json escrito por la aplicación)
    app.change_screen("elegir_partitura")
    yield 1.0
    yield esperar_captura("03_mis_partituras", [
        ("Barra superior (volver)", lambda: buscar("BarraSuperior", "Mis partituras")),
        ("Importar otra partitura", lambda: buscar("BotonIcono", "file-plus-outline")),
        ("Partitura del historial (ruta y carpeta)", lambda: buscar("FilaPartitura", "escala_do_mayor")),
        ("Segunda partitura importada", lambda: buscar("FilaPartitura", "oda_a_la_alegria")),
    ])
    app._elegir_partitura_del_historial(ESCALA, "escala_do_mayor")
    yield 1.0

    # 4) Inicio
    app.change_screen("menu")
    yield 1.2
    yield esperar_captura("01_menu_principal", [
        ("Ajustes generales", lambda: buscar("BotonIcono", "cog-outline")),
        ("Continuar la última partitura", lambda: pantalla("menu").ids.portada_tarjeta),
        ("Importar", lambda: buscar("Mosaico", "Importar")),
        ("Mis partituras", lambda: buscar("Mosaico", "Mis partituras")),
        ("Progreso", lambda: buscar("Mosaico", "Progreso")),
        ("Ajustes", lambda: buscar("Mosaico", "Micrófono y afinación")),
    ])

    # 5) Ajustes generales
    app.change_screen("ajustes")
    yield 1.0
    yield esperar_captura("05a_ajustes", [
        ("Micrófono", lambda: buscar("TarjetaAjuste", "Micrófono")),
        ("Ruido de fondo (calibración)", lambda: buscar("TarjetaAjuste", "Ruido de fondo")),
        ("Afinación de referencia (La4)", lambda: buscar("TarjetaAjuste", "Afinación de referencia")),
        ("Afinación de la guitarra", lambda: buscar("TarjetaAjuste", "Afinación de la guitarra")),
    ])
    for w in recorrer(pantalla("ajustes")):
        if type(w).__name__ == "ScrollView":
            w.scroll_y = 0
    yield 0.6
    yield esperar_captura("05b_ajustes_evaluacion", [
        ("Margen de tiempo por nota", lambda: buscar(None, "Margen de tiempo por nota")),
        ("Cuenta previa", lambda: buscar(None, "Cuenta previa")),
        ("Volumen de la referencia", lambda: buscar("TarjetaAjuste", "Volumen de la referencia")),
        ("Vista de partitura", lambda: buscar("TarjetaAjuste", "Vista de partitura")),
    ])

    # 6) Práctica preparada
    app.change_screen("ajustes_inicio")
    yield 0.8
    app.preparar_practica()
    yield 1.5
    interprete = pantalla("interprete")
    objetivos_practica = [
        ("Barra: título, leyenda, vista y ajustes", lambda: buscar("BarraSuperior", raiz=interprete)),
        ("Nota esperada («Toca»)", lambda: interprete.ids.nota_esperada.parent),
        ("Nota oída («Oído»)", lambda: buscar("Rotulo", "Oído", raiz=interprete).parent),
        ("Estado de la nota", lambda: buscar("EstadoPildora", raiz=interprete)),
        ("Medidor de afinación (cents)", lambda: buscar("MedidorCents", raiz=interprete)),
        ("Mensaje de resultado", lambda: interprete.ids.label_estado),
        ("Pentagrama con estado por nota", lambda: interprete.ids.partitura_widget),
        ("Guía del instrumento (teclado)", lambda: interprete.ids.guia_widget),
        ("Progreso, estado y controles", lambda: interprete.ids.pie),
    ]
    yield esperar_captura("06_practica_lista", objetivos_practica)

    # 7) Práctica en curso con entrada simulada
    app.boton_principal()            # «Empezar»: abre la captura simulada y la cuenta previa
    yield 0.9
    yield esperar_captura("07a_cuenta_previa", objetivos_practica)
    yield hasta(lambda: app.resultados_notas[:1] == ["correcta"])
    yield 0.15
    yield esperar_captura("07b_nota_correcta", objetivos_practica)
    yield hasta(lambda: len(app.resultados_notas) > 1 and app.resultados_notas[1] != "pendiente")
    yield 0.15
    yield esperar_captura("07c_nota_incorrecta", objetivos_practica)
    yield hasta(lambda: len(app.resultados_notas) > 3 and app.resultados_notas[3] != "pendiente")
    yield 0.15
    yield esperar_captura("07d_nota_desafinada", objetivos_practica)
    yield hasta(lambda: app.estado_practica == "terminada")
    yield 1.2
    yield esperar_captura("08_resumen_final", [
        ("Resultado global (anillo)", lambda: buscar("AnilloProgreso")),
        ("Desglose de aciertos y errores", lambda: buscar("Etiqueta", "notas correctas")),
        ("Ver progreso", lambda: buscar("Boton", "Ver progreso")),
        ("Repetir", lambda: buscar("Boton", "Repetir")),
    ])
    dialogs.cerrar_dialogo()
    yield 0.6

    # 8) Progreso (progreso_sesiones.json escrito por la aplicación al terminar)
    app.change_screen("progreso")
    yield 1.2
    progreso = pantalla("progreso")
    yield esperar_captura("09_progreso", [
        ("Resumen de sesiones y precisión media", lambda: buscar(None, "registrada", raiz=progreso)),
        ("Por partitura (mejor y última)", lambda: progreso.ids.lista_partituras_progreso),
        ("Sesiones recientes", lambda: progreso.ids.lista_progreso),
    ])

    # 9) Vista simplificada de la práctica
    app.cambiar_vista_simple(True)
    app.change_screen("ajustes_inicio")
    yield 0.8
    app.preparar_practica()
    yield 1.5
    simple = pantalla("partitura_simple")
    yield esperar_captura("10_vista_simplificada", [
        ("Cinta de notas (vista simplificada)", lambda: simple.ids.partitura_simple_widget),
        ("Nota esperada", lambda: simple.ids.nota_esperada),
        ("Guía del instrumento", lambda: simple.ids.guia_widget),
    ])
    app.cambiar_vista_simple(False)
    yield 0.5
    alimentador.detener.set()
    app.stop()


def main():
    plan = {1: "otra:65", 3: "cents:35", 6: "omitir"}   # D4→F4, F4 +35 cents, B4 sin tocar
    app = WynikApp()
    alimentador = Alimentador(app, plan)
    alimentador.start()
    estado = {"pasos": None, "hasta": 0.0, "condicion": None}

    def tick(_dt):
        registro = (app.estado_practica, tuple(app.resultados_notas))
        if app.controlador is not None and registro != estado.get("registro"):
            estado["registro"] = registro
            print("[capturas] estado:", registro[0], "|", ",".join(r[:4] for r in registro[1]))
        if estado["pasos"] is None:
            estado["pasos"] = guion(app, Capturador(), alimentador)
        if estado["condicion"] is not None:
            if not estado["condicion"]():
                return
            estado["condicion"] = None
        if time.monotonic() < estado["hasta"]:
            return
        try:
            paso = next(estado["pasos"])
        except StopIteration:
            return False
        if callable(paso):
            estado["condicion"] = paso
        else:
            estado["hasta"] = time.monotonic() + float(paso)

    Clock.schedule_interval(tick, 0.05)
    app.run()
    with open(AQUI / "capturas" / "entorno_captura.json", "w", encoding="utf-8") as f:
        import platform

        import kivy
        import kivymd
        json.dump({"fecha": time.strftime("%Y-%m-%d %H:%M:%S %z"), "sistema": platform.platform(),
                   "python": platform.python_version(), "kivy": kivy.__version__,
                   "kivymd": kivymd.__version__, "ventana_px": [ANCHO_DP * DENSIDAD, ALTO_DP * DENSIDAD],
                   "ventana_dp": [ANCHO_DP, ALTO_DP], "densidad": DENSIDAD,
                   "entrada": "simulada (CapturaManual + ondas senoidales)", "plan": plan},
                  f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
