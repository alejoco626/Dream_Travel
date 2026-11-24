"""Historial de negociaciones y carpeta de la calculadora.

Todo vive en ``Documentos/Calculadora D&T``:

    Historial/historial.json            negociaciones del periodo en curso
    Historial/historial.respaldo.json   copia de la versión anterior (se rehace en cada cambio)
    Historial/Meses anteriores/         el JSON de cada mes cerrado (por si acaso)
    Capturas/2026-11 Noviembre/         capturas con nombre reconocible
    Respaldos Excel/                    el Excel de cada mes cerrado y las exportaciones

Cuidados para no perder datos:
- Se escribe primero un archivo temporal y luego se reemplaza de golpe (os.replace):
  si se va la luz a medio guardar, queda el archivo anterior completo.
- Antes de cada cambio se copia la versión buena a historial.respaldo.json.
- Si el archivo principal está dañado se usa el respaldo; el dañado se aparta, no se borra.
- El día 2 de cada mes empieza un periodo nuevo: antes de vaciar se crea el Excel del mes,
  se vuelve a abrir para comprobar que tiene todas las filas y se guarda el JSON del mes.
  Si algo de eso falla, no se borra nada y se reintenta la próxima vez.
"""

import json
import os
import re
import shutil
import threading
import uuid
from datetime import date, datetime

NOMBRE_CARPETA = "Calculadora D&T"
VERSION_FORMATO = 1
DIA_DE_REINICIO = 2
MAXIMO_REGISTROS = 5000
MAXIMO_ENLACE = 500
MAXIMO_REFERENCIA = 80
MAXIMO_ESTADO = 200_000  # caracteres del JSON de la configuración guardada

MESES = (
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
)
DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")

PATRON_ENLACE = re.compile(r"^https?://[^\s/]+\.[^\s/]+(/\S*)?$", re.IGNORECASE)
PATRON_NEGOCIACION = re.compile(r"/crm/deal/details/(\d+)", re.IGNORECASE)
CARACTERES_PROHIBIDOS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


# ------------------------------------------------------------------ carpetas
def carpeta_documentos():
    """Documentos del usuario (respeta si Windows la movió a OneDrive u otro disco)."""
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            class GUID(ctypes.Structure):
                _fields_ = [
                    ("Data1", wintypes.DWORD),
                    ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD),
                    ("Data4", wintypes.BYTE * 8),
                ]

            # FOLDERID_Documents {FDD39AD0-238F-46AF-ADB4-6C85480369C7}
            carpeta = GUID(0xFDD39AD0, 0x238F, 0x46AF, (wintypes.BYTE * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7))
            ruta = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(carpeta), 0, None, ctypes.byref(ruta)) == 0:
                valor = ruta.value
                ctypes.windll.ole32.CoTaskMemFree(ruta)
                if valor:
                    return valor
        except (AttributeError, OSError, ValueError):
            pass
    return os.path.join(os.path.expanduser("~"), "Documents")


def carpeta_raiz():
    """Carpeta de la calculadora. CALCULADORA_CARPETA_DATOS la cambia (pruebas)."""
    return os.environ.get("CALCULADORA_CARPETA_DATOS") or os.path.join(carpeta_documentos(), NOMBRE_CARPETA)


# ------------------------------------------------------------------ periodos
def periodo_de(dia):
    """Periodo al que pertenece un día: del 2 de un mes al 1 del siguiente."""
    if dia.day >= DIA_DE_REINICIO:
        return f"{dia.year:04d}-{dia.month:02d}"
    anio, mes = (dia.year - 1, 12) if dia.month == 1 else (dia.year, dia.month - 1)
    return f"{anio:04d}-{mes:02d}"


def nombre_periodo(periodo):
    """'2026-11' -> 'Noviembre 2026'."""
    anio, mes = periodo.split("-")
    return f"{MESES[int(mes) - 1]} {anio}"


