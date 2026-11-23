# Calculadora de viajes D&T

Aplicación de escritorio (Windows) para armar presupuestos de viaje para adultos,
niños e infantes. Calcula el PVP por persona, el precio con descuento por pago
único en efectivo, el total en dólares y quetzales, la fecha de pago y el monto para reservar.

## Uso

1. Escribe cuántos adultos, niños e infantes viajan.
2. En **Servicios**, escribe el monto total de cada grupo (Diseñador va por persona).
   Con **＋ Agregar servicio** se suman cruceros, seguros, misceláneos, etc.
3. En **Condiciones de pago**, marca *No reembolsable* o escribe la fecha de viaje y
   la de cancelación del hotel (dd/mm/aaaa, o con el calendario 📅) para ver la fecha de pago y el **Monto para reservar** (el precio de los boletos de todo el grupo, ya dividido entre 0.80).
4. El panel derecho se actualiza mientras escribes: **Por persona**, **Resumen** y el
   **Ajuste de precio adulto**. *Redondear* lleva los precios al entero más próximo.
5. **Ver desglose** muestra el detalle por servicio y el botón de la cámara copia una captura
   de toda la calculadora al portapapeles. *PVP con descuento* muestra también el precio
   con descuento por pago en efectivo.

Atajos: `Enter` pasa al siguiente campo · `Ctrl + Enter` calcula.

Si la calculadora no abre, el detalle del error queda en
`%LOCALAPPDATA%\DreamTravel\calculadora_error.log`.

## Desarrollo

La ventana es una página web (HTML, CSS y JavaScript) que se muestra con
[pywebview](https://pywebview.flowrl.com/); todos los cálculos se hacen en Python.

```bash
pip install -r requirements.txt
python calculadora_dream_travel.py           # abrir la aplicación (Windows)
python herramientas/vista_previa.py          # ver la página en el navegador: http://127.0.0.1:8765
python -m unittest discover -s tests -t .    # pruebas (no requieren pantalla)
```

La vista previa sirve para cambiar el diseño sin compilar: edita los archivos de
`calculadora/web/` y recarga el navegador.

| Archivo | Contenido |
| --- | --- |
| `calculadora_dream_travel.py` | Punto de entrada |
| `calculadora/aplicacion.py` | Abre la ventana con pywebview |
| `calculadora/api.py` | Lo que la página le pide a Python: cálculos, formatos, captura, actualización |
| `calculadora/config.py` | Versión, porcentajes de costo, tipo de cambio, servicios y pesos de "Repartir monto" |
| `calculadora/calculo.py` | Fórmulas del presupuesto y redondeo |
| `calculadora/fechas.py` | Fechas dd/mm/aaaa y cálculo de la fecha de pago |
| `calculadora/actualizador.py` | Actualización automática desde GitHub Releases |
| `calculadora/novedades.py` | Notas que se muestran después de cada actualización |
| `calculadora/web/index.html` | Estructura de la pantalla |
| `calculadora/web/estilos.css` | Colores, tipografía, espacios y animaciones |
| `calculadora/web/app.js` | Comportamiento de la pantalla (muestra lo que calcula Python) |
| `calculadora/web/vendor/` | html2canvas (captura) y la fuente Inter, con sus licencias |
| `herramientas/vista_previa.py` | Vista previa en el navegador, sin pywebview |
| `icono_calculadora.ico` | Ícono de la app (16 a 256 px) |
| `instalador.iss` | Instalador de Inno Setup |
| `poner_version.py` | Escribe la versión del release en `config.py` |
| `tests/` | Pruebas automáticas |

## Publicar una versión

Antes de publicar, agrega las notas de la versión en `calculadora/novedades.py`
(cambios y correcciones). Cada computadora las muestra una vez al terminar de actualizar.

Crea un release con una etiqueta nueva (por ejemplo `v1.0.9`). GitHub Actions
ejecuta las pruebas, compila el `.exe` con PyInstaller, comprueba que abre, arma el
instalador con Inno Setup y lo adjunta al release. Los equipos con la calculadora
instalada ofrecen la actualización al abrirla.
