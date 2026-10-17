"""
Biblioteca: partituras importadas (historial).
"""

from kivy.uix.screenmanager import Screen
from kivymd.app import MDApp


class ElegirPartituraScreen(Screen):
    """Lista de partituras importadas; al elegir una se prepara la práctica."""

    def on_enter(self):
        MDApp.get_running_app()._refrescar_lista_partituras()