def carpeta_de_mes(periodo):
    """'2026-11' -> '2026-11 Noviembre'."""
    return f"{periodo} {MESES[int(periodo.split('-')[1]) - 1]}"


def siguiente_reinicio(periodo):
    anio, mes = (int(p) for p in periodo.split("-"))
    anio, mes = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
    return date(anio, mes, DIA_DE_REINICIO)


def texto_dia(dia, hoy):
    base = f"{DIAS[dia.weekday()]} {dia.day} de {MESES[dia.month - 1].lower()}"
    if dia == hoy:
        return f"Hoy · {base}"
    return base[0].upper() + base[1:]


# ------------------------------------------------------------------ textos
def revisar_enlace(texto):
    """Valida el enlace pegado. Devuelve dict con valido, negociacion y un mensaje."""
    enlace = str(texto or "").strip()
    if not enlace:
        return {"valido": False, "enlace": "", "negociacion": "", "tono": "neutro",
                "mensaje": "Pega el enlace de la negociación."}
    if len(enlace) > MAXIMO_ENLACE or not PATRON_ENLACE.match(enlace):
        return {"valido": False, "enlace": enlace, "negociacion": "", "tono": "error",
                "mensaje": "Eso no parece un enlace. Debe empezar con https:// (cópialo de la barra del navegador)."}
    encontrado = PATRON_NEGOCIACION.search(enlace)
    if encontrado:
        return {"valido": True, "enlace": enlace, "negociacion": encontrado.group(1), "tono": "exito",
                "mensaje": f"Negociación {encontrado.group(1)} de Bitrix24"}
    return {"valido": True, "enlace": enlace, "negociacion": "", "tono": "alerta",
            "mensaje": "No parece una negociación de Bitrix24, pero se puede guardar igual."}


def limpiar_referencia(texto):
    return re.sub(r"\s+", " ", str(texto or "")).strip()[:MAXIMO_REFERENCIA]


def nombre_seguro(texto):
    """Texto apto para nombre de archivo de Windows."""
    limpio = CARACTERES_PROHIBIDOS.sub("", str(texto or ""))
    return re.sub(r"\s+", " ", limpio).strip(" .")


def personas_corto(personas):
    letras = (("ADULTOS", "A"), ("NIÑOS", "N"), ("INFANTES", "I"))
    return " ".join(f"{personas.get(t, 0)}{l}" for t, l in letras if personas.get(t, 0))


def personas_largo(personas):
    nombres = (("ADULTOS", "adulto", "adultos"), ("NIÑOS", "niño", "niños"), ("INFANTES", "infante", "infantes"))
    partes = [f"{n} {uno if n == 1 else varios}" for t, uno, varios in nombres if (n := personas.get(t, 0))]
    return ", ".join(partes)


def monto_corto(valor):
    """4701 -> '$4,701'; 4701.5 -> '$4,701.50'."""
    return f"${valor:,.0f}" if abs(valor - round(valor)) < 0.005 else f"${valor:,.2f}"


def nombre_captura(momento, personas, total, referencia="", negociacion=""):
    """'2026-11-24 11h36 · Familia López · 3A 2N · $4,701.png'."""
    partes = [f"{momento:%Y-%m-%d %Hh%M}"]
    etiqueta = nombre_seguro(referencia) or (f"Negociación {negociacion}" if negociacion else "")
    if etiqueta:
        partes.append(etiqueta)
    if personas_corto(personas):
        partes.append(personas_corto(personas))
    if total > 0:
        partes.append(monto_corto(total))
    return nombre_seguro(" · ".join(partes))[:150] + ".png"


def ruta_libre(ruta):
    """Si el archivo ya existe agrega ' (2)', ' (3)'… para no pisarlo."""
    if not os.path.exists(ruta):
        return ruta
    base, extension = os.path.splitext(ruta)
    numero = 2
    while os.path.exists(f"{base} ({numero}){extension}"):
        numero += 1
    return f"{base} ({numero}){extension}"


