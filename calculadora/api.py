"""Puente entre la interfaz (HTML/JS en pywebview) y la lógica en Python.

La página llama estos métodos con ``window.pywebview.api.<método>(...)``. Toda la
lógica del presupuesto vive aquí y en calculo.py / fechas.py; la página solo muestra
lo que estos métodos devuelven, ya con formato.

pywebview expone los métodos públicos de la clase: los atributos internos empiezan
con guion bajo para que no queden a la vista de la página.
"""

import base64
import json
import binascii
import io
import os
import re
import queue
import subprocess
import sys
import threading
import traceback
from datetime import date, datetime

from . import actualizador, fechas, historial, novedades
from .calculo import (
    CLAVE_TOTAL,
    costos_cotizados,
    ServicioCapturado,
    calcular_presupuesto,
    diferencia_total,
    dinero,
    formato_quetzales,
    leer_monto,
    precios_por_persona,
    redondear_cercano,
    tipos_activos,
)
from .config import (
    ADULTOS,
    CLAVE_ADULTOS,
    CLAVE_ADULTOS_NINOS,
    CLAVE_ADULTOS_NINOS_INFANTES,
    CLAVES_MONTO,
    EDADES_TIPO,
    INFANTES,
    MODO_CAPTURA,
    MODO_PERSONA,
    MODO_REPARTO,
    MODO_TOTAL,
    NINOS,
    NOMBRE_APP,
    NOMBRES_SERVICIO,
    NOMBRES_TIPO,
    PESOS_REPARTO,
    PROPORCION_COSTO,
    REPARTIR_POR_DEFECTO,
    SERVICIO_MISCELANEOS,
    SERVICIOS_FIJOS,
    SERVICIOS_OPCIONALES,
    SUBTIPOS_MISCELANEOS,
    TIPO_CAMBIO_GTQ,
    TIPOS_PERSONA,
    VERSION_APP,
)

TITULO_PRESUPUESTO = "PRESUPUESTO PARA ADULTOS Y NIÑOS F1"
SERVICIO_BOLETOS = "BOLETOS NETOS"
MAXIMO_PERSONAS = 99
TAMANO_MAXIMO_CAPTURA = 40 * 1024 * 1024  # base64 de la captura; más que esto se rechaza

ENCABEZADOS_DESGLOSE = (
    "Concepto",
    "Costo neto total",
    "Costo neto por persona",
    "PVP total",
    "PVP por persona",
)

ARCHIVO_ERRORES = os.path.join(
    os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "DreamTravel", "calculadora_error.log"
)


def registrar_error(texto):
    """Guarda el error para poder diagnosticarlo (el .exe no tiene consola)."""
    try:
        os.makedirs(os.path.dirname(ARCHIVO_ERRORES), exist_ok=True)
        with open(ARCHIVO_ERRORES, "a", encoding="utf-8") as archivo:
            archivo.write(f"--- {datetime.now():%Y-%m-%d %H:%M:%S} · versión {VERSION_APP}\n{texto}\n")
    except OSError:
        pass


def con_registro(metodo):
    """Si un método falla, el error queda en el registro y la página recibe un aviso."""

    def envoltura(*args, **kwargs):
        try:
            return metodo(*args, **kwargs)
        except Exception:  # la página nunca debe quedarse sin respuesta
            registrar_error(traceback.format_exc())
            return {"ok": False, "mensaje": "Ocurrió un error inesperado. Quedó registrado."}

    envoltura.__name__ = metodo.__name__
    envoltura.__doc__ = metodo.__doc__
    return envoltura


# ------------------------------------------------------------------ lectura
def _entero(valor):
    try:
        numero = int(str(valor).strip() or "0")
    except (TypeError, ValueError):
        return 0
    return min(max(numero, 0), MAXIMO_PERSONAS)


def leer_cantidades(personas):
    personas = personas or {}
    return {tipo: _entero(personas.get(tipo, 0)) for tipo in TIPOS_PERSONA}


def incluye_tipo(servicio, tipo, activos):
    """Niños e infantes cuentan si están activos y, en Misceláneos, si están marcados."""
    if tipo == ADULTOS:
        return True
    if tipo not in activos:
        return False
    if servicio.get("base") != SERVICIO_MISCELANEOS:
        return True
    return bool((servicio.get("incluye") or {}).get(tipo))


class MontoInvalido(ValueError):
    def __init__(self, indice, clave, nombre):
        super().__init__("monto no válido")
        self.indice = indice
        self.clave = clave
        self.nombre = nombre


