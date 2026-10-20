"""
Aplicación KivyMD (WynikApp): navegación, pantallas y conexión con la práctica.

La lógica no depende de Kivy y vive en los servicios y el núcleo:
- `servicios.practica_service.ControladorPractica`: micrófono, análisis en otro hilo,
  calibración, cuenta previa y sesión (`nucleo.sesion`).
- `nucleo.digitacion`: posiciones de guitarra y teclas de piano para la guía visual.
- `servicios.audio_service`: guía de audio desde los tiempos de la partitura.

Esta clase traduce el estado de la práctica a propiedades que muestra `wynik.kv`. La guía de
audio y la escucha nunca coinciden: empezar a escuchar detiene la guía y reproducir la guía
detiene la escucha (C10).

La interfaz (Bloque 3) se carga una sola vez en `build()`: `componentes.kv` y `wynik.kv`.
`load_kv` se anula a propósito: Kivy cargaba `wynik.kv` por el nombre de la clase y `build()`
lo volvía a cargar, con lo que cada regla se aplicaba dos veces (textos y botones duplicados y
superpuestos, avisos «[Factory] Ignored class … re-declaration»).
"""

import os
import time

from kivy.clock import Clock
from kivy.core.audio import SoundLoader
for _cls in getattr(SoundLoader, "_classes", []):
    try:
        _cls.extensions()
    except Exception:
        pass
from kivy.lang import Builder
from kivy.properties import (BooleanProperty, DictProperty, ListProperty, NumericProperty,
                             ObjectProperty, StringProperty)

from kivymd.app import MDApp

# Servicios y núcleo (sin Kivy)
from servicios.reproductor_guia import ReproductorGuia
from servicios import (
    cargar_partitura_estructurada,
    ErrorPartitura,
    generar_guia,
    generar_audio_guia,
    formatear_tiempo,
    duracion_wav,
    cargar_historial,
    agregar_al_historial,
    detalle_de_entrada,
    nombre_para_mostrar,
    cargar_ajustes,
    guardar_ajustes,
    cargar_progreso,
    registrar_sesion,
    resumen_por_partitura,
)

# Vistas y componentes UI
from .screens import (
    MenuScreen,
    ElegirPartituraScreen,
    AjustesInicioScreen,
    InterpreteScreen,
    AjustesScreen,
    ProgresoScreen,
    PartituraSimpleScreen,
)
from .widgets import PartituraWidget, GuiaInstrumentoWidget, PartituraSimpleWidget
from .dialogs import abrir_selector_de_archivo

KV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wynik.kv")
KV_COMPONENTES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "componentes.kv")
# Profundidad de cada pantalla: decide el sentido de la transición (adelante / atrás).
PROFUNDIDAD = {"menu": 0, "elegir_partitura": 1, "progreso": 1, "ajustes": 2,
               "ajustes_inicio": 2, "interprete": 3, "partitura_simple": 3}
INTERVALO_TICK_S = 1.0 / 30.0
# Tiempo que se espera tras detener la guía de audio antes de abrir el micrófono: lo que tarda
# en apagarse el altavoz y la sala. El reproductor no informa cuándo termina de sonar (con SDL2
# no hay posición ni cola), así que es una guarda fija y no una medida. Propuesta inicial, sin
# validar con altavoces reales.
GUARDA_COLA_GUIA_S = 0.35
# Segunda pulsación de «Atrás» que confirma salir de la práctica o de la aplicación.
CONFIRMAR_ATRAS_S = 2.5
# Pantalla a la que lleva «Atrás» desde cada pantalla (ajustes y práctica se tratan aparte).
ATRAS = {"elegir_partitura": "menu", "progreso": "menu", "ajustes_inicio": "elegir_partitura"}

from . import tema  # noqa: E402

COLOR_NEUTRO = list(tema.NEUTRO)
COLOR_CORRECTO = list(tema.CORRECTO)
COLOR_DESAFINADO = list(tema.DESAFINADO)
COLOR_ERROR = list(tema.ERROR)


