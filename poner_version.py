import re
import sys

if len(sys.argv) != 2:
    sys.exit("Uso: python poner_version.py v1.0.1")

version = sys.argv[1].lstrip("vV")
if not re.fullmatch(r"\d+(\.\d+){1,2}", version):
    sys.exit(f"Version no valida: {sys.argv[1]} (usa algo como v1.0.1)")

ruta = "calculadora_dream_travel.py"
with open(ruta, encoding="utf-8") as archivo:
    texto = archivo.read()

nuevo, cambios = re.subn(
    r'^VERSION_APP = ".*"$', f'VERSION_APP = "{version}"', texto, flags=re.MULTILINE
)
if cambios != 1:
    sys.exit("No se encontro la linea VERSION_APP en el programa.")

with open(ruta, "w", encoding="utf-8") as archivo:
    archivo.write(nuevo)

print(f"Version del programa: {version}")
