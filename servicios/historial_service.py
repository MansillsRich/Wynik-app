"""
Servicio para la persistencia del historial de partituras recientes en JSON.

El archivo está en el directorio de datos (`servicios.almacenamiento`): por defecto la carpeta
del proyecto, como en la versión inicial; `WYNIK_DATOS` lo cambia (pruebas) y en Android es
el directorio de datos de la aplicación.
"""

import json
import os
from typing import Dict, List, Optional

from .almacenamiento import DIRECTORIO_RAIZ, ruta_dato

NOMBRE_HISTORIAL = "historial_partituras.json"
# Ruta por defecto sin WYNIK_DATOS (se conserva el nombre de la versión inicial).
HISTORIAL_PATH_DEFAULT = os.path.join(DIRECTORIO_RAIZ, NOMBRE_HISTORIAL)


def _ruta(ruta_archivo: Optional[str]) -> str:
    return ruta_archivo or ruta_dato(NOMBRE_HISTORIAL)


def cargar_historial(ruta_archivo: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Carga la lista de partituras guardadas en el historial.
    Retorna una lista de diccionarios con formato:
    [{"nombre": "the-entertainer", "ruta": "/ruta/al/archivo.mxl"}, ...]
    """
    ruta = _ruta(ruta_archivo)
    if os.path.exists(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as archivo:
                datos = json.load(archivo)
                if isinstance(datos, list):
                    return [d for d in datos if isinstance(d, dict) and "ruta" in d and "nombre" in d]
        except (json.JSONDecodeError, OSError) as error:
            print(f"[HistorialService] Error al leer historial: {error}")
            return []
    return []


def guardar_historial(historial: List[Dict[str, str]], ruta_archivo: Optional[str] = None) -> None:
    """
    Guarda la lista de partituras en el archivo de historial en formato JSON con indentación.
    """
    try:
        with open(_ruta(ruta_archivo), "w", encoding="utf-8") as archivo:
            json.dump(historial, archivo, ensure_ascii=False, indent=2)
    except OSError as error:
        print(f"[HistorialService] Error al guardar historial: {error}")


def agregar_al_historial(
    historial: List[Dict[str, str]],
    nombre: str,
    ruta: str,
    ruta_archivo: Optional[str] = None
) -> List[Dict[str, str]]:
    """
    Agrega una partitura al historial si no se encuentra ya presente y guarda los cambios.
    """
    ya_estaba = any(entrada.get("ruta") == ruta for entrada in historial)
    if not ya_estaba:
        nuevo_historial = list(historial)
        nuevo_historial.append({"nombre": nombre, "ruta": ruta})
        guardar_historial(nuevo_historial, ruta_archivo)
        return nuevo_historial
    return historial


def detalle_de_entrada(ruta: str, progreso: Optional[Dict] = None) -> str:
    """Texto secundario de una partitura en «Mis partituras»: la carpeta que la contiene (la
    ruta completa no cabe en una pantalla de teléfono) y, si ya se practicó, las sesiones y la
    mejor precisión (`progreso`, una entrada de `progreso_service.resumen_por_partitura`)."""
    if not ruta or not os.path.exists(ruta):
        return "Archivo no encontrado"
    carpeta = os.path.basename(os.path.dirname(os.path.abspath(ruta))) or os.path.dirname(ruta)
    texto = f"Carpeta «{carpeta}»"
    if progreso and progreso.get("sesiones"):
        sesiones = int(progreso["sesiones"])
        texto += (f" · {sesiones} {'sesión' if sesiones == 1 else 'sesiones'}"
                  f" · mejor {round(100 * float(progreso.get('mejor', 0.0)))} %")
    return texto
