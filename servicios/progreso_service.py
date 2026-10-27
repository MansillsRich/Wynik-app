"""
Historial de sesiones de práctica (`progreso_sesiones.json` en el directorio de datos).

Cada sesión terminada guarda su resumen: fecha, partitura, instrumento, modo, tempo,
aciertos por estado y precisión. Se conservan las 500 más recientes.
"""

import datetime
from typing import Dict, List, Optional

from nucleo.sesion import SesionProgreso

from .almacenamiento import escribir_json, leer_json

ARCHIVO_PROGRESO = "progreso_sesiones.json"
MAXIMO_SESIONES = 500


def cargar_progreso() -> List[Dict]:
    """Carga la lista de diccionarios con el historial de progreso."""
    datos = leer_json(ARCHIVO_PROGRESO, [])
    return [d for d in datos if isinstance(d, dict)] if isinstance(datos, list) else []


def cargar_sesiones() -> List[SesionProgreso]:
    """Carga el historial y deserializa cada elemento a instancias formales SesionProgreso (POO)."""
    return [SesionProgreso.from_dict(d) for d in cargar_progreso()]


def registrar_sesion(partitura: str, instrumento: str, modo: str, factor_tempo: float,
                     resumen: Dict) -> Dict:
    """Registra una sesión de práctica instanciando la clase POO SesionProgreso y serializando con to_dict()."""
    total = resumen.get("evaluables", resumen.get("total", 0))
    aciertos = resumen.get("aciertos", 0)
    precision = float(resumen.get("precision", 0.0))

    sesion = SesionProgreso(
        partitura=partitura,
        instrumento=instrumento,
        modo=modo,
        factor_tempo=float(factor_tempo),
        total=int(total),
        aciertos=int(aciertos),
        precision=precision,
        estados=resumen.get("estados", {}),
        cents_medios=resumen.get("cents_medios"),
        desfase_medio_s=resumen.get("desfase_medio_s"),
    )

    sesiones = cargar_progreso()
    sesiones.append(sesion.to_dict())
    escribir_json(ARCHIVO_PROGRESO, sesiones[-MAXIMO_SESIONES:])
    return sesion.to_dict()


def registrar_sesion_practica(nombre_partitura: str, aciertos: int, total: int,
                              instrumento: str = "piano", modo: str = "seguir_tempo") -> SesionProgreso:
    """Función de alto nivel para registrar una práctica retornando directamente el objeto POO SesionProgreso."""
    precision = aciertos / total if total > 0 else 0.0
    sesion = SesionProgreso(
        partitura=nombre_partitura,
        instrumento=instrumento,
        modo=modo,
        total=total,
        aciertos=aciertos,
        precision=precision,
    )
    sesiones = cargar_progreso()
    sesiones.append(sesion.to_dict())
    escribir_json(ARCHIVO_PROGRESO, sesiones[-MAXIMO_SESIONES:])
    return sesion


def resumen_por_partitura(sesiones: List[Dict]) -> List[Dict]:
    """Sesiones agrupadas por partitura: número de sesiones, mejor y última precisión."""
    grupos: Dict[str, Dict] = {}
    for sesion in sesiones:
        nombre = sesion.get("partitura", "?")
        grupo = grupos.setdefault(nombre, {"partitura": nombre, "sesiones": 0, "mejor": 0.0,
                                           "ultima": 0.0, "fecha": ""})
        grupo["sesiones"] += 1
        grupo["mejor"] = max(grupo["mejor"], float(sesion.get("precision", 0.0)))
        grupo["ultima"] = float(sesion.get("precision", 0.0))
        grupo["fecha"] = sesion.get("fecha", "")
    return sorted(grupos.values(), key=lambda g: g["fecha"], reverse=True)
