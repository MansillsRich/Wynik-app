"""
Pantalla de práctica: nota esperada, pentagrama, guía visual del instrumento, resultado de
la escucha y controles. La escucha empieza al pulsar «Empezar» (no al entrar).
"""

from kivy.uix.screenmanager import Screen
from kivymd.app import MDApp


class InterpreteScreen(Screen):
    """Pantalla interactiva de práctica."""

    def on_leave(self):
        """Al salir se detienen la escucha y la guía de audio."""
        app = MDApp.get_running_app()
        app.detener_escucha()
        app.detener_audio()
