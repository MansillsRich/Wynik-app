"""
Fuente de la interfaz con los símbolos musicales.

Roboto (la fuente por defecto de Kivy y KivyMD) no tiene ♭, ♯, ♮, ✓ ni ✗: se dibujaban como
un glifo vacío. DejaVu Sans, que Kivy incluye en `kivy/data/fonts` (también en Android),
sí los tiene. `registrar_fuentes()` la registra como «WynikTexto» y, si se le pasa el tema de
KivyMD, la asigna a todos los estilos de texto (no a los iconos).

Para los rótulos fijos (botones, títulos de sección), que no llevan símbolos musicales, se
registran además Roboto Medium («WynikRotulo») y Roboto Bold («WynikTitulo»), que vienen con
KivyMD. Si no se encuentran, ambos nombres apuntan a DejaVu Sans.
"""

import os

from .tema import FUENTE_ROTULO, FUENTE_TEXTO, FUENTE_TITULO  # noqa: F401
_registrada = False


def ruta_dejavu() -> str:
    import kivy
    return os.path.join(kivy.kivy_data_dir, "fonts", "DejaVuSans.ttf")


def ruta_roboto(peso: str) -> str:
    """Ruta de Roboto-<peso>.ttf de KivyMD (o "" si no está)."""
    try:
        import kivymd
        ruta = os.path.join(os.path.dirname(kivymd.__file__), "fonts", f"Roboto-{peso}.ttf")
    except Exception:  # noqa: BLE001 - sin KivyMD se usa DejaVu
        return ""
    return ruta if os.path.exists(ruta) else ""


def registrar_fuentes(tema=None) -> str:
    global _registrada
    if not _registrada:
        from kivy.core.text import LabelBase
        ruta = ruta_dejavu()
        LabelBase.register(name=FUENTE_TEXTO, fn_regular=ruta, fn_bold=ruta)
        medio, negrita = ruta_roboto("Medium") or ruta, ruta_roboto("Bold") or ruta
        LabelBase.register(name=FUENTE_ROTULO, fn_regular=medio, fn_bold=negrita)
        LabelBase.register(name=FUENTE_TITULO, fn_regular=negrita, fn_bold=negrita)
        _registrada = True
    if tema is not None:
        for estilo, roles in tema.font_styles.items():
            if estilo == "Icon" or not isinstance(roles, dict):
                continue
            for valores in roles.values():
                if isinstance(valores, dict) and "font-name" in valores:
                    valores["font-name"] = FUENTE_TEXTO
    return FUENTE_TEXTO
