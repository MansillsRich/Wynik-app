"""
Pantalla de progreso: sesiones de práctica terminadas, de la más reciente a la más antigua.
"""

from kivy.uix.screenmanager import Screen
from kivymd.app import MDApp


class ProgresoScreen(Screen):
    def on_enter(self):
        MDApp.get_running_app().refrescar_progreso()
