"""Lo que la pantalla muestra se calcula en calculadora/api.py.

Los valores esperados (tests/datos/referencia_interfaz.json) se tomaron de la versión
1.0.3: el cambio de interfaz (Tkinter -> pywebview) no debe cambiarlos.
"""

import base64
import io
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculadora import api  # noqa: E402

REFERENCIA = os.path.join(os.path.dirname(__file__), "datos", "referencia_interfaz.json")


def servicio(base, adultos, adultos_ninos, combinado, subtipo=None, incluye=None):
    return {
        "base": base,
        "subtipo": subtipo,
        "montos": {
            "adultos": f"$ {adultos}",
            "adultos_ninos": f"$ {adultos_ninos}",
            "adultos_ninos_infantes": f"$ {combinado}",
        },
        "incluye": incluye or {},
    }


def escenario(**cambios):
    """2 adultos, 1 niño y 1 infante con siete servicios (el caso de referencia)."""
    estado = {
        "personas": {"ADULTOS": "2", "NIÑOS": "1", "INFANTES": "1"},
        "servicios": [
            servicio("BOLETOS NETOS", 1000, 1600, 1700),
            servicio("DISEÑADOR", 100, 90, 80),
            servicio("CRUCEROS", 800, 1100, 1150),
            servicio("SEGURO DE VIAJE", 40, 60, 70),
            servicio("ENTRADAS EVENTOS", 10, 15, 16),
            servicio("MISCELANEOS", 80, 120, 130, "Asientos", {"NIÑOS": True, "INFANTES": True}),
            servicio("MISCELANEOS", 0, 0, 0, "Misceláneos"),
        ],
        "redondear": False,
        "no_reembolsable": False,
        "fecha_viaje": "",
        "fecha_cancelacion": "",
        "ajuste_nuevo": "",
    }
    estado.update(cambios)
    return estado


