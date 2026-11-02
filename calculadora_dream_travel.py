import ctypes
import hashlib
import io
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from datetime import datetime
import tkinter as tk
from tkinter import messagebox, ttk

import win32clipboard
from PIL import Image, ImageGrab


PORCENTAJES = {
    "BOLETOS NETOS ADULTOS": 0.80,
    "BOLETOS NETOS NIÑOS": 0.80,
    "BOLETOS NETOS INFANTES": 0.80,
    "DISEÑADOR ADULTOS": 0.95,
    "DISEÑADOR NIÑOS": 0.95,
    "DISEÑADOR INFANTES": 0.95,
    "CIRCUITOS": 0.90,
    "CRUCEROS": 0.90,
    "OPERADOR DIRECTO / JACKELINE": 0.90,
    "SEGURO DE VIAJE": 0.90,
    "TRASLADOS / SUPERVISOR": 0.90,
    "VISADOS O PERMISOS": 0.80,
    "MISCELANEOS": 0.80,
}

EDITABILIDAD_COSTOS = {
    "BOLETOS NETOS ADULTOS": "total",
    "BOLETOS NETOS NIÑOS": "total",
    "BOLETOS NETOS INFANTES": "total",
    "DISEÑADOR ADULTOS": "total",
    "DISEÑADOR NIÑOS": "total",
    "DISEÑADOR INFANTES": "total",
    "CIRCUITOS": "total",
    "CRUCEROS": "total",
    "OPERADOR DIRECTO / JACKELINE": "total",
    "ENTRADAS EVENTOS": "persona",
    "SEGURO DE VIAJE": "persona",
    "TRASLADOS / SUPERVISOR": "persona",
    "VISADOS O PERMISOS": "persona",
    "MISCELANEOS": "total",
}

FACTOR_CONVERSION = 7.88

VERSION_APP = "1.0.0"
REPO_GITHUB = "alejoco626/Dream_Travel"
NOMBRE_INSTALADOR = "Calculadora_Dream_Travel_Setup.exe"
URL_ULTIMA_VERSION = f"https://api.github.com/repos/{REPO_GITHUB}/releases/latest"
PREFIJO_DESCARGA = f"https://github.com/{REPO_GITHUB}/releases/download/"
CARPETA_ACTUALIZACION = os.path.join(tempfile.gettempdir(), "DreamTravel_Calculadora_Update")

SUBTITULOS = {
    "NIÑOS": "de 4 a 11 años",
    "INFANTES": "de 0 a 3 años",
}

AZUL = "#003D6B"
CORINTO = "#960018"
BLANCO = "#FFFFFF"
GRIS = "#F3F4F6"
GRIS_TEXTO = "#555555"
VERDE = "#198754"
FONDO_EDITABLE = "#FFFFFF"
GRIS_BLOQUEADO = "#878484"

CONCEPTOS_DISPONIBLES = [
    "CIRCUITOS",
    "CRUCEROS",
    "OPERADOR DIRECTO / JACKELINE",
    "ENTRADAS EVENTOS",
    "SEGURO DE VIAJE",
    "TRASLADOS / SUPERVISOR",
    "VISADOS O PERMISOS",
    "MISCELANEOS",
]

MISCELANEOS_SUBTIPOS = [
    "MISCELANEOS",
    "ASIENTOS",
    "EQUIPAJE",
    "DECORACIÓN LUNA DE MIEL",
    "DECORACIÓN PEDIDA DE MANO",
    "DECORACIÓN CUMPLEAÑOS",
    "DECORACIÓN ANIVERSARIO",
    "ENTRADAS A TOUR'S",
]

RUBROS_CANTIDAD = ["ADULTOS", "NIÑOS", "INFANTES"]
CONCEPTOS_AUTOMATICOS = (
    "BOLETOS NETOS ADULTOS",
    "BOLETOS NETOS NIÑOS",
    "BOLETOS NETOS INFANTES",
    "DISEÑADOR ADULTOS",
    "DISEÑADOR NIÑOS",
    "DISEÑADOR INFANTES",
)

filas_conceptos_fijas = []
filas_conceptos_dinamicas = []
orden_campos = []


def info_concepto(concepto):
    if concepto in CONCEPTOS_AUTOMATICOS:
        return concepto, None
    for base in CONCEPTOS_DISPONIBLES:
        if concepto == base:
            return base, None
        for rubro in RUBROS_CANTIDAD:
            if concepto == f"{base} {rubro}":
                return base, rubro
    return concepto, None


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

ventana = tk.Tk()
ventana.iconbitmap(resource_path("Logo_Ovalado.ico"))
ventana.title("Dream & Travel - Calculadora")
ventana.resizable(True, True)
ventana.geometry("1250x750")
ventana.minsize(1100, 700)
ventana.update_idletasks()

logo_original = tk.PhotoImage(file=resource_path("Logo_Letras_Blanco.png"))
logo = logo_original.subsample(3, 3)


def obtener_monto(campo):
    texto = campo.get().strip()
    if not texto:
        return 0.0
    texto = texto.replace("$", "").replace(",", "").strip()
    return float(texto)


def formatear_moneda(campo):
    try:
        valor = obtener_monto(campo)
        campo.delete(0, tk.END)
        campo.insert(0, f"$ {valor:,.2f}")
    except ValueError:
        pass


def limpiar_espacios_al_borrar(event):
    if event.keysym not in ("BackSpace", "Delete"):
        return

    campo = event.widget
    try:
        texto = campo.get()
    except:
        return

    if "$" in texto or "," in texto:
        posicion = campo.index(tk.INSERT)
        seleccion_inicio = None
        seleccion_fin = None

        try:
            seleccion_inicio = campo.index("sel.first")
            seleccion_fin = campo.index("sel.last")
        except tk.TclError:
            pass

        texto_limpio = texto.replace("$", "").replace(",", "").replace(" ", "")
        campo.delete(0, tk.END)
        campo.insert(0, texto_limpio)

        if seleccion_inicio is not None and seleccion_fin is not None:
            try:
                campo.selection_range(0, tk.END)
            except:
                pass
        else:
            try:
                campo.icursor(min(posicion, len(texto_limpio)))
            except:
                campo.icursor(tk.END)


def actualizar_casilla(campo, valor):
    campo.config(state="normal")
    campo.delete(0, tk.END)
    campo.insert(0, valor)
    campo.config(state="readonly")


def actualizar_conversiones():
    for grupo in (boletos_campos, disenador_campos):
        for campo in grupo.values():
            try:
                valor = obtener_monto(campo["entrada"])
            except ValueError:
                valor = 0.0
            actualizar_casilla(campo["quetzales"], f"Q {valor * FACTOR_CONVERSION:,.2f}")


def crear_encabezado_montos(marco):
    fila_frame = tk.Frame(marco, bg=GRIS)
    tk.Label(
        fila_frame,
        text="",
        font=("Arial", 9, "bold"),
        bg=GRIS,
        width=35,
    ).pack(side="left", padx=(0, 6))
    tk.Label(
        fila_frame,
        text="DÓLARES",
        font=("Arial", 10, "bold"),
        bg=GRIS,
        fg=GRIS_TEXTO,
        width=14,
    ).pack(side="left")
    tk.Label(
        fila_frame,
        text="QUETZALES",
        font=("Arial", 10, "bold"),
        bg=GRIS,
        fg=GRIS_TEXTO,
        width=14,
    ).pack(side="left", padx=(6, 0))
    fila_frame.grid(row=0, column=0, sticky="w", pady=(0, 2))


def colocar_costo_editable(campo, fila, columna, color_fila):
    if not campo.get().strip():
        campo.insert(0, "$ 0.00")

    campo.configure(
        bg=FONDO_EDITABLE,
        fg="#000000",
        insertbackground="#000000",
    )
    campo.grid(
        row=fila,
        column=columna,
        sticky="nsew",
        padx=1,
        pady=1,
        ipady=5,
    )
    campo.bind("<KeyPress>", limpiar_espacios_al_borrar, add="+")
    campo.bind("<FocusOut>", lambda event: formatear_moneda(event.widget), add="+")


def siguiente_campo(event):
    widget_actual = event.widget
    entradas_rubros = [rubro["entrada"] for rubro in rubros_cantidad]

    if widget_actual in orden_campos and widget_actual not in entradas_rubros:
        formatear_moneda(widget_actual)

    try:
        indice = orden_campos.index(widget_actual)
    except ValueError:
        return "break"

    if indice < len(orden_campos) - 1:
        siguiente = orden_campos[indice + 1]
        siguiente.focus()
        if isinstance(siguiente, tk.Entry):
            siguiente.select_range(0, tk.END)
    else:
        calcular()

    return "break"


encabezado = tk.Frame(ventana, bg=AZUL, height=95)
encabezado.pack(fill="x")
encabezado.pack_propagate(False)

fecha_label = tk.Label(
    encabezado,
    text="",
    font=("Arial", 13, "bold"),
    bg=CORINTO,
    fg=BLANCO,
    relief="solid",
    bd=1,
    highlightbackground=BLANCO,
    highlightcolor=BLANCO,
    highlightthickness=1,
    padx=8,
    pady=2,
)
fecha_label.place(relx=0.97, rely=0.12, anchor="ne")

