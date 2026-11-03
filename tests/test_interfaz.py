"""Recorre la interfaz completa con Tkinter simulado.

Los valores esperados (tests/datos/referencia_interfaz.json) se tomaron de la
versión 1.0.3 antes de la auditoría: la refactorización no debe cambiarlos.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests import tk_simulado  # noqa: E402

REFERENCIA = os.path.join(os.path.dirname(__file__), "datos", "referencia_interfaz.json")


def texto(widget):
    return widget.kw.get("text")


class PruebaInterfaz(unittest.TestCase):
    def setUp(self):
        tk, self.errores = tk_simulado.instalar()
        from calculadora import interfaz

        self.interfaz = interfaz
        self.app = interfaz.Calculadora(tk.Tk())

    def poner_personas(self, adultos, ninos, infantes):
        for tipo, valor in zip(("ADULTOS", "NIÑOS", "INFANTES"), (adultos, ninos, infantes)):
            self.app.personas[tipo].valor = str(valor)
        self.app.al_cambiar_personas()

    @staticmethod
    def poner_montos(fila, adultos, adultos_ninos, combinado):
        fila.entradas["adultos"].valor = f"$ {adultos}"
        fila.entradas["adultos_ninos"].valor = f"$ {adultos_ninos}"
        fila.entradas["adultos_ninos_infantes"].valor = f"$ {combinado}"

    def armar_escenario(self):
        """2 adultos, 1 niño y 1 infante con siete servicios (el caso de referencia)."""
        app = self.app
        self.poner_personas(2, 1, 1)
        self.poner_montos(app.filas[0], 1000, 1600, 1700)
        self.poner_montos(app.filas[1], 100, 90, 80)
        self.poner_montos(app.agregar_servicio("CRUCEROS"), 800, 1100, 1150)
        self.poner_montos(app.agregar_servicio("SEGURO DE VIAJE"), 40, 60, 70)
        self.poner_montos(app.agregar_servicio("ENTRADAS EVENTOS"), 10, 15, 16)
        asientos = app.agregar_servicio("MISCELANEOS")
        asientos.subtipo.set("Asientos")
        asientos.marcas["NIÑOS"][0].set(True)
        asientos.marcas["INFANTES"][0].set(True)
        app.al_cambiar_inclusion(asientos)
        self.poner_montos(asientos, 80, 120, 130)
        self.poner_montos(app.agregar_servicio("MISCELANEOS"), 0, 0, 0)
        return asientos

    def test_estado_inicial(self):
        app = self.app
        self.assertEqual([fila.base for fila in app.filas], ["BOLETOS NETOS", "DISEÑADOR"])
        self.assertEqual(app.personas["ADULTOS"].valor, "1")
        self.assertEqual(len(app.orden_campos), 3 + 2)
        self.assertEqual(texto(app.total_pvp), "$ 0.00")

    def test_columnas_y_tabulacion_siguen_a_las_personas(self):
        self.poner_personas(2, 1, 1)
        self.assertEqual(self.app.tipos_activos(), ["ADULTOS", "NIÑOS", "INFANTES"])
        self.assertEqual(len(self.app.orden_campos), 3 + 6)
        self.poner_personas(2, 0, 1)
        encabezado = self.app.encabezados_servicios["adultos_ninos_infantes"]
        self.assertEqual(texto(encabezado), "Adultos + infantes")

    def test_resultados_iguales_a_la_version_anterior(self):
        self.armar_escenario()
        self.app.calcular()
        self.assertEqual(self.errores, [])
        with open(REFERENCIA, encoding="utf-8") as archivo:
            referencia = json.load(archivo)

        app = self.app
        for tipo, valores in referencia["resumen"].items():
            for clave, esperado in valores.items():
                self.assertEqual(texto(app.resumen_filas[tipo][clave]), esperado, (tipo, clave))
        totales = [texto(w) for w in (app.total_pvp, app.total_pvp_q, app.total_descuento, app.total_descuento_q)]
        self.assertEqual(totales, referencia["totales"])

        app.alternar_desglose()
        desglose = [texto(w) for w in app.tabla_desglose.winfo_children()]
        self.assertEqual(desglose, referencia["desglose"])

    def test_miscelaneos_opcional(self):
        self.poner_personas(2, 1, 1)
        fila = self.app.agregar_servicio("MISCELANEOS")
        self.assertEqual(fila.entradas["adultos_ninos"].kw.get("state"), "disabled")
        fila.marcas["INFANTES"][0].set(True)
        self.app.al_cambiar_inclusion(fila)
        self.assertEqual(fila.entradas["adultos_ninos_infantes"].kw.get("state"), "normal")
        self.poner_montos(fila, 50, 0, 70)
        self.app.calcular()
        renglones = dict(self.app._presupuesto.servicios)["Misceláneos"]
        self.assertEqual([r.tipo for r in renglones], ["ADULTOS", "INFANTES"])
        self.assertAlmostEqual(renglones[1].costo_total, 20)

    def test_quitar_servicio_y_fijos(self):
        crucero = self.app.agregar_servicio("CRUCEROS")
        self.app.quitar_servicio(crucero)
        self.assertEqual(len(self.app.filas), 2)
        self.app.quitar_servicio(self.app.filas[0])
        self.assertEqual(len(self.app.filas), 2)

    def test_resaltado_de_fila_y_columna(self):
        fila = self.app.filas[0]
        self.app.resaltar(fila, "adultos")
        self.assertEqual(self.app.encabezados_servicios["adultos"].kw["bg"], "#E3EEF9")
        self.assertEqual(fila._columnas[0].kw["bg"], "#E3EEF9")
        self.app.quitar_resalte(fila, "adultos")
        self.assertNotEqual(fila._columnas[0].kw["bg"], "#E3EEF9")

    def test_monto_invalido(self):
        self.app.filas[0].entradas["adultos"].valor = "abc"
        self.app.calcular(silencioso=True)
        self.assertEqual(self.errores, [])
        self.app.calcular()
        self.assertEqual(len(self.errores), 1)

    def test_limpiar(self):
        self.armar_escenario()
        self.app.calcular()
        self.app.alternar_desglose()
        self.app.limpiar()
        self.assertEqual(len(self.app.filas), 2)
        self.assertEqual(self.app.personas["NIÑOS"].valor, "0")
        self.assertEqual(texto(self.app.total_pvp), "$ 0.00")
        self.assertEqual(self.app.filas[0].entradas["adultos"].valor, "$ 0.00")
        mensajes = [texto(w) for w in self.app.tabla_desglose.winfo_children()]
        self.assertIn("Todavía no hay montos para mostrar.", mensajes)


if __name__ == "__main__":
    unittest.main()