class PruebaCalculo(unittest.TestCase):
    def test_resultados_iguales_a_la_version_anterior(self):
        with open(REFERENCIA, encoding="utf-8") as archivo:
            referencia = json.load(archivo)
        resultado = api.calcular_estado(escenario())
        self.assertTrue(resultado["ok"])
        for tipo, valores in referencia["resumen"].items():
            for clave, esperado in valores.items():
                self.assertEqual(resultado["por_persona"][tipo][clave], esperado, (tipo, clave))
        totales = resultado["totales"]
        self.assertEqual(
            [totales["pvp"], totales["pvp_q"], totales["descuento"], totales["descuento_q"]],
            referencia["totales"],
        )
        desglose = resultado["desglose"]
        plano = list(desglose["encabezados"])
        for grupo in desglose["grupos"]:
            plano.append(grupo["nombre"])
            for renglon in grupo["renglones"]:
                plano.append(renglon["concepto"])
                plano.extend(renglon["valores"])
        plano.append("TOTAL")
        plano.extend(desglose["totales"])
        self.assertEqual(plano, referencia["desglose"])

    def test_redondeo(self):
        adultos = api.calcular_estado(escenario(redondear=True))["por_persona"]["ADULTOS"]
        self.assertEqual(adultos["pvp"], "$ 1,252.00")  # real: $ 1,251.93
        self.assertEqual(adultos["pvp_total"], "Total $ 2,504.00")

    def test_ajuste_de_precio_adulto(self):
        resultado = api.calcular_estado(escenario(redondear=True, ajuste_nuevo="1,151.50"))
        # (1,252 - 1,151.50) x 2 adultos = 201.00
        self.assertEqual(resultado["ajuste"], {"actual": "$ 1,252.00", "diferencia": "$ 201.00"})
        resultado = api.calcular_estado(escenario(redondear=True, ajuste_nuevo="1151.76"))
        self.assertEqual(resultado["ajuste"]["diferencia"], "$ 200.00")  # 200.48 -> 200
        resultado = api.calcular_estado(escenario(ajuste_nuevo="1151.76"))
        self.assertEqual(resultado["ajuste"]["diferencia"], "$ 200.34")  # sin redondeo
        self.assertEqual(api.calcular_estado(escenario())["ajuste"]["diferencia"], "—")

    def test_monto_para_reservar(self):
        def reserva(adultos, ninos, infantes):
            estado = escenario(personas={"ADULTOS": adultos, "NIÑOS": ninos, "INFANTES": infantes})
            return api.calcular_estado(estado)["monto_reserva"]

        # boletos 1000 / 1600 / 1700, divididos entre 0.80
        self.assertEqual(reserva("2", "0", "0"), "$ 1,250.00")
        self.assertEqual(reserva("2", "1", "0"), "$ 2,000.00")
        self.assertEqual(reserva("2", "1", "1"), "$ 2,125.00")
        self.assertEqual(reserva("2", "0", "1"), "$ 2,125.00")

    def test_fecha_de_pago(self):
        pago = api.calcular_estado(escenario())["pago"]
        self.assertIn("Escribe las dos fechas", pago["texto"])
        pago = api.calcular_estado(escenario(fecha_viaje="20/12/2026", fecha_cancelacion="01/10/2026"))["pago"]
        self.assertEqual((pago["texto"], pago["tono"]), ("Fecha de pago: 20/11/2026", "exito"))
        pago = api.calcular_estado(escenario(fecha_viaje="20/12/2026", fecha_cancelacion="01/12/2026"))["pago"]
        self.assertEqual((pago["texto"], pago["tono"]), ("Fecha de pago: 16/11/2026", "peligro"))
        pago = api.calcular_estado(escenario(no_reembolsable=True, fecha_viaje="20/12/2026"))["pago"]
        self.assertFalse(pago["visible"])

    def test_miscelaneos_solo_cuenta_lo_marcado(self):
        estado = escenario(
            servicios=[servicio("MISCELANEOS", 50, 999, 70, "Equipaje", {"INFANTES": True})]
        )
        resultado = api.calcular_estado(estado)
        grupo = resultado["desglose"]["grupos"][0]
        self.assertEqual(grupo["nombre"], "Equipaje")
        self.assertEqual([r["concepto"] for r in grupo["renglones"]], ["Adultos (2)", "Infantes (1)"])
        self.assertEqual(grupo["renglones"][1]["valores"][0], "$ 20.00")

    def test_errores(self):
        estado = escenario()
        estado["servicios"][2]["montos"]["adultos"] = "abc"
        resultado = api.calcular_estado(estado)
        self.assertFalse(resultado["ok"])
        self.assertEqual(resultado["campo"], {"tipo": "monto", "fila": 2, "clave": "adultos"})
        self.assertIn("Cruceros", resultado["mensaje"])
        sin_personas = api.calcular_estado(escenario(personas={"ADULTOS": "0", "NIÑOS": "", "INFANTES": "x"}))
        self.assertFalse(sin_personas["ok"])
        self.assertEqual(sin_personas["campo"], {"tipo": "personas"})
        # un monto en una columna que no se usa no importa
        estado = escenario(personas={"ADULTOS": "2", "NIÑOS": "0", "INFANTES": "0"})
        estado["servicios"][0]["montos"]["adultos_ninos"] = "abc"
        self.assertTrue(api.calcular_estado(estado)["ok"])

    def test_datos_fuera_de_lo_normal(self):
        with self.assertRaises(ValueError):
            api.calcular_estado(escenario(servicios=[{"base": "OTRO"}]))
        resultado = api.calcular_estado(escenario(personas={"ADULTOS": "500"}))
        self.assertEqual(resultado["cantidades"]["ADULTOS"], 99)
        estado = escenario(servicios=[servicio("MISCELANEOS", 10, 0, 0, "<script>")])
        grupo = api.calcular_estado(estado)["desglose"]["grupos"][0]
        self.assertEqual(grupo["nombre"], "Misceláneos")  # solo se aceptan subtipos de la lista

    def test_formatear_monto(self):
        self.assertEqual(api.formatear_monto("1000"), {"valido": True, "texto": "$ 1,000.00"})
        self.assertEqual(api.formatear_monto(""), {"valido": True, "texto": "$ 0.00"})
        self.assertFalse(api.formatear_monto("1e999")["valido"])


