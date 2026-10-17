"""
Ubicación y escritura segura de los datos locales (ajustes y progreso).

- Por defecto, la carpeta del proyecto (donde ya se guarda `historial_partituras.json`).
- `WYNIK_DATOS=<carpeta>` la cambia (pruebas, varias instalaciones).
- En Android la aplicación llama a `configurar_directorio(app.user_data_dir)`.

La escritura es atómica (archivo temporal + `os.replace`): un corte a mitad no deja un JSON
a medias. Un archivo ilegible se trata como vacío y se informa por consola.
"""

import json
import os
import tempfile
from typing import Any, Optional

DIRECTORIO_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_directorio: Optional[str] = None


def configurar_directorio(ruta: Optional[str]) -> None:
    global _directorio
    if ruta:
        os.makedirs(ruta, exist_ok=True)
    _directorio = ruta


def directorio_datos() -> str:
    return _directorio or os.environ.get("WYNIK_DATOS") or DIRECTORIO_RAIZ


def ruta_dato(nombre: str) -> str:
    return os.path.join(directorio_datos(), nombre)


def leer_json(nombre: str, por_defecto: Any) -> Any:
    ruta = ruta_dato(nombre)
    if not os.path.exists(ruta):
        return por_defecto
    try:
        with open(ruta, encoding="utf-8") as archivo:
            return json.load(archivo)
    except (OSError, json.JSONDecodeError) as error:
        print(f"[Wynik] No se pudo leer {nombre}: {error}")
        return por_defecto


def escribir_json(nombre: str, datos: Any) -> bool:
    ruta = ruta_dato(nombre)
    directorio = os.path.dirname(ruta)
    try:
        os.makedirs(directorio, exist_ok=True)
        descriptor, temporal = tempfile.mkstemp(prefix=".wynik_", suffix=".json", dir=directorio)
        with os.fdopen(descriptor, "w", encoding="utf-8") as archivo:
            json.dump(datos, archivo, ensure_ascii=False, indent=2)
        os.replace(temporal, ruta)
        return True
    except OSError as error:
        print(f"[Wynik] No se pudo guardar {nombre}: {error}")
        return False
