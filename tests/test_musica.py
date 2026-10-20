import unittest

from nucleo.musica import Altura, ErrorAltura, comparar_alturas


class TestMusica(unittest.TestCase):
    def test_altura_desde_nombre(self):
        do_central = Altura.desde_nombre("C4")
        self.assertEqual(do_central.midi, 60)
        self.assertEqual(do_central.paso, "C")
        self.assertEqual(do_central.octava, 4)
        self.assertEqual(do_central.nombre_solfeo, "Do4")

    def test_enarmonicos(self):
        la_sostenido = Altura.desde_nombre("A#4")
        si_bemol = Altura.desde_nombre("Bb4")
        self.assertEqual(la_sostenido.midi, si_bemol.midi)
        self.assertEqual(la_sostenido.midi, 70)

    def test_comparar_alturas(self):
        resultado = comparar_alturas("C4", "C4")
        self.assertTrue(resultado.es_acierto)
        self.assertEqual(resultado.diferencia_semitonos, 0)

        # Enarmónico debe considerarse acierto en altura
        resultado_enarmonico = comparar_alturas("F#4", "Gb4")
        self.assertTrue(resultado_enarmonico.es_acierto)

        # Distinta nota
        resultado_error = comparar_alturas("C4", "D4")
        self.assertFalse(resultado_error.es_acierto)
        self.assertEqual(resultado_error.diferencia_semitonos, -2)

    def test_nombre_invalido(self):
        with self.assertRaises(ErrorAltura):
            Altura.desde_nombre("NotaInvalida")


if __name__ == "__main__":
    unittest.main()
