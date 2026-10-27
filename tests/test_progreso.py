import sys
import tempfile
import unittest
from pathlib import Path

# Permitir ejecución directa del archivo de test
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nucleo.sesion import SesionProgreso
from servicios.almacenamiento import configurar_directorio
from servicios.progreso_service import (
    cargar_progreso,
    cargar_sesiones,
    registrar_sesion,
    registrar_sesion_practica,
)


class TestProgreso(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        configurar_directorio(self.temp_dir.name)

    def tearDown(self):
        configurar_directorio(None)
        self.temp_dir.cleanup()

    def test_sesion_progreso_to_dict_y_from_dict(self):
        sesion = SesionProgreso(
            partitura="ode_to_joy",
            instrumento="piano",
            modo="seguir_tempo",
            factor_tempo=1.0,
            total=50,
            aciertos=48,
            precision=0.96,
        )
        # Verificación del método to_dict requerido por la evaluación
        d = sesion.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["partitura"], "ode_to_joy")
        self.assertEqual(d["total"], 50)
        self.assertEqual(d["aciertos"], 48)
        self.assertEqual(d["precision"], 0.96)
        self.assertIn("fecha", d)

        # Propiedades de compatibilidad
        self.assertEqual(sesion.nombre_partitura, "ode_to_joy")
        self.assertEqual(sesion.notas_correctas, 48)
        self.assertEqual(sesion.total_notas, 50)
        self.assertEqual(sesion.precision_media, 0.96)
        self.assertEqual(sesion.timestamp, sesion.fecha)

        # Deserialización from_dict
        reconstruida = SesionProgreso.from_dict(d)
        self.assertEqual(reconstruida.partitura, sesion.partitura)
        self.assertEqual(reconstruida.aciertos, sesion.aciertos)
        self.assertEqual(reconstruida.precision, sesion.precision)

    def test_persistencia_sesion_con_to_dict(self):
        resumen = {"evaluables": 10, "aciertos": 9, "precision": 0.9}
        guardado = registrar_sesion("test_song", "guitarra", "esperar_nota", 1.2, resumen)
        self.assertEqual(guardado["partitura"], "test_song")
        self.assertEqual(guardado["aciertos"], 9)

        # Comprobar recuperación en JSON
        progreso = cargar_progreso()
        self.assertEqual(len(progreso), 1)
        self.assertEqual(progreso[0]["partitura"], "test_song")

        # Comprobar recuperación como objetos POO
        sesiones_poo = cargar_sesiones()
        self.assertEqual(len(sesiones_poo), 1)
        self.assertIsInstance(sesiones_poo[0], SesionProgreso)
        self.assertEqual(sesiones_poo[0].partitura, "test_song")

    def test_registrar_sesion_practica(self):
        sesion_obj = registrar_sesion_practica("bach_minuet", 25, 25)
        self.assertIsInstance(sesion_obj, SesionProgreso)
        self.assertEqual(sesion_obj.precision, 1.0)
        self.assertEqual(len(cargar_progreso()), 1)


if __name__ == "__main__":
    unittest.main()
