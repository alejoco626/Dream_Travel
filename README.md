# Calculadora Dream & Travel

Aplicación de escritorio (Windows) para armar presupuestos de viaje para adultos,
niños e infantes. Calcula el PVP por persona, el precio con descuento por pago
único en efectivo, el total en dólares y quetzales, y la fecha de pago.

## Uso

1. Escribe cuántos adultos, niños e infantes viajan.
2. En **Servicios**, escribe el monto total de cada grupo (Diseñador va por persona).
   Con **＋ Agregar servicio** se suman cruceros, seguros, misceláneos, etc.
3. En **Condiciones de pago**, marca *No reembolsable* o escribe la fecha de viaje y
   la de cancelación del hotel (dd/mm/aaaa, o con el calendario 📅) para ver la fecha de pago.
4. El panel derecho se actualiza mientras escribes: **Por persona**, **Resumen** y el
   **Ajuste de precio adulto**. *Redondear* lleva los precios al entero más próximo.
5. **Ver desglose** muestra el detalle por servicio y 📷 copia una captura de toda la
   calculadora al portapapeles.

Atajos: `Enter` pasa al siguiente campo · `Ctrl + Enter` calcula.

Si la calculadora no abre, el detalle del error queda en
`%LOCALAPPDATA%\DreamTravel\calculadora_error.log`.

## Desarrollo

```bash
pip install -r requirements.txt
python calculadora_dream_travel.py           # abrir la aplicación
python -m unittest discover -s tests -t .    # pruebas (no requieren pantalla)
```

| Archivo | Contenido |
| --- | --- |
| `calculadora_dream_travel.py` | Punto de entrada |
| `calculadora/config.py` | Versión, porcentajes de costo, tipo de cambio y servicios |
| `calculadora/calculo.py` | Fórmulas del presupuesto y redondeo, sin interfaz |
| `calculadora/fechas.py` | Fechas dd/mm/aaaa y cálculo de la fecha de pago |
| `calculadora/tema.py` | Colores, tipografía, espaciado y radios |
| `calculadora/componentes.py` | Tarjetas, campos, botones, calendario y textos de ayuda |
| `calculadora/interfaz.py` | Ventana principal |
| `calculadora/actualizador.py` | Actualización automática desde GitHub Releases |
| `calculadora/captura.py` | Captura de pantalla al portapapeles |
| `icono_calculadora.ico` | Ícono de la app (16 a 256 px) |
| `Logo_Letras_Blanco.png` | Logo del encabezado |
| `instalador.iss` | Instalador de Inno Setup |
| `poner_version.py` | Escribe la versión del release en `config.py` |
| `tests/` | Pruebas automáticas |

## Publicar una versión

Crea un release con una etiqueta nueva (por ejemplo `v1.0.9`). GitHub Actions
ejecuta las pruebas, compila el `.exe` con PyInstaller, comprueba que abre, arma el
instalador con Inno Setup y lo adjunta al release. Los equipos con la calculadora
instalada ofrecen la actualización al abrirla.
