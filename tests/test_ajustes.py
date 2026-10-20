import unittest

from servicios.ajustes_service import AjustesPractica


class TestAjustes(unittest.TestCase):
    def test_valores_por_defecto(self):
        ajustes = AjustesPractica()
        self.assertEqual(ajustes.instrumento, "piano")
        self.assertEqual(ajustes.la4, 440.0)
        self.assertEqual(ajustes.modo, "seguir_tempo")
        self.assertFalse(ajustes.vista_simple)

    def test_correccion_valores_fuera_de_rango(self):
        ajustes = AjustesPractica(
            instrumento="trompeta_inexistente",
            la4=600.0,
            factor_tempo=3.5,
            tolerancia_ms=999,
        )
        corregidos = ajustes.corregidos()
        self.assertEqual(corregidos.instrumento, "piano")
        self.assertEqual(corregidos.la4, 450.0)  # maximo 450
        self.assertEqual(corregidos.factor_tempo, 1.5)  # maximo 1.5
        self.assertEqual(corregidos.tolerancia_ms, 150)  # valor por defecto si invalido


if __name__ == "__main__":
    unittest.main()
