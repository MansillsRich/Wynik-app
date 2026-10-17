"""
Pantalla de ajustes generales: micrófono, ruido de fondo, afinación de referencia,
afinación de la guitarra, tolerancia temporal, cuenta previa y volumen de la guía.
"""

from kivy.uix.screenmanager import Screen
from kivymd.app import MDApp


class AjustesScreen(Screen):
    def on_enter(self):
        MDApp.get_running_app().refrescar_dispositivo()
