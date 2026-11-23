"""
Servicio defensivo de analítica local para Wynik (metodología MJV y Funnel).

Persiste eventos en `analytics_events.json` reutilizando `servicios.almacenamiento`
(escritura atómica con archivo temporal + `os.replace`). Nunca propaga excepciones
hacia la interfaz ni almacena información personal, audio o rutas completas.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import shutil
import threading
import uuid
from typing import Any, Dict, List, Optional

from .almacenamiento import escribir_json, leer_json, ruta_dato

ARCHIVO_ANALITICA = "analytics_events.json"
MAXIMO_EVENTOS = 1000
ETAPAS_FUNNEL = ("partitura_cargada", "practica_iniciada", "sesion_finalizada")

logger = logging.getLogger(__name__)
_LOCK = threading.Lock()
_ERROR_LECTURA = object()


def generar_id(prefijo: str = "evt") -> str:
    """Genera un identificador único con prefijo legible."""
    prefijo_limpio = (prefijo or "evt").strip() or "evt"
    return f"{prefijo_limpio}-{uuid.uuid4()}"


def _valor_json_seguro(valor: Any) -> Any:
    """Convierte valores arbitrarios a tipos serializables en JSON sin fallar."""
    if valor is None or isinstance(valor, (bool, int, float, str)):
        return valor
    if isinstance(valor, dict):
        return {str(k): _valor_json_seguro(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple, set)):
        return [_valor_json_seguro(v) for v in valor]
    return str(valor)


def _sanitizar_datos(datos: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Valida y normaliza el diccionario de propiedades del evento."""
    if datos is None:
        return {}
    if not isinstance(datos, dict):
        logger.warning("Datos de analítica con tipo inesperado (%s); se normalizan a {}.", type(datos).__name__)
        return {}
    seguro = _valor_json_seguro(datos)
    try:
        json.dumps(seguro, ensure_ascii=False)
    except (TypeError, ValueError):
        return {}
    return seguro


def _respaldar_archivo_invalido(ruta: str) -> Optional[str]:
    """Crea un respaldo del archivo corrupto para no destruir evidencia silenciosamente."""
    directorio = os.path.dirname(ruta) or "."
    marca = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    nombre_respaldo = f"analytics_events.corrupt.{marca}.json"
    ruta_respaldo = os.path.join(directorio, nombre_respaldo)
    try:
        shutil.copy2(ruta, ruta_respaldo)
        return ruta_respaldo
    except OSError as error:
        logger.error("No se pudo respaldar el archivo de analítica inválido (%s): %s", ruta, error)
        return None


