"""Notas que se muestran una sola vez, al abrir la calculadora recién actualizada.

Antes de publicar una versión, agrega aquí su entrada con el mismo número del release.
Lo "nuevo" se muestra con punto negro (●), los "cambios" con guion y las
"correcciones" con punto (•); una sección vacía no aparece. Si la versión no tiene entrada, no se muestra ninguna ventana.
"""

import os

from .actualizador import es_mas_nueva

# (clave, título, viñeta) en el orden en que aparecen en la ventana.
SECCIONES = (
    ("nuevo", "Nuevo", "●"),
    ("cambios", "Cambios", "-"),
    ("correcciones", "Correcciones", "•"),
)

NOVEDADES = {
    "1.0.19": {
        "nuevo": [
            "La conversión funciona en los dos sentidos: de quetzales a dólares y de dólares a quetzales",
        ],
    },
    "1.0.18": {
        "nuevo": [
            "Interruptor Repartir monto para cotizaciones atípicas",
            "Las cifras se copian con un clic",
            "Conversión de quetzales a dólares",
            "Aviso cuando una cotización da precios ilógicos",
        ],
        "cambios": [
            "Panel de resultados más ordenado",
            "La captura incluye el desglose",
        ],
        "correcciones": [
            "Ningún costo puede salir negativo",
            "El descuento cuadra con el PVP redondeado",
            "Se revisan las fechas que no existen",
            "La actualización ya no se queda congelada",
            "Al cerrar la calculadora no queda nada abierto en segundo plano",
        ],
    },
    "1.0.17": {
        "nuevo": [
            "Nuevo diseño de la calculadora, más claro y con animaciones",
            "Se agregó la opción PVP con descuento",
        ],
    },
    "1.0.16": {
        "nuevo": ["Se agregó monto para reservar"],
        "cambios": ["La calculadora abre en pantalla completa"],
    },
    "1.0.15": {
        "nuevo": ["Se agregó monto para reservar"],
    },
    "1.0.14": {
        "nuevo": ["Se agregó monto para reservar"],
    },
    "1.0.13": {
        "cambios": ["La app ahora se llama Calculadora de viajes D&T"],
        "correcciones": ["El ícono de la ventana y el logo del encabezado se ven completos"],
    },
    "1.0.12": {
        "cambios": [],
        "correcciones": ["Se cambiaron los parámetros de edad de niños e infantes"],
    },
}

ARGUMENTO_ACTUALIZADO = "--actualizado"  # lo pasa el instalador al reabrir el programa
ARCHIVO_VERSION_VISTA = os.path.join(
    os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"),
    "DreamTravel",
    "ultima_version.txt",
)


def leer_version_vista():
    try:
        with open(ARCHIVO_VERSION_VISTA, encoding="utf-8") as archivo:
            return archivo.read().strip() or None
    except OSError:
        return None


def guardar_version_vista(version):
    try:
        os.makedirs(os.path.dirname(ARCHIVO_VERSION_VISTA), exist_ok=True)
        with open(ARCHIVO_VERSION_VISTA, "w", encoding="utf-8") as archivo:
            archivo.write(version)
    except OSError:
        pass


def notas_a_mostrar(version_actual, recien_actualizado, version_vista):
    """Las notas de esta versión si hay que mostrarlas ahora; si no, None.

    Se muestran cuando el instalador avisa que acaba de actualizar o cuando la última
    versión abierta en esta computadora es anterior a la actual.
    """
    notas = NOVEDADES.get(version_actual)
    if not notas or not any(notas.get(clave) for clave, _titulo, _vineta in SECCIONES):
        return None
    if recien_actualizado:
        return notas
    if version_vista is not None and es_mas_nueva(version_actual, version_vista):
        return notas
    return None
