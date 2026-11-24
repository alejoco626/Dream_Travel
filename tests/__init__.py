import os
import tempfile

# Las pruebas nunca escriben en Documentos: la carpeta de la calculadora va a un temporal.
os.environ.setdefault("CALCULADORA_CARPETA_DATOS", tempfile.mkdtemp(prefix="calculadora_pruebas_"))
