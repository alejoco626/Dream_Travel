import json
import os
import shutil
import tempfile
import unittest
from datetime import date, datetime
from unittest import mock

from openpyxl import load_workbook

from calculadora import api, historial


class Reloj:
    def __init__(self, momento):
        self.momento = momento

    def __call__(self):
        return self.momento


def registro(monto=100.0, enlace="https://dt.bitrix24.com/crm/deal/details/1/", negociacion="1", referencia=""):
    return {
        "enlace": enlace, "negociacion": negociacion, "referencia": referencia,
        "personas": {"ADULTOS": 2, "NIÑOS": 0, "INFANTES": 0}, "servicios": ["Boletos"],
        "monto_pvp": monto, "monto_pvp_q": monto * 7.88, "con_descuento": False,
        "monto_descuento": monto / 1.05, "monto_descuento_q": monto / 1.05 * 7.88, "estado": {},
    }


class PruebaPeriodos(unittest.TestCase):
    def test_periodo_empieza_el_dia_2(self):
        self.assertEqual(historial.periodo_de(date(2026, 11, 2)), "2026-11")
        self.assertEqual(historial.periodo_de(date(2026, 11, 30)), "2026-11")
        self.assertEqual(historial.periodo_de(date(2026, 12, 1)), "2026-11")
        self.assertEqual(historial.periodo_de(date(2027, 1, 1)), "2026-12")
        self.assertEqual(historial.siguiente_reinicio("2026-12"), date(2027, 1, 2))
        self.assertEqual(historial.nombre_periodo("2026-11"), "Noviembre 2026")


class PruebaTextos(unittest.TestCase):
    def test_enlace(self):
        bueno = historial.revisar_enlace(" https://dreamtravel.bitrix24.com/crm/deal/details/18452/ ")
        self.assertTrue(bueno["valido"])
        self.assertEqual(bueno["negociacion"], "18452")
        otro = historial.revisar_enlace("https://example.com/algo")
        self.assertTrue(otro["valido"])
        self.assertEqual(otro["tono"], "alerta")
        for malo in ("", "18452", "hola mundo", "javascript:alert(1)", "https://" + "a" * 600 + ".com"):
            self.assertFalse(historial.revisar_enlace(malo)["valido"], malo)

    def test_nombre_captura(self):
        momento = datetime(2026, 11, 24, 11, 36)
        personas = {"ADULTOS": 3, "NIÑOS": 2, "INFANTES": 0}
        self.assertEqual(
            historial.nombre_captura(momento, personas, 4701.0, "Familia López"),
            "2026-11-24 11h36 · Familia López · 3A 2N · $4,701.png",
        )
        self.assertEqual(
            historial.nombre_captura(momento, personas, 4701.5, "", "18440"),
            "2026-11-24 11h36 · Negociación 18440 · 3A 2N · $4,701.50.png",
        )
        self.assertEqual(
            historial.nombre_captura(momento, {"ADULTOS": 1}, 0, 'a/b:c*?"<>|'), "2026-11-24 11h36 · abc · 1A.png"
        )


