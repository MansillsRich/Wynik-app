"""
Módulo de servicios de Wynik: procesamiento musical, audio, captura y persistencia.
Todas las funciones que no hacen uso de Kivy ni KivyMD residen en esta capa de servicios.

Los nombres se importan bajo demanda (PEP 562): `from servicios import nota_coincide` no
carga numpy ni el análisis de audio; sounddevice solo se importa al abrir el micrófono.
Así, los componentes musicales se pueden usar sin las dependencias de escritorio.
"""

import importlib

_ORIGEN = {
    "cargar_partitura": "partitura_service",
    "cargar_partitura_estructurada": "partitura_service",
    "validar_extension_partitura": "partitura_service",
    "ErrorPartitura": "partitura_service",
    "generar_audio_guia": "audio_service",
    "generar_guia": "audio_service",
    "formatear_tiempo": "audio_service",
    "duracion_wav": "audio_service",
    "DetectorDeNotas": "detector_service",
    "MicrofonoNoDisponibleError": "detector_service",
    "frecuencia_a_nota": "detector_service",
    "cargar_historial": "historial_service",
    "guardar_historial": "historial_service",
    "agregar_al_historial": "historial_service",
    "detalle_de_entrada": "historial_service",
    "HISTORIAL_PATH_DEFAULT": "historial_service",
    "paso_diatonico": "notacion_service",
    "PASO_B4": "notacion_service",
    "nombre_para_mostrar": "notacion_service",
    "nota_coincide": "notacion_service",
    "ControladorPractica": "practica_service",
    "OpcionesPractica": "practica_service",
    "AjustesPractica": "ajustes_service",
    "cargar_ajustes": "ajustes_service",
    "guardar_ajustes": "ajustes_service",
    "cargar_progreso": "progreso_service",
    "registrar_sesion": "progreso_service",
    "resumen_por_partitura": "progreso_service",
}

__all__ = list(_ORIGEN)


def __getattr__(nombre):
    modulo = _ORIGEN.get(nombre)
    if modulo is None:
        raise AttributeError(f"module {__name__!r} has no attribute {nombre!r}")
    valor = getattr(importlib.import_module(f".{modulo}", __name__), nombre)
    globals()[nombre] = valor
    return valor


def __dir__():
    return sorted(set(globals()) | set(__all__))
