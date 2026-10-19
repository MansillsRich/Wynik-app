"""
Módulo de vistas y componentes de interfaz de usuario de Wynik.
Todas las pantallas y componentes gráficos residen en este paquete.
"""

from .screens import (
    MenuScreen,
    ElegirPartituraScreen,
    AjustesInicioScreen,
    InterpreteScreen,
    AjustesScreen,
    ProgresoScreen,
    PartituraSimpleScreen,
)
from .widgets import PartituraWidget, GuiaInstrumentoWidget, PartituraSimpleWidget
from .dialogs import abrir_selector_de_archivo
from .app import WynikApp, KV_PATH

__all__ = [
    "MenuScreen",
    "ElegirPartituraScreen",
    "AjustesInicioScreen",
    "InterpreteScreen",
    "AjustesScreen",
    "ProgresoScreen",
    "PartituraSimpleScreen",
    "PartituraWidget",
    "GuiaInstrumentoWidget",
    "PartituraSimpleWidget",
    "abrir_selector_de_archivo",
    "WynikApp",
    "KV_PATH",
]