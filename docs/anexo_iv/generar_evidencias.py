"""
Script auxiliar del Anexo IV (no forma parte de la aplicación Wynik).

Ejecuta los comandos de verificación del anexo y guarda su salida textual en
docs/anexo_iv/evidencias/, además de una imagen de cada salida (capturas/terminal/):

- entorno.txt: sistema, Python y versiones instaladas de las dependencias fijadas.
- arbol.txt: árbol del repositorio a nivel de archivo (archivos versionados con git).
- unittest.txt: python -m unittest discover -s tests -v
- ruff.txt: ruff check . y ruff check . --statistics (configuración de pyproject.toml)
- cobertura.txt: coverage run -m unittest discover -s tests; coverage report -m
- parametros_deteccion.txt: parámetros efectivos del detector, calculados con las clases reales.

Uso (desde la raíz del repositorio, con el entorno virtual activado y ruff/coverage instalados):
    python docs/anexo_iv/generar_evidencias.py
"""

import importlib.metadata as metadatos
import os
import platform
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent
EVIDENCIAS = AQUI / "evidencias"
TERMINAL = AQUI / "capturas" / "terminal"
PAQUETES = ("kivy", "kivymd", "numpy", "sounddevice", "music21", "pycairo", "materialyoucolor",
            "materialshapes", "asynckivy", "pillow", "matplotlib", "ruff", "coverage")
sys.path.insert(0, str(RAIZ))


def ejecutar(comando, **opciones):
    resultado = subprocess.run(comando, cwd=RAIZ, capture_output=True, text=True, **opciones)
    salida = (resultado.stdout + resultado.stderr).rstrip()
    lineas = [linea for linea in salida.splitlines() if not linea.startswith("[")]  # registro de Kivy
    visible = ["python" if parte == sys.executable else parte for parte in comando]
    return f"$ {' '.join(visible)}\n" + "\n".join(lineas) + f"\n[código de salida: {resultado.returncode}]\n"


