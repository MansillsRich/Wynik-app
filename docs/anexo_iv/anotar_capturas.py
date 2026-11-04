"""
Script auxiliar del Anexo IV (no forma parte de la aplicación Wynik).

Lee cada captura de `capturas/originales/` y sus cajas de `capturas/cajas/<nombre>.json`
(generadas por `capturar_pantallas.py` a partir de la posición real de cada widget) y dibuja
con Pillow un recuadro y un marcador numerado por elemento. El resultado se guarda en
`capturas/anotadas/` con el mismo nombre; las originales no se modifican.

Uso (desde la raíz del repositorio):
    python docs/anexo_iv/anotar_capturas.py
"""

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

AQUI = Path(__file__).resolve().parent
ORIGINALES = AQUI / "capturas" / "originales"
CAJAS = AQUI / "capturas" / "cajas"
ANOTADAS = AQUI / "capturas" / "anotadas"
COLOR = (214, 40, 120)          # magenta: contrasta con el verde, el rojo y el ocre de la app
RADIO = 25
GROSOR = 5


def _fuente(tamano: int):
    candidatas = []
    try:
        import kivy
        candidatas.append(Path(kivy.kivy_data_dir) / "fonts" / "DejaVuSans-Bold.ttf")
        candidatas.append(Path(kivy.kivy_data_dir) / "fonts" / "DejaVuSans.ttf")
    except ImportError:
        pass
    candidatas += [Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
                   Path("/Library/Fonts/Arial Bold.ttf")]
    for ruta in candidatas:
        if ruta.exists():
            return ImageFont.truetype(str(ruta), tamano)
    return ImageFont.load_default()


def _posicion_marcador(caja, ocupados, ancho, alto):
    x, y, w, h = caja
    # El marcador se centra en la esquina superior izquierda del recuadro (tapa poco contenido).
    cx = min(max(x + 4, RADIO + 2), ancho - RADIO - 2)
    cy = min(max(y + 4, RADIO + 2), alto - RADIO - 2)
    for _ in range(12):
        if all(math.hypot(cx - ox, cy - oy) > 2 * RADIO + 6 for ox, oy in ocupados):
            break
        cx = min(cx + 2 * RADIO + 8, ancho - RADIO - 2)
        if cx >= ancho - RADIO - 2:
            cx, cy = RADIO + 2, min(cy + 2 * RADIO + 8, alto - RADIO - 2)
    ocupados.append((cx, cy))
    return cx, cy


def anotar(ruta_json: Path) -> Path:
    datos = json.loads(ruta_json.read_text(encoding="utf-8"))
    imagen = Image.open(ORIGINALES / datos["imagen"]).convert("RGB")
    dibujo = ImageDraw.Draw(imagen)
    fuente = _fuente(28)
    ocupados = []
    ancho, alto = imagen.size
    for elemento in datos["cajas"]:
        x, y, w, h = elemento["caja"]
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(ancho - 1, x + w), min(alto - 1, y + h)
        if x1 <= x0 or y1 <= y0:
            continue
        dibujo.rounded_rectangle([x0, y0, x1, y1], radius=12, outline=COLOR, width=GROSOR)
    for elemento in datos["cajas"]:
        cx, cy = _posicion_marcador(elemento["caja"], ocupados, ancho, alto)
        dibujo.ellipse([cx - RADIO, cy - RADIO, cx + RADIO, cy + RADIO], fill=COLOR,
                       outline=(255, 255, 255), width=3)
        dibujo.text((cx, cy), str(elemento["n"]), fill=(255, 255, 255), font=fuente, anchor="mm")
    ANOTADAS.mkdir(parents=True, exist_ok=True)
    destino = ANOTADAS / datos["imagen"]
    imagen.save(destino, optimize=True)
    return destino


def main() -> None:
    for ruta in sorted(CAJAS.glob("*.json")):
        destino = anotar(ruta)
        print(f"Anotada {destino.name}")


if __name__ == "__main__":
    main()