hora_label = tk.Label(
    encabezado,
    text="",
    font=("Arial", 11, "bold"),
    bg=CORINTO,
    fg=BLANCO,
    relief="solid",
    bd=1,
    highlightbackground=BLANCO,
    highlightcolor=BLANCO,
    highlightthickness=1,
    padx=8,
    pady=2,
)
hora_label.place(relx=0.97, rely=0.50, anchor="ne")


def actualizar_fecha_hora():
    ahora = datetime.now()
    fecha_label.config(text=ahora.strftime("Fecha: %d/%m/%Y"))
    hora_label.config(text=ahora.strftime("Hora: %I:%M %p"))
    ventana.after(1000, actualizar_fecha_hora)


actualizar_fecha_hora()

logo_label = tk.Label(encabezado, image=logo, bg=AZUL)
logo_label.place(x=30, rely=0.5, anchor="w")

titulo = tk.Label(
    encabezado,
    text="PRESUPUESTO PARA ADULTOS Y NIÑOS F1",
    font=("Arial", 18, "bold"),
    bg=AZUL,
    fg=BLANCO,
)
titulo.place(relx=0.5, rely=0.35, anchor="center")

contenedor = tk.Frame(ventana, bg=BLANCO)
contenedor.pack(fill="both", expand=True, padx=20, pady=8)

resumen_frame = tk.Frame(contenedor, bg=GRIS, padx=15, pady=6)
resumen_frame.pack(fill="x", pady=(4, 0))

rubros_cantidad = []
rubros_frame = tk.Frame(resumen_frame, bg=GRIS)
rubros_frame.grid(row=0, column=0, columnspan=2, sticky="w", padx=(5, 10), pady=0)

boletos_frame = tk.LabelFrame(
    resumen_frame,
    text="MONTOS TOTALES DE BOLETOS",
    font=("Arial", 9, "bold"),
    bg=GRIS,
    fg=AZUL,
    padx=5,
    pady=3,
)
boletos_frame.grid(row=0, column=2, columnspan=2, sticky="nsew", padx=(5, 8), pady=(0, 4))
boletos_campos = {}
crear_encabezado_montos(boletos_frame)


def crear_campo_boleto(clave, texto):
    fila_frame = tk.Frame(boletos_frame, bg=GRIS)
    etiqueta = tk.Label(
        fila_frame,
        text=texto,
        font=("Arial", 9, "bold"),
        bg=GRIS,
        fg=AZUL,
        anchor="w",
        width=35,
    )
    etiqueta.pack(side="left", padx=(0, 6))
    entrada = tk.Entry(
        fila_frame,
        font=("Arial", 10),
        justify="right",
        width=14,
        relief="solid",
        bd=1,
    )
    entrada.insert(0, "$ 0.00")
    entrada.bind("<KeyPress>", limpiar_espacios_al_borrar, add="+")
    entrada.bind("<FocusOut>", lambda event: formatear_moneda(event.widget), add="+")
    entrada.bind("<KeyRelease>", lambda event: actualizar_conversiones(), add="+")
    entrada.bind("<FocusOut>", lambda event: actualizar_conversiones(), add="+")
    entrada.pack(side="left")
    entrada.bind("<Return>", siguiente_campo)
    entrada.bind("<KP_Enter>", siguiente_campo)
    entrada_quetzales = tk.Entry(
        fila_frame,
        font=("Arial", 10),
        justify="right",
        width=14,
        relief="solid",
        bd=1,
        state="readonly",
    )
    entrada_quetzales.pack(side="left", padx=(6, 0))
    actualizar_casilla(entrada_quetzales, "Q 0.00")
    boletos_campos[clave] = {
        "frame": fila_frame,
        "label": etiqueta,
        "entrada": entrada,
        "quetzales": entrada_quetzales,
        "texto": texto,
        "precio_original": None,
        "ultimo_resultado": None,
    }


crear_campo_boleto("adultos", "BOLETOS ADULTOS")
crear_campo_boleto("adultos_ninos", "BOLETOS ADULTOS Y NIÑOS")
crear_campo_boleto("adultos_ninos_infantes", "BOLETOS ADULTOS, NIÑOS E INFANTES")


def actualizar_campos_boleto():
    nombres = {r.get("nombre") for r in rubros_cantidad if r.get("nombre")}
    hay_ninos = "NIÑOS" in nombres
    hay_infantes = "INFANTES" in nombres
    boletos_campos["adultos"]["frame"].grid(row=1, column=0, sticky="w", pady=1)
    if hay_ninos:
        boletos_campos["adultos_ninos"]["label"].config(text="BOLETOS ADULTOS Y NIÑOS")
        boletos_campos["adultos_ninos"]["frame"].grid(row=2, column=0, sticky="w", pady=1)
    else:
        boletos_campos["adultos_ninos"]["frame"].grid_remove()
    if hay_infantes:
        texto = (
            "BOLETOS ADULTOS, NIÑOS E INFANTES"
            if hay_ninos
            else "BOLETOS ADULTOS E INFANTES"
        )
        boletos_campos["adultos_ninos_infantes"]["label"].config(text=texto)
        boletos_campos["adultos_ninos_infantes"]["frame"].grid(
            row=3 if hay_ninos else 2, column=0, sticky="w", pady=1
        )
    else:
        boletos_campos["adultos_ninos_infantes"]["frame"].grid_remove()
    if "pvp_rubros_campos" in globals():
        actualizar_filas_pvp()


disenador_frame = tk.LabelFrame(
    resumen_frame,
    text="MONTOS TOTALES DE DISEÑADOR",
    font=("Arial", 9, "bold"),
    bg=GRIS,
    fg=AZUL,
    padx=5,
    pady=3,
)
disenador_frame.grid(row=0, column=4, columnspan=2, sticky="nsew", padx=(8, 5), pady=(0, 4))
disenador_campos = {}
crear_encabezado_montos(disenador_frame)


def crear_campo_disenador(clave, texto):
    fila_frame = tk.Frame(disenador_frame, bg=GRIS)
    etiqueta = tk.Label(
        fila_frame,
        text=texto,
        font=("Arial", 9, "bold"),
        bg=GRIS,
        fg=AZUL,
        anchor="w",
        width=35,
    )
    etiqueta.pack(side="left", padx=(0, 6))
    entrada = tk.Entry(
        fila_frame,
        font=("Arial", 10),
        justify="right",
        width=14,
        relief="solid",
        bd=1,
    )
    entrada.insert(0, "$ 0.00")
    entrada.bind("<KeyPress>", limpiar_espacios_al_borrar, add="+")
    entrada.bind("<FocusOut>", lambda event: formatear_moneda(event.widget), add="+")
    entrada.bind("<KeyRelease>", lambda event: actualizar_conversiones(), add="+")
    entrada.bind("<FocusOut>", lambda event: actualizar_conversiones(), add="+")
    entrada.pack(side="left")
    entrada.bind("<Return>", siguiente_campo)
    entrada.bind("<KP_Enter>", siguiente_campo)
    entrada_quetzales = tk.Entry(
        fila_frame,
        font=("Arial", 10),
        justify="right",
        width=14,
        relief="solid",
        bd=1,
        state="readonly",
    )
    entrada_quetzales.pack(side="left", padx=(6, 0))
    actualizar_casilla(entrada_quetzales, "Q 0.00")
    disenador_campos[clave] = {
        "frame": fila_frame,
        "label": etiqueta,
        "entrada": entrada,
        "quetzales": entrada_quetzales,
        "texto": texto,
        "precio_original": None,
        "ultimo_resultado": None,
    }


crear_campo_disenador("adultos", "DISEÑADOR ADULTOS")
crear_campo_disenador("adultos_ninos", "DISEÑADOR ADULTOS Y NIÑOS")
crear_campo_disenador("adultos_ninos_infantes", "DISEÑADOR ADULTOS, NIÑOS E INFANTES")


def actualizar_campos_disenador():
    nombres = {r.get("nombre") for r in rubros_cantidad if r.get("nombre")}
    hay_ninos = "NIÑOS" in nombres
    hay_infantes = "INFANTES" in nombres
    disenador_campos["adultos"]["frame"].grid(row=1, column=0, sticky="w", pady=1)
    if hay_ninos:
        disenador_campos["adultos_ninos"]["label"].config(text="DISEÑADOR ADULTOS Y NIÑOS")
        disenador_campos["adultos_ninos"]["frame"].grid(row=2, column=0, sticky="w", pady=1)
    else:
        disenador_campos["adultos_ninos"]["frame"].grid_remove()
    if hay_infantes:
        texto = (
            "DISEÑADOR ADULTOS, NIÑOS E INFANTES"
            if hay_ninos
            else "DISEÑADOR ADULTOS E INFANTES"
        )
        disenador_campos["adultos_ninos_infantes"]["label"].config(text=texto)
        disenador_campos["adultos_ninos_infantes"]["frame"].grid(
            row=3 if hay_ninos else 2, column=0, sticky="w", pady=1
        )
    else:
        disenador_campos["adultos_ninos_infantes"]["frame"].grid_remove()


actualizar_campos_boleto()
actualizar_campos_disenador()


def actualizar_selectores_rubros():
    utilizados = [r["nombre"] for r in rubros_cantidad if r.get("nombre")]
    for rubro in rubros_cantidad:
        if rubro.get("fijo"):
            continue
        actual = rubro.get("nombre", "")
        disponibles = [
            nombre
            for nombre in RUBROS_CANTIDAD
            if nombre == actual or nombre not in utilizados
        ]
        rubro["selector"]["values"] = disponibles


