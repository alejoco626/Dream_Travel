import hashlib
import io
import os
import queue
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculadora import actualizador  # noqa: E402
from calculadora.config import NOMBRE_INSTALADOR, PREFIJO_DESCARGA  # noqa: E402


class Respuesta(io.BytesIO):
    def __init__(self, datos, url="https://objects.githubusercontent.com/x"):
        super().__init__(datos)
        self.headers = {"Content-Length": str(len(datos))}
        self._url = url

    def geturl(self):
        return self._url


def mensajes(cola):
    salida = []
    while not cola.empty():
        salida.append(cola.get())
    return salida


class PruebaVersiones(unittest.TestCase):
    def test_comparacion(self):
        self.assertTrue(actualizador.es_mas_nueva("1.0.10", "1.0.9"))
        self.assertTrue(actualizador.es_mas_nueva("v2.0", "1.99.99"))
        self.assertFalse(actualizador.es_mas_nueva("1.0", "1.0.0"))

    def test_interpretar_release(self):
        url = PREFIJO_DESCARGA + f"v1.2.0/{NOMBRE_INSTALADOR}"
        datos = {"tag_name": "v1.2.0", "assets": [
            {"name": "otro.zip", "browser_download_url": PREFIJO_DESCARGA + "x"},
            {"name": NOMBRE_INSTALADOR, "browser_download_url": url, "digest": "sha256:" + "AB" * 32},
        ]}
        info = actualizador.interpretar_release(datos)
        self.assertEqual(info["version"], "1.2.0")
        self.assertEqual(info["sha256"], "ab" * 32)

    def test_rechazos(self):
        externo = {"tag_name": "v9", "assets": [{"name": NOMBRE_INSTALADOR, "browser_download_url": "https://malo.com/x.exe"}]}
        self.assertIsNone(actualizador.interpretar_release(externo))
        self.assertIsNone(actualizador.interpretar_release({"tag_name": "v3", "draft": True, "assets": []}))
        self.assertIsNone(actualizador.interpretar_release({"tag_name": "v3", "assets": []}))
        url = PREFIJO_DESCARGA + f"v1.2.0/{NOMBRE_INSTALADOR}"
        sin_huella = {"tag_name": "v1.2.0", "assets": [{"name": NOMBRE_INSTALADOR, "browser_download_url": url}]}
        self.assertIsNone(actualizador.interpretar_release(sin_huella), "sin huella no se actualiza")
        version_rara = {"tag_name": "v1.2.0;calc", "assets": []}
        self.assertIsNone(actualizador.interpretar_release(version_rara))


class PruebaDescarga(unittest.TestCase):
    def setUp(self):
        self.carpeta = os.path.join(tempfile.mkdtemp(), "actualizacion")
        mock.patch.object(actualizador, "CARPETA_ACTUALIZACION", self.carpeta).start()
        self.addCleanup(mock.patch.stopall)
        self.contenido = os.urandom(150_000)

    def descargar(self, contenido, sha256, url_final="https://objects.githubusercontent.com/x"):
        info = {"version": "1.2.0", "url": PREFIJO_DESCARGA + "x", "nombre": NOMBRE_INSTALADOR, "sha256": sha256}
        cola = queue.Queue()
        with mock.patch("urllib.request.urlopen", return_value=Respuesta(contenido, url_final)):
            actualizador.hilo_descargar(info, cola)
        return mensajes(cola)

    def test_descarga_correcta(self):
        resultado = self.descargar(self.contenido, hashlib.sha256(self.contenido).hexdigest())
        self.assertEqual(resultado[-1][0], "listo")
        self.assertEqual(os.path.getsize(resultado[-1][1]), len(self.contenido))
        self.assertFalse(os.path.exists(resultado[-1][1] + ".part"))

    def test_huella_distinta(self):
        resultado = self.descargar(self.contenido, "00" * 32)
        self.assertEqual(resultado[-1][0], "error")
        self.assertFalse(os.path.exists(self.carpeta))

    def test_descarga_vacia(self):
        self.assertEqual(self.descargar(b"", hashlib.sha256(b"").hexdigest())[-1][0], "error")

    def test_rechaza_conexion_no_segura(self):
        sha = hashlib.sha256(self.contenido).hexdigest()
        self.assertEqual(self.descargar(self.contenido, sha, "http://x/y")[-1][0], "error")

    def test_rechaza_archivo_demasiado_grande(self):
        with mock.patch.object(actualizador, "TAMANO_MAXIMO", 1000):
            sha = hashlib.sha256(self.contenido).hexdigest()
            self.assertEqual(self.descargar(self.contenido, sha)[-1][0], "error")


class PruebaInstalador(unittest.TestCase):
    def setUp(self):
        self.ruta = os.path.join(tempfile.mkdtemp(), "Setup.exe")
        with open(self.ruta, "wb") as archivo:
            archivo.write(b"instalador")
        self.sha = hashlib.sha256(b"instalador").hexdigest()

    def test_no_abre_un_instalador_modificado(self):
        with mock.patch("subprocess.Popen") as popen, self.assertRaises(ValueError):
            actualizador.lanzar_instalador(self.ruta, "00" * 32)
        popen.assert_not_called()

    def test_lanza_en_silencio_con_entorno_limpio(self):
        with mock.patch.dict(os.environ, {"_PYI_APPLICATION_HOME_DIR": "x", "_MEIPASS2": "y"}), \
                mock.patch("subprocess.Popen") as popen:
            actualizador.lanzar_instalador(self.ruta, self.sha)
        argumentos, opciones = popen.call_args
        self.assertEqual(argumentos[0][1:], ["/SILENT", "/NORESTART", "/CLOSEAPPLICATIONS"])
        self.assertEqual(opciones["env"]["PYINSTALLER_RESET_ENVIRONMENT"], "1")
        self.assertNotIn("_MEIPASS2", opciones["env"])
        self.assertFalse(any(clave.startswith("_PYI") for clave in opciones["env"]))


if __name__ == "__main__":
    unittest.main()