def nombre_servicio(servicio):
    base = servicio["base"]
    if base == SERVICIO_MISCELANEOS:
        subtipo = str(servicio.get("subtipo") or "").strip()
        if subtipo in SUBTIPOS_MISCELANEOS:
            return subtipo
    return NOMBRES_SERVICIO[base]


def capturar_servicio(indice, servicio, activos, cantidades=None, repartir=False):
    """Convierte la fila que manda la página en un ServicioCapturado. Lanza MontoInvalido."""
    base = servicio.get("base")
    if base not in PROPORCION_COSTO:
        raise ValueError(f"servicio desconocido: {base!r}")
    incluidos = frozenset(t for t in TIPOS_PERSONA if incluye_tipo(servicio, t, activos))
    if repartir:
        return capturar_total(indice, servicio, incluidos, cantidades or {})
    usados = {
        CLAVE_ADULTOS: True,
        CLAVE_ADULTOS_NINOS: NINOS in incluidos,
        CLAVE_ADULTOS_NINOS_INFANTES: INFANTES in incluidos,
    }
    textos = servicio.get("montos") or {}
    montos = {}
    for clave, se_usa in usados.items():
        if not se_usa:
            montos[clave] = 0.0
            continue
        try:
            montos[clave] = leer_monto(str(textos.get(clave, "")))
        except ValueError:
            raise MontoInvalido(indice, clave, nombre_servicio(servicio)) from None
    return ServicioCapturado(
        nombre_servicio(servicio),
        PROPORCION_COSTO[base],
        MODO_CAPTURA.get(base, MODO_TOTAL),
        montos,
        incluidos,
    )


def capturar_total(indice, servicio, incluidos, cantidades):
    """Repartir monto: un solo total por servicio. El Diseñador se escribe por persona y
    se multiplica por todas las personas incluidas (niños e infantes también)."""
    base = servicio["base"]
    try:
        monto = leer_monto(str((servicio.get("montos") or {}).get(CLAVE_TOTAL, "")))
    except ValueError:
        raise MontoInvalido(indice, CLAVE_TOTAL, nombre_servicio(servicio)) from None
    if MODO_CAPTURA.get(base) == MODO_PERSONA:
        monto *= sum(cantidades.get(tipo, 0) for tipo in incluidos)
    return ServicioCapturado(
        nombre_servicio(servicio), PROPORCION_COSTO[base], MODO_REPARTO, {CLAVE_TOTAL: monto}, incluidos
    )


def clave_columna_grupo(activos):
    """Columna de montos que suma a todas las personas del grupo."""
    if INFANTES in activos:
        return CLAVE_ADULTOS_NINOS_INFANTES
    if NINOS in activos:
        return CLAVE_ADULTOS_NINOS
    return CLAVE_ADULTOS


def monto_para_reservar(servicios, activos, repartir=False):
    """Precio bruto de los boletos para todo el grupo: la columna de boletos que suma a
    todas las personas (o el total, al repartir), dividida entre su proporción de costo
    (0.80). None si no es válido."""
    boletos = next((s for s in servicios if s.get("base") == SERVICIO_BOLETOS), None)
    if boletos is None:
        return 0.0
    clave = CLAVE_TOTAL if repartir else clave_columna_grupo(activos)
    try:
        return leer_monto(str((boletos.get("montos") or {}).get(clave, ""))) / PROPORCION_COSTO[
            SERVICIO_BOLETOS
        ]
    except ValueError:
        return None


def hoy():
    return date.today()


def resultado_pago(estado):
    if estado.get("no_reembolsable"):
        return {"visible": False, "texto": "", "tono": "neutro", "campo": None}
    resultado = fechas.revisar_fechas(
        str(estado.get("fecha_viaje") or ""), str(estado.get("fecha_cancelacion") or ""), hoy()
    )
    resultado["visible"] = True
    return resultado


def filas_desglose(presupuesto):
    grupos = []
    for nombre, renglones in presupuesto.servicios:
        con_monto = [renglon for renglon in renglones if renglon.costo_total]
        if not con_monto:
            continue
        grupos.append(
            {
                "nombre": nombre,
                "renglones": [
                    {
                        "concepto": f"{NOMBRES_TIPO[r.tipo]} ({r.cantidad})",
                        "valores": [dinero(v) for v in r.valores],
                    }
                    for r in con_monto
                ],
            }
        )
    return {
        "encabezados": list(ENCABEZADOS_DESGLOSE),
        "grupos": grupos,
        "totales": [dinero(v) for v in presupuesto.totales_columnas] if grupos else [],
    }