def registrar_evento(
    nombre_evento: str,
    datos: Optional[Dict[str, Any]],
    funnel_id: str,
    practice_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Registra un evento de analítica local de forma defensiva y atómica.

    Devuelve el diccionario del evento persistido, o `None` si los parámetros son
    inválidos o ocurre un error de E/S (sin interrumpir jamás la aplicación).
    """
    try:
        if not isinstance(nombre_evento, str) or not nombre_evento.strip():
            logger.warning("Evento de analítica ignorado: nombre_evento vacío o inválido.")
            return None
        if not isinstance(funnel_id, str) or not funnel_id.strip():
            logger.warning("Evento '%s' ignorado: funnel_id vacío o inválido.", nombre_evento)
            return None

        practice_limpio = (
            practice_id.strip()
            if isinstance(practice_id, str) and practice_id.strip()
            else None
        )
        evento: Dict[str, Any] = {
            "event_id": generar_id("evt"),
            "event_name": nombre_evento.strip(),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(timespec="seconds"),
            "funnel_id": funnel_id.strip(),
            "practice_id": practice_limpio,
            "data": _sanitizar_datos(datos),
        }

        with _LOCK:
            ruta = ruta_dato(ARCHIVO_ANALITICA)
            if not os.path.exists(ruta):
                eventos: List[Dict[str, Any]] = []
            else:
                cargados = leer_json(ARCHIVO_ANALITICA, _ERROR_LECTURA)
                if cargados is _ERROR_LECTURA or not isinstance(cargados, list):
                    respaldo = _respaldar_archivo_invalido(ruta)
                    if respaldo is None:
                        logger.error(
                            "No se sobrescribe %s porque falló el respaldo del archivo corrupto.",
                            ARCHIVO_ANALITICA,
                        )
                        return None
                    logger.error(
                        "Archivo %s inválido o corrupto; respaldo preservado en %s.",
                        ARCHIVO_ANALITICA,
                        respaldo,
                    )
                    eventos = []
                else:
                    eventos = [item for item in cargados if isinstance(item, dict)]
                    descartados = len(cargados) - len(eventos)
                    if descartados > 0:
                        logger.warning(
                            "Se descartaron %d elementos no válidos al leer %s.",
                            descartados,
                            ARCHIVO_ANALITICA,
                        )

            eventos.append(evento)
            eventos = eventos[-MAXIMO_EVENTOS:]

            if not escribir_json(ARCHIVO_ANALITICA, eventos):
                logger.error("No se pudo persistir el evento '%s' en %s.", evento["event_name"], ARCHIVO_ANALITICA)
                return None

        return evento
    except Exception:  # noqa: BLE001 - la analítica nunca debe interrumpir Wynik
        logger.exception("Error inesperado al registrar evento de analítica '%s'.", nombre_evento)
        return None


def cargar_eventos(nombre_archivo: str = ARCHIVO_ANALITICA) -> List[Dict[str, Any]]:
    """Carga los eventos almacenados de forma defensiva y en modo solo lectura."""
    try:
        ruta = ruta_dato(nombre_archivo)
        if not os.path.exists(ruta):
            return []
        cargados = leer_json(nombre_archivo, _ERROR_LECTURA)
        if cargados is _ERROR_LECTURA or not isinstance(cargados, list):
            logger.error("No se pudo leer una lista válida de eventos desde %s.", nombre_archivo)
            return []
        return [item for item in cargados if isinstance(item, dict)]
    except Exception:  # noqa: BLE001
        logger.exception("Error inesperado al cargar eventos desde %s.", nombre_archivo)
        return []


def _porcentaje(numerador: int, denominador: int) -> float:
    if denominador <= 0:
        return 0.0
    return round((numerador / denominador) * 100.0, 2)


def calcular_funnel(eventos: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Calcula métricas del Funnel por `funnel_id` único y orden secuencial estricto."""
    lista_eventos = cargar_eventos() if eventos is None else eventos

    progreso: Dict[str, int] = {}
    repetidos_en_etapa = 0
    huerfanos_o_fuera_de_secuencia = 0
    total_analizados = 0

    for evento in lista_eventos:
        if not isinstance(evento, dict):
            continue
        total_analizados += 1
        nombre = evento.get("event_name")
        fid = evento.get("funnel_id")
        if not isinstance(fid, str) or not fid.strip() or nombre not in ETAPAS_FUNNEL:
            continue
        fid = fid.strip()
        nivel_actual = progreso.get(fid, 0)

        if nombre == "partitura_cargada":
            if nivel_actual >= 1:
                repetidos_en_etapa += 1
            progreso[fid] = max(nivel_actual, 1)
        elif nombre == "practica_iniciada":
            if nivel_actual < 1:
                huerfanos_o_fuera_de_secuencia += 1
                continue
            if nivel_actual >= 2:
                repetidos_en_etapa += 1
            progreso[fid] = max(nivel_actual, 2)
        elif nombre == "sesion_finalizada":
            if nivel_actual < 2:
                huerfanos_o_fuera_de_secuencia += 1
                continue
            if nivel_actual >= 3:
                repetidos_en_etapa += 1
            progreso[fid] = max(nivel_actual, 3)

    etapa_1 = sum(1 for nivel in progreso.values() if nivel >= 1)
    etapa_2 = sum(1 for nivel in progreso.values() if nivel >= 2)
    etapa_3 = sum(1 for nivel in progreso.values() if nivel >= 3)

    abandono_1_2 = max(0, etapa_1 - etapa_2)
    abandono_2_3 = max(0, etapa_2 - etapa_3)
    abandono_total = max(0, etapa_1 - etapa_3)

    return {
        "total_eventos_analizados": total_analizados,
        "recorridos_unicos": len(progreso),
        "etapas": {
            "partitura_cargada": etapa_1,
            "practica_iniciada": etapa_2,
            "sesion_finalizada": etapa_3,
        },
        "conversiones_porcentaje": {
            "etapa_1_a_2": _porcentaje(etapa_2, etapa_1),
            "etapa_2_a_3": _porcentaje(etapa_3, etapa_2),
            "total_1_a_3": _porcentaje(etapa_3, etapa_1),
        },
        "abandono": {
            "etapa_1_a_2": {
                "cantidad": abandono_1_2,
                "porcentaje": _porcentaje(abandono_1_2, etapa_1),
            },
            "etapa_2_a_3": {
                "cantidad": abandono_2_3,
                "porcentaje": _porcentaje(abandono_2_3, etapa_2),
            },
            "total_1_a_3": {
                "cantidad": abandono_total,
                "porcentaje": _porcentaje(abandono_total, etapa_1),
            },
        },
        "recorridos_incompletos": abandono_total,
        "eventos_repetidos_en_etapa": repetidos_en_etapa,
        "eventos_huerfanos_o_fuera_de_secuencia": huerfanos_o_fuera_de_secuencia,
    }


__all__ = [
    "ARCHIVO_ANALITICA",
    "ETAPAS_FUNNEL",
    "MAXIMO_EVENTOS",
    "calcular_funnel",
    "cargar_eventos",
    "generar_id",
    "registrar_evento",
]


if __name__ == "__main__":
    resumen = calcular_funnel()
    etapas = resumen["etapas"]
    conv = resumen["conversiones_porcentaje"]
    abandono = resumen["abandono"]
    print("=== Resumen Funnel MJV – Wynik ===")
    print(f"Eventos analizados: {resumen['total_eventos_analizados']}")
    print(f"Recorridos únicos (funnel_id): {resumen['recorridos_unicos']}")
    print(f"  1. partitura_cargada : {etapas['partitura_cargada']}")
    print(f"  2. practica_iniciada : {etapas['practica_iniciada']}")
    print(f"  3. sesion_finalizada : {etapas['sesion_finalizada']}")
    print(f"Conversión 1 -> 2 : {conv['etapa_1_a_2']:.2f} % (abandono: {abandono['etapa_1_a_2']['cantidad']})")
    print(f"Conversión 2 -> 3 : {conv['etapa_2_a_3']:.2f} % (abandono: {abandono['etapa_2_a_3']['cantidad']})")
    print(f"Conversión total  : {conv['total_1_a_3']:.2f} % (incompletos: {resumen['recorridos_incompletos']})")
    print(f"Eventos repetidos en etapa : {resumen['eventos_repetidos_en_etapa']}")
    print(f"Eventos huérfanos/fuera de secuencia : {resumen['eventos_huerfanos_o_fuera_de_secuencia']}")