class PruebaHistorial(unittest.TestCase):
    def setUp(self):
        self.raiz = tempfile.mkdtemp()
        self.reloj = Reloj(datetime(2026, 11, 24, 11, 36))
        self.h = historial.Historial(self.raiz, self.reloj)

    def tearDown(self):
        shutil.rmtree(self.raiz, ignore_errors=True)

    def test_guardar_actualizar_quitar(self):
        primero = self.h.guardar(registro(100))
        self.h.guardar(registro(250, "https://dt.bitrix24.com/crm/deal/details/2/", "2"))
        resumen = self.h.resumen()
        self.assertEqual(resumen["cantidad"], 2)
        self.assertEqual(resumen["total"], 350)
        self.assertEqual(resumen["hoy_cantidad"], 2)
        self.assertEqual(self.h.duplicado("https://otro/", "1")["id"], primero["id"])
        self.assertIsNotNone(self.h.duplicado("https://DT.bitrix24.com/crm/deal/details/1", ""))
        self.reloj.momento = datetime(2026, 11, 24, 12, 0)
        cambiado = self.h.guardar(registro(300), reemplazar=primero["id"])
        self.assertEqual(cambiado["creado"], primero["creado"])
        self.assertEqual(self.h.resumen()["total"], 550)
        self.assertTrue(self.h.quitar(primero["id"]))
        self.assertFalse(self.h.quitar(primero["id"]))
        self.assertEqual(self.h.resumen()["cantidad"], 1)
        with self.assertRaises(KeyError):
            self.h.guardar(registro(1), reemplazar="no-existe")

    def test_respaldo_y_archivo_danado(self):
        self.h.guardar(registro(100))
        self.h.guardar(registro(200, "https://x.com/2", ""))
        self.assertTrue(os.path.exists(self.h.respaldo))
        with open(self.h.archivo, "w", encoding="utf-8") as archivo:
            archivo.write('{"periodo": "2026-11", "registros": [')  # se cortó a medio guardar
        recuperado = historial.Historial(self.raiz, self.reloj)
        self.assertEqual(recuperado.resumen()["cantidad"], 1)  # versión anterior completa
        self.assertIn("copia de seguridad", recuperado.aviso)
        apartados = [n for n in os.listdir(os.path.dirname(self.h.archivo)) if "dañado" in n]
        self.assertEqual(len(apartados), 1)

    def test_reinicio_el_dia_2_con_excel(self):
        self.h.guardar(registro(100, referencia="Familia López"))
        self.h.guardar(registro(250, "https://x.com/2", ""))
        self.reloj.momento = datetime(2026, 12, 1, 18, 0)  # el 1 sigue siendo noviembre
        self.assertEqual(self.h.resumen()["cantidad"], 2)
        self.reloj.momento = datetime(2026, 12, 2, 8, 0)
        resumen = self.h.resumen()
        self.assertEqual(resumen["cantidad"], 0)
        self.assertEqual(resumen["titulo"], "Diciembre 2026")
        excel = os.path.join(self.raiz, "Respaldos Excel", "Historial 2026-11 Noviembre.xlsx")
        hoja = load_workbook(excel)["Historial"]
        self.assertEqual(hoja.max_row, 5)  # título, encabezados, 2 filas, total
        self.assertEqual(hoja["C3"].value, "Familia López")
        self.assertEqual(hoja["H3"].value, 100)
        self.assertEqual(hoja["E3"].hyperlink.target, "https://dt.bitrix24.com/crm/deal/details/1/")
        copia = os.path.join(self.raiz, "Historial", "Meses anteriores", "historial 2026-11.json")
        with open(copia, encoding="utf-8") as archivo:
            self.assertEqual(len(json.load(archivo)["registros"]), 2)

    def test_si_falla_el_excel_no_se_borra_nada(self):
        self.h.guardar(registro(100))
        self.reloj.momento = datetime(2026, 12, 2, 8, 0)
        with mock.patch.object(historial, "exportar_excel", side_effect=OSError("disco lleno")):
            resumen = self.h.resumen()
        self.assertEqual(resumen["cantidad"], 1)
        self.assertIn("no se reinició", resumen["aviso"])
        self.h.aviso = None
        self.assertEqual(self.h.resumen()["cantidad"], 0)  # al reintentar sí se reinicia

    def test_mes_sin_registros_no_crea_excel(self):
        self.h.resumen()
        self.reloj.momento = datetime(2026, 12, 2, 8, 0)
        self.assertEqual(self.h.resumen()["titulo"], "Diciembre 2026")
        self.assertFalse(os.listdir(self.h.carpeta("respaldos")))

    def test_exportar_y_ruta_captura(self):
        self.h.guardar(registro(100))
        ruta = self.h.exportar()
        self.assertTrue(ruta.endswith("Historial 2026-11 Noviembre (al 24-11-2026 11h36).xlsx"))
        self.assertNotEqual(self.h.exportar(), ruta)  # no pisa el anterior
        captura = self.h.ruta_captura({"ADULTOS": 2}, 100, "Ref")
        self.assertIn(os.path.join("Capturas", "2026-11 Noviembre"), captura)
        open(captura, "w").close()
        self.assertTrue(self.h.ruta_captura({"ADULTOS": 2}, 100, "Ref").endswith(" (2).png"))


