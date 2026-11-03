# Calculadora Dream & Travel

Aplicación de escritorio (Windows) para armar presupuestos de viaje para adultos,
niños e infantes. Calcula el PVP por persona, el precio con descuento por pago
único en efectivo y el total en dólares y quetzales.

## Uso

1. Escribe cuántos adultos, niños e infantes viajan.
2. En **Servicios**, escribe el monto total de cada grupo (Diseñador va por persona).
   Con **＋ Agregar servicio** se suman cruceros, seguros, misceláneos, etc.
3. El **Resumen** se actualiza mientras escribes; **Ver desglose** muestra el detalle.
4. 📷 copia una captura de toda la calculadora al portapapeles.

Atajos: `Enter` pasa al siguiente campo · `Ctrl + Enter` calcula.

## Desarrollo

```bash
pip install -r requirements.txt
python calculadora_dream_travel.py           # abrir la aplicación
python -m unittest discover -s tests -t .    # pruebas (no requieren pantalla)
```

| Archivo | Contenido |
| --- | --- |
| `calculadora/config.py` | Versión, porcentajes de costo, tipo de cambio y servicios |
| `calculadora/calculo.py` | Lógica del presupuesto, sin interfaz |
| `calculadora/tema.py` | Colores, tipografía y espaciado |
| `calculadora/componentes.py` | Botón accesible y texto de ayuda |
| `calculadora/interfaz.py` | Ventana principal |
| `calculadora/actualizador.py` | Actualización automática desde GitHub Releases |
| `calculadora/captura.py` | Captura de pantalla al portapapeles |

## Publicar una versión

Crea un release con una etiqueta nueva (por ejemplo `v1.0.4`). GitHub Actions
ejecuta las pruebas, compila el `.exe` con PyInstaller, arma el instalador con
Inno Setup y lo adjunta al release. Los equipos con la calculadora instalada
ofrecen la actualización al abrirla.
