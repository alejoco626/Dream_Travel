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
        self.app.redondear.set(False)  # la referencia es sin redondeo
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

    def test_redondeo_activo_por_defecto(self):
        self.armar_escenario()
        self.app.calcular()
        self.assertTrue(self.app.redondear.get())
        adultos = self.app.resumen_filas["ADULTOS"]
        self.assertEqual(texto(adultos["pvp"]), "$ 1,252.00")  # real: $ 1,251.93
        self.assertEqual(texto(adultos["pvp_total"]), "Total $ 2,504.00")
        self.app.redondear.set(False)
        self.app.calcular()
        self.assertEqual(texto(adultos["pvp"]), "$ 1,251.93")

    def test_ajuste_de_precio_adulto(self):
        self.armar_escenario()
        self.app.calcular()
        self.assertEqual(texto(self.app.ajuste_actual), "$ 1,252.00")
        self.assertEqual(texto(self.app.ajuste_diferencia), "—")
        self.app.ajuste_nuevo.valor = "1,151.50"
        self.app._formatear_ajuste()
        # (1,252 - 1,151.50) x 2 adultos = 201.00
        self.assertEqual(texto(self.app.ajuste_diferencia), "$ 201.00")
        self.app.ajuste_nuevo.valor = "1,151.75"
        self.app._formatear_ajuste()
        # (1,252 - 1,151.75) x 2 = 200.50 -> se redondea a 201
        self.assertEqual(texto(self.app.ajuste_diferencia), "$ 201.00")
        self.app.ajuste_nuevo.valor = "1,151.76"
        self.app._formatear_ajuste()
        # 200.48 -> 200
        self.assertEqual(texto(self.app.ajuste_diferencia), "$ 200.00")
        self.app.redondear.set(False)
        self.app.calcular()
        # sin redondeo: (1,251.93 - 1,151.76) x 2 = 200.34
        self.assertEqual(texto(self.app.ajuste_diferencia), "$ 200.34")
        self.app.limpiar()
        self.assertEqual(texto(self.app.ajuste_diferencia), "—")

    def test_fecha_de_pago(self):
        app = self.app
        viaje, cancelacion = app.fechas_pago["viaje"], app.fechas_pago["cancelacion"]
        self.assertIn("Escribe las dos fechas", texto(app.aviso_pago))
        viaje.entrada.valor = "201226"
        viaje._poner_diagonales()
        self.assertEqual(viaje.entrada.valor, "20/12/26")
        cancelacion.poner_fecha(__import__("datetime").date(2026, 10, 1))
        self.assertEqual(texto(app.aviso_pago), "Fecha de pago: 20/11/26")
        self.assertEqual(app.aviso_pago.kw["fg"], "#1E7A4C")
        cancelacion.entrada.valor = "01/12/26"
        app._actualizar_pago()
        self.assertEqual(texto(app.aviso_pago), "Fecha de pago: 16/11/26")
        self.assertEqual(app.aviso_pago.kw["fg"], "#C62828")
        app.no_reembolsable.set(True)
        app._actualizar_pago()
        app.limpiar()
        self.assertFalse(app.no_reembolsable.get())
        self.assertEqual(viaje.entrada.valor, "")

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
