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
)
from .widgets import PartituraWidget, GuiaInstrumentoWidget
from .dialogs import abrir_selector_de_archivo
from .app import WynikApp, KV_PATH

__all__ = [
    "MenuScreen",
    "ElegirPartituraScreen",
    "AjustesInicioScreen",
    "InterpreteScreen",
    "AjustesScreen",
    "ProgresoScreen",
    "PartituraWidget",
    "GuiaInstrumentoWidget",
    "abrir_selector_de_archivo",
    "WynikApp",
    "KV_PATH",
]
