"""Ventana de la calculadora: pywebview muestra la interfaz web (carpeta web/)."""

import ctypes
import os
import sys
import threading
import traceback

from .api import ARCHIVO_ERRORES, Api, registrar_error
from .config import ID_APP_WINDOWS, NOMBRE_APP

COLOR_FONDO = "#EEF2F6"  # mismo color que el lienzo de la página: no hay destello blanco al abrir
TAMANO_INICIAL = (1280, 800)
TAMANO_MINIMO = (1000, 620)
ESPERA_PRUEBA_S = 45  # la prueba de arranque falla si la página no está lista antes de esto
PAUSA_PRUEBA_S = 3


def ruta_recurso(*partes):
    """Ruta de un archivo incluido, tanto en desarrollo como dentro del .exe."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *partes)


def identificar_en_barra_de_tareas():
    """Hace que Windows muestre el ícono propio en la barra de tareas (y no el de Python)."""
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(ID_APP_WINDOWS)
    except (AttributeError, OSError):
        pass


def avisar_error_de_arranque():
    mensaje = f"La calculadora no pudo iniciar.\nEl detalle quedó en:\n{ARCHIVO_ERRORES}"
    try:
        ctypes.windll.user32.MessageBoxW(None, mensaje, NOMBRE_APP, 0x10)
    except (AttributeError, OSError):
        print(mensaje, file=sys.stderr)


def prueba_de_arranque(api, ventana):
    """Usado por el workflow: la página debe terminar de cargar y luego se cierra sola."""
    if api._listo.wait(ESPERA_PRUEBA_S):
        threading.Event().wait(PAUSA_PRUEBA_S)
    else:
        registrar_error("Prueba de arranque: la interfaz no terminó de cargar a tiempo.")
    ventana.destroy()


def main():
    identificar_en_barra_de_tareas()
    try:
        import webview

        api = Api()
        ventana = webview.create_window(
            NOMBRE_APP,
            url=ruta_recurso("calculadora", "web", "index.html"),
            js_api=api,
            width=TAMANO_INICIAL[0],
            height=TAMANO_INICIAL[1],
            min_size=TAMANO_MINIMO,
            maximized=True,
            background_color=COLOR_FONDO,
            text_select=True,
        )
        api._asignar_ventana(ventana)
        argumentos = {}
        if os.environ.get("CALCULADORA_PRUEBA_ARRANQUE"):
            argumentos = {"func": prueba_de_arranque, "args": (api, ventana)}
        webview.start(http_server=True, private_mode=True, **argumentos)
    except Exception:
        registrar_error(traceback.format_exc())
        avisar_error_de_arranque()
        raise
