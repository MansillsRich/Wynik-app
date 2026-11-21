import os
import sys
import tempfile
import unittest
from pathlib import Path

# Permitir ejecución directa del archivo de test
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from servicios.almacenamiento import configurar_directorio
from servicios.historial_service import (
    agregar_al_historial,
    cargar_historial,
    eliminar_del_historial,
    guardar_historial,
)


class TestHistorialService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        configurar_directorio(self.temp_dir.name)
        self.archivo_historial = os.path.join(self.temp_dir.name, "historial_partituras.json")

    def tearDown(self):
        configurar_directorio(None)
        self.temp_dir.cleanup()

    def test_agregar_y_cargar_historial(self):
        # Crear archivo simulado
        ruta_dummy = os.path.join(self.temp_dir.name, "dummy.mxl")
        with open(ruta_dummy, "w", encoding="utf-8") as f:
            f.write("partitura")

        historial = []
        historial = agregar_al_historial(historial, "dummy", ruta_dummy, self.archivo_historial)
        self.assertEqual(len(historial), 1)
        self.assertEqual(historial[0]["nombre"], "dummy")

        # Cargar de nuevo
        leido = cargar_historial(self.archivo_historial)
        self.assertEqual(len(leido), 1)
        self.assertEqual(leido[0]["ruta"], ruta_dummy)

    def test_eliminar_del_historial_con_borrado_fisico(self):
        # Crear archivo temporal
        ruta_partitura = os.path.join(self.temp_dir.name, "cancion.mxl")
        with open(ruta_partitura, "w", encoding="utf-8") as f:
            f.write("musica")

        historial = [{"nombre": "cancion", "ruta": ruta_partitura}]
        guardar_historial(historial, self.archivo_historial)
        self.assertTrue(os.path.isfile(ruta_partitura))

        # Eliminar
        nuevo_historial = eliminar_del_historial(
            historial,
            ruta_partitura,
            ruta_archivo=self.archivo_historial,
            borrar_archivo_fisico=True,
        )

        self.assertEqual(len(nuevo_historial), 0)
        # El archivo físico debe haberse borrado
        self.assertFalse(os.path.isfile(ruta_partitura))

        # Verificar persistencia en el JSON
        leido = cargar_historial(self.archivo_historial)
        # Como no hay elementos válidos en el archivo, fallback a ejemplos o lista vacía
        rutas_leidas = [e["ruta"] for e in leido]
        self.assertNotIn(ruta_partitura, rutas_leidas)

    def test_eliminar_ruta_inexistente_no_falla(self):
        historial = [{"nombre": "a", "ruta": "/ruta/no/existe.mxl"}]
        nuevo = eliminar_del_historial(historial, "/otra/ruta.mxl", self.archivo_historial)
        self.assertEqual(len(nuevo), 1)

    def test_historial_utf8_caracteres_especiales(self):
        # Verificar soporte correcto de Ñ, ñ y acentos
        ruta_cancion = os.path.join(self.temp_dir.name, "mira-niñita.musicxml")
        with open(ruta_cancion, "w", encoding="utf-8") as f:
            f.write("<xml>mira-niñita</xml>")

        historial = []
        nombre_original = "mira-niñita con Ñ"
        historial = agregar_al_historial(historial, nombre_original, ruta_cancion, self.archivo_historial)

        leido = cargar_historial(self.archivo_historial)
        self.assertEqual(len(leido), 1)
        self.assertEqual(leido[0]["nombre"], nombre_original)
        self.assertEqual(leido[0]["ruta"], ruta_cancion)


if __name__ == "__main__":
    unittest.main()