class WynikApp(MDApp):
    """Aplicación KivyMD y controlador de vistas de Wynik."""

    # Ajustes de práctica (persistentes)
    instrumento = StringProperty("piano")
    afinacion_guitarra = StringProperty("estandar")
    la4 = NumericProperty(440.0)
    factor_tempo = NumericProperty(1.0)
    tolerancia_ms = NumericProperty(150)
    seguir_de_largo = BooleanProperty(True)          # True: seguir el tempo; False: esperar
    notacion_solfeo = BooleanProperty(False)
    calibrar_al_iniciar = BooleanProperty(True)
    pulsos_cuenta = NumericProperty(3)
    bpm = NumericProperty(120)                       # tempo de listas sin tiempos propios
    texto_dispositivo = StringProperty("Micrófono predeterminado del sistema")
    texto_calibracion = StringProperty("Sin medir: se usan niveles por defecto.")

    # Partitura
    notas_partitura = ListProperty([])
    estado_notas = ListProperty([])                  # True / False / None (compatibilidad)
    resultados_notas = ListProperty([])              # nucleo.sesion.EstadoNota (valores)
    disposicion_partitura = ObjectProperty(None, allownone=True)  # nucleo.notacion.Disposicion
    nombre_partitura = StringProperty("(Sin partitura)")
    resumen_partitura = StringProperty("")
    avisos_partitura = StringProperty("")
    historial_partituras = ListProperty([])
    ultima_partitura = StringProperty("")
    tempo_partitura = NumericProperty(120)
    texto_tempo = StringProperty("")
    texto_instrumento = StringProperty("")
    texto_afinacion = StringProperty("")             # afinación de guitarra activa (breve)
    nombre_instrumento = StringProperty("Piano")
    pantalla_anterior = StringProperty("menu")
    convencion_guitarra = StringProperty("auto")     # auto | sonora | escrita_octava_alta
    convencion_elegible = BooleanProperty(False)     # la guitarra ambigua deja elegir
    usar_vista_simple = BooleanProperty(False)       # usar PartituraSimpleScreen en lugar de InterpreteScreen
    escala_fuente = NumericProperty(1.0)             # escala del tamaño de fuente (1.0 = normal, 1.15 = grande, 1.3 = muy grande)

    # Práctica
    estado_practica = StringProperty("lista")
    indice_actual = NumericProperty(0)
    texto_estado = StringProperty("")
    texto_esperada = StringProperty("")
    texto_esperada_detalle = StringProperty("")
    texto_detectada = StringProperty("Todavía no se ha oído ninguna nota.")
    texto_resultado = StringProperty("Pulsa «Empezar» cuando estés listo")
    icono_resultado = StringProperty("microphone-outline")
    color_resultado = ListProperty(COLOR_NEUTRO)
    texto_guia = StringProperty("")
    modelo_guia = DictProperty({"tipo": "vacio", "mensaje": ""})
    progreso = NumericProperty(0)
    texto_progreso = StringProperty("")
    texto_boton_principal = StringProperty("Empezar")
    icono_boton_principal = StringProperty("play")
    texto_resumen_progreso = StringProperty("")
    # Bloque 3: estado visual de la práctica
    clave_resultado = StringProperty("neutro")       # clave de vistas.tema.ESTADOS
    nota_detectada = StringProperty("")
    cents_detectados = ObjectProperty(None, allownone=True)
    texto_aviso = StringProperty("")                 # señal débil, ruido, fuera de tiempo…
    # Inicio, biblioteca y progreso
    texto_ultima = StringProperty("")
    texto_biblioteca = StringProperty("")
    texto_progreso_inicio = StringProperty("")
    texto_progreso_detalle = StringProperty("")
    progreso_media = NumericProperty(0)
    progreso_sesiones = NumericProperty(0)
    progreso_historial = ListProperty([])

    # Reproductor de la guía de audio
    reproduciendo_audio = BooleanProperty(False)
    volumen_audio = NumericProperty(0.8)
    posicion_audio_actual = NumericProperty(0)
    duracion_audio_total = NumericProperty(1)
    tiempo_actual_str = StringProperty("00:00")
    duracion_total_str = StringProperty("00:00")
    audio_busqueda = BooleanProperty(False)          # el reproductor admite posición y búsqueda
    audio_pausa = BooleanProperty(False)             # … y por tanto pausa real
    audio_pausado = BooleanProperty(False)
    texto_audio_info = StringProperty("")

    # =========================================================================
    #  Arranque
    # =========================================================================

    def load_kv(self, filename=None):
        """No se carga nada por el nombre de la clase: `build()` carga los archivos KV una sola
        vez (antes, `wynik.kv` se aplicaba dos veces)."""
        return False

    def build(self):
        from .fuentes import registrar_fuentes
        from . import componentes  # noqa: F401 - registra los componentes en Factory
        from .widgets import ilustraciones  # noqa: F401
        self.theme_cls.theme_style = "Light"
        self.theme_cls.primary_palette = "Teal"
        registrar_fuentes(self.theme_cls)
        self._configurar_directorio_datos()
        self._inicializar_estado()
        self._cargar_ajustes()
        self.historial_partituras = cargar_historial()
        self._actualizar_ultima()
        self._con_interfaz = True
        # Tras redimensionar, los textos que se parten en líneas cambian la altura de tarjetas
        # y filas de rejilla en cadena: se asienta en 21–40 pasadas del reloj (medido; no es un
        # bucle: en reposo no hay ninguna). Con el límite de 20 de Kivy quedaba para el
        # fotograma siguiente y avisaba «too much iteration».
        Clock.max_iteration = 40
        for ruta in (KV_COMPONENTES, KV_PATH):
            Builder.unload_file(ruta)        # por si build() se llama dos veces (pruebas)
        Builder.load_file(KV_COMPONENTES)
        return Builder.load_file(KV_PATH)

    def _configurar_directorio_datos(self):
        try:
            from kivy.utils import platform
            if platform == "android":
                from servicios.almacenamiento import configurar_directorio
                configurar_directorio(self.user_data_dir)
        except Exception as error:  # noqa: BLE001
            print(f"[Wynik] No se pudo preparar el directorio de datos: {error}")

    def _inicializar_estado(self):
        """Atributos de trabajo (también los usan las simulaciones, que no llaman a build)."""
        self.detector = None            # motor de escucha activo (o None)
        self.controlador = None         # ControladorPractica de la partitura actual
        self.partitura = None
        self.sonido_guia = None
        self.nota_esperada = None
        self.reloj = time.monotonic
        self.fabrica_captura = None     # None: micrófono del sistema (sounddevice)
        self.usar_hilo_analisis = True
        self.dispositivo_entrada = None
        self.ruido_calibrado = None
        self._siguiente_sesion = 1
        self._evento_tick = None
        self._evento_actualizar_progreso = None
        self._evento_calibracion = None
        self._motor_calibracion = None
        self._posicion_anterior = None
        self._guia_detenida_en = None   # instante en que se detuvo la guía (guarda de la cola)
        self._evento_espera_guia = None
        self._convenciones = {}         # ruta → convención de guitarra elegida en esta sesión
        self._atras_hasta = float("-inf")  # plazo de la segunda pulsación de «Atrás»
        self._ruta_actual = None
        self.reproductor = None         # servicios.reproductor_guia.ReproductorGuia
        self._con_interfaz = False      # True con la interfaz Kivy real (no en simulaciones)
        self._actualizar_textos_configuracion()

    def on_start(self):
        from kivy.core.window import Window
        Window.bind(on_keyboard=self._tecla)
        self._refrescar_lista_partituras()
        self._actualizar_textos_configuracion()
        self.refrescar_inicio()

    def on_stop(self):
        self.detener_escucha()
        self._cancelar_calibracion()

    def change_screen(self, screen_name: str):
        actual = self.root.current
        if screen_name == "ajustes" and actual != "ajustes":
            self.pantalla_anterior = actual
        transicion = getattr(self.root, "transition", None)
        if transicion is not None and hasattr(transicion, "direction"):
            adelante = PROFUNDIDAD.get(screen_name, 0) >= PROFUNDIDAD.get(actual, 0)
            transicion.direction = "left" if adelante else "right"
        self.root.current = screen_name

    def _mensaje(self, texto: str):
        """Mensaje breve en pantalla (y en la consola). Si el aviso no se puede mostrar, el
        motivo se escribe en la consola con su traza: nunca se pierde en silencio."""
        print(f"[Wynik] {texto}")
        try:
            self._mostrar_aviso(texto)
        except Exception:  # noqa: BLE001 - un aviso fallido no debe interrumpir la acción
            import traceback
            print(f"[Wynik] No se pudo mostrar el aviso en pantalla:\n{traceback.format_exc()}")

    def _mostrar_aviso(self, texto: str):
        from .avisos import mostrar_aviso
        mostrar_aviso(texto)

    def _dialogo(self, titulo: str, mensaje: str = "", **opciones):
        """Abre un diálogo (ver `vistas.dialogs.mostrar_dialogo`). Devuelve None si no hay
        interfaz o si falla (quien llama recurre entonces a `_mensaje`)."""
        if not self._con_interfaz:
            return None
        try:
            from .dialogs import mostrar_dialogo
            return mostrar_dialogo(titulo, mensaje, **opciones)
        except Exception:  # noqa: BLE001 - un diálogo fallido no debe interrumpir la acción
            import traceback
            print(f"[Wynik] No se pudo abrir el diálogo «{titulo}»:\n{traceback.format_exc()}")
            return None

    def _error(self, titulo: str, mensaje: str):
        """Error que el usuario tiene que leer: diálogo; si no se puede, aviso breve."""
        print(f"[Wynik] {titulo}: {mensaje}")
        if self._dialogo(titulo, mensaje, icono="alert-circle-outline", color_icono=tema.ERROR) is None:
            self._mensaje(mensaje)

    # =========================================================================
    #  Navegación: «Atrás» (tecla Esc en escritorio, botón o gesto en Android)
    # =========================================================================

    def _tecla(self, ventana, tecla, *args):
        """Esc / Atrás se gestionan aquí: devolver True evita que Kivy cierre la aplicación
        (en Android, que la mande a segundo plano)."""
        if tecla != 27:
            return False
        from .dialogs import cerrar_dialogo
        if self._con_interfaz and cerrar_dialogo():   # con un diálogo abierto, Atrás lo cierra
            self._atras_hasta = float("-inf")
            return True
        self.atras()
        return True

    def atras(self):
        """Vuelve a la pantalla anterior. En la práctica en curso y en Inicio hace falta una
        segunda pulsación en `CONFIRMAR_ATRAS_S` segundos: así un gesto accidental no pierde la
        sesión ni cierra la aplicación."""
        actual = self.root.current
        if actual == "menu":
            if self._confirmar_atras("Pulsa Atrás otra vez para salir de Wynik."):
                self.stop()
            return
        if actual in ("interprete", "partitura_simple"):
            if self.estado_practica in ("calibrando", "cuenta", "escuchando", "pausada"):
                dialogo = {"titulo": "¿Dejar la práctica?",
                           "mensaje": "Se perderá el avance de esta sesión.",
                           "icono": "exit-to-app",
                           "botones": (("Seguir practicando", "texto", None),
                                       ("Salir", "primario", self._salir_de_la_practica))}
                if not self._confirmar_atras("Pulsa Atrás otra vez para dejar la práctica; "
                                             "se perderá el avance de esta sesión.", dialogo):
                    return
            self._salir_de_la_practica()
            return
        if actual == "ajustes":
            self.change_screen(self.pantalla_anterior or "menu")
            return
        if actual == "ajustes_inicio":
            self.detener_audio()
        self.change_screen(ATRAS.get(actual, "menu"))

    def _salir_de_la_practica(self):
        self._atras_hasta = float("-inf")
        self.detener_escucha()
        self.detener_audio()
        self.change_screen("ajustes_inicio")

    def _confirmar_atras(self, aviso: str, dialogo: dict = None) -> bool:
        """True en la segunda pulsación dentro del plazo; si no, pide confirmación: con un
        diálogo (`dialogo`, argumentos de `_dialogo`) si se puede, o con el aviso breve."""
        ahora = self.reloj()
        if ahora <= self._atras_hasta:
            self._atras_hasta = float("-inf")
            return True
        self._atras_hasta = ahora + CONFIRMAR_ATRAS_S
        if dialogo is None or self._dialogo(**dialogo) is None:
            self._mensaje(aviso)
        return False

    # =========================================================================
    #  Ajustes persistentes
    # =========================================================================

    def _cargar_ajustes(self):
        ajustes = cargar_ajustes()
        self.instrumento = ajustes.instrumento
        self.afinacion_guitarra = ajustes.afinacion_guitarra
        self.la4 = ajustes.la4
        self.seguir_de_largo = ajustes.modo == "seguir_tempo"
        self.factor_tempo = ajustes.factor_tempo
        self.tolerancia_ms = ajustes.tolerancia_ms
        self.notacion_solfeo = ajustes.notacion_solfeo
        self.calibrar_al_iniciar = ajustes.calibrar_al_empezar
        self.pulsos_cuenta = ajustes.pulsos_cuenta
        self.dispositivo_entrada = ajustes.dispositivo
        self.volumen_audio = ajustes.volumen_guia
        self.usar_vista_simple = getattr(ajustes, "vista_simple", False)
        self.escala_fuente = float(getattr(ajustes, "escala_fuente", 1.0))
        from kivy.metrics import Metrics
        Metrics.fontscale = self.escala_fuente

        self._actualizar_textos_configuracion()

    def _guardar_ajustes(self):
        from servicios.ajustes_service import AjustesPractica
        guardar_ajustes(AjustesPractica(
            instrumento=self.instrumento, afinacion_guitarra=self.afinacion_guitarra,
            la4=float(self.la4), modo="seguir_tempo" if self.seguir_de_largo else "esperar_nota",
            factor_tempo=float(self.factor_tempo), tolerancia_ms=int(self.tolerancia_ms),
            notacion_solfeo=bool(self.notacion_solfeo),
            calibrar_al_empezar=bool(self.calibrar_al_iniciar),
            pulsos_cuenta=int(self.pulsos_cuenta), dispositivo=self.dispositivo_entrada,
            volumen_guia=float(self.volumen_audio),
            vista_simple=bool(self.usar_vista_simple),
            escala_fuente=float(self.escala_fuente)))

    def _perfil(self):
        from nucleo.instrumentos import PERFILES, perfil_de_guitarra
        if self.instrumento == "guitarra":
            return perfil_de_guitarra(self.afinacion_guitarra)
        return PERFILES.get(self.instrumento, PERFILES["piano"])

    def _actualizar_textos_configuracion(self):
        perfil = self._perfil()
        self.nombre_instrumento = perfil.nombre
        texto = f"{perfil.nombre}: notas de {perfil.rango_texto}, una cada vez."
        self.texto_afinacion = ""
        if perfil.clave == "guitarra":
            from nucleo.instrumentos import NOMBRES_AFINACION
            texto += f" Afinación: {NOMBRES_AFINACION[self.afinacion_guitarra]}."
            self.texto_afinacion = f"Afinación: {NOMBRES_AFINACION[self.afinacion_guitarra]} (se cambia en Ajustes)"
        texto += " Validación con instrumento real pendiente."
        self.texto_instrumento = texto
        tempo = self.tempo_partitura * self.factor_tempo
        self.texto_tempo = f"♩ = {tempo:.0f}  ({self.factor_tempo * 100:.0f} %)"

    def _ajuste_cambiado(self):
        self._actualizar_textos_configuracion()
        self._guardar_ajustes()
        if self.controlador is not None and self.estado_practica != "lista":
            self._mensaje("El cambio se aplicará al volver a empezar.")
        self.controlador = None
        if self.notas_partitura:
            self._mostrar_nota(int(self.indice_actual))
        if self.sonido_guia is not None:
            self.preparar_audio_guia()
        else:
            self._actualizar_info_audio()

    def cambiar_instrumento(self, clave: str):
        from nucleo.instrumentos import PERFILES
        perfil = PERFILES.get(clave)
        if perfil is None or perfil.experimental:
            self._mensaje(f"{perfil.nombre if perfil else clave}: todavía no disponible (experimental).")
            return
        self.instrumento = clave
        self._ajuste_cambiado()

    def cambiar_modo(self, seguir_tempo: bool):
        self.seguir_de_largo = bool(seguir_tempo)
        self._ajuste_cambiado()

    def cambiar_factor_tempo(self, delta: float):
        from servicios.ajustes_service import FACTOR_TEMPO_MAX, FACTOR_TEMPO_MIN
        self.factor_tempo = round(min(max(self.factor_tempo + delta, FACTOR_TEMPO_MIN),
                                      FACTOR_TEMPO_MAX), 2)
        self._ajuste_cambiado()

    def cambiar_bpm(self, delta: int):
        """Compatibilidad: cambia el tempo en pasos de 5 negras por minuto."""
        self.cambiar_factor_tempo(delta / max(self.tempo_partitura, 1.0))

    def cambiar_notacion(self, solfeo: bool):
        self.notacion_solfeo = bool(solfeo)
        self._ajuste_cambiado()

    def cambiar_la4(self, delta: float):
        from servicios.ajustes_service import LA4_MAX, LA4_MIN
        self.la4 = min(max(self.la4 + delta, LA4_MIN), LA4_MAX)
        self._ajuste_cambiado()

    def cambiar_afinacion(self, clave: str):
        self.afinacion_guitarra = clave
        self._posicion_anterior = None
        self._ajuste_cambiado()

    def cambiar_tolerancia(self, milisegundos: int):
        self.tolerancia_ms = int(milisegundos)
        self._ajuste_cambiado()

    def cambiar_pulsos(self, pulsos: int):
        self.pulsos_cuenta = int(pulsos)
        self._ajuste_cambiado()

    def cambiar_calibracion(self, al_empezar: bool):
        self.calibrar_al_iniciar = bool(al_empezar)
        self._ajuste_cambiado()

    def cambiar_vista_simple(self, simple: bool):
        """Alterna entre la vista estándar de pentagrama y la vista simplificada."""
        self.usar_vista_simple = bool(simple)
        self._guardar_ajustes()

    def alternar_vista_practica(self):
        """Cambia entre la vista de pentagrama y la vista simplificada durante la práctica."""
        self.cambiar_vista_simple(not self.usar_vista_simple)
        if self.root and self.root.current in ("interprete", "partitura_simple"):
            self.root.current = "partitura_simple" if self.usar_vista_simple else "interprete"

    def cambiar_escala_fuente(self, escala: float):
        """Cambia la escala del tamaño de fuente en toda la aplicación."""
        self.escala_fuente = float(escala)
        from kivy.metrics import Metrics
        Metrics.fontscale = self.escala_fuente
        from .widgets import dibujo
        dibujo._texturas.clear()
        self._guardar_ajustes()

    # =========================================================================
    #  Micrófono y calibración
    # =========================================================================

    def refrescar_dispositivo(self):
        from audio.captura import dispositivos_de_entrada
        dispositivos = dispositivos_de_entrada()
        if not dispositivos:
            self.texto_dispositivo = "No se encontró ningún micrófono."
            return
        if self.dispositivo_entrada is None:
            nombre = next((d["nombre"] for d in dispositivos if d["predeterminado"]),
                          "predeterminado del sistema")
            self.texto_dispositivo = f"Micrófono predeterminado ({nombre})"
        else:
            datos = next((d for d in dispositivos if d["indice"] == self.dispositivo_entrada), None)
            self.texto_dispositivo = (f"{datos['nombre']} · {datos['frecuencia']:.0f} Hz" if datos
                                      else "El micrófono elegido ya no está conectado")

    def siguiente_dispositivo(self):
        from audio.captura import dispositivos_de_entrada
        indices = [None] + [d["indice"] for d in dispositivos_de_entrada()]
        posicion = indices.index(self.dispositivo_entrada) if self.dispositivo_entrada in indices else 0
        self.dispositivo_entrada = indices[(posicion + 1) % len(indices)]
        self.ruido_calibrado = None
        self.texto_calibracion = "Micrófono cambiado: vuelve a medir el ruido de fondo."
        self.refrescar_dispositivo()
        self._ajuste_cambiado()

    def _crear_captura(self):
        if self.fabrica_captura is not None:
            return self.fabrica_captura()
        from audio.captura import CapturaSounddevice
        return CapturaSounddevice(dispositivo=self.dispositivo_entrada, reloj=self.reloj)

    def calibrar_ahora(self):
        from audio.captura import MicrofonoNoDisponibleError
        from audio.escucha import MotorDeEscucha
        if self.controlador is not None and self.controlador.escuchando:
            self._mensaje("Detén la práctica para medir el ruido de fondo.")
            return
        if not self._guia_en_silencio(self.calibrar_ahora):  # el ruido de fondo no incluye la guía
            return
        self._cancelar_calibracion()
        motor = MotorDeEscucha(self._perfil(), self.la4, captura=self._crear_captura(),
                               usar_hilo=self.usar_hilo_analisis)
        try:
            motor.iniciar()
        except MicrofonoNoDisponibleError as error:
            self.texto_calibracion = "No se pudo abrir el micrófono."
            self._mensaje(str(error))
            return
        motor.calibrar(1.0)
        self._motor_calibracion = motor
        self.texto_calibracion = "Midiendo… guarda silencio durante 1 s."
        self._evento_calibracion = Clock.schedule_interval(self._comprobar_calibracion, 0.1)

    def _comprobar_calibracion(self, dt):
        motor = self._motor_calibracion
        if motor is None:
            return False
        if motor.calibrando:
            return True
        self.ruido_calibrado = motor.ruido
        self._cancelar_calibracion()
        self.texto_calibracion = self._describir_ruido(self.ruido_calibrado)
        return False

    def _cancelar_calibracion(self):
        if self._evento_calibracion is not None:
            self._evento_calibracion.cancel()
            self._evento_calibracion = None
        if self._motor_calibracion is not None:
            self._motor_calibracion.detener()
            self._motor_calibracion = None

    @staticmethod
    def _describir_ruido(ruido) -> str:
        if ruido is None:
            return "Sin medir: se usan niveles por defecto."
        texto = (f"Fondo: {ruido.nivel_fondo_dbfs:.0f} dBFS · nivel mínimo de una nota: "
                 f"{ruido.umbral_minimo_dbfs:.0f} dBFS")
        if ruido.tonos_estacionarios:
            tonos = ", ".join(f"{t.frecuencia_hz:.0f} Hz" for t in ruido.tonos_estacionarios)
            texto += f" · zumbido detectado: {tonos} (se ignora)"
        if ruido.nivel_fondo_dbfs > -40:
            texto += " · Hay mucho ruido: la detección puede fallar."
        return texto

    # =========================================================================
    #  Partituras
    # =========================================================================

    def subir_partitura(self):
        abrir_selector_de_archivo(self._partitura_seleccionada)

    def _partitura_seleccionada(self, ruta):
        if not ruta:
            return
        if self._cargar_partitura(ruta, agregar=True):
            self.change_screen("ajustes_inicio")

    def _mostrar_datos_partitura(self):
        """Datos de la partitura como chips en «Preparar la práctica»."""
        try:
            contenedor = self.root.get_screen("ajustes_inicio").ids.datos_partitura
        except Exception:  # noqa: BLE001 - sin interfaz (simulaciones)
            return
        from .componentes import Chip
        contenedor.clear_widgets()
        for icono, texto in getattr(self, "_datos_partitura", []):
            contenedor.add_widget(Chip(icono=icono, texto=texto))

    def _cargar_partitura(self, ruta: str, nombre: str = None, agregar: bool = False) -> bool:
        from servicios.partitura_service import ataque_a_nota
        convencion = self._convenciones.get(ruta, "auto")
        try:
            partitura = cargar_partitura_estructurada(ruta, convencion_guitarra=convencion)
        except FileNotFoundError:
            self._error("Archivo no encontrado", f"No se encuentra el archivo: {ruta}")
            return False
        except ErrorPartitura as error:
            print(f"[Wynik] Error al leer {ruta}: {error}")
            self._error("No se pudo abrir la partitura", str(error))
            return False
        except Exception as error:  # noqa: BLE001 - un archivo no debe cerrar la app
            print(f"[Wynik] Error al leer {ruta}: {type(error).__name__}: {error}")
            self._error("No se pudo abrir la partitura",
                        "No se pudo abrir la partitura. Comprueba que es un archivo MusicXML válido.")
            return False
        linea = partitura.linea_de_practica()
        if not linea:
            self._error("Partitura sin notas", "La partitura no contiene notas que practicar.")
            return False
        self.detener_escucha()
        self.detener_audio()
        self.partitura = partitura
        self.notas_partitura = [ataque_a_nota(a) for a in linea]
        self.nombre_partitura = nombre or os.path.splitext(os.path.basename(ruta))[0]
        self.tempo_partitura = partitura.tempo.negras_por_minuto_en(0.0)
        parte = partitura.partes[0]
        try:
            from nucleo.notacion import disponer
            self.disposicion_partitura = disponer(parte)
        except Exception as error:  # noqa: BLE001 - sin dibujo la práctica sigue funcionando
            import traceback
            print(f"[Wynik] No se pudo maquetar la partitura: {error}\n{traceback.format_exc()}")
            self.disposicion_partitura = None
        compases = max((e.compas or 0) for e in parte.eventos) if parte.eventos else 0
        acordes = sum(1 for a in linea if a.es_acorde)
        resumen = f"{len(linea)} notas · {compases} compases · ♩ = {self.tempo_partitura:.0f} · parte «{parte.nombre}»"
        if acordes:
            resumen += f" · {acordes} acordes (solo referencia, no se evalúan)"
        self.resumen_partitura = resumen
        self.avisos_partitura = "\n".join(partitura.avisos)
        datos = [("music-note-outline", f"{len(linea)} notas"), ("view-week-outline", f"{compases} compases"),
                 ("metronome", f"♩ = {self.tempo_partitura:.0f}"), ("account-music-outline", parte.nombre or "Parte 1")]
        if acordes:
            datos.append(("circle-outline", f"{acordes} acordes · solo referencia"))
        self._datos_partitura = datos
        self._mostrar_datos_partitura()
        from nucleo.musica import OrigenTransposicion
        self.convencion_guitarra = convencion
        self.convencion_elegible = (parte.perfil == "guitarra" and parte.transposicion.origen in
                                    (OrigenTransposicion.INDETERMINADA, OrigenTransposicion.CONFIGURADA))
        from nucleo.instrumentos import PERFILES
        perfil_parte = PERFILES.get(parte.perfil) if parte.perfil else None
        if perfil_parte is not None and not perfil_parte.experimental:
            self.instrumento = perfil_parte.clave
        if agregar:
            self.historial_partituras = agregar_al_historial(
                self.historial_partituras, self.nombre_partitura, ruta)
        self._ruta_actual = ruta
        self._actualizar_ultima(ruta)
        self._refrescar_lista_partituras()
        self.controlador = None
        self.sonido_guia = None
        self.reproductor = None
        self._timbre_cargado = None
        self._reiniciar_resultados()
        self._aplicar_estado("lista")
        self._actualizar_textos_configuracion()
        self._actualizar_info_audio()
        self._mostrar_nota(0)
        return True

    def cambiar_convencion_guitarra(self, convencion: str):
        """Elección del usuario para una guitarra sin <transpose> ni clave de octava: «sonora»
        (las notas suenan como están escritas) o «escrita_octava_alta» (suenan una octava más
        grave, lo habitual). Se vuelve a leer la partitura con esa convención. Solo se recuerda
        mientras la aplicación está abierta."""
        ruta = getattr(self, "_ruta_actual", None)
        if not ruta or convencion not in ("sonora", "escrita_octava_alta"):
            return
        self._convenciones[ruta] = convencion
        self._cargar_partitura(ruta, nombre=self.nombre_partitura)

    def _actualizar_ultima(self, ruta: str = None):
        if ruta is None and self.historial_partituras:
            ruta = self.historial_partituras[-1].get("ruta")
        if ruta:
            nombre = next((e["nombre"] for e in self.historial_partituras if e.get("ruta") == ruta),
                          os.path.splitext(os.path.basename(ruta))[0])
            self.ultima_partitura = nombre
            self._ultima_ruta = ruta
        self._actualizar_textos_inicio()

    def _actualizar_textos_inicio(self):
        n = len(self.historial_partituras)
        self.texto_biblioteca = ("Ninguna todavía" if n == 0 else
                                 "1 partitura" if n == 1 else f"{n} partituras")
        try:
            grupos = {g["partitura"]: g for g in resumen_por_partitura(cargar_progreso())}
        except Exception:  # noqa: BLE001 - el progreso es informativo
            grupos = {}
        ultima = grupos.get(self.ultima_partitura)
        partes = [self.nombre_instrumento]
        if ultima:
            partes.append(f"mejor {round(100 * ultima['mejor'])} %")
            partes.append("1 sesión" if ultima["sesiones"] == 1 else f"{ultima['sesiones']} sesiones")
        else:
            partes.append("sin practicar todavía")
        self.texto_ultima = " · ".join(partes)

    def refrescar_inicio(self):
        """Textos del inicio (al entrar en él)."""
        self._actualizar_textos_inicio()
        try:
            sesiones = cargar_progreso()
        except Exception:  # noqa: BLE001
            sesiones = []
        if sesiones:
            media = sum(s.get("precision", 0) for s in sesiones) / len(sesiones)
            self.texto_progreso_inicio = f"Media {media * 100:.0f} % · {len(sesiones)} sesiones"
        else:
            self.texto_progreso_inicio = "Sin sesiones todavía"

    def practicar_ultima(self):
        ruta = getattr(self, "_ultima_ruta", None)
        if ruta:
            self._elegir_partitura_del_historial(ruta, self.ultima_partitura)

    def _refrescar_lista_partituras(self):
        try:
            lista_widget = self.root.get_screen("elegir_partitura").ids.song_list
        except Exception:  # noqa: BLE001 - sin interfaz (simulaciones)
            return
        from kivy.factory import Factory
        lista_widget.clear_widgets()
        self._actualizar_textos_inicio()
        if not self.historial_partituras:
            return   # el estado vacío lo muestra wynik.kv
        try:
            sesiones = cargar_progreso()
            progreso = {g["partitura"]: g for g in resumen_por_partitura(sesiones)}
            instrumentos = {s.get("partitura"): s.get("instrumento") for s in sesiones}
        except Exception:  # noqa: BLE001 - el progreso es informativo
            progreso, instrumentos = {}, {}
        for entrada in reversed(self.historial_partituras):
            existe = os.path.exists(entrada["ruta"])
            instrumento = instrumentos.get(entrada["nombre"])
            fila = Factory.FilaPartitura(
                titulo=entrada["nombre"], existe=existe,
                detalle=detalle_de_entrada(entrada["ruta"], progreso.get(entrada["nombre"])),
                instrumento=instrumento if instrumento in ("guitarra", "piano") else "partitura")
            fila.bind(on_release=lambda _fila, ruta=entrada["ruta"], nombre=entrada["nombre"]: (
                self._elegir_partitura_del_historial(ruta, nombre)))
            lista_widget.add_widget(fila)

    def _elegir_partitura_del_historial(self, ruta: str, nombre: str):
        if not os.path.exists(ruta):
            self._error("Archivo no encontrado", f"El archivo ya no está en esta ubicación: {ruta}")
            return
        if self._cargar_partitura(ruta, nombre=nombre):
            self.change_screen("ajustes_inicio")

    # =========================================================================
    #  Guía de audio (nunca suena mientras se escucha)
    # =========================================================================

    def _ruta_guia(self) -> str:
        from servicios.almacenamiento import ruta_cache
        return ruta_cache("temp_guia.wav")

    def _timbre_guia(self) -> str:
        return self.instrumento if self.instrumento in ("piano", "guitarra") else "seno"

    def preparar_audio_guia(self):
        """Sintetiza la referencia (con el timbre del instrumento elegido) y la carga."""
        if self.reproduciendo_audio:
            self._guia_detenida_en = self.reloj()
        if self.reproductor is not None:
            self.reproductor.detener()
        if self.sonido_guia:
            self.sonido_guia.stop()
            self.sonido_guia.unload()
        self.sonido_guia = None
        self.reproductor = None
        self._cancelar_progreso_audio()
        self.reproduciendo_audio = False
        self.audio_pausado = False
        self.posicion_audio_actual = 0
        self.tiempo_actual_str = "00:00"
        if not self.notas_partitura:
            self._actualizar_info_audio()
            return
        timbre = self._timbre_guia()
        if all(n.get("inicio_s") is not None for n in self.notas_partitura):
            total = self.partitura.duracion_s if self.partitura is not None else None
            ruta_wav = generar_guia(self.notas_partitura, self._ruta_guia(),
                                    factor_tempo=self.factor_tempo, duracion_total_s=total, timbre=timbre)
        else:
            ruta_wav = generar_audio_guia(self.notas_partitura, self.bpm * self.factor_tempo,
                                          self._ruta_guia(), timbre=timbre)
        self._timbre_cargado = timbre
        if ruta_wav and os.path.exists(ruta_wav):
            self.sonido_guia = SoundLoader.load(ruta_wav)
            if self.sonido_guia:
                self.sonido_guia.volume = self.volumen_audio
                self.reproductor = ReproductorGuia(self.sonido_guia, duracion_wav(ruta_wav),
                                                   reloj=self.reloj, al_terminar=self._guia_terminada)
                self.duracion_audio_total = self.reproductor.duracion_s
                self.duracion_total_str = formatear_tiempo(self.duracion_audio_total)
            else:
                self.duracion_audio_total = 0
                self.duracion_total_str = "--:--"
                print("[Wynik] La guía de audio no se pudo cargar (¿hay salida de audio?).")
        self.audio_busqueda = bool(self.reproductor and self.reproductor.admite_busqueda)
        self.audio_pausa = bool(self.reproductor and self.reproductor.admite_pausa)
        self._actualizar_info_audio()

    def _actualizar_info_audio(self):
        """Texto del reproductor: timbre y duración (la del audio cargado o, antes de
        generarlo, la de la partitura al tempo elegido)."""
        nombres = {"piano": "Sonido de piano", "guitarra": "Sonido de guitarra"}
        texto = nombres.get(self._timbre_guia(), "Tono puro")
        if self.reproductor is None and self.notas_partitura and not self.reproduciendo_audio:
            fin = max((n.get("inicio_s") or 0) + (n.get("duracion_s") or 0) for n in self.notas_partitura)
            total = self.partitura.duracion_s if self.partitura is not None else fin
            self.duracion_audio_total = max(total, fin) / max(self.factor_tempo, 0.01)
            self.duracion_total_str = formatear_tiempo(self.duracion_audio_total)
        if self.notas_partitura:
            texto += f" · {self.duracion_total_str}"
        if self.reproductor is None and getattr(self, "_timbre_cargado", None) is not None:
            texto += " · no se pudo cargar el audio"
        self.texto_audio_info = texto

    def _cancelar_espera_guia(self):
        if self._evento_espera_guia is not None:
            self._evento_espera_guia.cancel()
            self._evento_espera_guia = None
            self._aplicar_estado(self.estado_practica)

    def _guia_en_silencio(self, reintentar) -> bool:
        """Regla única entre la guía de audio y el micrófono (C10): no se abre el micrófono, ni
        se calibra el ruido, mientras la guía suene ni durante `GUARDA_COLA_GUIA_S` después de
        detenerla. True: se puede abrir ya. False: no todavía; si es solo cuestión de esperar,
        `reintentar()` se llama sola cuando pase la guarda; si la guía no se detuvo, se avisa y
        no se reintenta (no se arriesgan falsos aciertos)."""
        self._cancelar_espera_guia()
        ahora = self.reloj()
        if self.reproduciendo_audio:
            self.detener_audio()
            sonido = self.sonido_guia
            if sonido is not None and getattr(sonido, "state", "stop") == "play":
                self._mensaje("No se pudo detener la guía de audio, así que no se empieza a escuchar. "
                              "Vuelve a intentarlo.")
                return False
        if self._guia_detenida_en is None:
            return True
        restante = GUARDA_COLA_GUIA_S - (ahora - self._guia_detenida_en)
        if restante > 0:
            self.texto_estado = "Esperando a que termine el sonido de la guía…"
            self._evento_espera_guia = Clock.schedule_once(lambda dt: self._reintentar_tras_guia(reintentar),
                                                           restante)
            return False
        self._guia_detenida_en = None
        return True

    def _reintentar_tras_guia(self, reintentar):
        self._evento_espera_guia = None
        reintentar()

    def toggle_reproduccion_audio(self):
        """Reproduce la referencia; si ya suena, la pausa (si el reproductor lo admite de
        verdad) o la detiene."""
        self._cancelar_espera_guia()  # si había un inicio esperando, la guía tiene preferencia
        if self.controlador is not None and self.estado_practica in ("calibrando", "cuenta", "escuchando"):
            # Requisito: la guía no suena mientras Wynik escucha. Reproducirla detiene la escucha.
            self.detener_escucha()
            self.texto_estado = "Escucha detenida para reproducir la guía."
        if not self.sonido_guia or getattr(self, "_timbre_cargado", None) != self._timbre_guia():
            self.preparar_audio_guia()
        if self.reproductor is None:
            self._error("No se puede reproducir la referencia",
                        "No se pudo preparar el audio de referencia (¿hay salida de audio?). "
                        "La práctica funciona igual sin él.")
            return
        if self.reproduciendo_audio:
            self._guia_detenida_en = self.reloj()  # la cola del altavoz y la sala sigue un rato
            self.reproductor.pausar()
            self._sincronizar_audio()
            if not self.audio_pausado:
                self._reiniciar_posicion_audio()
            self._cancelar_progreso_audio()
        else:
            self.reproductor.reproducir()
            self._sincronizar_audio()
            if self._evento_actualizar_progreso is None:
                self._evento_actualizar_progreso = Clock.schedule_interval(self._actualizar_progreso_ui, 0.2)

    def _sincronizar_audio(self):
        """Propiedades de la interfaz a partir del estado real del reproductor."""
        reproductor = self.reproductor
        self.reproduciendo_audio = bool(reproductor and reproductor.sonando)
        self.audio_pausado = bool(reproductor and reproductor.estado == "pausado")
        if reproductor is not None:
            self.posicion_audio_actual = reproductor.posicion()
            self.tiempo_actual_str = formatear_tiempo(self.posicion_audio_actual)

    def _reiniciar_posicion_audio(self):
        self.posicion_audio_actual = 0
        self.tiempo_actual_str = "00:00"

    def _cancelar_progreso_audio(self):
        if self._evento_actualizar_progreso:
            self._evento_actualizar_progreso.cancel()
            self._evento_actualizar_progreso = None

    def _guia_terminada(self):
        """El audio de referencia llegó al final solo."""
        self._guia_detenida_en = self.reloj()
        self.reproduciendo_audio = False
        self.audio_pausado = False
        self._reiniciar_posicion_audio()
        self._cancelar_progreso_audio()

    def detener_audio(self):
        if self.reproduciendo_audio:
            self._guia_detenida_en = self.reloj()  # la cola del altavoz y la sala sigue un rato
        if self.reproductor is not None:
            self.reproductor.detener()
        elif self.sonido_guia:
            self.sonido_guia.stop()
        self.reproduciendo_audio = False
        self.audio_pausado = False
        self._reiniciar_posicion_audio()
        self._cancelar_progreso_audio()

    def adelantar_retroceder_audio(self, segundos: float):
        if self.reproductor is not None and self.reproductor.admite_busqueda:
            self.cambiar_posicion_audio(self.reproductor.posicion() + segundos)

    def cambiar_posicion_audio(self, nuevo_tiempo: float):
        """Solo con un reproductor que busca de verdad; si no, no hace nada (y la barra de la
        interfaz no se puede arrastrar)."""
        if self.reproductor is not None and self.reproductor.buscar(nuevo_tiempo):
            self._sincronizar_audio()

    def ajustar_volumen(self, valor: float):
        self.volumen_audio = max(0.0, min(1.0, float(valor)))
        if self.sonido_guia:
            self.sonido_guia.volume = self.volumen_audio
        self._guardar_volumen = getattr(self, "_guardar_volumen", None) or Clock.schedule_once(
            lambda dt: self._volumen_guardado(), 0.6)

    def _volumen_guardado(self):
        self._guardar_volumen = None
        self._guardar_ajustes()

    def _actualizar_progreso_ui(self, dt):
        reproductor = self.reproductor
        if reproductor is None:
            self._cancelar_progreso_audio()
            return
        if reproductor.actualizar():      # terminó solo: _guia_terminada ya lo reflejó
            return
        if reproductor.sonando:
            self._sincronizar_audio()

    # =========================================================================
    #  Práctica
    # =========================================================================

    def preparar_practica(self):
        """Botón «Ir a practicar» de la pantalla de preparación.

        La pantalla de práctica a usar depende del ajuste `vista_simple` en
        `ajustes_wynik.json`:
        - `true` → PartituraSimpleScreen (vista alternativa simplificada)
        - `false` (o ausente) → InterpreteScreen (vista por defecto con pentagrama completo)
        """
        if not self.notas_partitura:
            self._mensaje("Primero elige una partitura.")
            return
        self.iniciar_interpretacion()
        if self.usar_vista_simple:
            self.root.current = "partitura_simple"
        else:
            self.root.current = "interprete"

    def iniciar_interpretacion(self):
        """Deja la práctica preparada (sin escuchar todavía) y genera la guía de audio."""
        self.detener_escucha()
        self.controlador = None
        self._reiniciar_resultados()
        self.preparar_audio_guia()
        self._mostrar_nota(0)
        self._aplicar_estado("lista")

    def _opciones(self):
        from nucleo.sesion import ModoPractica
        from servicios.practica_service import OpcionesPractica
        modo = ModoPractica.SEGUIR_TEMPO if self.seguir_de_largo else ModoPractica.ESPERAR_NOTA
        tempo = self.tempo_partitura * self.factor_tempo
        return OpcionesPractica(
            perfil=self._perfil(), la4=float(self.la4), modo=modo,
            factor_tempo=float(self.factor_tempo), tolerancia_s=self.tolerancia_ms / 1000.0,
            bpm_por_defecto=float(self.bpm), calibrar=bool(self.calibrar_al_iniciar),
            pulsos_cuenta=int(self.pulsos_cuenta),
            segundos_por_pulso=min(max(60.0 / max(tempo, 1.0), 0.3), 1.2),
            dispositivo=self.dispositivo_entrada)

    def iniciar_escucha(self):
        """Empieza a escuchar: detiene la guía, abre el micrófono y arranca la secuencia."""
        from servicios.practica_service import ControladorPractica, MicrofonoNoDisponibleError
        if not self.notas_partitura:
            self.texto_estado = "No hay partitura cargada."
            return
        if not self._guia_en_silencio(self.iniciar_escucha):  # C10: nunca juntas
            return
        self._cancelar_calibracion()
        self.detener_escucha()
        controlador = ControladorPractica(
            self.notas_partitura, self._opciones(), fabrica_captura=self._crear_captura,
            reloj=self.reloj, usar_hilo=self.usar_hilo_analisis,
            ruido=None if self.calibrar_al_iniciar else self.ruido_calibrado,
            primera_sesion=self._siguiente_sesion)
        try:
            controlador.iniciar()
        except MicrofonoNoDisponibleError as error:
            self.controlador = None
            self.detector = None
            self.texto_estado = "No se pudo abrir el micrófono"
            self.texto_resultado = "No se pudo abrir el micrófono"
            self.icono_resultado = "microphone-off"
            self.color_resultado = COLOR_ERROR
            self.clave_resultado = "error"
            print(f"[Wynik] {error}")
            self._error("No se pudo abrir el micrófono",
                        "Revisa el permiso del micrófono y el dispositivo elegido en Ajustes.")
            return
        self.controlador = controlador
        self.detector = controlador.motor
        self._siguiente_sesion = controlador.numero_sesion + 1
        self._reiniciar_resultados()
        self._mostrar_nota(0)
        self._aplicar_estado(controlador.estado)
        self._programar_tick()

    def _programar_tick(self):
        if self._evento_tick is None:
            self._evento_tick = Clock.schedule_interval(self._tick, INTERVALO_TICK_S)

    def _cancelar_tick(self):
        if self._evento_tick is not None:
            self._evento_tick.cancel()
            self._evento_tick = None

    def detener_escucha(self):
        self._cancelar_espera_guia()
        self._cancelar_tick()
        controlador = self.controlador
        if controlador is not None:
            controlador.detener()
        self.detector = None
        if controlador is not None and self.estado_practica != "terminada":
            self._aplicar_estado("lista")

    def boton_principal(self):
        estado = self.estado_practica
        if estado in ("lista", "terminada"):
            self.iniciar_escucha()
        elif estado == "escuchando":
            self.controlador.pausar()
            self.detector = None
            self._aplicar_estado("pausada")
        elif estado == "pausada":
            from servicios.practica_service import MicrofonoNoDisponibleError
            if not self._guia_en_silencio(self.boton_principal):  # la guía pudo sonar en la pausa
                return
            try:
                self.controlador.reanudar()
            except MicrofonoNoDisponibleError as error:
                self._mensaje(str(error))
                return
            self.detector = self.controlador.motor
            self._aplicar_estado(self.controlador.estado)
            self._programar_tick()
        else:  # calibrando o cuenta: cancelar
            self.detener_escucha()

    def reiniciar_practica(self):
        self.detener_escucha()
        self.controlador = None
        self._reiniciar_resultados()
        self._mostrar_nota(0)
        self._aplicar_estado("lista")

    def _reiniciar_resultados(self):
        n = len(self.notas_partitura)
        self.estado_notas = [None] * n
        self.resultados_notas = ["pendiente"] * n
        self.indice_actual = 0
        self._posicion_anterior = None
        self.progreso = 0
        self.texto_detectada = "Todavía no se ha oído ninguna nota."
        self.texto_resultado = "Pulsa «Empezar» cuando estés listo"
        self.icono_resultado = "microphone-outline"
        self.color_resultado = COLOR_NEUTRO
        self.clave_resultado = "neutro"
        self.nota_detectada = ""
        self.cents_detectados = None
        self.texto_aviso = ""
        self._actualizar_progreso_texto()

    # ------------------------------------------------------------------ bucle de la interfaz
    def _tick(self, dt):
        controlador = self.controlador
        if controlador is None:
            return
        actualizacion = controlador.actualizar()
        for procesado in actualizacion.eventos:
            self._procesar_evento(procesado)
        for cambio in actualizacion.cambios:
            self._aplicar_cambio(cambio)
        if actualizacion.indice_cambiado:
            self._avanzar_a(actualizacion.indice_actual)
        if actualizacion.estado_cambiado or actualizacion.estado == "cuenta":
            self._aplicar_estado(actualizacion.estado, actualizacion.cuenta_restante)
        self.detector = controlador.motor
        if actualizacion.terminada:
            self._terminar()

    def _procesar_evento(self, procesado):
        """Muestra lo que se oyó (cada evento de la sesión vigente)."""
        from nucleo.eventos import TipoEvento
        evento = procesado.evento
        if evento.tipo is TipoEvento.FIN:
            return
        if evento.tipo is TipoEvento.NOTA:
            nombre = nombre_para_mostrar(evento.nombre, self.notacion_solfeo)
            self.texto_detectada = (f"Oído: {nombre} · {evento.cents:+.0f} cents · "
                                    f"confianza {evento.confianza * 100:.0f} %")
            self.nota_detectada = nombre
            self.cents_detectados = float(evento.cents)
            self.texto_aviso = ""
            if not procesado.cambios:
                self.texto_detectada += " (fuera de tiempo: no cuenta)"
                self.texto_aviso = f"{nombre} fuera de tiempo: no cuenta."
            if self.instrumento == "piano":
                self._marcar_detectada_en_teclado(evento.midi_entero)
        elif evento.tipo is TipoEvento.FUERA_DE_RANGO:
            nombre = nombre_para_mostrar(evento.nombre, self.notacion_solfeo)
            self.texto_detectada = (f"Oído: {nombre}, fuera del rango del {self._perfil().nombre.lower()} "
                                    f"({self._perfil().rango_texto})")
            self.nota_detectada = nombre
            self.cents_detectados = None
            self.texto_aviso = f"{nombre} está fuera del rango del {self._perfil().nombre.lower()}."
        elif evento.tipo is TipoEvento.SENAL_DEBIL:
            self.texto_detectada = "Señal muy débil: toca más fuerte o acércate al micrófono."
            self.texto_aviso = self.texto_detectada
        else:
            self.texto_detectada = "Sonido sin altura clara (ruido o golpe): no se evalúa."
            self.texto_aviso = "Sonido sin altura clara: no se evalúa."

    def _aplicar_cambio(self, cambio):
        from nucleo.sesion import EstadoNota, describir_estado
        indice, resultado = cambio.indice, cambio.resultado
        if indice >= len(self.resultados_notas):
            return
        resultados = list(self.resultados_notas)
        resultados[indice] = resultado.estado.value
        self.resultados_notas = resultados
        booleanos = list(self.estado_notas)
        neutro = resultado.estado in (EstadoNota.PENDIENTE, EstadoNota.SIN_EVALUAR)
        booleanos[indice] = None if neutro else resultado.es_acierto
        self.estado_notas = booleanos
        esperada = self._nombre_nota(indice)
        estado = resultado.estado
        if estado is EstadoNota.CORRECTA:
            texto, icono, color = f"✓ {esperada}: correcta", "check-circle", COLOR_CORRECTO
            clave = "correcta"
        elif estado is EstadoNota.DESAFINADA:
            texto = f"≈ {esperada}: correcta pero desafinada ({resultado.cents:+.0f} cents)"
            icono, color, clave = "check-circle-outline", COLOR_DESAFINADO, "desafinada"
        elif estado in (EstadoNota.NOTA_INCORRECTA, EstadoNota.OCTAVA_INCORRECTA):
            tocada = nombre_para_mostrar(resultado.evento.nombre, self.notacion_solfeo) if resultado.evento else "?"
            motivo = "octava incorrecta" if estado is EstadoNota.OCTAVA_INCORRECTA else "nota equivocada"
            texto, icono, color = f"✗ {motivo}: tocaste {tocada}, se esperaba {esperada}", "close-circle", COLOR_ERROR
            clave = "error"
        elif estado is EstadoNota.SIN_EVALUAR:
            texto, icono, color = "Acorde: solo referencia, no se evalúa", "music-note", COLOR_NEUTRO
            clave = "sin_evaluar"
        else:
            texto = f"{describir_estado(estado)}: {esperada}"
            icono = "help-circle-outline" if estado is not EstadoNota.OMITIDA else "minus-circle-outline"
            color = COLOR_ERROR if estado is EstadoNota.FUERA_DE_RANGO else COLOR_NEUTRO
            clave = "fuera_de_rango" if estado is EstadoNota.FUERA_DE_RANGO else "omitida"
        self.texto_resultado, self.icono_resultado, self.color_resultado = texto, icono, color
        self.clave_resultado = clave
        self._actualizar_progreso_texto()

    def _avanzar_a(self, indice: int):
        self.indice_actual = indice
        self._mostrar_nota(indice)

    def _aplicar_estado(self, estado: str, cuenta: int = 0):
        self.estado_practica = estado
        modo = "sigue el tempo" if self.seguir_de_largo else "la partitura espera cada nota"
        textos = {
            "lista": ("Lista", "Empezar", "play"),
            "calibrando": ("Silencio, por favor: midiendo el ruido de fondo…", "Cancelar", "close"),
            "cuenta": (f"Prepárate… {cuenta}", "Cancelar", "close"),
            "escuchando": (f"Escuchando · {modo}", "Pausa", "pause"),
            "pausada": ("En pausa", "Reanudar", "play"),
            "terminada": ("Terminado", "Repetir", "restart"),
        }
        texto, boton, icono = textos.get(estado, ("", "Empezar", "play"))
        self.texto_estado = texto
        self.texto_boton_principal, self.icono_boton_principal = boton, icono
        if estado == "cuenta":
            self.texto_resultado = f"Empieza en {cuenta}…"
            self.icono_resultado = "timer-sand"
            self.color_resultado = COLOR_NEUTRO
            self.clave_resultado = "cuenta"
        elif estado == "escuchando" and self.texto_resultado.startswith("Empieza en"):
            self.texto_resultado = "¡Ahora!"
            self.icono_resultado = "microphone"
            self.clave_resultado = "escuchando"
        elif estado == "calibrando":
            self.texto_resultado = "Midiendo el ruido de fondo (1 s)"
            self.icono_resultado = "waveform"
            self.clave_resultado = "cuenta"

    def _terminar(self):
        self._cancelar_tick()
        self.detector = None
        resumen = self.controlador.resumen() if self.controlador else {}
        if self.controlador is not None and self.controlador.ruido is not None:
            self.ruido_calibrado = self.controlador.ruido
            self.texto_calibracion = self._describir_ruido(self.ruido_calibrado)
        total = resumen.get("evaluables", resumen.get("total", 0)) or 1
        aciertos = resumen.get("aciertos", 0)
        estados = resumen.get("estados", {})
        errores = estados.get("nota_incorrecta", 0) + estados.get("octava_incorrecta", 0)
        omitidas = (estados.get("omitida", 0) + estados.get("senal_insuficiente", 0)
                    + estados.get("baja_confianza", 0) + estados.get("fuera_de_rango", 0))
        self.texto_resultado = f"Terminado: {aciertos} de {total} ({100 * aciertos / total:.0f} %)"
        self.texto_detectada = f"Errores de nota u octava: {errores} · sin tocar o sin señal: {omitidas}"
        self.icono_resultado = "flag-checkered"
        self.color_resultado = COLOR_CORRECTO if aciertos == total else COLOR_NEUTRO
        self.clave_resultado = "terminada"
        self._aplicar_estado("terminada")
        self._mostrar_resumen_final(aciertos, total, errores, omitidas, estados.get("sin_evaluar", 0))
        try:
            registrar_sesion(self.nombre_partitura, self.instrumento,
                             "seguir_tempo" if self.seguir_de_largo else "esperar_nota",
                             float(self.factor_tempo), resumen)
        except Exception as error:  # noqa: BLE001
            print(f"[Wynik] No se pudo guardar el progreso: {error}")

    def _mostrar_resumen_final(self, aciertos, total, errores, omitidas, sin_evaluar):
        """Diálogo al terminar: porcentaje, desglose y qué hacer ahora."""
        if not self._con_interfaz:
            return
        try:
            from kivy.metrics import dp, sp
            from kivy.uix.boxlayout import BoxLayout
            from .componentes import AnilloProgreso, Etiqueta
            fraccion = aciertos / total if total else 0
            caja = BoxLayout(size_hint_y=None, height=dp(120), spacing=dp(18))
            caja.add_widget(AnilloProgreso(valor=fraccion, size_hint=(None, None), size=(dp(112), dp(112)),
                                           color=tema.CORRECTO if fraccion >= 0.8 else tema.PRIMARIO,
                                           pos_hint={"center_y": 0.5}))
            lineas = [f"[b]{aciertos}[/b] de {total} notas correctas",
                      f"[color=#C43A2D]✗[/color] errores de nota u octava: {errores}",
                      f"– sin tocar o sin señal: {omitidas}"]
            if sin_evaluar:
                lineas.append(f"○ acordes (solo referencia): {sin_evaluar}")
            caja.add_widget(Etiqueta(text="\n".join(lineas), markup=True, font_size=sp(tema.T_SECUNDARIO + 1),
                                     line_height=1.25, pos_hint={"center_y": 0.5}))
        except Exception:  # noqa: BLE001
            caja = None
        self._dialogo("Práctica terminada", icono="flag-checkered", contenido=caja,
                      botones=(("Ver progreso", "texto", lambda: self.change_screen("progreso")),
                               ("Repetir", "primario", self.boton_principal)))

    def mostrar_leyenda(self):
        """Qué significa cada marca de la partitura (no se muestra de forma permanente)."""
        filas = (("✓", tema.CORRECTO, "Correcta"), ("≈", tema.DESAFINADO, "Correcta pero desafinada"),
                 ("✗", tema.ERROR, "Nota u octava equivocada"), ("!", tema.ERROR, "Fuera del rango del instrumento"),
                 ("–", tema.NEUTRO, "Sin tocar"), ("?", tema.NEUTRO, "Señal insuficiente o dudosa"),
                 ("○", tema.NEUTRO, "Acorde: solo referencia, no se evalúa"),
                 ("▲", tema.ACENTO, "Posición actual"))
        try:
            from kivy.metrics import dp, sp
            from kivy.uix.gridlayout import GridLayout
            from kivy.uix.label import Label
            from .componentes import Etiqueta
            rejilla = GridLayout(cols=2, size_hint_y=None, spacing=(dp(12), dp(6)))
            rejilla.bind(minimum_height=rejilla.setter("height"))
            for simbolo, color, texto in filas:
                rejilla.add_widget(Label(text=simbolo, color=color, bold=True, font_name=tema.FUENTE_TEXTO,
                                         font_size=sp(18), size_hint=(None, None), size=(dp(24), dp(26))))
                rejilla.add_widget(Etiqueta(text=texto, font_size=sp(tema.T_SECUNDARIO + 1)))
        except Exception:  # noqa: BLE001
            rejilla = None
        if self._dialogo("Marcas de la partitura", icono="help-circle-outline", contenido=rejilla) is None:
            self._mensaje(" · ".join(f"{s} {t}" for s, _c, t in filas))

    def _actualizar_progreso_texto(self):
        total = len(self.notas_partitura)
        evaluadas = sum(1 for r in self.resultados_notas if r != "pendiente")
        aciertos = sum(1 for e in self.estado_notas if e is True)
        self.progreso = evaluadas / total if total else 0
        if total:
            self.texto_progreso = f"Nota {min(int(self.indice_actual) + 1, total)} de {total} · {aciertos} ✓"
        else:
            self.texto_progreso = ""

    # ------------------------------------------------------------------ nota esperada y guía
    def _nombre_nota(self, indice: int, nombre: str = None) -> str:
        if nombre is None:
            if not 0 <= indice < len(self.notas_partitura):
                return ""
            nombre = self.notas_partitura[indice]["nombre"]
        return nombre_para_mostrar(nombre, self.notacion_solfeo)

    def _mostrar_nota(self, indice: int):
        if not self.notas_partitura or indice >= len(self.notas_partitura):
            self.nota_esperada = None
            self.texto_esperada = "—"
            self.texto_esperada_detalle = ""
            self.modelo_guia = {"tipo": "vacio", "mensaje": ""}
            self.texto_guia = ""
            return
        nota = self.notas_partitura[indice]
        self.nota_esperada = nota["nombre"]
        self.texto_esperada = self._nombre_nota(indice)
        detalle = []
        escrita = nota.get("nombre_escrito")
        if escrita and escrita != nota["nombre"]:
            detalle.append(f"Suena {self._nombre_nota(indice)}; se escribe {self._nombre_nota(indice, escrita)}")
        if nota.get("es_acorde"):
            nombres = " ".join(self._nombre_nota(indice, n) for n in nota.get("nombres", []))
            detalle.append(f"Acorde {nombres}: solo referencia, no se evalúa")
        self.texto_esperada_detalle = "\n".join(detalle)
        self._actualizar_guia(nota)
        self._actualizar_progreso_texto()

    def _actualizar_guia(self, nota: dict):
        from nucleo import digitacion
        from nucleo.instrumentos import AFINACIONES_GUITARRA
        from nucleo.musica import ErrorAltura, a_midi
        try:
            principal = int(round(nota["midi"] if nota.get("midi") is not None else a_midi(nota["nombre"])))
        except (ErrorAltura, KeyError, TypeError):
            self.modelo_guia = {"tipo": "vacio", "mensaje": "Nota sin altura reconocible"}
            self.texto_guia = ""
            return
        alturas = [int(round(m)) for m in (nota.get("alturas_midi") or [principal])]
        if self.instrumento == "guitarra":
            afinacion = AFINACIONES_GUITARRA[self.afinacion_guitarra]
            if len(alturas) > 1:
                diagrama = digitacion.acorde_guitarra(alturas, afinacion)
                if diagrama is None:
                    self.modelo_guia = {"tipo": "vacio",
                                        "mensaje": "Sin propuesta de digitación validada"}
                    self.texto_guia = "No hay una digitación de guitarra fiable para este acorde."
                    return
                self.modelo_guia = {"tipo": "guitarra_acorde", "afinacion": afinacion,
                                    "trastes": diagrama.trastes, "dedos": diagrama.dedos,
                                    "validado": diagrama.validado, "nombre": diagrama.nombre,
                                    "traste_base": diagrama.traste_base,
                                    "cejillas": [(c.traste, c.cuerda_desde, c.cuerda_hasta, c.dedo)
                                                 for c in diagrama.cejillas]}
                if diagrama.cejillas:
                    texto = f"{diagrama.nombre}: dedo 1 en cejilla (solo referencia)."
                elif diagrama.validado:
                    texto = f"{diagrama.nombre}: forma y digitación habituales (solo referencia)."
                else:
                    texto = "Posiciones calculadas, sin digitación verificada (solo referencia)."
                self.texto_guia = texto
                return
            posicion = digitacion.posicion_sugerida(principal, afinacion, anterior=self._posicion_anterior)
            if posicion is None:
                self.modelo_guia = {"tipo": "guitarra", "afinacion": afinacion, "posicion": None,
                                    "mensaje": "Esta nota no está en la guitarra con esta afinación"}
                self.texto_guia = "Nota fuera del rango de la guitarra."
                return
            self._posicion_anterior = posicion
            alternativas = digitacion.alternativas_guitarra(principal, afinacion, elegida=posicion)
            self.modelo_guia = {"tipo": "guitarra", "afinacion": afinacion,
                                "posicion": (posicion.cuerda, posicion.traste, posicion.dedo),
                                "alternativas": [(p.cuerda, p.traste) for p in alternativas]}
            texto = posicion.descripcion()
            if alternativas:
                otras = ", ".join(f"c{p.cuerda} t{p.traste}" for p in alternativas[:3])
                texto += f" · también: {otras}"
            self.texto_guia = texto
            return
        mano = "derecha" if principal >= 60 else "izquierda"
        dedos = digitacion.digitacion_piano(alturas, mano) if len(alturas) > 1 else None
        mapa_dedos = dict(zip(sorted(set(alturas)), dedos)) if dedos else {}
        self.modelo_guia = {"tipo": "piano", "rango": digitacion.rango_teclado(alturas),
                            "teclas": alturas, "principal": principal, "dedos": mapa_dedos,
                            "detectada": None, "acierto": None}
        if len(alturas) > 1:
            self.texto_guia = (f"Tríada en posición fundamental: dedos {'-'.join(map(str, dedos))} (mano {mano})"
                               if dedos else "Acorde: teclas marcadas; sin digitación propuesta.")
        else:
            self.texto_guia = f"Tecla {self._nombre_nota(0, nota['nombre'])} (resaltada)"

    def _marcar_detectada_en_teclado(self, midi):
        if self.modelo_guia.get("tipo") != "piano" or midi is None:
            return
        modelo = dict(self.modelo_guia)
        modelo["detectada"] = int(midi)
        modelo["acierto"] = int(midi) == modelo.get("principal")
        self.modelo_guia = modelo

    # =========================================================================
    #  Progreso
    # =========================================================================

    def refrescar_progreso(self):
        sesiones = cargar_progreso()
        grupos = resumen_por_partitura(sesiones) if sesiones else []
        self.progreso_sesiones = len(sesiones)
        self.progreso_historial = [float(s.get("precision", 0)) for s in sesiones[-12:]]
        if sesiones:
            media = sum(s.get("precision", 0) for s in sesiones) / len(sesiones)
            self.progreso_media = media
            cuantas = "1 sesión registrada" if len(sesiones) == 1 else f"{len(sesiones)} sesiones registradas"
            self.texto_resumen_progreso = f"{cuantas} · precisión media {media * 100:.0f} %"
            mejor = max(grupos, key=lambda g: g["mejor"]) if grupos else None
            detalle = f"{len(grupos)} {'partitura' if len(grupos) == 1 else 'partituras'} practicadas"
            if mejor is not None:
                detalle += f" · mejor resultado {round(100 * mejor['mejor'])} % en «{mejor['partitura']}»"
            self.texto_progreso_detalle = detalle
        else:
            self.progreso_media = 0
            self.texto_resumen_progreso = "Todavía no has terminado ninguna práctica."
            self.texto_progreso_detalle = "Al terminar una práctica, su resultado aparece aquí."
        try:
            pantalla = self.root.get_screen("progreso")
            lista = pantalla.ids.lista_progreso
            lista_partituras = pantalla.ids.lista_partituras_progreso
        except Exception:  # noqa: BLE001
            return
        from kivy.factory import Factory
        lista.clear_widgets()
        lista_partituras.clear_widgets()
        for grupo in grupos[:12]:
            n = grupo["sesiones"]
            lista_partituras.add_widget(Factory.FilaPartituraProgreso(
                titulo=grupo["partitura"], mejor=float(grupo["mejor"]),
                detalle=(f"mejor {round(100 * grupo['mejor'])} % · última {round(100 * grupo['ultima'])} % · "
                         f"{n} {'sesión' if n == 1 else 'sesiones'}")))
        for sesion in reversed(sesiones[-40:]):
            iso = sesion.get("fecha", "")
            # «16/10 16:12»: la línea tiene que caber en una pantalla de teléfono.
            fecha = f"{iso[8:10]}/{iso[5:7]} {iso[11:16]}" if len(iso) >= 16 else iso
            modo = "sigue el tempo" if sesion.get("modo") == "seguir_tempo" else "espera cada nota"
            lista.add_widget(Factory.FilaSesion(
                titulo=str(sesion.get("partitura", "?")), porcentaje=float(sesion.get("precision", 0)),
                detalle=(f"{fecha} · {sesion.get('instrumento', '')} · {sesion.get('aciertos', 0)}/"
                         f"{sesion.get('total', 0)} · {modo} al {sesion.get('factor_tempo', 1) * 100:.0f} %")))
