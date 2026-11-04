"""
Script auxiliar del Anexo IV (no forma parte de la aplicación Wynik).

Genera la documentación HTML del código fuente con `pydoc` (biblioteca estándar de Python,
sin dependencias nuevas) a partir de los docstrings de todos los módulos de los paquetes
audio, nucleo, servicios y vistas, y de main.py. Escribe un archivo por módulo y un índice en
docs/anexo_iv/pydoc/.

Uso (desde la raíz del repositorio, con el entorno virtual activado; en Linux sin pantalla,
anteponer «xvfb-run -a», porque importar las vistas crea la ventana de Kivy):
    python docs/anexo_iv/generar_pydoc.py
"""

import html
import importlib
import os
import pkgutil
import pydoc
import shutil
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent
SALIDA = AQUI / "pydoc"
PAQUETES = ("audio", "nucleo", "servicios", "vistas")

os.environ.setdefault("KIVY_NO_ARGS", "1")
sys.path.insert(0, str(RAIZ))


def modulos():
    nombres = ["main"]
    for paquete in PAQUETES:
        modulo = importlib.import_module(paquete)
        nombres.append(paquete)
        for info in pkgutil.walk_packages(modulo.__path__, prefix=f"{paquete}."):
            nombres.append(info.name)
    return nombres


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    os.chdir(SALIDA)
    filas, fallos = [], []
    for nombre in modulos():
        try:
            modulo = importlib.import_module(nombre)
            pydoc.writedoc(modulo)
            resumen = (pydoc.splitdoc(pydoc.getdoc(modulo))[0] or "").strip()
            filas.append(f'<li><a href="{nombre}.html">{nombre}</a> — {html.escape(resumen)}</li>')
        except Exception as error:  # noqa: BLE001 - se informa y se sigue con el resto
            fallos.append(f"{nombre}: {type(error).__name__}: {error}")
    import pydoc_data
    hoja = Path(pydoc_data.__file__).parent / "_pydoc.css"
    shutil.copy(hoja, SALIDA / "_pydoc.css")
    estilo = f"<style>\n{hoja.read_text(encoding='utf-8')}\n</style>\n</head>"
    for pagina in SALIDA.glob("*.html"):  # hoja de estilo incrustada y rutas relativas
        texto = pagina.read_text(encoding="utf-8").replace("</head>", estilo, 1)
        pagina.write_text(texto.replace(f"file:{RAIZ}/", "../../../").replace(f"{RAIZ}/", "")
                          .replace(str(RAIZ), "&lt;raíz del repositorio&gt;"), encoding="utf-8")
    (SALIDA / "index.html").write_text(
        "<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'>"
        "<title>Wynik · documentación del código (pydoc)</title></head><body>"
        "<h1>Wynik · documentación del código generada con pydoc</h1>"
        f"<p>{len(filas)} módulos. Generado con <code>python docs/anexo_iv/generar_pydoc.py</code>.</p>"
        f"<ul>{''.join(filas)}</ul></body></html>", encoding="utf-8")
    print(f"{len(filas)} módulos documentados en {SALIDA}")
    for fallo in fallos:
        print("FALLO", fallo)


if __name__ == "__main__":
    main()