# ------------------------------------------------------------------ archivos
def escribir_json_seguro(ruta, datos):
    """Escribe a un temporal y lo pone en su lugar de un solo golpe."""
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    temporal = f"{ruta}.{uuid.uuid4().hex[:8]}.tmp"
    try:
        with open(temporal, "w", encoding="utf-8") as archivo:
            json.dump(datos, archivo, ensure_ascii=False, indent=1)
            archivo.flush()
            os.fsync(archivo.fileno())
        os.replace(temporal, ruta)
    finally:
        if os.path.exists(temporal):
            os.remove(temporal)


def leer_json(ruta):
    with open(ruta, encoding="utf-8") as archivo:
        datos = json.load(archivo)
    if not isinstance(datos, dict) or not isinstance(datos.get("registros"), list) or not datos.get("periodo"):
        raise ValueError("formato no reconocido")
    return datos


def exportar_excel(ruta, registros, titulo):
    """Crea el Excel del historial y comprueba que quedó completo. Devuelve la ruta."""
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Historial"
    hoja.append([f"Historial de negociaciones · {titulo}"])
    hoja["A1"].font = Font(bold=True, size=14, color="003D6B")
    encabezados = [
        "Fecha", "Hora", "Referencia", "Negociación", "Enlace de negociación", "Personas",
        "Servicios", "Total PVP ($)", "Total PVP (Q)", "Con descuento", "Total con descuento ($)",
    ]
    hoja.append(encabezados)
    for celda in hoja[2]:
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill("solid", fgColor="003D6B")
        celda.alignment = Alignment(vertical="center")
    for registro in ordenar(registros):
        creado = datetime.fromisoformat(registro["creado"])
        hoja.append([
            creado.date(), creado.strftime("%H:%M"), registro.get("referencia") or "",
            registro.get("negociacion") or "", registro.get("enlace") or "",
            personas_largo(registro.get("personas") or {}), ", ".join(registro.get("servicios") or []),
            registro.get("monto_pvp", 0.0), registro.get("monto_pvp_q", 0.0),
            "Sí" if registro.get("con_descuento") else "No",
            registro.get("monto_descuento", 0.0) if registro.get("con_descuento") else None,
        ])
        fila = hoja.max_row
        hoja.cell(fila, 1).number_format = "dd/mm/yyyy"
        for columna in (8, 9, 11):
            hoja.cell(fila, columna).number_format = "#,##0.00"
        enlace = registro.get("enlace") or ""
        if enlace:
            hoja.cell(fila, 5).hyperlink = enlace
            hoja.cell(fila, 5).font = Font(color="00528F", underline="single")
    total_fila = hoja.max_row + 1
    hoja.cell(total_fila, 7, "TOTAL").font = Font(bold=True)
    for columna, letra in ((8, "H"), (9, "I")):
        celda = hoja.cell(total_fila, columna, f"=SUM({letra}3:{letra}{total_fila - 1})" if registros else 0)
        celda.font = Font(bold=True)
        celda.number_format = "#,##0.00"
    for letra, ancho in zip("ABCDEFGHIJK", (12, 8, 28, 13, 48, 22, 30, 14, 15, 13, 20)):
        hoja.column_dimensions[letra].width = ancho
    hoja.freeze_panes = "A3"

    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    temporal = f"{ruta}.{uuid.uuid4().hex[:8]}.tmp.xlsx"
    try:
        libro.save(temporal)
        comprobado = load_workbook(temporal, read_only=True)
        filas = comprobado["Historial"].max_row
        comprobado.close()
        if filas != len(registros) + 3:  # título + encabezados + filas + total
            raise OSError("El Excel no quedó completo.")
        os.replace(temporal, ruta)
    finally:
        if os.path.exists(temporal):
            os.remove(temporal)
    return ruta


