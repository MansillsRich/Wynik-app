import os
import sys
import tempfile
import unittest
from pathlib import Path

# Permitir ejecución directa del archivo de test
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from servicios.almacenamiento import (
    configurar_directorio,
    directorio_datos,
    escribir_json,
    leer_json,
    ruta_cache,
    ruta_dato,
)


class TestAlmacenamiento(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        configurar_directorio(self.temp_dir.name)

    def tearDown(self):
        configurar_directorio(None)
        self.temp_dir.cleanup()

    def test_directorio_configurado(self):
        self.assertEqual(directorio_datos(), self.temp_dir.name)

    def test_ruta_cache_crea_directorio(self):
        ruta = ruta_cache("audio_prueba.wav")
        self.assertTrue(os.path.isdir(os.path.dirname(ruta)))
        self.assertTrue(ruta.endswith(os.path.join(".cache", "audio_prueba.wav")))

    def test_lectura_escritura_json(self):
        datos = {"clave": "valor", "numero": 42}
        exito = escribir_json("prueba.json", datos)
        self.assertTrue(exito)

        leido = leer_json("prueba.json", por_defecto={})
        self.assertEqual(leido, datos)

    def test_leer_archivo_inexistente(self):
        leido = leer_json("no_existe.json", por_defecto={"defecto": True})
        self.assertEqual(leido, {"defecto": True})


if __name__ == "__main__":
    unittest.main()
