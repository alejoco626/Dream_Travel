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

    @mock.patch.object(api, "hoy", lambda: __import__("datetime").date(2026, 9, 1))
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

    def test_cotizacion_que_baja_no_da_precios_negativos(self):
        # Diseñador: $491 por persona para 3 adultos y $250 para los 5 -> niños -$223
        estado = escenario(
            personas={"ADULTOS": "3", "NIÑOS": "2", "INFANTES": "0"},
            servicios=[servicio("DISEÑADOR", 491, 250, 0), servicio("BOLETOS NETOS", 1000, 900, 0)],
        )
        resultado = api.calcular_estado(estado)
        self.assertEqual(resultado["por_persona"]["NIÑOS"]["pvp"], "$ 0.00")
        self.assertEqual([a["fila"] for a in resultado["avisos"]], [0, 1])
        self.assertEqual(resultado["avisos"][0]["clave"], "adultos_ninos")
        self.assertIn("salió más baja", resultado["avisos"][0]["mensaje"])

    def test_aviso_si_un_menor_paga_mas(self):
        estado = escenario(
            personas={"ADULTOS": "3", "NIÑOS": "2", "INFANTES": "0"},
            servicios=[servicio("BOLETOS NETOS", 1547, 2522, 0), servicio("DISEÑADOR", 491, 819, 0)],
        )
        avisos = api.calcular_estado(estado)["avisos"]
        self.assertEqual(len(avisos), 1)
        self.assertIn("a cada niño le toca $ 1,311.00 y a cada adulto $ 491.00", avisos[0]["mensaje"])
        normal = escenario(servicios=[servicio("BOLETOS NETOS", 1000, 1400, 1450), servicio("DISEÑADOR", 300, 250, 210)])
        self.assertEqual(api.calcular_estado(normal)["avisos"], [])  # el caso normal no avisa

    def test_sin_aviso_mientras_faltan_cotizaciones(self):
        # Solo la cotización de adultos escrita: "Adultos + niños" vacío no es una baja
        estado = escenario(
            personas={"ADULTOS": "3", "NIÑOS": "2", "INFANTES": "0"},
            servicios=[servicio("BOLETOS NETOS", 1547, 0, 0), servicio("DISEÑADOR", 491, 0, 0)],
        )
        self.assertEqual(api.calcular_estado(estado)["avisos"], [])

    def test_descuento_sale_del_pvp_redondeado(self):
        for redondear in (True, False):
            resultado = api.calcular_estado(escenario(redondear=redondear))
            for valores in resultado["por_persona"].values():
                pvp = float(valores["pvp"][2:].replace(",", ""))
                descuento = float(valores["descuento"][2:].replace(",", ""))
                esperado = round(pvp / 1.05) if redondear else pvp / 1.05
                self.assertAlmostEqual(descuento, esperado, delta=0.006)

    def test_formatear_monto(self):
        self.assertEqual(api.formatear_monto("1000"), {"valido": True, "texto": "$ 1,000.00"})
        self.assertEqual(api.formatear_monto(""), {"valido": True, "texto": "$ 0.00"})
        self.assertFalse(api.formatear_monto("1e999")["valido"])


class PruebaRepartir(unittest.TestCase):
    """Interruptor "Repartir monto": un total por servicio repartido por pesos."""

    @staticmethod
    def total(base, monto, **extra):
        return {"base": base, "montos": {"total": str(monto)}, **extra}

    def estado(self, servicios, personas=("2", "2", "1")):
        return {
            "personas": dict(zip(("ADULTOS", "NIÑOS", "INFANTES"), personas)),
            "servicios": servicios,
            "repartir": True,
            "redondear": True,
        }

    def test_ejemplo_de_la_familia(self):
        # Boletos $2,449 en total y Diseñador $220 por persona (x 5 = $1,100)
        resultado = api.calcular_estado(
            self.estado([self.total("BOLETOS NETOS", 2449), self.total("DISEÑADOR", 220)])
        )
        precios = [resultado["por_persona"][t]["pvp"] for t in ("ADULTOS", "NIÑOS", "INFANTES")]
        self.assertEqual(precios, ["$ 1,156.00", "$ 867.00", "$ 173.00"])
        self.assertEqual(resultado["totales"]["pvp"], "$ 4,219.00")
        self.assertEqual(
            resultado["reparto"][0], {"ADULTOS": "$ 670.96", "NIÑOS": "$ 503.22", "INFANTES": "$ 100.64"}
        )
        self.assertEqual(resultado["monto_reserva"], "$ 3,061.25")  # 2,449 / 0.80

    def test_el_infante_nunca_paga_mas_que_el_nino(self):
        for personas in (("1", "3", "1"), ("4", "1", "2"), ("2", "0", "1"), ("1", "1", "0")):
            resultado = api.calcular_estado(self.estado([self.total("BOLETOS NETOS", 1000)], personas))
            neto = resultado["reparto"][0]
            valores = [float(neto[t][2:].replace(",", "")) for t in ("ADULTOS", "NIÑOS", "INFANTES") if t in neto]
            self.assertEqual(valores, sorted(valores, reverse=True), personas)

    def test_miscelaneos_solo_entre_los_marcados(self):
        resultado = api.calcular_estado(
            self.estado([self.total("MISCELANEOS", 150, subtipo="Asientos", incluye={"INFANTES": True})])
        )
        self.assertEqual(resultado["reparto"][0], {"ADULTOS": "$ 69.77", "INFANTES": "$ 10.47"})

    def test_total_invalido(self):
        resultado = api.calcular_estado(self.estado([self.total("CRUCEROS", "abc")]))
        self.assertEqual(resultado["campo"], {"tipo": "monto", "fila": 0, "clave": "total"})