def ordenar(registros):
    return sorted(registros, key=lambda r: r.get("creado", ""))


# ------------------------------------------------------------------ historial
class Historial:
    def __init__(self, raiz=None, ahora=None):
        self._raiz = raiz
        self._ahora = ahora or datetime.now
        self._candado = threading.RLock()
        self.aviso = None  # mensaje para la pantalla si algo no salió bien (reinicio pendiente)

    # -- rutas
    @property
    def raiz(self):
        return self._raiz or carpeta_raiz()

    def ruta(self, *partes):
        return os.path.join(self.raiz, *partes)

    @property
    def archivo(self):
        return self.ruta("Historial", "historial.json")

    @property
    def respaldo(self):
        return self.ruta("Historial", "historial.respaldo.json")

    def carpeta(self, cual="raiz"):
        rutas = {
            "raiz": self.raiz,
            "capturas": self.ruta("Capturas"),
            "respaldos": self.ruta("Respaldos Excel"),
            "historial": self.ruta("Historial"),
        }
        ruta = rutas.get(cual, self.raiz)
        os.makedirs(ruta, exist_ok=True)
        return ruta

    def preparar_carpetas(self):
        for cual in ("historial", "capturas", "respaldos"):
            self.carpeta(cual)

    # -- lectura y escritura
    def _vacio(self, periodo):
        return {"version": VERSION_FORMATO, "periodo": periodo, "registros": []}

    def _leer(self):
        """Lee el historial; si el principal está dañado usa el respaldo y aparta el dañado."""
        if not os.path.exists(self.archivo):
            if os.path.exists(self.respaldo):
                try:
                    return leer_json(self.respaldo)
                except (OSError, ValueError):
                    pass
            return self._vacio(periodo_de(self._ahora().date()))
        try:
            return leer_json(self.archivo)
        except (OSError, ValueError):
            apartado = f"{self.archivo}.dañado-{self._ahora():%Y%m%d-%H%M%S}"
            try:
                shutil.copy2(self.archivo, apartado)
            except OSError:
                pass
            try:
                datos = leer_json(self.respaldo)
                self.aviso = "El historial estaba dañado y se recuperó desde la copia de seguridad."
                return datos
            except (OSError, ValueError):
                self.aviso = "El historial estaba dañado. Se apartó una copia en la carpeta Historial."
                return self._vacio(periodo_de(self._ahora().date()))

    def _escribir(self, datos):
        if os.path.exists(self.archivo):
            try:
                leer_json(self.archivo)  # solo se respalda una versión que se puede leer
                shutil.copy2(self.archivo, self.respaldo)
            except (OSError, ValueError):
                pass
        escribir_json_seguro(self.archivo, datos)

    # -- periodo
    def revisar_periodo(self):
        """Si ya empezó un periodo nuevo: Excel + JSON del mes anterior y luego se vacía."""
        with self._candado:
            datos = self._leer()
            actual = periodo_de(self._ahora().date())
            if datos["periodo"] == actual:
                return datos
            if datos["registros"]:
                anterior = datos["periodo"]
                titulo = nombre_periodo(anterior)
                destino = ruta_libre(self.ruta("Respaldos Excel", f"Historial {carpeta_de_mes(anterior)}.xlsx"))
                try:
                    exportar_excel(destino, datos["registros"], titulo)
                    escribir_json_seguro(
                        ruta_libre(self.ruta("Historial", "Meses anteriores", f"historial {anterior}.json")), datos
                    )
                except Exception as error:  # noqa: BLE001 - nunca se borra si no hay copia
                    self.aviso = (
                        f"No se pudo crear el Excel de {titulo}, así que el historial no se reinició. "
                        f"Se volverá a intentar al abrir la calculadora. ({error})"
                    )
                    return datos
            nuevo = self._vacio(actual)
            self._escribir(nuevo)
            return nuevo

    # -- consultas
    def resumen(self):
        with self._candado:
            datos = self.revisar_periodo()
            hoy = self._ahora().date()
            registros = ordenar(datos["registros"])
            de_hoy = [r for r in registros if r["creado"][:10] == hoy.isoformat()]
            dias = {}
            for registro in reversed(registros):
                dias.setdefault(registro["creado"][:10], []).append(registro)
            return {
                "periodo": datos["periodo"],
                "titulo": nombre_periodo(datos["periodo"]),
                "reinicio": siguiente_reinicio(datos["periodo"]),
                "cantidad": len(registros),
                "total": sum(r.get("monto_pvp", 0.0) for r in registros),
                "total_q": sum(r.get("monto_pvp_q", 0.0) for r in registros),
                "hoy_cantidad": len(de_hoy),
                "hoy_total": sum(r.get("monto_pvp", 0.0) for r in de_hoy),
                "dias": [
                    {
                        "fecha": fecha,
                        "titulo": texto_dia(date.fromisoformat(fecha), hoy),
                        "registros": lista,
                        "total": sum(r.get("monto_pvp", 0.0) for r in lista),
                    }
                    for fecha, lista in dias.items()
                ],
                "aviso": self.aviso,
            }

    def buscar(self, identificador):
        with self._candado:
            return next((r for r in self._leer()["registros"] if r["id"] == identificador), None)

    def duplicado(self, enlace, negociacion):
        with self._candado:
            for registro in self.revisar_periodo()["registros"]:
                if negociacion and registro.get("negociacion") == negociacion:
                    return registro
                if registro.get("enlace", "").rstrip("/").lower() == enlace.rstrip("/").lower():
                    return registro
            return None

    # -- cambios
    def guardar(self, registro, reemplazar=None):
        """Agrega un registro, o reemplaza el de id `reemplazar` conservando su fecha."""
        with self._candado:
            datos = self.revisar_periodo()
            ahora = self._ahora().isoformat(timespec="seconds")
            if reemplazar:
                anterior = next((r for r in datos["registros"] if r["id"] == reemplazar), None)
                if anterior is None:
                    raise KeyError("La negociación ya no está en el historial.")
                registro = {**registro, "id": anterior["id"], "creado": anterior["creado"], "actualizado": ahora}
                datos["registros"] = [registro if r["id"] == reemplazar else r for r in datos["registros"]]
            else:
                if len(datos["registros"]) >= MAXIMO_REGISTROS:
                    raise OverflowError("El historial de este mes está lleno.")
                registro = {**registro, "id": uuid.uuid4().hex, "creado": ahora, "actualizado": ahora}
                datos["registros"].append(registro)
            self._escribir(datos)
            return registro

    def quitar(self, identificador):
        with self._candado:
            datos = self.revisar_periodo()
            antes = len(datos["registros"])
            datos["registros"] = [r for r in datos["registros"] if r["id"] != identificador]
            if len(datos["registros"]) == antes:
                return False
            self._escribir(datos)
            return True

    def exportar(self):
        """Excel del periodo en curso en Respaldos Excel. Devuelve la ruta."""
        with self._candado:
            datos = self.revisar_periodo()
            momento = self._ahora()
            nombre = f"Historial {carpeta_de_mes(datos['periodo'])} (al {momento:%d-%m-%Y %Hh%M}).xlsx"
            return exportar_excel(
                ruta_libre(self.ruta("Respaldos Excel", nombre)), datos["registros"], nombre_periodo(datos["periodo"])
            )

    def ruta_captura(self, personas, total, referencia="", negociacion=""):
        momento = self._ahora()
        carpeta = self.ruta("Capturas", carpeta_de_mes(f"{momento:%Y-%m}"))
        os.makedirs(carpeta, exist_ok=True)
        return ruta_libre(os.path.join(carpeta, nombre_captura(momento, personas, total, referencia, negociacion)))
