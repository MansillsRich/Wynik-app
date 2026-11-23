import copy
import datetime
import glob
import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from audio.captura import CapturaBase, MicrofonoNoDisponibleError
from servicios.almacenamiento import configurar_directorio, ruta_dato
from servicios.analytics_service import (
    ARCHIVO_ANALITICA,
    MAXIMO_EVENTOS,
    calcular_funnel,
    cargar_eventos,
    generar_id,
    registrar_evento,
)


def _cargar_wynik_app_cls():
    """Carga `vistas/app.py` sin inicializar ventana OpenGL de Kivy/KivyMD en entornos headless."""
    raiz = Path(__file__).resolve().parent.parent

    class _Prop:
        def __init__(self, default=None, **_kwargs):
            self._default = default
            self._name = None

        def __set_name__(self, owner, name):
            self._name = f"_prop_{name}"

        def __get__(self, instance, owner=None):
            if instance is None:
                return self
            if self._name not in instance.__dict__:
                val = self._default
                instance.__dict__[self._name] = copy.deepcopy(val) if isinstance(val, (list, dict)) else val
            return instance.__dict__[self._name]

        def __set__(self, instance, value):
            instance.__dict__[self._name] = value

    class _TriggerStub:
        def cancel(self):
            pass

        def __call__(self, *args, **kwargs):
            pass

    kivy_mod = types.ModuleType("kivy")
    kivy_clock = types.ModuleType("kivy.clock")
    kivy_clock.Clock = types.SimpleNamespace(
        max_iteration=20,
        schedule_interval=lambda cb, dt: _TriggerStub(),
        schedule_once=lambda cb, dt=0: _TriggerStub(),
        create_trigger=lambda cb, dt=0: _TriggerStub(),
    )
    kivy_core = types.ModuleType("kivy.core")
    kivy_core_audio = types.ModuleType("kivy.core.audio")
    kivy_core_audio.SoundLoader = types.SimpleNamespace(_classes=[], load=lambda _p: None)
    kivy_lang = types.ModuleType("kivy.lang")
    kivy_lang.Builder = types.SimpleNamespace(unload_file=lambda _p: None, load_file=lambda _p, **_k: None)
    kivy_props = types.ModuleType("kivy.properties")
    for _pname in (
        "BooleanProperty",
        "DictProperty",
        "ListProperty",
        "NumericProperty",
        "ObjectProperty",
        "StringProperty",
    ):
        setattr(kivy_props, _pname, _Prop)
    kivy_utils = types.ModuleType("kivy.utils")
    kivy_utils.platform = "macosx"
    kivy_metrics = types.ModuleType("kivy.metrics")
    kivy_metrics.Metrics = types.SimpleNamespace(fontscale=1.0)

    kivymd_mod = types.ModuleType("kivymd")
    kivymd_app = types.ModuleType("kivymd.app")

    class _MDApp:
        pass

    kivymd_app.MDApp = _MDApp

    vistas_pkg = types.ModuleType("vistas")
    vistas_pkg.__path__ = [str(raiz / "vistas")]
    vistas_screens = types.ModuleType("vistas.screens")
    for _sname in (
        "MenuScreen",
        "ElegirPartituraScreen",
        "AjustesInicioScreen",
        "InterpreteScreen",
        "AjustesScreen",
        "ProgresoScreen",
        "PartituraSimpleScreen",
    ):
        setattr(vistas_screens, _sname, type(_sname, (), {}))
    vistas_widgets = types.ModuleType("vistas.widgets")
    for _wname in ("PartituraWidget", "GuiaInstrumentoWidget", "PartituraSimpleWidget"):
        setattr(vistas_widgets, _wname, type(_wname, (), {}))
    vistas_dialogs = types.ModuleType("vistas.dialogs")
    vistas_dialogs.abrir_selector_de_archivo = lambda cb: None

    stubs = {
        "kivy": kivy_mod,
        "kivy.clock": kivy_clock,
        "kivy.core": kivy_core,
        "kivy.core.audio": kivy_core_audio,
        "kivy.lang": kivy_lang,
        "kivy.properties": kivy_props,
        "kivy.utils": kivy_utils,
        "kivy.metrics": kivy_metrics,
        "kivymd": kivymd_mod,
        "kivymd.app": kivymd_app,
        "vistas": vistas_pkg,
        "vistas.screens": vistas_screens,
        "vistas.widgets": vistas_widgets,
        "vistas.dialogs": vistas_dialogs,
    }

    with mock.patch.dict(sys.modules, stubs):
        spec = importlib.util.spec_from_file_location("vistas.app_headless", str(raiz / "vistas" / "app.py"))
        modulo = importlib.util.module_from_spec(spec)
        modulo.__package__ = "vistas"
        sys.modules["vistas.app_headless"] = modulo
        try:
            spec.loader.exec_module(modulo)
            return modulo.WynikApp, stubs
        finally:
            sys.modules.pop("vistas.app_headless", None)