def actualizar_orden_campos():
    orden_campos.clear()
    for rubro in rubros_cantidad:
        orden_campos.append(rubro["entrada"])
    if "boletos_campos" in globals():
        for clave in ("adultos", "adultos_ninos", "adultos_ninos_infantes"):
            orden_campos.append(boletos_campos[clave]["entrada"])
    if "disenador_campos" in globals():
        for clave in ("adultos", "adultos_ninos", "adultos_ninos_infantes"):
            orden_campos.append(disenador_campos[clave]["entrada"])
    for fila in filas_conceptos_fijas + filas_conceptos_dinamicas:
        if (
            fila.get("campo_editable") is not None
            and fila["concepto"].get().strip() not in CONCEPTOS_AUTOMATICOS
        ):
            orden_campos.append(fila["campo_editable"])


def cambiar_rubro_cantidad(event=None):
    widget = event.widget if event else None
    for rubro in rubros_cantidad:
        if rubro.get("selector") is widget:
            rubro["nombre"] = widget.get().strip()
            actualizar_selectores_rubros()
            sincronizar_filas_dependientes()
            actualizar_campos_boleto()
            actualizar_campos_disenador()
            actualizar_orden_campos()
            break


def quitar_rubro_cantidad(rubro):
    if rubro not in rubros_cantidad or rubro.get("fijo"):
        return
    rubros_cantidad.remove(rubro)
    rubro["frame"].destroy()
    actualizar_selectores_rubros()
    actualizar_posiciones_rubros()
    sincronizar_filas_dependientes()
    actualizar_campos_boleto()
    actualizar_campos_disenador()
    actualizar_orden_campos()
    actualizar_campos_boleto()
    actualizar_orden_campos()


def validar_cantidad_rubro(event):
    if event.keysym in (
        "BackSpace",
        "Delete",
        "Left",
        "Right",
        "Home",
        "End",
        "Tab",
        "Return",
        "KP_Enter",
    ):
        return
    if event.char and not event.char.isdigit():
        return "break"


def crear_rubro_cantidad(nombre="", fijo=False):
    fila_frame = tk.Frame(rubros_frame, bg=GRIS)
    etiqueta = tk.Label(
        fila_frame,
        text="CANTIDAD DE",
        font=("Arial", 10, "bold"),
        bg=GRIS,
        fg=AZUL,
    )
    etiqueta.grid(row=0, column=0, padx=(5, 5), pady=2)

    selector = ttk.Combobox(
        fila_frame,
        values=RUBROS_CANTIDAD,
        font=("Arial", 10),
        state="disabled" if fijo else "readonly",
        width=16,
    )
    selector.grid(row=0, column=1, padx=(0, 5), pady=2)
    if nombre:
        selector.set(nombre)

    entrada = tk.Entry(
        fila_frame,
        font=("Arial", 11, "bold"),
        justify="center",
        width=8,
        relief="solid",
        bd=1,
    )
    entrada.bind("<KeyPress>", validar_cantidad_rubro, add="+")
    entrada.grid(row=0, column=2, padx=(0, 5), pady=2)
    entrada.insert(0, "1" if fijo else "")

    boton_quitar = tk.Button(
        fila_frame,
        text="⊗",
        command=lambda: quitar_rubro_cantidad(rubro),
        font=("Arial", 16, "bold"),
        bg=GRIS,
        fg="#C00000",
        activebackground=GRIS,
        activeforeground="#C00000",
        relief="flat",
        bd=0,
        highlightthickness=0,
        cursor="hand2",
        width=2,
        padx=0,
        pady=0,
    )

    rubro = {
        "nombre": nombre,
        "fijo": fijo,
        "frame": fila_frame,
        "selector": selector,
        "entrada": entrada,
        "boton_quitar": boton_quitar,
    }

    if not fijo:
        selector.bind("<<ComboboxSelected>>", cambiar_rubro_cantidad)
        boton_quitar.grid(row=0, column=3, padx=(0, 2), pady=2)

    entrada.bind("<Return>", siguiente_campo)
    entrada.bind("<KP_Enter>", siguiente_campo)
    rubros_cantidad.append(rubro)
    actualizar_selectores_rubros()
    actualizar_orden_campos()
    return rubro


def agregar_rubro_cantidad():
    utilizados = [r["nombre"] for r in rubros_cantidad if r.get("nombre")]
    disponibles = [nombre for nombre in RUBROS_CANTIDAD if nombre not in utilizados]
    if not disponibles:
        return
    crear_rubro_cantidad(disponibles[0], fijo=False)
    actualizar_selectores_rubros()
    actualizar_posiciones_rubros()
    sincronizar_filas_dependientes()
    actualizar_campos_boleto()
    actualizar_campos_disenador()
    actualizar_orden_campos()
    actualizar_campos_boleto()
    actualizar_orden_campos()


def actualizar_posiciones_rubros():
    for indice, rubro in enumerate(rubros_cantidad):
        rubro["frame"].grid(
            row=indice,
            column=0,
            sticky="w",
            padx=(0, 12),
            pady=1,
        )
    boton_agregar_rubro.grid(
        row=len(rubros_cantidad),
        column=0,
        sticky="w",
        padx=(0, 5),
        pady=2,
    )


boton_agregar_rubro = tk.Button(
    rubros_frame,
    text="⊕",
    command=agregar_rubro_cantidad,
    font=("Arial", 16, "bold"),
    bg=AZUL,
    fg=BLANCO,
    activebackground=CORINTO,
    activeforeground=BLANCO,
    relief="flat",
    bd=0,
    cursor="hand2",
    width=3,
    height=1,
)

crear_rubro_cantidad("ADULTOS", fijo=True)
actualizar_posiciones_rubros()
actualizar_campos_boleto()

for indice in range(6):
    resumen_frame.grid_columnconfigure(indice, weight=1)

pvp_rubros_frame = tk.LabelFrame(
    resumen_frame,
    text="PVP POR PERSONAS",
    font=("Arial", 9, "bold"),
    bg=GRIS,
    fg=AZUL,
    padx=6,
    pady=4,
)
pvp_rubros_frame.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=5, pady=(4, 0))

pvp_descuento_frame = tk.LabelFrame(
    resumen_frame,
    text="PVP CON DESCUENTO POR PERSONAS",
    font=("Arial", 9, "bold"),
    bg=GRIS,
    fg=AZUL,
    padx=6,
    pady=4,
)
pvp_descuento_frame.grid(row=1, column=3, columnspan=3, sticky="nsew", padx=5, pady=(4, 0))

ENCABEZADOS_PVP = (
    ("CATEGORÍA", AZUL, "w"),
    ("PRECIO DÓLAR", GRIS_TEXTO, "center"),
    ("PRECIO QUETZALES", GRIS_TEXTO, "center"),
    ("TOTAL DÓLAR", GRIS_TEXTO, "center"),
    ("TOTAL QUETZALES", GRIS_TEXTO, "center"),
)

for marco, subtitulo in (
    (pvp_rubros_frame, " "),
    (pvp_descuento_frame, "(Un solo pago con efectivo)"),
):
    tk.Label(
        marco,
        text=subtitulo,
        font=("Arial", 8, "bold"),
        bg=GRIS,
        fg=CORINTO,
        anchor="w",
    ).grid(row=0, column=0, columnspan=5, sticky="w", padx=4, pady=(0, 2))
    for numero_columna, (titulo_columna, color_columna, ancla) in enumerate(ENCABEZADOS_PVP):
        tk.Label(
            marco,
            text=titulo_columna,
            font=("Arial", 8, "bold"),
            bg=GRIS,
            fg=color_columna,
            anchor=ancla,
        ).grid(row=1, column=numero_columna, sticky="ew", padx=3, pady=(0, 3))


def crear_casilla_pvp(marco, fila, columna, valor, color="#000000"):
    campo = tk.Entry(
        marco,
        font=("Arial", 10, "bold"),
        justify="right",
        width=11,
        relief="solid",
        bd=1,
        state="readonly",
        fg=color,
    )
    campo.grid(row=fila, column=columna, sticky="ew", padx=3, pady=2)
    actualizar_casilla(campo, valor)
    return campo