def calcular_estado(estado):
    """Calcula todo lo que muestra la pantalla a partir de lo que escribió el usuario.

    Siempre devuelve el monto para reservar y la fecha de pago; si un monto no es válido
    o no hay personas, devuelve ``ok: False`` con el motivo y el campo a corregir.
    """
    estado = estado or {}
    cantidades = leer_cantidades(estado.get("personas"))
    activos = tipos_activos(cantidades)
    servicios = [s for s in (estado.get("servicios") or []) if isinstance(s, dict)]
    redondear = bool(estado.get("redondear", True))
    repartir = bool(estado.get("repartir", False))

    reserva = monto_para_reservar(servicios, activos, repartir)
    resultado = {
        "ok": True,
        "activos": activos,
        "cantidades": cantidades,
        "monto_reserva": "—" if reserva is None else dinero(reserva),
        "pago": resultado_pago(estado),
    }

    if sum(cantidades.values()) < 1:
        resultado.update(
            ok=False,
            mensaje="Debe haber al menos una persona en el presupuesto.",
            campo={"tipo": "personas"},
        )
        return resultado

    capturados = []
    for indice, servicio in enumerate(servicios):
        try:
            capturados.append(capturar_servicio(indice, servicio, activos, cantidades, repartir))
        except MontoInvalido as error:
            resultado.update(
                ok=False,
                mensaje=f"El valor ingresado en {error.nombre} no es válido.",
                campo={"tipo": "monto", "fila": error.indice, "clave": error.clave},
            )
            return resultado

    presupuesto = calcular_presupuesto(capturados, cantidades)
    resultado["avisos"] = avisos_de_cotizacion(capturados, cantidades)
    precios = precios_por_persona(presupuesto, cantidades, redondear, cuadrar=bool(estado.get("repartir")))

    resultado["por_persona"] = {
        tipo: {
            "cantidad": f"× {cantidades[tipo]}",
            "pvp": dinero(precios.pvp[tipo]),
            "pvp_q": formato_quetzales(precios.pvp_q[tipo]),
            "pvp_total": f"Total {dinero(precios.subtotal_pvp[tipo])}",
            "descuento": dinero(precios.descuento[tipo]),
            "descuento_q": formato_quetzales(precios.descuento_q[tipo]),
            "descuento_total": f"Total {dinero(precios.subtotal_descuento[tipo])}",
        }
        for tipo in TIPOS_PERSONA
    }
    resultado["totales"] = {
        "pvp": dinero(precios.total_pvp),
        "pvp_q": formato_quetzales(precios.total_pvp_q),
        "descuento": dinero(precios.total_descuento),
        "descuento_q": formato_quetzales(precios.total_descuento_q),
    }
    resultado["ajuste"] = calcular_ajuste(precios.pvp[ADULTOS], estado.get("ajuste_nuevo"), cantidades, redondear)
    resultado["desglose"] = filas_desglose(presupuesto)
    resultado["reparto"] = reparto_por_servicio(presupuesto)
    return resultado


NOMBRES_AVISO = {
    ADULTOS: ("adulto", "adultos"),
    NINOS: ("niño", "niños"),
    INFANTES: ("infante", "infantes"),
}
COLUMNA_DE_TIPO = {NINOS: CLAVE_ADULTOS_NINOS, INFANTES: CLAVE_ADULTOS_NINOS_INFANTES}


def avisos_de_cotizacion(capturados, cantidades):
    """Cotizaciones atípicas al restar (sin "Repartir monto"): una cotización con más
    personas que sale más barata que la anterior, o un menor que paga más que un mayor."""
    avisos = []
    for indice, servicio in enumerate(capturados):
        if servicio.modo == MODO_REPARTO:
            continue
        tipos = [t for t in TIPOS_PERSONA if t in servicio.tipos_incluidos and cantidades.get(t, 0) > 0]
        columnas = [CLAVE_ADULTOS] + [COLUMNA_DE_TIPO[t] for t in tipos if t != ADULTOS]
        if any(servicio.montos.get(columna, 0) <= 0 for columna in columnas):
            continue  # todavía falta llenar alguna cotización de este servicio
        crudos = costos_cotizados(servicio, cantidades)
        negativos = [t for t in tipos if crudos[t] < -0.005]
        mensaje = tipo_marcado = None
        if negativos:
            tipo_marcado = negativos[0]
            plural = NOMBRES_AVISO[tipo_marcado][1]
            mensaje = (
                f"En {servicio.nombre}, la cotización con {plural} salió más baja que la anterior: "
                f"se tomó $ 0.00 para los {plural}."
            )
        else:
            por_persona = {t: crudos[t] / cantidades[t] for t in tipos}
            for mayor, menor in ((ADULTOS, NINOS), (NINOS, INFANTES), (ADULTOS, INFANTES)):
                if mayor in por_persona and menor in por_persona and por_persona[menor] > por_persona[mayor] + 0.005:
                    tipo_marcado = menor
                    mensaje = (
                        f"En {servicio.nombre}, a cada {NOMBRES_AVISO[menor][0]} le toca "
                        f"{dinero(por_persona[menor])} y a cada {NOMBRES_AVISO[mayor][0]} "
                        f"{dinero(por_persona[mayor])}."
                    )
                    break
        if mensaje:
            avisos.append(
                {
                    "fila": indice,
                    "clave": COLUMNA_DE_TIPO.get(tipo_marcado, CLAVE_ADULTOS),
                    "mensaje": f"{mensaje} Revisa las cotizaciones o enciende Repartir monto.",
                }
            )
    return avisos