class _CapturaFalsa(CapturaBase):
    """Captura simulada en memoria para probar flujos sin micrófono físico."""

    def __init__(self, fallar_al_iniciar: bool = False):
        super().__init__()
        self.frecuencia_muestreo = 48000.0
        self.fallar_al_iniciar = fallar_al_iniciar
        self._activa = False

    def abrir(self) -> None:
        if self.fallar_al_iniciar:
            raise MicrofonoNoDisponibleError("Micrófono simulado no disponible")
        self._activa = True

    def cerrar(self) -> None:
        self._activa = False

    @property
    def activa(self) -> bool:
        return self._activa


class TestAnalyticsService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        configurar_directorio(self.temp_dir.name)

    def tearDown(self):
        configurar_directorio(None)
        self.temp_dir.cleanup()

    def test_registrar_evento_estructura_y_persistencia(self):
        funnel_id = generar_id("fnl")
        practice_id = generar_id("prc")
        evento = registrar_evento(
            "practica_iniciada",
            {"instrumento": "piano", "modalidad": "seguir_tempo"},
            funnel_id,
            practice_id=practice_id,
        )
        self.assertIsNotNone(evento)
        self.assertTrue(evento["event_id"].startswith("evt-"))
        self.assertEqual(evento["event_name"], "practica_iniciada")
        self.assertEqual(evento["funnel_id"], funnel_id)
        self.assertEqual(evento["practice_id"], practice_id)
        self.assertEqual(evento["data"], {"instrumento": "piano", "modalidad": "seguir_tempo"})
        # Validar formato ISO 8601
        parsed_ts = datetime.datetime.fromisoformat(evento["timestamp"])
        self.assertIsNotNone(parsed_ts.tzinfo)

        cargados = cargar_eventos()
        self.assertEqual(len(cargados), 1)
        self.assertEqual(cargados[0]["event_id"], evento["event_id"])

    def test_relacion_identificadores_secuencia_completa(self):
        fid = generar_id("fnl")
        pid = generar_id("prc")
        e1 = registrar_evento("partitura_cargada", {"formato": "musicxml", "cantidad_notas": 8}, fid)
        e2 = registrar_evento("practica_iniciada", {"instrumento": "piano"}, fid, practice_id=pid)
        e3 = registrar_evento("sesion_finalizada", {"precision_porcentaje": 87.5}, fid, practice_id=pid)

        self.assertIsNotNone(e1)
        self.assertIsNotNone(e2)
        self.assertIsNotNone(e3)
        self.assertIsNone(e1["practice_id"])
        self.assertEqual(e2["practice_id"], pid)
        self.assertEqual(e3["practice_id"], pid)
        self.assertEqual({e1["funnel_id"], e2["funnel_id"], e3["funnel_id"]}, {fid})
        self.assertEqual(len({e1["event_id"], e2["event_id"], e3["event_id"]}), 3)

    def test_archivo_inexistente(self):
        self.assertFalse(os.path.exists(ruta_dato(ARCHIVO_ANALITICA)))
        self.assertEqual(cargar_eventos(), [])

        evento = registrar_evento("partitura_cargada", {"formato": "mxl"}, generar_id("fnl"))
        self.assertIsNotNone(evento)
        self.assertTrue(os.path.exists(ruta_dato(ARCHIVO_ANALITICA)))
        self.assertEqual(len(cargar_eventos()), 1)

    def test_json_invalido_preserva_evidencia_y_loguea(self):
        ruta = ruta_dato(ARCHIVO_ANALITICA)
        contenido_corrupto = "{esto no es json valido ["
        with open(ruta, "w", encoding="utf-8") as archivo:
            archivo.write(contenido_corrupto)

        with self.assertLogs("servicios.analytics_service", level="ERROR") as logs_lectura:
            self.assertEqual(cargar_eventos(), [])
        self.assertTrue(any("No se pudo leer una lista válida" in msg for msg in logs_lectura.output))
        # El modo solo lectura no debe alterar el archivo corrupto
        with open(ruta, "r", encoding="utf-8") as archivo:
            self.assertEqual(archivo.read(), contenido_corrupto)

        with self.assertLogs("servicios.analytics_service", level="ERROR") as logs_escritura:
            evento = registrar_evento("partitura_cargada", {"formato": "xml"}, generar_id("fnl"))
        self.assertIsNotNone(evento)
        self.assertTrue(any("corrupto" in msg.lower() for msg in logs_escritura.output))

        respaldos = glob.glob(os.path.join(self.temp_dir.name, "analytics_events.corrupt.*.json"))
        self.assertEqual(len(respaldos), 1)
        with open(respaldos[0], "r", encoding="utf-8") as archivo:
            self.assertEqual(archivo.read(), contenido_corrupto)

        cargados = cargar_eventos()
        self.assertEqual(len(cargados), 1)
        self.assertEqual(cargados[0]["event_id"], evento["event_id"])

    def test_excepcion_en_escritura_no_interrumpe_aplicacion(self):
        with mock.patch("servicios.analytics_service.escribir_json", side_effect=RuntimeError("Disco lleno")):
            with self.assertLogs("servicios.analytics_service", level="ERROR"):
                resultado = registrar_evento("partitura_cargada", {"formato": "musicxml"}, generar_id("fnl"))
        self.assertIsNone(resultado)

        with mock.patch("servicios.analytics_service.escribir_json", return_value=False):
            with self.assertLogs("servicios.analytics_service", level="ERROR"):
                resultado = registrar_evento("partitura_cargada", {"formato": "musicxml"}, generar_id("fnl"))
        self.assertIsNone(resultado)

    def test_limite_maximo_1000_eventos(self):
        ruta = ruta_dato(ARCHIVO_ANALITICA)
        base = [
            {
                "event_id": f"evt-base-{i}",
                "event_name": "partitura_cargada",
                "timestamp": "2026-11-23T10:00:00-03:00",
                "funnel_id": f"fnl-{i}",
                "practice_id": None,
                "data": {"indice": i},
            }
            for i in range(995)
        ]
        with open(ruta, "w", encoding="utf-8") as archivo:
            json.dump(base, archivo)

        for i in range(25):
            ev = registrar_evento("partitura_cargada", {"indice": 995 + i}, f"fnl-{995 + i}")
            self.assertIsNotNone(ev)

        cargados = cargar_eventos()
        self.assertEqual(len(cargados), MAXIMO_EVENTOS)
        self.assertEqual(cargados[0]["data"]["indice"], 20)
        self.assertEqual(cargados[-1]["data"]["indice"], 1019)

    def test_calcular_funnel_conversiones_y_abandono(self):
        eventos = [
            # Recorrido 1: completo
            {"event_name": "partitura_cargada", "funnel_id": "f1"},
            {"event_name": "practica_iniciada", "funnel_id": "f1"},
            {"event_name": "sesion_finalizada", "funnel_id": "f1"},
            # Recorrido 2: completo
            {"event_name": "partitura_cargada", "funnel_id": "f2"},
            {"event_name": "practica_iniciada", "funnel_id": "f2"},
            {"event_name": "sesion_finalizada", "funnel_id": "f2"},
            # Recorrido 3: abandona tras iniciar práctica
            {"event_name": "partitura_cargada", "funnel_id": "f3"},
            {"event_name": "practica_iniciada", "funnel_id": "f3"},
            # Recorrido 4: abandona tras cargar partitura
            {"event_name": "partitura_cargada", "funnel_id": "f4"},
        ]
        resumen = calcular_funnel(eventos)
        self.assertEqual(resumen["recorridos_unicos"], 4)
        self.assertEqual(resumen["etapas"]["partitura_cargada"], 4)
        self.assertEqual(resumen["etapas"]["practica_iniciada"], 3)
        self.assertEqual(resumen["etapas"]["sesion_finalizada"], 2)
        self.assertEqual(resumen["conversiones_porcentaje"]["etapa_1_a_2"], 75.0)
        self.assertEqual(resumen["conversiones_porcentaje"]["etapa_2_a_3"], 66.67)
        self.assertEqual(resumen["conversiones_porcentaje"]["total_1_a_3"], 50.0)
        self.assertEqual(resumen["abandono"]["etapa_1_a_2"]["cantidad"], 1)
        self.assertEqual(resumen["abandono"]["etapa_1_a_2"]["porcentaje"], 25.0)
        self.assertEqual(resumen["abandono"]["etapa_2_a_3"]["cantidad"], 1)
        self.assertEqual(resumen["abandono"]["etapa_2_a_3"]["porcentaje"], 33.33)
        self.assertEqual(resumen["abandono"]["total_1_a_3"]["cantidad"], 2)
        self.assertEqual(resumen["abandono"]["total_1_a_3"]["porcentaje"], 50.0)

    def test_calcular_funnel_vacio_sin_division_por_cero(self):
        resumen = calcular_funnel([])
        self.assertEqual(resumen["etapas"]["partitura_cargada"], 0)
        self.assertEqual(resumen["etapas"]["practica_iniciada"], 0)
        self.assertEqual(resumen["etapas"]["sesion_finalizada"], 0)
        self.assertEqual(resumen["conversiones_porcentaje"]["etapa_1_a_2"], 0.0)
        self.assertEqual(resumen["conversiones_porcentaje"]["etapa_2_a_3"], 0.0)
        self.assertEqual(resumen["conversiones_porcentaje"]["total_1_a_3"], 0.0)
        self.assertEqual(resumen["abandono"]["total_1_a_3"]["cantidad"], 0)

    def test_calcular_funnel_duplicados_y_huerfanos(self):
        eventos = [
            # Recorrido con repeticiones en etapa 2 y etapa 3
            {"event_name": "partitura_cargada", "funnel_id": "f1"},
            {"event_name": "practica_iniciada", "funnel_id": "f1"},
            {"event_name": "practica_iniciada", "funnel_id": "f1"},
            {"event_name": "sesion_finalizada", "funnel_id": "f1"},
            {"event_name": "sesion_finalizada", "funnel_id": "f1"},
            # Eventos huérfanos / fuera de secuencia
            {"event_name": "practica_iniciada", "funnel_id": "f_huerfano_1"},
            {"event_name": "sesion_finalizada", "funnel_id": "f_huerfano_2"},
        ]
        resumen = calcular_funnel(eventos)
        self.assertEqual(resumen["etapas"]["partitura_cargada"], 1)
        self.assertEqual(resumen["etapas"]["practica_iniciada"], 1)
        self.assertEqual(resumen["etapas"]["sesion_finalizada"], 1)
        self.assertEqual(resumen["conversiones_porcentaje"]["etapa_1_a_2"], 100.0)
        self.assertEqual(resumen["conversiones_porcentaje"]["etapa_2_a_3"], 100.0)
        self.assertEqual(resumen["conversiones_porcentaje"]["total_1_a_3"], 100.0)
        self.assertEqual(resumen["eventos_repetidos_en_etapa"], 2)
        self.assertEqual(resumen["eventos_huerfanos_o_fuera_de_secuencia"], 2)

    def test_integracion_wynik_app_sin_microfono_fisico(self):
        raiz = Path(__file__).resolve().parent.parent
        partitura_real = str(raiz / "docs" / "anexo_iv" / "partituras" / "escala_do_mayor.musicxml")
        self.assertTrue(os.path.exists(partitura_real))

        tiempo_actual = [100.0]

        def reloj_ficticio():
            return tiempo_actual[0]

        wynik_app_cls, stubs = _cargar_wynik_app_cls()
        with mock.patch.dict(sys.modules, stubs):
            app = wynik_app_cls()
            app._inicializar_estado()
            app._mostrar_aviso = lambda _texto: None
            app.reloj = reloj_ficticio
            app.usar_hilo_analisis = False
            app.calibrar_al_iniciar = False

            # 1. Carga fallida no debe registrar evento
            self.assertFalse(app._cargar_partitura(os.path.join(self.temp_dir.name, "no_existe.musicxml")))
            self.assertEqual(len(cargar_eventos()), 0)

            # 2. Carga exitosa registra partitura_cargada sin ruta completa
            self.assertTrue(app._cargar_partitura(partitura_real))
            eventos = cargar_eventos()
            self.assertEqual(len(eventos), 1)
            self.assertEqual(eventos[0]["event_name"], "partitura_cargada")
            self.assertNotIn(partitura_real, json.dumps(eventos[0], ensure_ascii=False))

            # 3. Cambio de convención en guitarra no debe duplicar partitura_cargada
            app.cambiar_convencion_guitarra("sonora")
            self.assertEqual(len(cargar_eventos()), 1)

            # 4. Fallo de micrófono no debe registrar practica_iniciada
            app.fabrica_captura = lambda: _CapturaFalsa(fallar_al_iniciar=True)
            app.iniciar_escucha()
            self.assertEqual(len(cargar_eventos()), 1)

            # 5. Inicio exitoso de práctica registra practica_iniciada con mismo funnel_id
            app.fabrica_captura = lambda: _CapturaFalsa(fallar_al_iniciar=False)
            app.iniciar_escucha()
            eventos = cargar_eventos()
            self.assertEqual(len(eventos), 2)
            self.assertEqual(eventos[1]["event_name"], "practica_iniciada")
            self.assertEqual(eventos[1]["funnel_id"], eventos[0]["funnel_id"])
            self.assertIsNotNone(eventos[1]["practice_id"])

            # 6. Salida anticipada no registra sesion_finalizada
            app.detener_escucha()
            self.assertEqual(len(cargar_eventos()), 2)

            # 7. Finalización natural registra sesion_finalizada una sola vez
            tiempo_actual[0] = 112.5
            app._terminar()
            app._terminar()  # Segunda invocación debe ser ignorada por la guarda
            eventos = cargar_eventos()
            self.assertEqual(len(eventos), 3)
            self.assertEqual(eventos[2]["event_name"], "sesion_finalizada")
            self.assertEqual(eventos[2]["funnel_id"], eventos[0]["funnel_id"])
            self.assertEqual(eventos[2]["practice_id"], eventos[1]["practice_id"])
            self.assertEqual(eventos[2]["data"]["duracion_s"], 12.5)


if __name__ == "__main__":
    unittest.main()
