import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculadora.calculo import (  # noqa: E402
    ServicioCapturado,
    calcular_presupuesto,
    costos_por_tipo,
    dinero,
    leer_monto,
    quetzales,
    tipos_activos,
)

TODOS = frozenset(("ADULTOS", "NIÑOS", "INFANTES"))


def servicio(adultos, adultos_ninos=0.0, combinado=0.0, proporcion=0.9, modo="total", tipos=TODOS):
    montos = {"adultos": adultos, "adultos_ninos": adultos_ninos, "adultos_ninos_infantes": combinado}
    return ServicioCapturado("Prueba", proporcion, modo, montos, tipos)


class PruebaFormato(unittest.TestCase):
    def test_leer_monto(self):
        self.assertEqual(leer_monto("$ 1,250.50"), 1250.5)
        self.assertEqual(leer_monto("   "), 0.0)
        self.assertEqual(leer_monto("80"), 80.0)
        with self.assertRaises(ValueError):
            leer_monto("abc")

    def test_redondear_arriba(self):
        from calculadora.calculo import redondear_arriba
        self.assertEqual(redondear_arriba(301.01), 302)
        self.assertEqual(redondear_arriba(301.00), 301)
        self.assertEqual(redondear_arriba(301.004), 301)

    def test_diferencia_por_persona(self):
        from calculadora.calculo import diferencia_por_persona
        cantidades = {"ADULTOS": 2, "NIÑOS": 2, "INFANTES": 1}
        self.assertEqual(diferencia_por_persona(2045, 1900, cantidades), (290, 58.0))

    def test_formatos(self):
        self.assertEqual(dinero(1234.5), "$ 1,234.50")
        self.assertEqual(quetzales(1000), "Q 7,880.00")


class PruebaCostos(unittest.TestCase):
    cantidades = {"ADULTOS": 2, "NIÑOS": 1, "INFANTES": 1}

    def test_tipos_activos(self):
        self.assertEqual(tipos_activos({"ADULTOS": 0, "NIÑOS": 0, "INFANTES": 2}), ["ADULTOS", "INFANTES"])

    def test_modo_total_resta_los_acumulados(self):
        costos = costos_por_tipo(servicio(1000, 1600, 1700), self.cantidades)
        self.assertEqual(costos, {"ADULTOS": 1000, "NIÑOS": 600, "INFANTES": 100})

    def test_modo_persona_multiplica_por_el_grupo(self):
        costos = costos_por_tipo(servicio(100, 90, 80, modo="persona"), self.cantidades)
        self.assertEqual(costos, {"ADULTOS": 200, "NIÑOS": 70, "INFANTES": 50})

    def test_modo_persona_infantes_no_negativos(self):
        costos = costos_por_tipo(servicio(100, 100, 60, modo="persona"), self.cantidades)
        self.assertEqual(costos["INFANTES"], 0.0)

    def test_sin_ninos_los_infantes_se_restan_de_adultos(self):
        solo_infantes = frozenset(("ADULTOS", "INFANTES"))
        costos = costos_por_tipo(servicio(50, 999, 70, tipos=solo_infantes), self.cantidades)
        self.assertEqual(costos, {"ADULTOS": 50, "NIÑOS": 0.0, "INFANTES": 20})


class PruebaPresupuesto(unittest.TestCase):
    def test_caso_de_referencia(self):
        cantidades = {"ADULTOS": 2, "NIÑOS": 1, "INFANTES": 1}
        servicios = [
            servicio(1000, 1600, 1700, 0.80),
            servicio(100, 90, 80, 0.95, "persona"),
            servicio(800, 1100, 1150, 0.90),
            servicio(40, 60, 70, 0.90),
            servicio(10, 15, 16, 1.0),
            servicio(80, 120, 130, 0.80),
        ]
        presupuesto = calcular_presupuesto(servicios, cantidades)
        self.assertEqual(dinero(presupuesto.total_pvp), "$ 3,995.90")
        self.assertEqual(dinero(presupuesto.total_descuento), "$ 3,805.62")
        self.assertAlmostEqual(presupuesto.descuento_persona["ADULTOS"], presupuesto.pvp_persona["ADULTOS"] / 1.05)
        self.assertAlmostEqual(presupuesto.totales_columnas[2], presupuesto.total_pvp)

    def test_tipo_sin_personas_no_suma_al_pvp(self):
        cantidades = {"ADULTOS": 0, "NIÑOS": 2, "INFANTES": 0}
        presupuesto = calcular_presupuesto([servicio(100, 300)], cantidades)
        self.assertEqual(presupuesto.pvp_persona["ADULTOS"], 0.0)
        self.assertAlmostEqual(presupuesto.pvp_persona["NIÑOS"], 200 / 0.9 / 2)


if __name__ == "__main__":
    unittest.main()