def reparto_por_servicio(presupuesto):
    """Costo neto por persona de cada tipo, por servicio (lo que muestran las etiquetas)."""
    return [
        {renglon.tipo: dinero(renglon.costo_persona) for renglon in renglones if renglon.cantidad}
        for _nombre, renglones in presupuesto.servicios
    ]


def calcular_ajuste(precio_actual, texto_nuevo, cantidades, redondear):
    """Precio adulto actual y diferencia total contra el precio nuevo que se quiere ofrecer."""
    ajuste = {"actual": dinero(precio_actual), "diferencia": "—"}
    texto_nuevo = str(texto_nuevo or "").strip()
    if not texto_nuevo:
        return ajuste
    try:
        precio_nuevo = leer_monto(texto_nuevo)
    except ValueError:
        return ajuste
    diferencia = diferencia_total(precio_actual, precio_nuevo, cantidades)
    if redondear:
        diferencia = redondear_cercano(diferencia)
    ajuste["diferencia"] = dinero(diferencia)
    return ajuste


def formatear_monto(texto):
    """'1000' -> '$ 1,000.00'. Si no es un número, devuelve el texto tal cual y valido=False."""
    try:
        return {"valido": True, "texto": dinero(leer_monto(str(texto or "")))}
    except ValueError:
        return {"valido": False, "texto": str(texto or "")}


def convertir_moneda(texto, origen="GTQ"):
    """Conversión rápida con el tipo de cambio de config, en los dos sentidos.

    origen="GTQ": 'Q 7,880' -> {'valido': True, 'resultado': '$ 1,000.00'}
    origen="USD": '$ 100'   -> {'valido': True, 'resultado': 'Q 788.00'}
    """
    a_quetzales = str(origen).upper() == "USD"
    formato = formato_quetzales if a_quetzales else dinero
    limpio = re.sub(r"[QqGgTt]", "", str(texto or ""))
    if not limpio.strip():
        return {"valido": True, "resultado": formato(0)}
    try:
        monto = leer_monto(limpio)
    except ValueError:
        return {"valido": False, "resultado": "—"}
    return {"valido": True, "resultado": formato(monto * TIPO_CAMBIO_GTQ if a_quetzales else monto / TIPO_CAMBIO_GTQ)}


def convertir_quetzales(texto):
    """'Q 1,000' -> {'valido': True, 'dolares': '$ 126.90'} (atajo de Q -> $)."""
    respuesta = convertir_moneda(texto, "GTQ")
    return {"valido": respuesta["valido"], "dolares": respuesta["resultado"]}


# ---------------------------------------------------------------- historial
CLAVES_ESTADO = (
    "personas", "servicios", "redondear", "repartir", "no_reembolsable",
    "fecha_viaje", "fecha_cancelacion", "ajuste_nuevo", "con_descuento",
)


def limpiar_estado(estado):
    """Solo lo necesario para volver a cargar la cotización, con un tamaño razonable."""
    if not isinstance(estado, dict):
        raise ValueError("La configuración llegó vacía.")
    limpio = {clave: estado[clave] for clave in CLAVES_ESTADO if clave in estado}
    if len(json.dumps(limpio, ensure_ascii=False)) > historial.MAXIMO_ESTADO:
        raise ValueError("La configuración es demasiado grande para guardarla.")
    return limpio


def _numero(texto):
    try:
        return leer_monto(re.sub(r"[Qq]", "", str(texto or "")))
    except ValueError:
        return 0.0