pvp_rubros_campos = {}
for indice, nombre_rubro in enumerate(("ADULTOS", "NIÑOS", "INFANTES"), start=2):
    texto_rubro = nombre_rubro
    if nombre_rubro in SUBTITULOS:
        texto_rubro += f"\n{SUBTITULOS[nombre_rubro]}"

    etiqueta_pvp = tk.Label(
        pvp_rubros_frame,
        text=texto_rubro,
        font=("Arial", 9, "bold"),
        bg=GRIS,
        fg=AZUL,
        anchor="w",
        justify="left",
    )
    etiqueta_pvp.grid(row=indice, column=0, sticky="ew", padx=3, pady=2)

    etiqueta_descuento = tk.Label(
        pvp_descuento_frame,
        text=texto_rubro,
        font=("Arial", 9, "bold"),
        bg=GRIS,
        fg=AZUL,
        anchor="w",
        justify="left",
    )
    etiqueta_descuento.grid(row=indice, column=0, sticky="ew", padx=3, pady=2)

    pvp_rubros_campos[nombre_rubro] = {
        "etiqueta_pvp": etiqueta_pvp,
        "pvp": crear_casilla_pvp(pvp_rubros_frame, indice, 1, "$ 0.00"),
        "pvp_quetzales": crear_casilla_pvp(pvp_rubros_frame, indice, 2, "Q 0.00"),
        "total_pvp": crear_casilla_pvp(pvp_rubros_frame, indice, 3, "$ 0.00"),
        "total_pvp_quetzales": crear_casilla_pvp(pvp_rubros_frame, indice, 4, "Q 0.00"),
        "etiqueta_descuento": etiqueta_descuento,
        "descuento": crear_casilla_pvp(pvp_descuento_frame, indice, 1, "$ 0.00"),
        "descuento_quetzales": crear_casilla_pvp(pvp_descuento_frame, indice, 2, "Q 0.00"),
        "total_descuento": crear_casilla_pvp(pvp_descuento_frame, indice, 3, "$ 0.00"),
        "total_descuento_quetzales": crear_casilla_pvp(
            pvp_descuento_frame, indice, 4, "Q 0.00"
        ),
    }

totales_generales = {}
for clave_total, marco_total in (
    ("pvp", pvp_rubros_frame),
    ("descuento", pvp_descuento_frame),
):
    tk.Label(
        marco_total,
        text="TOTAL",
        font=("Arial", 9, "bold"),
        bg=GRIS,
        fg=CORINTO,
        anchor="e",
    ).grid(row=5, column=0, columnspan=3, sticky="ew", padx=3, pady=(4, 2))
    totales_generales[clave_total] = (
        crear_casilla_pvp(marco_total, 5, 3, "$ 0.00", CORINTO),
        crear_casilla_pvp(marco_total, 5, 4, "Q 0.00", CORINTO),
    )


def actualizar_filas_pvp():
    nombres = {r.get("nombre") for r in rubros_cantidad if r.get("nombre")}
    for nombre_rubro, valores in pvp_rubros_campos.items():
        visible = nombre_rubro == "ADULTOS" or nombre_rubro in nombres
        for widget in valores.values():
            if visible:
                widget.grid()
            else:
                widget.grid_remove()


actualizar_filas_pvp()

for marco in (pvp_rubros_frame, pvp_descuento_frame):
    for numero_columna in range(5):
        marco.grid_columnconfigure(numero_columna, weight=1)

for indice in range(6):
    resumen_frame.grid_columnconfigure(indice, weight=1)

zona_tabla = tk.Frame(contenedor, bg=BLANCO)
zona_tabla.pack(fill="both", expand=True)

canvas_tabla = tk.Canvas(zona_tabla, bg=BLANCO, highlightthickness=0)
canvas_tabla.pack(side="left", fill="both", expand=True)

scrollbar_tabla = tk.Scrollbar(zona_tabla, orient="vertical", command=canvas_tabla.yview)
scrollbar_tabla.pack(side="right", fill="y")
canvas_tabla.configure(yscrollcommand=scrollbar_tabla.set)


def desplazar_tabla(event):
    x = canvas_tabla.winfo_pointerx() - canvas_tabla.winfo_rootx()
    y = canvas_tabla.winfo_pointery() - canvas_tabla.winfo_rooty()
    if 0 <= x <= canvas_tabla.winfo_width() and 0 <= y <= canvas_tabla.winfo_height():
        unidades = -int(event.delta / 120) if event.delta else 0
        if unidades == 0 and event.delta:
            unidades = -1 if event.delta > 0 else 1
        if unidades:
            canvas_tabla.yview_scroll(unidades, "units")


def desplazar_tabla_arriba(event):
    canvas_tabla.yview_scroll(-1, "units")


def desplazar_tabla_abajo(event):
    canvas_tabla.yview_scroll(1, "units")


ventana.bind_all("<MouseWheel>", desplazar_tabla)
ventana.bind_all("<Button-4>", desplazar_tabla_arriba)
ventana.bind_all("<Button-5>", desplazar_tabla_abajo)

tabla = tk.Frame(canvas_tabla, bg=BLANCO)
canvas_tabla_window = canvas_tabla.create_window((0, 0), window=tabla, anchor="nw")


def ajustar_ancho_tabla(event):
    canvas_tabla.itemconfig(canvas_tabla_window, width=event.width)
    ventana.after_idle(sincronizar_columnas_conceptos)


canvas_tabla.bind("<Configure>", ajustar_ancho_tabla)


def actualizar_scroll_tabla(event=None):
    canvas_tabla.configure(scrollregion=canvas_tabla.bbox("all"))


tabla.bind("<Configure>", actualizar_scroll_tabla)

encabezados = [
    ("CONCEPTO", 0),
    ("COSTO NETO TOTAL POR TODAS LAS PERSONAS", 1),
    ("COSTO NETO POR PERSONA", 2),
    ("PRECIO DE VENTA AL PUBLICO (PVP)", 3),
    ("PRECIO POR PERSONA (PVP)", 4),
]

for texto, columna in encabezados:
    label = tk.Label(
        tabla,
        text=texto,
        font=("Arial", 10, "bold"),
        bg=AZUL,
        fg=BLANCO,
        pady=5,
        wraplength=170,
        justify="center",
    )
    label.grid(row=0, column=columna, sticky="nsew", padx=1, pady=1)

tabla.grid_columnconfigure(0, weight=2, minsize=320)
tabla.grid_columnconfigure(1, weight=2, minsize=175)
tabla.grid_columnconfigure(2, weight=2, minsize=160)
tabla.grid_columnconfigure(3, weight=2, minsize=180)
tabla.grid_columnconfigure(4, weight=2, minsize=170)


def actualizar_selectores_conceptos():
    nombres_activos = {r.get("nombre") for r in rubros_cantidad if r.get("nombre")}
    activos = [r for r in RUBROS_CANTIDAD if r in nombres_activos]
    hay_tipos = len(activos) > 1
    todas = filas_conceptos_fijas + filas_conceptos_dinamicas
    for fila in filas_conceptos_dinamicas:
        actual = fila["concepto"].get().strip()
        otros = [
            otra["concepto"].get().strip()
            for otra in todas
            if otra is not fila and otra["concepto"].get().strip()
        ]
        generales = {c for c in otros if info_concepto(c)[1] is None}
        tipadas = {c for c in otros if info_concepto(c)[1] is not None}
        bases_tipadas = {info_concepto(c)[0] for c in tipadas}
        valores = []
        for base in CONCEPTOS_DISPONIBLES:
            repetible = base == "MISCELANEOS"
            if repetible or (base not in generales and base not in bases_tipadas):
                valores.append(base)
            if hay_tipos and (repetible or base not in generales):
                for rubro in activos:
                    nombre = f"{base} {rubro}"
                    if repetible or nombre not in tipadas:
                        valores.append(nombre)
        if actual and actual not in valores:
            valores.insert(0, actual)
        fila["concepto"]["values"] = valores


def reiniciar_fila_concepto(fila):
    fila["concepto"].set("")
    fila["subtipo"].set("")
    fila["subtipo"].grid_remove()
    fila["concepto"].grid(row=0, column=0, sticky="nsew", padx=0, pady=0, ipady=5)
    configurar_fila_concepto(fila)