class PruebaApiHistorial(unittest.TestCase):
    def setUp(self):
        self.raiz = tempfile.mkdtemp()
        self.api = api.Api()
        self.api._historial = historial.Historial(self.raiz, Reloj(datetime(2026, 11, 24, 11, 36)))
        self.estado = {
            "personas": {"ADULTOS": "3", "NIÑOS": "2", "INFANTES": "0"},
            "servicios": [
                {"base": "BOLETOS NETOS", "subtipo": None, "montos": {"adultos": "$ 1,547.00", "adultos_ninos": "$ 2,522.00",
                 "adultos_ninos_infantes": "$ 0.00", "total": "$ 0.00"}, "incluye": {}},
                {"base": "DISEÑADOR", "subtipo": None, "montos": {"adultos": "$ 491.00", "adultos_ninos": "$ 0.00",
                 "adultos_ninos_infantes": "$ 0.00", "total": "$ 0.00"}, "incluye": {}},
            ],
            "redondear": True, "repartir": False, "con_descuento": False, "intruso": "x" * 10,
        }

    def tearDown(self):
        shutil.rmtree(self.raiz, ignore_errors=True)

    def test_guardar_duplicado_y_reabrir(self):
        enlace = "https://dreamtravel.bitrix24.com/crm/deal/details/18452/"
        previo = self.api.preparar_guardado(self.estado)
        self.assertEqual(previo["pvp"], "$ 4,701.00")
        self.assertEqual(previo["servicios"], ["Boletos", "Diseñador"])
        r = self.api.guardar_negociacion({"enlace": enlace, "referencia": "  Familia   López ", "estado": self.estado})
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["registro"]["referencia"], "Familia López")
        self.assertEqual(r["registro"]["negociacion"], "18452")
        otra = self.api.guardar_negociacion({"enlace": enlace + "?x", "estado": self.estado})
        self.assertFalse(otra["ok"])
        self.assertEqual(otra["duplicado"]["id"], r["registro"]["id"])
        act = self.api.guardar_negociacion({"enlace": enlace, "estado": self.estado, "accion": "actualizar", "id": r["registro"]["id"]})
        self.assertTrue(act["ok"])
        self.assertEqual(self.api.historial_resumen()["cantidad"], 1)
        abierta = self.api.abrir_negociacion(r["registro"]["id"])
        self.assertEqual(abierta["estado"]["personas"]["ADULTOS"], "3")
        self.assertNotIn("intruso", abierta["estado"])
        self.assertTrue(self.api.quitar_negociacion(r["registro"]["id"])["ok"])
        self.assertFalse(self.api.abrir_negociacion(r["registro"]["id"])["ok"])

    def test_rechazos(self):
        self.assertEqual(self.api.guardar_negociacion({"enlace": "nada", "estado": self.estado})["campo"], "enlace")
        vacio = dict(self.estado, servicios=[])
        self.assertIn("$ 0.00", self.api.guardar_negociacion({"enlace": "https://x.com/1", "estado": vacio})["mensaje"])
        self.assertFalse(self.api.guardar_negociacion({"enlace": "https://x.com/1", "estado": None})["ok"])
        grande = dict(self.estado, fecha_viaje="x" * 300_000)
        self.assertFalse(self.api.guardar_negociacion({"enlace": "https://x.com/1", "estado": grande})["ok"])

    def test_resumen_para_pantalla(self):
        self.api.guardar_negociacion({"enlace": "https://x.com/1", "estado": self.estado})
        resumen = self.api.historial_resumen()
        self.assertEqual(resumen["titulo"], "Noviembre 2026")
        self.assertEqual(resumen["reinicio"], "2 de diciembre")
        self.assertEqual(resumen["total"], "$ 4,701.00")
        self.assertEqual(resumen["dias"][0]["titulo"], "Hoy · martes 24 de noviembre")
        fila = resumen["dias"][0]["registros"][0]
        self.assertEqual((fila["hora"], fila["personas"], fila["monto_q"]), ("11:36", "3 adultos, 2 niños", "Q 37,045.00"))

    def test_captura_se_guarda_aunque_falle_el_portapapeles(self):
        import base64, io
        from PIL import Image
        salida = io.BytesIO()
        Image.new("RGB", (4, 4), "white").save(salida, "PNG")
        datos = "data:image/png;base64," + base64.b64encode(salida.getvalue()).decode()
        with mock.patch.object(api, "copiar_imagen_portapapeles", side_effect=OSError("ocupado")):
            r = self.api.copiar_captura(datos, {"estado": self.estado, "referencia": "Familia López"})
        self.assertTrue(r["ok"])
        self.assertFalse(r["copiada"])
        self.assertEqual(r["archivo"], "2026-11-24 11h36 · Familia López · 3A 2N · $4,701.png")
        self.assertTrue(os.path.exists(os.path.join(self.raiz, "Capturas", "2026-11 Noviembre", r["archivo"])))


if __name__ == "__main__":
    unittest.main()