def servicios_con_monto(estado):
    nombres = []
    for servicio in estado.get("servicios") or []:
        if not isinstance(servicio, dict) or servicio.get("base") not in PROPORCION_COSTO:
            continue
        if any(_numero(valor) > 0 for valor in (servicio.get("montos") or {}).values()):
            nombre = nombre_servicio(servicio)
            if nombre not in nombres:
                nombres.append(nombre)
    return nombres


def resumen_cotizacion(estado):
    """Montos y textos de la cotización actual, para guardarla o nombrar su captura."""
    resultado = calcular_estado(estado)
    if not resultado.get("ok"):
        return {"ok": False, "mensaje": resultado.get("mensaje") or "Revisa la cotización antes de guardarla."}
    totales = resultado["totales"]
    cantidades = resultado["cantidades"]
    return {
        "ok": True,
        "personas": cantidades,
        "personas_texto": historial.personas_largo(cantidades),
        "servicios": servicios_con_monto(estado),
        "monto_pvp": _numero(totales["pvp"]),
        "monto_pvp_q": _numero(totales["pvp_q"]),
        "monto_descuento": _numero(totales["descuento"]),
        "monto_descuento_q": _numero(totales["descuento_q"]),
        "pvp": totales["pvp"],
        "pvp_q": totales["pvp_q"],
        "descuento": totales["descuento"],
        "descuento_q": totales["descuento_q"],
    }


def registro_para_pantalla(registro):
    creado = datetime.fromisoformat(registro["creado"])
    return {
        "id": registro["id"],
        "hora": creado.strftime("%H:%M"),
        "fecha": creado.strftime("%d/%m/%Y"),
        "referencia": registro.get("referencia") or "",
        "negociacion": registro.get("negociacion") or "",
        "enlace": registro.get("enlace") or "",
        "personas": historial.personas_largo(registro.get("personas") or {}),
        "monto": dinero(registro.get("monto_pvp", 0.0)),
        "monto_q": formato_quetzales(registro.get("monto_pvp_q", 0.0)),
        "con_descuento": bool(registro.get("con_descuento")),
        "descuento": dinero(registro.get("monto_descuento", 0.0)),
        "descuento_q": formato_quetzales(registro.get("monto_descuento_q", 0.0)),
    }


def resumen_historial(datos):
    return {
        "ok": True,
        "titulo": datos["titulo"],
        "reinicio": f"{datos['reinicio'].day} de {historial.MESES[datos['reinicio'].month - 1].lower()}",
        "cantidad": datos["cantidad"],
        "total": dinero(datos["total"]),
        "total_q": formato_quetzales(datos["total_q"]),
        "hoy_cantidad": datos["hoy_cantidad"],
        "hoy_total": dinero(datos["hoy_total"]),
        "dias": [
            {
                "titulo": dia["titulo"],
                "cantidad": len(dia["registros"]),
                "total": dinero(dia["total"]),
                "registros": [registro_para_pantalla(r) for r in dia["registros"]],
            }
            for dia in datos["dias"]
        ],
        "aviso": datos["aviso"],
    }


def abrir_en_windows(destino):
    if hasattr(os, "startfile"):
        os.startfile(destino)  # noqa: S606 - ruta o enlace ya validados
    else:
        import webbrowser

        webbrowser.open(destino)


def configuracion_inicial():
    """Lo que la página necesita para dibujarse: textos, servicios y novedades."""
    return {
        "version": VERSION_APP,
        "nombre_app": NOMBRE_APP,
        "titulo": TITULO_PRESUPUESTO,
        "tipos": [
            {"clave": tipo, "nombre": NOMBRES_TIPO[tipo], "edad": EDADES_TIPO[tipo]}
            for tipo in TIPOS_PERSONA
        ],
        "servicios": {
            base: {
                "nombre": NOMBRES_SERVICIO[base],
                "por_persona": MODO_CAPTURA.get(base) == MODO_PERSONA,
                "fijo": base in SERVICIOS_FIJOS,
            }
            for base in SERVICIOS_FIJOS + SERVICIOS_OPCIONALES
        },
        "fijos": list(SERVICIOS_FIJOS),
        "opcionales": list(SERVICIOS_OPCIONALES),
        "miscelaneos": SERVICIO_MISCELANEOS,
        "subtipos_miscelaneos": list(SUBTIPOS_MISCELANEOS),
        "claves_monto": list(CLAVES_MONTO),
        "repartir_por_defecto": REPARTIR_POR_DEFECTO,
        "pesos_reparto": {tipo: PESOS_REPARTO[tipo] for tipo in TIPOS_PERSONA},
        "tipo_cambio": TIPO_CAMBIO_GTQ,
    }