def configurar_fila_concepto(fila):
    concepto = fila["concepto"].get().strip()
    color_fila = fila["color"]
    frame = fila["frame"]

    for widget in list(fila["celdas"]):
        widget.destroy()

    fila["celdas"] = []
    fila["campo_editable"] = None
    fila["costo_total"] = None
    fila["costo_persona"] = None
    fila["costo_total_resultado"] = None
    fila["costo_persona_resultado"] = None
    fila["resultado"] = None
    fila["persona"] = None

    if not concepto:
        for columna in (1, 2):
            etiqueta = tk.Label(
                frame,
                text="$ 0.00",
                font=("Arial", 10, "bold"),
                bg=GRIS_BLOQUEADO,
                fg="#000000",
                anchor="e",
                padx=10,
            )
            etiqueta.grid(
                row=0,
                column=columna,
                sticky="nsew",
                padx=1,
                pady=1,
                ipady=5,
            )
            fila["celdas"].append(etiqueta)

        resultado = tk.Label(
            frame,
            text="$ 0.00",
            font=("Arial", 10, "bold"),
            bg=color_fila,
            fg=CORINTO,
            anchor="e",
            padx=10,
        )
        resultado.grid(row=0, column=3, sticky="nsew", padx=1, pady=1, ipady=5)

        persona = tk.Label(
            frame,
            text="$ 0.00",
            font=("Arial", 10, "bold"),
            bg=color_fila,
            fg=VERDE,
            anchor="e",
            padx=10,
        )
        persona.grid(row=0, column=4, sticky="nsew", padx=1, pady=1, ipady=5)

        fila["resultado"] = resultado
        fila["persona"] = persona
        fila["celdas"].extend([resultado, persona])
        actualizar_orden_campos()
        return

    if EDITABILIDAD_COSTOS[info_concepto(concepto)[0]] == "total":
        entrada_total = tk.Entry(
            frame,
            font=("Arial", 11),
            justify="right",
            relief="solid",
            bd=1,
        )
        colocar_costo_editable(entrada_total, 0, 1, color_fila)
        fila["costo_total"] = entrada_total
        fila["campo_editable"] = entrada_total
        fila["celdas"].append(entrada_total)
    else:
        etiqueta_total = tk.Label(
            frame,
            text="$ 0.00",
            font=("Arial", 10, "bold"),
            bg=GRIS_BLOQUEADO,
            fg="#000000",
            anchor="e",
            padx=10,
        )
        etiqueta_total.grid(row=0, column=1, sticky="nsew", padx=1, pady=1, ipady=5)
        fila["costo_total_resultado"] = etiqueta_total
        fila["celdas"].append(etiqueta_total)

    if EDITABILIDAD_COSTOS[info_concepto(concepto)[0]] == "persona":
        entrada_persona = tk.Entry(
            frame,
            font=("Arial", 11),
            justify="right",
            relief="solid",
            bd=1,
        )
        colocar_costo_editable(entrada_persona, 0, 2, color_fila)
        fila["costo_persona"] = entrada_persona
        fila["campo_editable"] = entrada_persona
        fila["celdas"].append(entrada_persona)
    else:
        etiqueta_persona = tk.Label(
            frame,
            text="$ 0.00",
            font=("Arial", 10, "bold"),
            bg=GRIS_BLOQUEADO,
            fg="#000000",
            anchor="e",
            padx=10,
        )
        etiqueta_persona.grid(row=0, column=2, sticky="nsew", padx=1, pady=1, ipady=5)
        fila["costo_persona_resultado"] = etiqueta_persona
        fila["celdas"].append(etiqueta_persona)

    resultado = tk.Label(
        frame,
        text="$ 0.00",
        font=("Arial", 10, "bold"),
        bg=color_fila,
        fg=CORINTO,
        anchor="e",
        padx=10,
    )
    resultado.grid(row=0, column=3, sticky="nsew", padx=1, pady=1, ipady=5)

    persona = tk.Label(
        frame,
        text="$ 0.00",
        font=("Arial", 10, "bold"),
        bg=color_fila,
        fg=VERDE,
        anchor="e",
        padx=10,
    )
    persona.grid(row=0, column=4, sticky="nsew", padx=1, pady=1, ipady=5)

    fila["resultado"] = resultado
    fila["persona"] = persona
    fila["celdas"].extend([resultado, persona])

    if fila["campo_editable"] is not None:
        fila["campo_editable"].bind("<Return>", siguiente_campo)
        fila["campo_editable"].bind("<KP_Enter>", siguiente_campo)

    if concepto in (
        "BOLETOS NETOS ADULTOS",
        "BOLETOS NETOS NIÑOS",
        "BOLETOS NETOS INFANTES",
    ):
        if fila.get("costo_total") is not None:
            fila["costo_total"].configure(
                state="readonly",
                readonlybackground="#F3F4F6",
                fg="#000000",
            )

    actualizar_orden_campos()


def cambiar_concepto(event=None):
    widget = event.widget if event else None
    for fila in filas_conceptos_dinamicas:
        if fila["concepto"] is widget:
            base, rubro_tipo = info_concepto(fila["concepto"].get().strip())
            if base == "MISCELANEOS":
                fila["subtipo"]["values"] = (
                    MISCELANEOS_SUBTIPOS
                    if rubro_tipo is None
                    else [f"{subtipo} {rubro_tipo}" for subtipo in MISCELANEOS_SUBTIPOS]
                )
                fila["subtipo"].set("")
                fila["concepto"].grid_remove()
                fila["subtipo"].grid(
                    row=0,
                    column=0,
                    sticky="nsew",
                    padx=0,
                    pady=0,
                    ipady=5,
                )
            else:
                fila["subtipo"].set("")
                fila["subtipo"].grid_remove()
                fila["concepto"].grid(
                    row=0,
                    column=0,
                    sticky="nsew",
                    padx=0,
                    pady=0,
                    ipady=5,
                )
            configurar_fila_concepto(fila)
            break
    actualizar_selectores_conceptos()
    actualizar_orden_campos()
    ventana.after_idle(sincronizar_columnas_conceptos)


def cambiar_subtipo(event=None):
    widget = event.widget if event else None
    for fila in filas_conceptos_dinamicas:
        if fila["subtipo"] is widget:
            fila["subtipo"].grid(
                row=0,
                column=0,
                sticky="nsew",
                padx=0,
                pady=0,
                ipady=5,
            )
            break
    ventana.after_idle(sincronizar_columnas_conceptos)


def quitar_fila_concepto(fila):
    if len(filas_conceptos_dinamicas) <= 1:
        return
    if fila not in filas_conceptos_dinamicas:
        return
    filas_conceptos_dinamicas.remove(fila)
    fila["frame"].destroy()
    actualizar_selectores_conceptos()
    actualizar_orden_campos()
    actualizar_posiciones_conceptos()
    ventana.after_idle(sincronizar_columnas_conceptos)


def crear_fila_concepto(concepto_inicial="", fijo=False, rubro_dependiente=None):
    numero_fila = len(filas_conceptos_dinamicas) + 1
    color_fila = GRIS if numero_fila % 2 == 0 else BLANCO
    fila_frame = tk.Frame(tabla, bg=color_fila)

    selector_frame = tk.Frame(fila_frame, bg=color_fila)
    selector_frame.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)

    concepto_widget = ttk.Combobox(
        selector_frame,
        values=CONCEPTOS_DISPONIBLES,
        font=("Arial", 10),
        state="readonly",
    )
    if concepto_inicial:
        concepto_widget.set(concepto_inicial)
    if fijo:
        concepto_widget.configure(state="disabled")
    concepto_widget.grid(row=0, column=0, sticky="nsew", padx=0, pady=0, ipady=5)

    subtipo_widget = ttk.Combobox(
        selector_frame,
        values=MISCELANEOS_SUBTIPOS,
        font=("Arial", 9),
        state="readonly",
    )
    subtipo_widget.grid(row=1, column=0, sticky="nsew", padx=0, pady=(2, 0), ipady=3)
    subtipo_widget.grid_remove()
    subtipo_widget.bind("<<ComboboxSelected>>", cambiar_subtipo)
    selector_frame.grid_columnconfigure(0, weight=1)

    boton_quitar = tk.Button(
        selector_frame,
        text="⊗",
        command=lambda: quitar_fila_concepto(fila),
        font=("Arial", 16, "bold"),
        bg=color_fila,
        fg="#C00000",
        activebackground=color_fila,
        activeforeground="#C00000",
        relief="flat",
        bd=0,
        highlightthickness=0,
        cursor="hand2",
        width=2,
        padx=0,
        pady=0,
    )
    if not fijo:
        boton_quitar.grid(row=0, column=1, sticky="ne", padx=(2, 2), pady=1)
    selector_frame.grid_columnconfigure(1, weight=0)

    fila = {
        "frame": fila_frame,
        "selector_frame": selector_frame,
        "boton_quitar": boton_quitar,
        "fijo": fijo,
        "concepto": concepto_widget,
        "subtipo": subtipo_widget,
        "color": color_fila,
        "celdas": [],
        "campo_editable": None,
        "costo_total": None,
        "costo_persona": None,
        "costo_total_resultado": None,
        "costo_persona_resultado": None,
        "resultado": None,
        "persona": None,
        "rubro_dependiente": rubro_dependiente,
    }

    if fijo:
        filas_conceptos_fijas.append(fila)
    else:
        filas_conceptos_dinamicas.append(fila)

    if not fijo:
        concepto_widget.bind("<<ComboboxSelected>>", cambiar_concepto)

    configurar_fila_concepto(fila)

    for columna in range(5):
        fila_frame.grid_columnconfigure(columna, weight=0)

    actualizar_selectores_conceptos()
    actualizar_orden_campos()
    return fila


def obtener_cantidad_rubro(nombre):
    for rubro in rubros_cantidad:
        if rubro.get("nombre") == nombre:
            try:
                return int(rubro["entrada"].get().strip() or "0")
            except ValueError:
                return 0
    return 0


def sincronizar_filas_dependientes():
    rubros_dependientes = {
        "NIÑOS": ("BOLETOS NETOS NIÑOS", "DISEÑADOR NIÑOS"),
        "INFANTES": ("BOLETOS NETOS INFANTES", "DISEÑADOR INFANTES"),
    }
    rubros_activos = {
        rubro.get("nombre") for rubro in rubros_cantidad if rubro.get("nombre")
    }

    for fila in list(filas_conceptos_fijas):
        rubro_dependiente = fila.get("rubro_dependiente")
        if rubro_dependiente and rubro_dependiente not in rubros_activos:
            filas_conceptos_fijas.remove(fila)
            fila["frame"].destroy()

    for fila in filas_conceptos_dinamicas:
        _, rubro_tipo = info_concepto(fila["concepto"].get().strip())
        if rubro_tipo and rubro_tipo not in rubros_activos:
            reiniciar_fila_concepto(fila)

    existentes = {
        fila.get("rubro_dependiente")
        for fila in filas_conceptos_fijas
        if fila.get("rubro_dependiente")
    }

    for rubro in ("NIÑOS", "INFANTES"):
        if rubro not in rubros_activos or rubro in existentes:
            continue
        boleto, disenador = rubros_dependientes[rubro]
        crear_fila_concepto(boleto, fijo=True, rubro_dependiente=rubro)
        crear_fila_concepto(disenador, fijo=True, rubro_dependiente=rubro)

    actualizar_selectores_conceptos()
    actualizar_orden_campos()
    actualizar_posiciones_conceptos()


