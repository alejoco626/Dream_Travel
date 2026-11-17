import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculadora import novedades  # noqa: E402


class PruebaNovedades(unittest.TestCase):
    def test_notas_de_la_1_0_12(self):
        notas = novedades.NOVEDADES["1.0.12"]
        self.assertEqual(notas["cambios"], [])
        self.assertEqual(notas["correcciones"], ["Se cambiaron los parámetros de edad de niños e infantes"])

    def test_notas_de_la_1_0_14_solo_nuevo(self):
        notas = novedades.notas_a_mostrar("1.0.14", True, None)
        self.assertEqual(notas, {"nuevo": ["Se agregó monto para reservar"]})

    def test_cuando_se_muestran(self):
        self.assertIsNotNone(novedades.notas_a_mostrar("1.0.12", True, None))
        self.assertIsNotNone(novedades.notas_a_mostrar("1.0.12", False, "1.0.11"))
        self.assertIsNone(novedades.notas_a_mostrar("1.0.12", False, "1.0.12"), "ya se vio")
        self.assertIsNone(novedades.notas_a_mostrar("1.0.12", False, None), "instalación nueva")
        self.assertIsNone(novedades.notas_a_mostrar("9.9.9", True, None), "versión sin notas")

    def test_guarda_y_lee_la_version(self):
        ruta = os.path.join(tempfile.mkdtemp(), "DreamTravel", "ultima_version.txt")
        with mock.patch.object(novedades, "ARCHIVO_VERSION_VISTA", ruta):
            self.assertIsNone(novedades.leer_version_vista())
            novedades.guardar_version_vista("1.0.12")
            self.assertEqual(novedades.leer_version_vista(), "1.0.12")


if __name__ == "__main__":
    unittest.main()
