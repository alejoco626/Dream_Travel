"""Búsqueda, descarga e instalación de versiones nuevas desde GitHub Releases."""

import hashlib
import json
import os
import shutil
import subprocess
import urllib.request

from .config import (
    AGENTE_HTTP,
    CARPETA_ACTUALIZACION,
    NOMBRE_INSTALADOR,
    PREFIJO_DESCARGA,
    URL_ULTIMA_VERSION,
)

TIEMPO_CONSULTA_S = 8
TIEMPO_DESCARGA_S = 30
TAMANO_BLOQUE = 64 * 1024


def version_a_tupla(texto):
    partes = []
    for fragmento in str(texto).lstrip("vV").split("."):
        digitos = "".join(c for c in fragmento if c.isdigit())
        partes.append(int(digitos) if digitos else 0)
    while len(partes) < 3:
        partes.append(0)
    return tuple(partes)


def es_mas_nueva(version, actual):
    return version_a_tupla(version) > version_a_tupla(actual)


def interpretar_release(datos):
    """Devuelve la información del instalador publicado, o None si no aplica."""
    if datos.get("draft") or datos.get("prerelease"):
        return None
    version = str(datos.get("tag_name", "")).lstrip("vV")
    if not version:
        return None
    for asset in datos.get("assets", []):
        url = asset.get("browser_download_url", "")
        if asset.get("name") == NOMBRE_INSTALADOR and url.startswith(PREFIJO_DESCARGA):
            digest = str(asset.get("digest") or "")
            sha256 = digest.split(":", 1)[1].lower() if digest.startswith("sha256:") else None
            return {"version": version, "url": url, "nombre": NOMBRE_INSTALADOR, "sha256": sha256}
    return None


def consultar_ultima_version():
    solicitud = urllib.request.Request(
        URL_ULTIMA_VERSION,
        headers={"User-Agent": AGENTE_HTTP, "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(solicitud, timeout=TIEMPO_CONSULTA_S) as respuesta:
        return interpretar_release(json.load(respuesta))


def hilo_consultar(cola):
    """Se ejecuta en segundo plano; sin conexión simplemente informa None."""
    try:
        info = consultar_ultima_version()
    except (OSError, ValueError, AttributeError):
        info = None
    cola.put(info)


def hilo_descargar(info, cola):
    """Descarga el instalador verificando su huella SHA-256.

    Envía a la cola ("progreso", leido, total), ("listo", ruta) o ("error", mensaje).
    """
    try:
        os.makedirs(CARPETA_ACTUALIZACION, exist_ok=True)
        destino = os.path.join(CARPETA_ACTUALIZACION, info["nombre"])
        parcial = destino + ".part"
        solicitud = urllib.request.Request(info["url"], headers={"User-Agent": AGENTE_HTTP})
        huella = hashlib.sha256()
        with urllib.request.urlopen(solicitud, timeout=TIEMPO_DESCARGA_S) as respuesta, open(
            parcial, "wb"
        ) as archivo:
            total = int(respuesta.headers.get("Content-Length") or 0)
            leido = 0
            while True:
                bloque = respuesta.read(TAMANO_BLOQUE)
                if not bloque:
                    break
                archivo.write(bloque)
                huella.update(bloque)
                leido += len(bloque)
                cola.put(("progreso", leido, total))
        if leido == 0:
            raise ValueError("La descarga llegó vacía.")
        if info["sha256"] and huella.hexdigest().lower() != info["sha256"]:
            raise ValueError("El archivo descargado no coincide con la huella publicada.")
        os.replace(parcial, destino)
        cola.put(("listo", destino))
    except (OSError, ValueError) as error:
        limpiar_descargas()
        cola.put(("error", str(error)))


def limpiar_descargas():
    shutil.rmtree(CARPETA_ACTUALIZACION, ignore_errors=True)


def lanzar_instalador(ruta_instalador):
    """Abre el instalador en modo silencioso, desligado de este proceso.

    Se limpia el entorno de PyInstaller para que el programa reabierto no herede
    la carpeta temporal del anterior (error "Failed to load Python DLL").
    """
    entorno = {
        clave: valor
        for clave, valor in os.environ.items()
        if not clave.startswith("_PYI") and clave != "_MEIPASS2"
    }
    entorno["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    subprocess.Popen(
        [ruta_instalador, "/SILENT", "/NORESTART", "/CLOSEAPPLICATIONS"],
        env=entorno,
        close_fds=True,
        creationflags=getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200),
    )