def sincronizar_columnas_conceptos():
    if not (filas_conceptos_fijas + filas_conceptos_dinamicas):
        return
    try:
        tabla.update_idletasks()
        anchos = []
        for columna in range(5):
            bbox = tabla.grid_bbox(columna, 0)
            if bbox:
                anchos.append(bbox[2])
            else:
                anchos.append(0)
        for fila in filas_conceptos_fijas + filas_conceptos_dinamicas:
            for columna in range(5):
                fila["frame"].grid_columnconfigure(
                    columna,
                    weight=0,
                    minsize=anchos[columna],
                )
    except tk.TclError:
        pass


def actualizar_posiciones_conceptos():
    fila_actual = 1
    for fila in filas_conceptos_fijas + filas_conceptos_dinamicas:
        color_fila = GRIS if fila_actual % 2 == 0 else BLANCO
        fila["color"] = color_fila
        fila["frame"].config(bg=color_fila)
        fila["selector_frame"].config(bg=color_fila)
        fila["boton_quitar"].config(bg=color_fila, activebackground=color_fila)
        fila["frame"].grid(
            row=fila_actual,
            column=0,
            columnspan=5,
            sticky="nsew",
            padx=0,
            pady=0,
        )
        fila_actual += 1

    boton_agregar_concepto.grid(row=fila_actual, column=0, columnspan=5, pady=5)
    fila_actual += 1

    total_label.grid(row=fila_actual, column=0, sticky="nsew", padx=1, pady=3)
    total_costo_label.grid(row=fila_actual, column=1, sticky="nsew", padx=1, pady=3)
    total_costo_persona_label.grid(row=fila_actual, column=2, sticky="nsew", padx=1, pady=3)
    total_resultado_label.grid(row=fila_actual, column=3, sticky="nsew", padx=1, pady=3)
    total_persona_label.grid(row=fila_actual, column=4, sticky="nsew", padx=1, pady=3)

    canvas_tabla.configure(scrollregion=canvas_tabla.bbox("all"))
    ventana.after_idle(sincronizar_columnas_conceptos)


def agregar_fila_concepto():
    fila = crear_fila_concepto()
    actualizar_posiciones_conceptos()
    fila["concepto"].focus()


def calcular():
    try:
        cantidades = {
            nombre: obtener_cantidad_rubro(nombre) for nombre in RUBROS_CANTIDAD
        }
        personas = sum(cantidades.values())
        if personas < 1 or any(v < 0 for v in cantidades.values()):
            raise ValueError
    except ValueError:
        messagebox.showerror(
            "Dato incorrecto",
            "La cantidad de personas debe ser un entero válido y debe haber al menos una persona.",
        )
        return

    try:
        cantidad_adultos = cantidades["ADULTOS"]
        cantidad_ninos = cantidades["NIÑOS"]
        cantidad_infantes = cantidades["INFANTES"]

        boletos_adultos = obtener_monto(boletos_campos["adultos"]["entrada"])
        boletos_adultos_ninos = (
            obtener_monto(boletos_campos["adultos_ninos"]["entrada"])
            if cantidad_ninos
            else boletos_adultos
        )
        boletos_adultos_ninos_infantes = (
            obtener_monto(boletos_campos["adultos_ninos_infantes"]["entrada"])
            if cantidad_infantes
            else boletos_adultos_ninos
        )
        boletos_totales = {
            "ADULTOS": boletos_adultos,
            "NIÑOS": (boletos_adultos_ninos - boletos_adultos) if cantidad_ninos else 0.0,
            "INFANTES": (
                (boletos_adultos_ninos_infantes - boletos_adultos_ninos)
                if cantidad_infantes
                else 0.0
            ),
        }

        precio_disenador_adultos = obtener_monto(disenador_campos["adultos"]["entrada"])
        disenador_adultos = precio_disenador_adultos * cantidad_adultos

        if cantidad_ninos:
            precio_disenador_adultos_ninos = obtener_monto(
                disenador_campos["adultos_ninos"]["entrada"]
            )
            disenador_adultos_ninos = precio_disenador_adultos_ninos * (
                cantidad_adultos + cantidad_ninos
            )
        else:
            disenador_adultos_ninos = disenador_adultos

        if cantidad_infantes:
            precio_disenador_combinado = obtener_monto(
                disenador_campos["adultos_ninos_infantes"]["entrada"]
            )
            disenador_combinado = precio_disenador_combinado * (
                cantidad_adultos + cantidad_ninos + cantidad_infantes
            )
        else:
            disenador_combinado = disenador_adultos_ninos

        disenador_totales = {
            "ADULTOS": disenador_adultos,
            "NIÑOS": (disenador_adultos_ninos - disenador_adultos) if cantidad_ninos else 0.0,
            "INFANTES": (
                (disenador_combinado - disenador_adultos_ninos)
                if cantidad_infantes
                else 0.0
            ),
        }

        if disenador_totales["INFANTES"] <= 0:
            disenador_totales["INFANTES"] = 0.0

    except ValueError as exc:
        messagebox.showerror(
            "Dato incorrecto",
            str(exc) or "Revisa los montos de boletos y diseñador.",
        )
        return

    automaticos = {
        "BOLETOS NETOS ADULTOS": ("ADULTOS", boletos_totales["ADULTOS"]),
        "BOLETOS NETOS NIÑOS": ("NIÑOS", boletos_totales["NIÑOS"]),
        "BOLETOS NETOS INFANTES": ("INFANTES", boletos_totales["INFANTES"]),
        "DISEÑADOR ADULTOS": ("ADULTOS", disenador_totales["ADULTOS"]),
        "DISEÑADOR NIÑOS": ("NIÑOS", disenador_totales["NIÑOS"]),
        "DISEÑADOR INFANTES": ("INFANTES", disenador_totales["INFANTES"]),
    }
    cantidades_nombres = {
        "ADULTOS": cantidades["ADULTOS"],
        "NIÑOS": cantidades["NIÑOS"],
        "INFANTES": cantidades["INFANTES"],
    }
    pvp_por_rubro = {"ADULTOS": 0.0, "NIÑOS": 0.0, "INFANTES": 0.0}
    total_costos = total_costos_persona = total_resultados = total_por_persona = 0.0

    filas = filas_conceptos_fijas + filas_conceptos_dinamicas
    for fila in filas:
        concepto = fila["concepto"].get().strip()
        if concepto in automaticos:
            rubro, costo_total = automaticos[concepto]
            cantidad = cantidades_nombres[rubro]
            costo_persona = costo_total / cantidad if cantidad else 0.0
            porcentaje = PORCENTAJES[concepto]
            pvp_total = costo_total / porcentaje
            pvp_persona = pvp_total / cantidad if cantidad else 0.0
            if fila.get("costo_total") is not None:
                campo = fila["costo_total"]
                campo.configure(state="normal")
                campo.delete(0, tk.END)
                campo.insert(0, f"$ {costo_total:,.2f}")
                campo.configure(
                    state="readonly",
                    readonlybackground="#F3F4F6",
                    fg="#000000",
                )
            if fila.get("costo_total_resultado") is not None:
                fila["costo_total_resultado"].config(text=f"$ {costo_total:,.2f}")
            if fila.get("costo_persona_resultado") is not None:
                fila["costo_persona_resultado"].config(text=f"$ {costo_persona:,.2f}")
            fila["resultado"].config(text=f"$ {pvp_total:,.2f}")
            fila["persona"].config(text=f"$ {pvp_persona:,.2f}")
            if cantidad:
                pvp_por_rubro[rubro] += pvp_persona
            total_costos += costo_total
            total_costos_persona += costo_persona
            total_resultados += pvp_total
            total_por_persona += pvp_persona
            continue

        if not concepto:
            continue
        base, rubro_tipo = info_concepto(concepto)
        tipo_editable = EDITABILIDAD_COSTOS[base]
        personas_fila = cantidades_nombres[rubro_tipo] if rubro_tipo else personas
        try:
            if tipo_editable == "total":
                costo_total = obtener_monto(fila["costo_total"])
                costo_persona = costo_total / personas_fila if personas_fila else 0.0
            else:
                costo_persona = obtener_monto(fila["costo_persona"])
                costo_total = costo_persona * personas_fila
        except ValueError:
            campo_error = (
                fila["costo_total"]
                if tipo_editable == "total"
                else fila["costo_persona"]
            )
            messagebox.showerror(
                "Dato incorrecto",
                f"El valor ingresado en {concepto} no es válido.",
            )
            campo_error.focus()
            return

        if fila.get("costo_total_resultado") is not None:
            fila["costo_total_resultado"].config(text=f"$ {costo_total:,.2f}")
        if fila.get("costo_persona_resultado") is not None:
            fila["costo_persona_resultado"].config(text=f"$ {costo_persona:,.2f}")
        if base == "ENTRADAS EVENTOS":
            resultado, precio_persona = costo_total, costo_persona
        else:
            porcentaje = PORCENTAJES[base]
            resultado = costo_total / porcentaje
            precio_persona = resultado / personas_fila if personas_fila else 0.0
        if rubro_tipo:
            if personas_fila:
                pvp_por_rubro[rubro_tipo] += precio_persona
        else:
            for nombre_rubro, cantidad in cantidades_nombres.items():
                if cantidad:
                    pvp_por_rubro[nombre_rubro] += precio_persona
        fila["resultado"].config(text=f"$ {resultado:,.2f}")
        fila["persona"].config(text=f"$ {precio_persona:,.2f}")
        total_costos += costo_total
        total_costos_persona += costo_persona
        total_resultados += resultado
        total_por_persona += precio_persona

    total_costo_label.config(text=f"$ {total_costos:,.2f}")
    total_costo_persona_label.config(text=f"$ {total_costos_persona:,.2f}")
    total_resultado_label.config(text=f"$ {total_resultados:,.2f}")
    total_persona_label.config(text=f"$ {total_por_persona:,.2f}")
    total_general_pvp = total_general_descuento = 0.0
    for nombre_rubro, valores in pvp_rubros_campos.items():
        monto_pvp = pvp_por_rubro[nombre_rubro]
        monto_descuento = monto_pvp / 1.05
        total_rubro_pvp = monto_pvp * cantidades_nombres[nombre_rubro]
        total_rubro_descuento = monto_descuento * cantidades_nombres[nombre_rubro]
        total_general_pvp += total_rubro_pvp
        total_general_descuento += total_rubro_descuento
        actualizar_casilla(valores["pvp"], f"$ {monto_pvp:,.2f}")
        actualizar_casilla(
            valores["pvp_quetzales"],
            f"Q {monto_pvp * FACTOR_CONVERSION:,.2f}",
        )
        actualizar_casilla(valores["descuento"], f"$ {monto_descuento:,.2f}")
        actualizar_casilla(
            valores["descuento_quetzales"],
            f"Q {monto_descuento * FACTOR_CONVERSION:,.2f}",
        )
        actualizar_casilla(valores["total_pvp"], f"$ {total_rubro_pvp:,.2f}")
        actualizar_casilla(
            valores["total_pvp_quetzales"],
            f"Q {total_rubro_pvp * FACTOR_CONVERSION:,.2f}",
        )
        actualizar_casilla(valores["total_descuento"], f"$ {total_rubro_descuento:,.2f}")
        actualizar_casilla(
            valores["total_descuento_quetzales"],
            f"Q {total_rubro_descuento * FACTOR_CONVERSION:,.2f}",
        )
    actualizar_casilla(totales_generales["pvp"][0], f"$ {total_general_pvp:,.2f}")
    actualizar_casilla(
        totales_generales["pvp"][1],
        f"Q {total_general_pvp * FACTOR_CONVERSION:,.2f}",
    )
    actualizar_casilla(totales_generales["descuento"][0], f"$ {total_general_descuento:,.2f}")
    actualizar_casilla(
        totales_generales["descuento"][1],
        f"Q {total_general_descuento * FACTOR_CONVERSION:,.2f}",
    )


