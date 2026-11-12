import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculadora.fechas import (  # noqa: E402
    con_diagonales,
    fecha_de_pago,
    formato_fecha,
    leer_fecha,
    restar_meses,
)


class PruebaFechas(unittest.TestCase):
    def test_diagonales_automaticas(self):
        self.assertEqual(con_diagonales("2"), "2")
        self.assertEqual(con_diagonales("251"), "25/1")
        self.assertEqual(con_diagonales("2512"), "25/12")
        self.assertEqual(con_diagonales("25122"), "25/12/2")
        self.assertEqual(con_diagonales("25122026"), "25/12/2026")
        self.assertEqual(con_diagonales("25/12/20269"), "25/12/2026")

    def test_leer_y_formatear(self):
        self.assertEqual(leer_fecha("25/12/2026"), date(2026, 12, 25))
        self.assertIsNone(leer_fecha("31/02/2026"))
        self.assertIsNone(leer_fecha("25/12/26"))
        self.assertIsNone(leer_fecha("25/12"))
        self.assertEqual(formato_fecha(date(2026, 3, 5)), "05/03/2026")

    def test_restar_meses(self):
        self.assertEqual(restar_meses(date(2026, 3, 31), 1), date(2026, 2, 28))
        self.assertEqual(restar_meses(date(2026, 1, 15), 1), date(2025, 12, 15))

    def test_viaje_mas_de_un_mes_despues(self):
        pago, holgada = fecha_de_pago(date(2026, 12, 20), date(2026, 10, 1))
        self.assertEqual((pago, holgada), (date(2026, 11, 20), True))

    def test_viaje_cercano_a_la_cancelacion(self):
        pago, holgada = fecha_de_pago(date(2026, 12, 20), date(2026, 12, 1))
        self.assertEqual((pago, holgada), (date(2026, 11, 16), False))

    def test_exactamente_un_mes_no_es_mayor(self):
        pago, holgada = fecha_de_pago(date(2026, 12, 20), date(2026, 11, 20))
        self.assertEqual((pago, holgada), (date(2026, 11, 5), False))


if __name__ == "__main__":
    unittest.main()