class PruebaApi(unittest.TestCase):
    def test_metodos_publicos(self):
        publicos = sorted(n for n in dir(api.Api) if not n.startswith("_"))
        self.assertEqual(
            publicos,
            [
                "buscar_actualizacion", "calcular", "copiar_captura", "descargar_actualizacion",
                "estado_descarga", "formatear_monto", "inicio", "instalar_actualizacion", "listo",
                "registrar_error_pagina",
            ],
        )

    def test_inicio_en_desarrollo(self):
        datos = api.Api().inicio()
        self.assertEqual(datos["fijos"], ["BOLETOS NETOS", "DISEÑADOR"])
        self.assertIsNone(datos["novedades"])  # solo el programa instalado muestra novedades
        self.assertEqual([t["edad"] for t in datos["tipos"]][1:], ["de 2 a 9 años", "de 0 a 23 meses"])

    def test_novedades_tras_actualizar(self):
        import tempfile

        ruta = os.path.join(tempfile.mkdtemp(), "ultima_version.txt")
        with mock.patch.object(sys, "frozen", True, create=True), \
                mock.patch.object(sys, "argv", ["calculadora", "--actualizado"]), \
                mock.patch.object(api, "VERSION_APP", "1.0.12"), \
                mock.patch.object(api.novedades, "ARCHIVO_VERSION_VISTA", ruta):
            notas = api.notas_de_novedades()
            self.assertEqual(notas["version"], "1.0.12")
            self.assertEqual(
                notas["secciones"],
                [{"titulo": "Correcciones", "vineta": "•",
                  "elementos": ["Se cambiaron los parámetros de edad de niños e infantes"]}],
            )
            sys.argv = ["calculadora"]
            self.assertIsNone(api.notas_de_novedades())  # la segunda vez ya no aparece

    def test_errores_quedan_registrados(self):
        with mock.patch.object(api, "registrar_error") as registrar:
            respuesta = api.Api().calcular({"personas": {"ADULTOS": 1}, "servicios": [{"base": "NO EXISTE"}]})
        self.assertFalse(respuesta["ok"])
        registrar.assert_called_once()

    def test_captura(self):
        from PIL import Image

        salida = io.BytesIO()
        Image.new("RGB", (4, 3), "red").save(salida, "PNG")
        datos = "data:image/png;base64," + base64.b64encode(salida.getvalue()).decode()
        copiadas = []
        with mock.patch.object(api, "copiar_imagen_portapapeles", copiadas.append):
            self.assertEqual(api.Api().copiar_captura(datos), {"ok": True})
        self.assertEqual(copiadas[0].size, (4, 3))
        with mock.patch.object(api, "registrar_error"):
            self.assertFalse(api.Api().copiar_captura("no es una imagen")["ok"])

    def test_actualizacion_solo_en_el_programa_instalado(self):
        self.assertIsNone(api.Api().buscar_actualizacion())
        self.assertEqual(api.Api().estado_descarga()["estado"], "error")
        self.assertFalse(api.Api().instalar_actualizacion()["ok"])


class PruebaPaginaWeb(unittest.TestCase):
    """La página y sus recursos están completos (se empaquetan dentro del .exe)."""

    CARPETA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "calculadora", "web")

    def test_archivos(self):
        for nombre in (
            "index.html", "estilos.css", "app.js", "img/logo.png",
            "vendor/html2canvas.min.js", "vendor/inter-latin.woff2", "vendor/inter-latin-ext.woff2",
        ):
            self.assertTrue(os.path.exists(os.path.join(self.CARPETA, nombre)), nombre)

    def test_sin_recursos_externos(self):
        for nombre in ("index.html", "estilos.css", "app.js"):
            with open(os.path.join(self.CARPETA, nombre), encoding="utf-8") as archivo:
                contenido = archivo.read()
            self.assertNotIn("http://", contenido.replace("http://www.w3.org/2000/svg", ""), nombre)
            self.assertNotIn("https://", contenido, nombre)

    def test_la_pagina_llama_solo_metodos_que_existen(self):
        import re

        with open(os.path.join(self.CARPETA, "app.js"), encoding="utf-8") as archivo:
            llamados = set(re.findall(r"api\.([a-z_]+)\(", archivo.read()))
        self.assertTrue(llamados)
        self.assertLessEqual(llamados, {n for n in dir(api.Api) if not n.startswith("_")})


if __name__ == "__main__":
    unittest.main()