def arbol() -> str:
    archivos = subprocess.run(["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True).stdout.split()
    archivos = [a for a in archivos if not a.startswith("docs/anexo_iv/")]
    lineas = ["Wynik-app/"]
    previos = []
    for ruta in sorted(archivos, key=lambda r: (r.count("/") == 0, r.lower())):
        partes = ruta.split("/")
        for nivel, parte in enumerate(partes[:-1]):
            if previos[:nivel + 1] != partes[:nivel + 1]:
                lineas.append("    " * (nivel + 1) + parte + "/")
        lineas.append("    " * len(partes) + partes[-1])
        previos = partes[:-1]
    return "\n".join(lineas) + f"\n\n{len(archivos)} archivos versionados (git ls-files, sin docs/anexo_iv/)\n"


def parametros() -> str:
    from audio.analizador import DURACION_SALTO_S, Analizador
    from audio.captura import CAPACIDAD_COLA_BLOQUES, TAM_BLOQUE
    from nucleo.instrumentos import GUITARRA, PIANO
    from nucleo.musica import TOLERANCIA_AFINADA_CENTS, TOLERANCIA_IDENTIDAD_CENTS
    from nucleo.sesion import ConfiguracionSesion
    lineas = [f"Bloque de captura: {TAM_BLOQUE} muestras · cola de {CAPACIDAD_COLA_BLOQUES} bloques",
              f"Salto de análisis: {DURACION_SALTO_S * 1000:.0f} ms",
              f"Tolerancias de altura: afinada <= {TOLERANCIA_AFINADA_CENTS:g} cents; misma nota <= {TOLERANCIA_IDENTIDAD_CENTS:g} cents",
              f"Sesión por defecto: {ConfiguracionSesion()}"]
    for perfil in (PIANO, GUITARRA):
        p = perfil.deteccion
        for fs in (44100.0, 48000.0):
            a = Analizador(fs, perfil)
            f_min, f_max = perfil.rango_busqueda_hz(440.0, fs)
            lineas.append(f"{perfil.nombre} a {fs:.0f} Hz: búsqueda {f_min:.2f}–{f_max:.1f} Hz · trama YIN "
                          f"{a.estimador.longitud_trama} muestras ({a.estimador.duracion_trama_s * 1000:.1f} ms) · "
                          f"salto {a.salto} muestras · latencia mínima {a.latencia_minima_s * 1000:.1f} ms")
        lineas.append(f"  {perfil.nombre}: umbral_yin={p.umbral_yin} aperiodicidad_max={p.aperiodicidad_max} "
                      f"tramas_confirmacion={p.tramas_confirmacion} confirmacion_max_s={p.confirmacion_max_s} "
                      f"subida_ataque_db={p.subida_ataque_db} refinar_fundamental={p.refinar_fundamental} "
                      f"nivel_silencio_dbfs={p.nivel_silencio_dbfs} nivel_minimo_dbfs={p.nivel_minimo_dbfs}")
    return "\n".join(lineas) + "\n"


def imagen_terminal(texto: str, destino: Path, titulo: str, max_lineas: int = 60) -> None:
    from PIL import Image, ImageDraw, ImageFont
    texto = texto.expandtabs(4)
    lineas = texto.splitlines()
    if len(lineas) > max_lineas:
        lineas = lineas[: max_lineas - 1] + [f"… ({len(texto.splitlines()) - max_lineas + 1} líneas más en el archivo de evidencia)"]
    try:
        import kivy
        fuente = ImageFont.truetype(str(Path(kivy.kivy_data_dir) / "fonts" / "DejaVuSansMono.ttf"), 22)
    except Exception:  # noqa: BLE001
        fuente = ImageFont.load_default()
    alto_linea, margen = 30, 28
    ancho = max(1200, int(max(fuente.getlength(linea) for linea in lineas + [titulo])) + 2 * margen)
    alto = 56 + margen + alto_linea * len(lineas) + margen
    imagen = Image.new("RGB", (ancho, alto), (30, 32, 36))
    dibujo = ImageDraw.Draw(imagen)
    dibujo.rectangle([0, 0, ancho, 44], fill=(52, 55, 61))
    for i, color in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
        dibujo.ellipse([18 + i * 30, 13, 36 + i * 30, 31], fill=color)
    dibujo.text((ancho // 2, 22), titulo, fill=(200, 200, 200), font=fuente, anchor="mm")
    for i, linea in enumerate(lineas):
        color = (152, 195, 121) if linea.startswith("$") else (220, 220, 220)
        if " ok" in linea or linea.strip() == "OK":
            color = (152, 195, 121)
        dibujo.text((margen, 56 + margen // 2 + i * alto_linea), linea, fill=color, font=fuente)
    destino.parent.mkdir(parents=True, exist_ok=True)
    imagen.save(destino, optimize=True)


def main() -> None:
    EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    versiones = "\n".join(f"{p}=={metadatos.version(p)}" for p in PAQUETES if _instalado(p))
    entorno = (f"Sistema: {platform.platform()} ({platform.machine()})\nPython: {sys.version.split()[0]} "
               f"(entorno virtual)\n{versiones}\n")
    salidas = {
        "entorno.txt": entorno,
        "arbol.txt": arbol(),
        "unittest.txt": ejecutar([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]),
        "ruff.txt": ejecutar(["ruff", "--version"]) + ejecutar(["ruff", "check", ".", "--statistics"])
        + ejecutar(["ruff", "check", ".", "--output-format", "concise"]),
        "cobertura.txt": ejecutar(["coverage", "run", "--source=audio,nucleo,servicios,vistas", "-m",
                                   "unittest", "discover", "-s", "tests"])
        + ejecutar(["coverage", "report", "--skip-empty"]),
        "parametros_deteccion.txt": parametros(),
    }
    for nombre, texto in salidas.items():
        (EVIDENCIAS / nombre).write_text(texto, encoding="utf-8")
        print(f"Escrita {EVIDENCIAS / nombre}")
    imagen_terminal(salidas["unittest.txt"], TERMINAL / "pruebas_unittest.png", "Pruebas automatizadas (unittest)")
    imagen_terminal(ejecutar(["ruff", "--version"]) + ejecutar(["ruff", "check", ".", "--statistics"]),
                    TERMINAL / "ruff_estadisticas.png", "Análisis estático (Ruff)")
    if Path(RAIZ / ".coverage").exists():
        os.remove(RAIZ / ".coverage")


def _instalado(paquete: str) -> bool:
    try:
        metadatos.version(paquete)
        return True
    except metadatos.PackageNotFoundError:
        return False


if __name__ == "__main__":
    main()
