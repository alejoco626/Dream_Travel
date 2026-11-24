"""Vista previa de la interfaz en un navegador, sin pywebview (solo para desarrollo).

    python herramientas/vista_previa.py [puerto]

Sirve la carpeta calculadora/web y responde las llamadas de la página
(window.pywebview.api.*) con la misma clase Api que usa el programa. La captura
no va al portapapeles: se guarda como captura_vista_previa.png.
"""

import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from calculadora import api as modulo_api  # noqa: E402

CARPETA_WEB = os.path.join(RAIZ, "calculadora", "web")
ARCHIVO_CAPTURA = os.environ.get("VISTA_PREVIA_CAPTURA") or os.path.join(RAIZ, "captura_vista_previa.png")

PUENTE = """
// Igual que pywebview: la API aparece un poco después de cargar la página.
window.addEventListener('DOMContentLoaded', () => setTimeout(() => {
  window.pywebview = {
    api: new Proxy({}, {
      get: (_, metodo) => (...args) =>
        fetch('/__api/' + metodo, {method: 'POST', body: JSON.stringify(args)}).then(r => r.json()),
    }),
  };
  window.dispatchEvent(new Event('pywebviewready'));
}, Number(new URLSearchParams(location.search).get('demora') || 0)));
"""


def guardar_captura(imagen):
    imagen.save(ARCHIVO_CAPTURA)


modulo_api.copiar_imagen_portapapeles = guardar_captura
modulo_api.copiar_texto_portapapeles = lambda texto: print(f"Copiado: {texto}", flush=True)
API = modulo_api.Api()

if os.environ.get("VISTA_PREVIA_DEMO"):
    # Muestra la ventana de novedades y simula una actualización disponible.
    from calculadora import novedades

    _inicio_original = API.inicio
    ultima = max(novedades.NOVEDADES, key=lambda v: tuple(int(p) for p in v.split(".")))

    def _inicio_demo():
        datos = _inicio_original()
        notas = novedades.NOVEDADES[ultima]
        datos["novedades"] = {
            "version": ultima,
            "secciones": [
                {"titulo": t, "vineta": v, "elementos": notas[c]}
                for c, t, v in novedades.SECCIONES
                if notas.get(c)
            ],
        }
        return datos

    API.inicio = _inicio_demo
    API.buscar_actualizacion = lambda: {"version": "9.9.9", "actual": ultima}
METODOS = {
    nombre: getattr(API, nombre)
    for nombre in dir(API)
    if not nombre.startswith("_") and callable(getattr(API, nombre))
}


class Manejador(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=CARPETA_WEB, **kwargs)

    def log_message(self, *args):
        pass

    def do_GET(self):
        ruta = self.path.split("?", 1)[0]
        if ruta in ("/", "/index.html"):
            with open(os.path.join(CARPETA_WEB, "index.html"), encoding="utf-8") as archivo:
                html = archivo.read()
            html = html.replace("<script src=", f"<script>{PUENTE}</script>\n    <script src=", 1)
            self._responder(200, html.encode("utf-8"), "text/html; charset=utf-8")
            return
        super().do_GET()

    def do_POST(self):
        nombre = self.path.rsplit("/", 1)[-1]
        largo = int(self.headers.get("Content-Length") or 0)
        argumentos = json.loads(self.rfile.read(largo) or b"[]")
        metodo = METODOS.get(nombre)
        if metodo is None:
            self._responder(404, b"null", "application/json")
            return
        resultado = metodo(*argumentos)
        self._responder(200, json.dumps(resultado, ensure_ascii=False).encode("utf-8"), "application/json")

    def _responder(self, codigo, cuerpo, tipo):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)


def main():
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print(f"Vista previa en http://127.0.0.1:{puerto}")
    ThreadingHTTPServer(("127.0.0.1", puerto), Manejador).serve_forever()


if __name__ == "__main__":
    main()