def notas_de_novedades():
    """Notas de la versión si hay que mostrarlas ahora (solo en el programa instalado)."""
    if not getattr(sys, "frozen", False):
        return None
    notas = novedades.notas_a_mostrar(
        VERSION_APP,
        novedades.ARGUMENTO_ACTUALIZADO in sys.argv,
        novedades.leer_version_vista(),
    )
    novedades.guardar_version_vista(VERSION_APP)
    if not notas:
        return None
    return {
        "version": VERSION_APP,
        "secciones": [
            {"titulo": titulo, "vineta": vineta, "elementos": list(notas.get(clave) or [])}
            for clave, titulo, vineta in novedades.SECCIONES
            if notas.get(clave)
        ],
    }


def imagen_desde_base64(datos):
    """Decodifica la captura PNG que manda la página ('data:image/png;base64,...')."""
    from PIL import Image

    texto = str(datos or "")
    if len(texto) > TAMANO_MAXIMO_CAPTURA:
        raise ValueError("La captura es demasiado grande.")
    if "," in texto and texto.startswith("data:"):
        texto = texto.split(",", 1)[1]
    try:
        crudo = base64.b64decode(texto, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("La captura llegó dañada.") from None
    imagen = Image.open(io.BytesIO(crudo))
    imagen.load()
    return imagen


MAXIMO_TEXTO_COPIADO = 60


def copiar_texto_portapapeles(texto):
    import win32clipboard

    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(texto, win32clipboard.CF_UNICODETEXT)
    finally:
        win32clipboard.CloseClipboard()


def copiar_imagen_portapapeles(imagen):
    import win32clipboard

    salida = io.BytesIO()
    imagen.convert("RGB").save(salida, "BMP")
    datos = salida.getvalue()[14:]  # CF_DIB no lleva la cabecera de archivo BMP
    salida.close()
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, datos)
    finally:
        win32clipboard.CloseClipboard()


class DescargaEnCurso:
    """Estado de la descarga de una actualización, consultado por la página."""

    def __init__(self, info):
        self.info = info
        self.cola = queue.Queue()
        self.progreso = 0.0
        self.resultado = None  # ("listo", ruta) o ("error", mensaje)
        threading.Thread(target=self._descargar, daemon=True).start()

    def _descargar(self):
        # Cualquier falla (también las de red que no son OSError) debe llegar a la pantalla;
        # si el hilo muriera en silencio, la barra se quedaría quieta para siempre.
        try:
            actualizador.hilo_descargar(self.info, self.cola)
        except Exception as error:  # noqa: BLE001
            registrar_error(traceback.format_exc())
            self.cola.put(("error", str(error) or error.__class__.__name__))

    def estado(self):
        while self.resultado is None:
            try:
                mensaje = self.cola.get_nowait()
            except queue.Empty:
                break
            if mensaje[0] == "progreso":
                if mensaje[2]:
                    self.progreso = min(1.0, mensaje[1] / mensaje[2])
            else:
                self.resultado = mensaje
        if self.resultado is None:
            return {"estado": "descargando", "progreso": self.progreso}
        if self.resultado[0] == "error":
            return {"estado": "error", "mensaje": f"No se pudo descargar la actualización.\n{self.resultado[1]}"}
        return {"estado": "listo", "progreso": 1.0}