class PruebaApi(unittest.TestCase):
    def test_metodos_publicos(self):
        publicos = sorted(n for n in dir(api.Api) if not n.startswith("_"))
        self.assertEqual(
            publicos,
            [
                "abrir_carpeta", "abrir_enlace", "abrir_negociacion", "buscar_actualizacion", "calcular",
                "convertir_moneda", "copiar_captura", "copiar_texto", "descargar_actualizacion", "estado_descarga",
                "exportar_historial", "formatear_monto", "guardar_negociacion", "historial_resumen", "inicio",
                "instalar_actualizacion", "listo", "preparar_guardado", "quitar_negociacion",
                "registrar_error_pagina", "revisar_enlace",
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

    def test_convertir_moneda(self):
        convertir = api.Api().convertir_moneda
        self.assertEqual(convertir("7880", "GTQ"), {"valido": True, "resultado": "$ 1,000.00"})
        self.assertEqual(convertir("Q 1,000"), {"valido": True, "resultado": "$ 126.90"})
        self.assertEqual(convertir("100", "USD"), {"valido": True, "resultado": "Q 788.00"})
        self.assertEqual(convertir("$ 1,250.50", "USD"), {"valido": True, "resultado": "Q 9,853.94"})
        self.assertEqual(convertir("", "USD"), {"valido": True, "resultado": "Q 0.00"})
        self.assertEqual(convertir("", "GTQ"), {"valido": True, "resultado": "$ 0.00"})
        self.assertFalse(convertir("abc", "USD")["valido"])
        self.assertEqual(convertir("abc", "USD")["resultado"], "—")

    def test_convertir_quetzales(self):
        convertir = api.convertir_quetzales
        self.assertEqual(convertir("1000"), {"valido": True, "dolares": "$ 126.90"})
        self.assertEqual(convertir("Q 7,880"), {"valido": True, "dolares": "$ 1,000.00"})
        self.assertEqual(convertir(""), {"valido": True, "dolares": "$ 0.00"})
        self.assertFalse(convertir("abc")["valido"])

    def test_copiar_texto(self):
        copiados = []
        with mock.patch.object(api, "copiar_texto_portapapeles", copiados.append):
            self.assertEqual(api.Api().copiar_texto(" $ 1,161.00 "), {"ok": True})
            self.assertFalse(api.Api().copiar_texto("")["ok"])
            self.assertFalse(api.Api().copiar_texto("x" * 500)["ok"])
        self.assertEqual(copiados, ["$ 1,161.00"])

    def test_captura(self):
        from PIL import Image

        salida = io.BytesIO()
        Image.new("RGB", (4, 3), "red").save(salida, "PNG")
        datos = "data:image/png;base64," + base64.b64encode(salida.getvalue()).decode()
        copiadas = []
        with mock.patch.object(api, "copiar_imagen_portapapeles", copiadas.append):
            respuesta = api.Api().copiar_captura(datos)
            self.assertTrue(respuesta["ok"] and respuesta["copiada"])
            self.assertTrue(respuesta["archivo"].endswith(".png"))
        self.assertEqual(copiadas[0].size, (4, 3))
        with mock.patch.object(api, "registrar_error"):
            self.assertFalse(api.Api().copiar_captura("no es una imagen")["ok"])

    def test_descarga_que_falla_con_error_raro_no_se_queda_quieta(self):
        import http.client
        import time

        def falla(info, cola):
            raise http.client.IncompleteRead(b"")

        with mock.patch.object(api.actualizador, "hilo_descargar", falla), mock.patch.object(api, "registrar_error"):
            descarga = api.DescargaEnCurso({"version": "9.9.9"})
            for _ in range(50):
                estado = descarga.estado()
                if estado["estado"] != "descargando":
                    break
                time.sleep(0.02)
        self.assertEqual(estado["estado"], "error")

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
