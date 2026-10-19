"""
Pantalla de práctica con vista simplificada de partitura: alternativa ligera
al pentagrama completo con visualización directa de notas, progresión y guía.
"""

from kivy.uix.screenmanager import Screen
from kivymd.app import MDApp


class PartituraSimpleScreen(Screen):
    """Pantalla interactiva de práctica con vista simplificada."""

    def on_leave(self):
        """Al salir se detienen la escucha y la guía de audio."""
        app = MDApp.get_running_app()
        app.detener_escucha()
        app.detener_audio()