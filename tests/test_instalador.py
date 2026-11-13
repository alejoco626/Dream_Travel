import os
import re
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from calculadora.config import ID_APP_WINDOWS  # noqa: E402


class PruebaInstalador(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(RAIZ, "instalador.iss"), encoding="utf-8") as archivo:
            self.iss = archivo.read()

    def test_accesos_directos_con_icono_y_la_misma_identidad(self):
        accesos = [l for l in self.iss.splitlines() if l.startswith("Name: \"{auto")]
        self.assertEqual(len(accesos), 2)
        for acceso in accesos:
            self.assertIn('IconFilename: "{app}\\icono_calculadora.ico"', acceso)
            self.assertIn(f'AppUserModelID: "{ID_APP_WINDOWS}"', acceso)

    def test_el_icono_se_instala_y_no_quedan_iconos_viejos(self):
        self.assertIn('Source: "icono_calculadora.ico"', self.iss)
        self.assertIsNone(re.search(r"Logo_Ovalado", self.iss))
        self.assertTrue(os.path.exists(os.path.join(RAIZ, "icono_calculadora.ico")))


if __name__ == "__main__":
    unittest.main()
