"""Constantes de la aplicación y reglas del negocio."""

import os
import tempfile

# --- Versión y actualizaciones -------------------------------------------
# El workflow de GitHub reescribe esta línea con la etiqueta de la versión.
VERSION_APP = "1.0.0"

REPO_GITHUB = "alejoco626/Dream_Travel"
NOMBRE_INSTALADOR = "Calculadora_Dream_Travel_Setup.exe"
URL_ULTIMA_VERSION = f"https://api.github.com/repos/{REPO_GITHUB}/releases/latest"
PREFIJO_DESCARGA = f"https://github.com/{REPO_GITHUB}/releases/download/"
CARPETA_ACTUALIZACION = os.path.join(tempfile.gettempdir(), "DreamTravel_Calculadora_Update")
AGENTE_HTTP = "DreamTravel-Calculadora"

# --- Moneda ----------------------------------------------------------------
TIPO_CAMBIO_GTQ = 7.88
# El precio con descuento por pago único en efectivo es PVP / 1.05.
DIVISOR_DESCUENTO_EFECTIVO = 1.05

# --- Servicios ---------------------------------------------------------------
# PVP = costo / proporción. Ej.: con 0.80 el costo representa el 80 % del PVP.
PROPORCION_COSTO = {
    "BOLETOS NETOS": 0.80,
    "DISEÑADOR": 0.95,
    "CIRCUITOS": 0.90,
    "CRUCEROS": 0.90,
    "OPERADOR DIRECTO / JACKELINE": 0.90,
    "ENTRADAS EVENTOS": 1.0,
    "SEGURO DE VIAJE": 0.90,
    "TRASLADOS / SUPERVISOR": 0.90,
    "VISADOS O PERMISOS": 0.80,
    "MISCELANEOS": 0.80,
}

# "total": el monto escrito es el total del grupo (la resta da niños e infantes).
# "persona": el monto escrito es el precio por persona y se multiplica por el grupo.
MODO_TOTAL = "total"
MODO_PERSONA = "persona"
MODO_CAPTURA = {"DISEÑADOR": MODO_PERSONA}

SERVICIOS_FIJOS = ("BOLETOS NETOS", "DISEÑADOR")
SERVICIOS_OPCIONALES = (
    "CIRCUITOS",
    "CRUCEROS",
    "OPERADOR DIRECTO / JACKELINE",
    "ENTRADAS EVENTOS",
    "SEGURO DE VIAJE",
    "TRASLADOS / SUPERVISOR",
    "VISADOS O PERMISOS",
    "MISCELANEOS",
)
# Único servicio que se puede agregar varias veces y en el que niños e
# infantes son opcionales.
SERVICIO_MISCELANEOS = "MISCELANEOS"

NOMBRES_SERVICIO = {
    "BOLETOS NETOS": "Boletos",
    "DISEÑADOR": "Diseñador",
    "CIRCUITOS": "Circuitos",
    "CRUCEROS": "Cruceros",
    "OPERADOR DIRECTO / JACKELINE": "Operador directo / Jackeline",
    "ENTRADAS EVENTOS": "Entradas eventos",
    "SEGURO DE VIAJE": "Seguro de viaje",
    "TRASLADOS / SUPERVISOR": "Traslados / Supervisor",
    "VISADOS O PERMISOS": "Visados o permisos",
    "MISCELANEOS": "Misceláneos",
}

SUBTIPOS_MISCELANEOS = (
    "Misceláneos",
    "Asientos",
    "Equipaje",
    "Decoración luna de miel",
    "Decoración pedida de mano",
    "Decoración cumpleaños",
    "Decoración aniversario",
    "Entradas a tours",
)

# --- Tipos de persona -----------------------------------------------------
ADULTOS = "ADULTOS"
NINOS = "NIÑOS"
INFANTES = "INFANTES"
TIPOS_PERSONA = (ADULTOS, NINOS, INFANTES)
NOMBRES_TIPO = {ADULTOS: "Adultos", NINOS: "Niños", INFANTES: "Infantes"}
EDADES_TIPO = {
    ADULTOS: "mayores de 11 años",
    NINOS: "de 4 a 11 años",
    INFANTES: "de 0 a 3 años",
}

# Cada servicio se captura en tres montos acumulados:
# adultos, adultos + niños y adultos + niños + infantes.
CLAVE_ADULTOS = "adultos"
CLAVE_ADULTOS_NINOS = "adultos_ninos"
CLAVE_ADULTOS_NINOS_INFANTES = "adultos_ninos_infantes"
CLAVES_MONTO = (CLAVE_ADULTOS, CLAVE_ADULTOS_NINOS, CLAVE_ADULTOS_NINOS_INFANTES)
TIPO_DE_CLAVE = {CLAVE_ADULTOS_NINOS: NINOS, CLAVE_ADULTOS_NINOS_INFANTES: INFANTES}