class Api:
    """Métodos que la página puede llamar."""

    def __init__(self):
        self._ventana = None
        self._listo = threading.Event()
        self._info_actualizacion = None
        self._descarga = None
        self._candado = threading.Lock()
        self._historial = historial.Historial()
        self._ultima_captura = None

    def _asignar_ventana(self, ventana):
        self._ventana = ventana

    # -- arranque -----------------------------------------------------------
    @con_registro
    def inicio(self):
        configuracion = configuracion_inicial()
        configuracion["novedades"] = notas_de_novedades()
        try:  # la carpeta y el cambio de mes nunca deben impedir que abra la calculadora
            self._historial.preparar_carpetas()
            configuracion["historial"] = resumen_historial(self._historial.resumen())
        except Exception:
            registrar_error(traceback.format_exc())
            configuracion["historial"] = None
        return configuracion

    @con_registro
    def listo(self):
        """La página avisa que terminó de dibujarse (lo usa la prueba de arranque)."""
        self._listo.set()
        return True

    # -- cálculo ------------------------------------------------------------
    @con_registro
    def calcular(self, estado):
        return calcular_estado(estado)

    @con_registro
    def formatear_monto(self, texto):
        return formatear_monto(texto)

    # -- captura ------------------------------------------------------------
    @con_registro
    def copiar_captura(self, datos_png, info=None):
        """Copia la captura al portapapeles y la guarda en Capturas con un nombre claro."""
        try:
            imagen = imagen_desde_base64(datos_png)
        except Exception as error:  # imagen dañada
            registrar_error(traceback.format_exc())
            return {"ok": False, "mensaje": f"No se pudo tomar la captura.\n{error}"}
        copiada = guardada = None
        try:
            copiar_imagen_portapapeles(imagen)
            copiada = True
        except Exception:  # portapapeles de Windows ocupado
            registrar_error(traceback.format_exc())
        try:
            info = info if isinstance(info, dict) else {}
            resumen = resumen_cotizacion(info.get("estado") or {})
            ruta = self._historial.ruta_captura(
                resumen.get("personas") or {},
                resumen.get("monto_pvp", 0.0) if resumen.get("ok") else 0.0,
                historial.limpiar_referencia(info.get("referencia")),
                re.sub(r"\D", "", str(info.get("negociacion") or "")),
            )
            imagen.convert("RGB").save(ruta, "PNG")
            guardada = os.path.basename(ruta)
            self._ultima_captura = ruta
        except Exception:  # carpeta sin permiso, disco lleno...
            registrar_error(traceback.format_exc())
        if not copiada and not guardada:
            return {"ok": False, "mensaje": "No se pudo copiar ni guardar la captura."}
        return {"ok": True, "copiada": bool(copiada), "archivo": guardada}

    @con_registro
    def convertir_moneda(self, texto, origen="GTQ"):
        """Conversión rápida Q <-> $ (no afecta el presupuesto)."""
        return convertir_moneda(texto, origen)

    @con_registro
    def copiar_texto(self, texto):
        """Copia una cifra de la pantalla ("$ 1,161.00", "Q 9,149.00")."""
        texto = str(texto or "").strip()
        if not texto or len(texto) > MAXIMO_TEXTO_COPIADO:
            return {"ok": False, "mensaje": "No hay nada que copiar."}
        try:
            copiar_texto_portapapeles(texto)
        except Exception as error:  # portapapeles de Windows ocupado
            registrar_error(traceback.format_exc())
            return {"ok": False, "mensaje": f"No se pudo copiar.\n{error}"}
        return {"ok": True}

    # -- historial ----------------------------------------------------------
    @con_registro
    def historial_resumen(self):
        return resumen_historial(self._historial.resumen())

    @con_registro
    def revisar_enlace(self, texto):
        return historial.revisar_enlace(texto)

    @con_registro
    def preparar_guardado(self, estado):
        return resumen_cotizacion(estado)

    @con_registro
    def guardar_negociacion(self, datos):
        """datos: enlace, referencia, estado, accion ("comprobar" | "nuevo" | "actualizar"), id."""
        datos = datos if isinstance(datos, dict) else {}
        enlace = historial.revisar_enlace(datos.get("enlace"))
        if not enlace["valido"]:
            return {"ok": False, "campo": "enlace", "mensaje": enlace["mensaje"]}
        try:
            estado = limpiar_estado(datos.get("estado"))
        except ValueError as error:
            return {"ok": False, "mensaje": str(error)}
        resumen = resumen_cotizacion(estado)
        if not resumen["ok"]:
            return resumen
        if resumen["monto_pvp"] <= 0:
            return {"ok": False, "mensaje": "La cotización está en $ 0.00: escribe los montos antes de guardarla."}
        accion = datos.get("accion") or "comprobar"
        if accion == "comprobar":
            repetido = self._historial.duplicado(enlace["enlace"], enlace["negociacion"])
            if repetido:
                return {
                    "ok": False,
                    "duplicado": {
                        **registro_para_pantalla(repetido),
                        "hoy": repetido["creado"][:10] == datetime.now().date().isoformat(),
                    },
                    "nuevo_monto": resumen["pvp"],
                }
        con_descuento = bool(estado.get("con_descuento"))
        registro = {
            "enlace": enlace["enlace"],
            "negociacion": enlace["negociacion"],
            "referencia": historial.limpiar_referencia(datos.get("referencia")),
            "personas": resumen["personas"],
            "servicios": resumen["servicios"],
            "monto_pvp": resumen["monto_pvp"],
            "monto_pvp_q": resumen["monto_pvp_q"],
            "con_descuento": con_descuento,
            "monto_descuento": resumen["monto_descuento"],
            "monto_descuento_q": resumen["monto_descuento_q"],
            "estado": estado,
        }
        try:
            guardado = self._historial.guardar(registro, datos.get("id") if accion == "actualizar" else None)
        except (KeyError, OverflowError) as error:
            return {"ok": False, "mensaje": str(error).strip("'\"")}
        return {"ok": True, "registro": registro_para_pantalla(guardado), "actualizado": accion == "actualizar"}

    @con_registro
    def abrir_negociacion(self, identificador):
        registro = self._historial.buscar(str(identificador or ""))
        if registro is None:
            return {"ok": False, "mensaje": "Esa negociación ya no está en el historial."}
        return {
            "ok": True,
            "id": registro["id"],
            "enlace": registro.get("enlace") or "",
            "negociacion": registro.get("negociacion") or "",
            "referencia": registro.get("referencia") or "",
            "estado": registro.get("estado") or {},
        }

    @con_registro
    def quitar_negociacion(self, identificador):
        if not self._historial.quitar(str(identificador or "")):
            return {"ok": False, "mensaje": "Esa negociación ya no está en el historial."}
        return {"ok": True}

    @con_registro
    def exportar_historial(self):
        try:
            ruta = self._historial.exportar()
        except Exception as error:  # Excel abierto, sin permiso...
            registrar_error(traceback.format_exc())
            return {"ok": False, "mensaje": f"No se pudo crear el Excel.\n{error}"}
        self._mostrar_en_carpeta(ruta)
        return {"ok": True, "archivo": os.path.basename(ruta)}

    @con_registro
    def abrir_enlace(self, enlace):
        revisado = historial.revisar_enlace(enlace)
        if not revisado["valido"]:
            return {"ok": False, "mensaje": "El enlace no es válido."}
        abrir_en_windows(revisado["enlace"])
        return {"ok": True}

    @con_registro
    def abrir_carpeta(self, cual="raiz"):
        if cual == "ultima_captura" and self._ultima_captura and os.path.exists(self._ultima_captura):
            self._mostrar_en_carpeta(self._ultima_captura)
            return {"ok": True}
        abrir_en_windows(self._historial.carpeta(cual if cual != "ultima_captura" else "capturas"))
        return {"ok": True}

    def _mostrar_en_carpeta(self, ruta):
        if os.name == "nt":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(ruta)])  # noqa: S603,S607
        else:
            abrir_en_windows(os.path.dirname(ruta))

    # -- errores de la página ------------------------------------------------
    def registrar_error_pagina(self, texto):
        registrar_error(f"Error en la página:\n{str(texto)[:4000]}")
        return True

    # -- actualización ------------------------------------------------------
    @con_registro
    def buscar_actualizacion(self):
        if not getattr(sys, "frozen", False):
            return None  # solo el programa instalado se actualiza
        actualizador.limpiar_descargas()
        try:
            info = actualizador.consultar_ultima_version()
        except (OSError, ValueError, AttributeError):
            return None
        if not info or not actualizador.es_mas_nueva(info["version"], VERSION_APP):
            return None
        self._info_actualizacion = info
        return {"version": info["version"], "actual": VERSION_APP}

    @con_registro
    def descargar_actualizacion(self):
        with self._candado:
            if self._info_actualizacion is None:
                return {"estado": "error", "mensaje": "No hay una actualización pendiente."}
            if self._descarga is None:
                self._descarga = DescargaEnCurso(self._info_actualizacion)
            return self._descarga.estado()

    @con_registro
    def estado_descarga(self):
        with self._candado:
            if self._descarga is None:
                return {"estado": "error", "mensaje": "La descarga no ha empezado."}
            estado = self._descarga.estado()
            if estado["estado"] == "error":
                self._descarga = None  # se puede volver a intentar
            return estado

    @con_registro
    def instalar_actualizacion(self):
        with self._candado:
            descarga = self._descarga
        if descarga is None or descarga.resultado is None or descarga.resultado[0] != "listo":
            return {"ok": False, "mensaje": "La actualización todavía no se ha descargado."}
        try:
            actualizador.lanzar_instalador(descarga.resultado[1], descarga.info["sha256"])
        except (OSError, ValueError) as error:
            return {"ok": False, "mensaje": f"No se pudo instalar la actualización.\n{error}"}
        if self._ventana is not None:
            threading.Timer(0.2, self._ventana.destroy).start()
        # Red de seguridad: el instalador necesita el .exe libre. Si algo retiene el
        # proceso después de cerrar la ventana, se termina igual.
        temporizador = threading.Timer(4.0, os._exit, args=(0,))
        temporizador.daemon = True
        temporizador.start()
        return {"ok": True}