def limpiar():
    while len(rubros_cantidad) > 1:
        rubro = rubros_cantidad.pop()
        rubro["frame"].destroy()

    if rubros_cantidad:
        rubro_adultos = rubros_cantidad[0]
        rubro_adultos["nombre"] = "ADULTOS"
        rubro_adultos["selector"].set("ADULTOS")
        rubro_adultos["entrada"].delete(0, tk.END)
        rubro_adultos["entrada"].insert(0, "1")

    actualizar_selectores_rubros()
    actualizar_posiciones_rubros()
    for campo in boletos_campos.values():
        campo["entrada"].delete(0, tk.END)
        campo["entrada"].insert(0, "$ 0.00")
        campo["precio_original"] = None
        campo["ultimo_resultado"] = None
    for campo in disenador_campos.values():
        campo["entrada"].delete(0, tk.END)
        campo["entrada"].insert(0, "$ 0.00")
        campo["precio_original"] = None
        campo["ultimo_resultado"] = None
    actualizar_campos_boleto()

    for fila in list(filas_conceptos_fijas):
        if fila.get("rubro_dependiente"):
            filas_conceptos_fijas.remove(fila)
            fila["frame"].destroy()

    while len(filas_conceptos_dinamicas) > 1:
        fila = filas_conceptos_dinamicas.pop()
        fila["frame"].destroy()

    if filas_conceptos_dinamicas:
        reiniciar_fila_concepto(filas_conceptos_dinamicas[0])

    actualizar_selectores_conceptos()
    for fila in filas_conceptos_fijas:
        configurar_fila_concepto(fila)
    actualizar_orden_campos()
    actualizar_posiciones_conceptos()

    total_costo_label.config(text="$ 0.00")
    total_costo_persona_label.config(text="$ 0.00")
    total_resultado_label.config(text="$ 0.00")
    total_persona_label.config(text="$ 0.00")

    for valores in pvp_rubros_campos.values():
        actualizar_casilla(valores["pvp"], "$ 0.00")
        actualizar_casilla(valores["pvp_quetzales"], "Q 0.00")
        actualizar_casilla(valores["descuento"], "$ 0.00")
        actualizar_casilla(valores["descuento_quetzales"], "Q 0.00")
        actualizar_casilla(valores["total_pvp"], "$ 0.00")
        actualizar_casilla(valores["total_pvp_quetzales"], "Q 0.00")
        actualizar_casilla(valores["total_descuento"], "$ 0.00")
        actualizar_casilla(valores["total_descuento_quetzales"], "Q 0.00")
    for casillas in totales_generales.values():
        actualizar_casilla(casillas[0], "$ 0.00")
        actualizar_casilla(casillas[1], "Q 0.00")

    for campo in disenador_campos.values():
        campo["entrada"].delete(0, tk.END)
        campo["entrada"].insert(0, "$ 0.00")
    actualizar_campos_disenador()
    actualizar_conversiones()

    if rubros_cantidad:
        rubros_cantidad[0]["entrada"].focus()


crear_fila_concepto("BOLETOS NETOS ADULTOS", fijo=True)
crear_fila_concepto("DISEÑADOR ADULTOS", fijo=True)
crear_fila_concepto()

boton_agregar_concepto = tk.Button(
    tabla,
    text="⊕",
    command=agregar_fila_concepto,
    font=("Arial", 18, "bold"),
    bg=AZUL,
    fg=BLANCO,
    activebackground=CORINTO,
    activeforeground=BLANCO,
    relief="flat",
    bd=0,
    cursor="hand2",
    width=3,
    height=1,
)

fila_total = len(filas_conceptos_fijas) + len(filas_conceptos_dinamicas) + 2

total_label = tk.Label(
    tabla,
    text="TOTAL",
    font=("Arial", 11, "bold"),
    bg=CORINTO,
    fg=BLANCO,
    anchor="w",
    padx=10,
    pady=6,
)
total_label.grid(row=fila_total, column=0, sticky="nsew", padx=1, pady=3)

total_costo_label = tk.Label(
    tabla,
    text="$ 0.00",
    font=("Arial", 12, "bold"),
    bg=CORINTO,
    fg=BLANCO,
    anchor="e",
    padx=10,
    pady=6,
)
total_costo_label.grid(row=fila_total, column=1, sticky="nsew", padx=1, pady=3)

total_costo_persona_label = tk.Label(
    tabla,
    text="$ 0.00",
    font=("Arial", 12, "bold"),
    bg=CORINTO,
    fg=BLANCO,
    anchor="e",
    padx=10,
    pady=6,
)
total_costo_persona_label.grid(row=fila_total, column=2, sticky="nsew", padx=1, pady=3)

total_resultado_label = tk.Label(
    tabla,
    text="$ 0.00",
    font=("Arial", 12, "bold"),
    bg=CORINTO,
    fg=BLANCO,
    anchor="e",
    padx=10,
    pady=6,
)
total_resultado_label.grid(row=fila_total, column=3, sticky="nsew", padx=1, pady=3)

total_persona_label = tk.Label(
    tabla,
    text="$ 0.00",
    font=("Arial", 12, "bold"),
    bg=CORINTO,
    fg=BLANCO,
    anchor="e",
    padx=10,
    pady=6,
)
total_persona_label.grid(row=fila_total, column=4, sticky="nsew", padx=1, pady=3)

actualizar_posiciones_conceptos()

for campo in orden_campos:
    campo.bind("<Return>", siguiente_campo)
    campo.bind("<KP_Enter>", siguiente_campo)

botones_frame = tk.Frame(contenedor, bg=BLANCO)
botones_frame.pack(pady=(5, 3))

boton_calcular = tk.Button(
    botones_frame,
    text="CALCULAR",
    command=calcular,
    font=("Arial", 11, "bold"),
    bg=AZUL,
    fg=BLANCO,
    activebackground=CORINTO,
    activeforeground=BLANCO,
    relief="flat",
    cursor="hand2",
    width=18,
    pady=6,
)
boton_calcular.pack(side="left", padx=10)

boton_limpiar = tk.Button(
    botones_frame,
    text="LIMPIAR",
    command=limpiar,
    font=("Arial", 11, "bold"),
    bg=CORINTO,
    fg=BLANCO,
    activebackground=AZUL,
    activeforeground=BLANCO,
    relief="flat",
    cursor="hand2",
    width=18,
    pady=6,
)
boton_limpiar.pack(side="left", padx=10)

footer = tk.Label(
    ventana,
    text=f"Los datos ingresados son temporales y no se almacenan permanentemente.  ·  Versión {VERSION_APP}",
    font=("Arial", 9),
    bg=BLANCO,
    fg=GRIS_TEXTO,
)
footer.pack(pady=(0, 12))

tabla.bind(
    "<Configure>",
    lambda event: ventana.after_idle(sincronizar_columnas_conceptos),
    add="+",
)



def copiar_imagen_portapapeles(imagen):
    salida = io.BytesIO()
    imagen.convert("RGB").save(salida, "BMP")
    datos = salida.getvalue()[14:]
    salida.close()
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, datos)
    finally:
        win32clipboard.CloseClipboard()


def restaurar_boton_captura():
    boton_captura.config(text="📷", fg=GRIS_TEXTO)


def refrescar_pantalla():
    ventana.update_idletasks()
    ventana.update()
    time.sleep(0.12)


def obtener_bbox_ventana():
    x = ventana.winfo_rootx()
    y = ventana.winfo_rooty()
    return (x, y, x + ventana.winfo_width(), y + ventana.winfo_height())


def capturar_ventana():
    return ImageGrab.grab(bbox=obtener_bbox_ventana(), all_screens=True).convert("RGB")


def capturar_contenido_completo():
    maximizada = False
    _, _, derecha, abajo = obtener_bbox_ventana()
    if ventana.state() == "normal" and (
        derecha > ventana.winfo_screenwidth() or abajo > ventana.winfo_screenheight()
    ):
        ventana.state("zoomed")
        maximizada = True
        refrescar_pantalla()

    posicion_scroll = canvas_tabla.yview()[0]
    try:
        actualizar_scroll_tabla()
        canvas_tabla.yview_moveto(0)
        refrescar_pantalla()
        x0, y0, _, _ = obtener_bbox_ventana()
        base = capturar_ventana()
        cx = canvas_tabla.winfo_rootx() - x0
        cy = canvas_tabla.winfo_rooty() - y0
        ancho_canvas = canvas_tabla.winfo_width()
        alto_canvas = canvas_tabla.winfo_height()
        region = canvas_tabla.bbox("all")
        if not region or region[3] - region[1] <= alto_canvas:
            return base

        origen = region[1]
        alto_total = region[3] - region[1]
        piezas = [(0, base.crop((cx, cy, cx + ancho_canvas, cy + alto_canvas)))]
        tope = 0
        while tope + alto_canvas < alto_total and len(piezas) < 200:
            canvas_tabla.yview_moveto((tope + alto_canvas) / alto_total)
            refrescar_pantalla()
            nuevo_tope = int(round(canvas_tabla.canvasy(0))) - origen
            if nuevo_tope <= tope:
                break
            pieza = capturar_ventana().crop((cx, cy, cx + ancho_canvas, cy + alto_canvas))
            piezas.append((nuevo_tope, pieza))
            tope = nuevo_tope

        inferior = base.crop((0, cy + alto_canvas, base.width, base.height))
        final = Image.new(
            "RGB",
            (base.width, cy + alto_total + inferior.height),
            base.getpixel((1, cy + 2)),
        )
        final.paste(base.crop((0, 0, base.width, cy)), (0, 0))
        for tope_pieza, pieza in piezas:
            final.paste(pieza, (cx, cy + tope_pieza))
        final.paste(inferior, (0, cy + alto_total))
        return final
    finally:
        canvas_tabla.yview_moveto(posicion_scroll)
        if maximizada:
            ventana.state("normal")
        refrescar_pantalla()


def tomar_captura():
    exito = False
    try:
        imagen = capturar_contenido_completo()
        copiar_imagen_portapapeles(imagen)
        exito = True
    except Exception as exc:
        messagebox.showerror("Captura", f"No se pudo capturar la pantalla.\n{exc}")
    boton_captura.place(relx=0.995, rely=0.995, anchor="se")
    boton_captura.lift()
    if exito:
        boton_captura.config(text="✔", fg=VERDE)
        ventana.after(1200, restaurar_boton_captura)


def capturar_pantalla():
    boton_captura.place_forget()
    ventana.update()
    ventana.after(150, tomar_captura)


boton_captura = tk.Button(
    ventana,
    text="📷",
    command=capturar_pantalla,
    font=("Segoe UI Emoji", 12),
    bg=BLANCO,
    fg=GRIS_TEXTO,
    activebackground=BLANCO,
    activeforeground=AZUL,
    relief="flat",
    bd=0,
    highlightthickness=0,
    cursor="hand2",
)
boton_captura.place(relx=0.995, rely=0.995, anchor="se")

def version_a_tupla(texto):
    partes = []
    for fragmento in str(texto).lstrip("vV").split("."):
        digitos = "".join(c for c in fragmento if c.isdigit())
        partes.append(int(digitos) if digitos else 0)
    while len(partes) < 3:
        partes.append(0)
    return tuple(partes)


def interpretar_release(datos):
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
            return {
                "version": version,
                "url": url,
                "nombre": NOMBRE_INSTALADOR,
                "sha256": sha256,
            }
    return None


def consultar_ultima_version():
    solicitud = urllib.request.Request(
        URL_ULTIMA_VERSION,
        headers={
            "User-Agent": "DreamTravel-Calculadora",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(solicitud, timeout=8) as respuesta:
        return interpretar_release(json.load(respuesta))


def hilo_consultar(cola):
    try:
        info = consultar_ultima_version()
    except Exception:
        info = None
    cola.put(info)


def hilo_descargar(info, cola):
    try:
        os.makedirs(CARPETA_ACTUALIZACION, exist_ok=True)
        destino = os.path.join(CARPETA_ACTUALIZACION, info["nombre"])
        parcial = destino + ".part"
        solicitud = urllib.request.Request(
            info["url"], headers={"User-Agent": "DreamTravel-Calculadora"}
        )
        huella = hashlib.sha256()
        with urllib.request.urlopen(solicitud, timeout=30) as respuesta, open(parcial, "wb") as archivo:
            total = int(respuesta.headers.get("Content-Length") or 0)
            leido = 0
            while True:
                bloque = respuesta.read(65536)
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
    except Exception as exc:
        shutil.rmtree(CARPETA_ACTUALIZACION, ignore_errors=True)
        cola.put(("error", str(exc)))


def instalar_actualizacion(ruta_instalador):
    subprocess.Popen(
        [ruta_instalador, "/SILENT", "/NORESTART", "/CLOSEAPPLICATIONS"],
        close_fds=True,
        creationflags=getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200),
    )
    ventana.destroy()


def actualizar_programa(info):
    cola = queue.Queue()
    dialogo = tk.Toplevel(ventana)
    dialogo.title("Actualizando")
    dialogo.configure(bg=BLANCO)
    dialogo.resizable(False, False)
    dialogo.transient(ventana)
    dialogo.protocol("WM_DELETE_WINDOW", lambda: None)
    tk.Label(
        dialogo,
        text=f"Descargando la versión {info['version']}...",
        font=("Arial", 10, "bold"),
        bg=BLANCO,
        fg=AZUL,
        padx=30,
        pady=15,
    ).pack()
    barra = ttk.Progressbar(dialogo, mode="determinate", length=320, maximum=100)
    barra.pack(padx=30, pady=(0, 20))
    dialogo.grab_set()
    threading.Thread(target=hilo_descargar, args=(info, cola), daemon=True).start()

    def revisar_descarga():
        resultado = None
        try:
            while resultado is None:
                mensaje = cola.get_nowait()
                if mensaje[0] == "progreso":
                    if mensaje[2]:
                        barra["value"] = mensaje[1] * 100 / mensaje[2]
                else:
                    resultado = mensaje
        except queue.Empty:
            pass
        if resultado is None:
            ventana.after(100, revisar_descarga)
            return
        dialogo.grab_release()
        dialogo.destroy()
        if resultado[0] == "error":
            messagebox.showerror(
                "Actualización",
                f"No se pudo descargar la actualización.\n{resultado[1]}",
            )
            return
        instalar_actualizacion(resultado[1])

    ventana.after(100, revisar_descarga)


def revisar_actualizacion(cola):
    try:
        info = cola.get_nowait()
    except queue.Empty:
        ventana.after(300, lambda: revisar_actualizacion(cola))
        return
    if info and version_a_tupla(info["version"]) > version_a_tupla(VERSION_APP):
        if messagebox.askyesno(
            "Actualización disponible",
            f"Hay una versión nueva ({info['version']}).\n"
            f"Tu versión es la {VERSION_APP}.\n\n¿Quieres actualizar ahora?",
        ):
            actualizar_programa(info)


def iniciar_revision_actualizacion():
    if not getattr(sys, "frozen", False):
        return
    shutil.rmtree(CARPETA_ACTUALIZACION, ignore_errors=True)
    if "USUARIO" in REPO_GITHUB:
        return
    cola = queue.Queue()
    threading.Thread(target=hilo_consultar, args=(cola,), daemon=True).start()
    ventana.after(300, lambda: revisar_actualizacion(cola))


rubros_cantidad[0]["entrada"].focus() if rubros_cantidad else None
ventana.after_idle(sincronizar_columnas_conceptos)
ventana.after(2500, iniciar_revision_actualizacion)
ventana.mainloop()
