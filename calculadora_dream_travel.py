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
    "BOLETOS NETOS": 0.80,
    "DISEÑADOR": 0.95,
    "CIRCUITOS": 0.90,
    "CRUCEROS": 0.90,
    "OPERADOR DIRECTO / JACKELINE": 0.90,
    "ENTRADAS EVENTOS": 1.0,
    "SEGURO DE VIAJE": 0.90,
    "TRASLADOS / SUPERVISOR": 0.90,
    "VISADOS O PERMISOS": 0.80,
    "MISCELANEOS": 0.80,
}

# "total": el monto escrito es el total del grupo (la resta da niños e infantes).
# "persona": el monto escrito es el precio por persona y se multiplica por el grupo.
MODO_CAPTURA = {
    "DISEÑADOR": "persona",
}

FACTOR_CONVERSION = 7.88

VERSION_APP = "1.0.0"
REPO_GITHUB = "alejoco626/Dream_Travel"
NOMBRE_INSTALADOR = "Calculadora_Dream_Travel_Setup.exe"
URL_ULTIMA_VERSION = f"https://api.github.com/repos/{REPO_GITHUB}/releases/latest"
PREFIJO_DESCARGA = f"https://github.com/{REPO_GITHUB}/releases/download/"
CARPETA_ACTUALIZACION = os.path.join(tempfile.gettempdir(), "DreamTravel_Calculadora_Update")

FUENTE = "Segoe UI"

AZUL = "#003D6B"
CORINTO = "#960018"
BLANCO = "#FFFFFF"
TEXTO = "#1F2937"
GRIS_TEXTO = "#6B7280"
GRIS_ICONO = "#9AA4B2"
SECCION = "#F4F6F9"
ZEBRA = "#FAFBFC"
BORDE = "#CBD5E1"
RESALTE = "#E3EEF9"
FOCO = "#F3F8FE"
DESACTIVADO = "#ECEFF3"
BOTON_SUAVE = "#E6EEF7"
BOTON_SUAVE_HOVER = "#D3E2F1"
PELIGRO_SUAVE = "#FBE9EB"

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

NOMBRES_VISTA = {
    "BOLETOS NETOS": "Boletos",
    "DISEÑADOR": "Diseñador",
    "CIRCUITOS": "Circuitos",
    "CRUCEROS": "Cruceros",
    "OPERADOR DIRECTO / JACKELINE": "Operador directo / Jackeline",
    "ENTRADAS EVENTOS": "Entradas eventos",
    "SEGURO DE VIAJE": "Seguro de viaje",
    "TRASLADOS / SUPERVISOR": "Traslados / Supervisor",
    "VISADOS O PERMISOS": "Visados o permisos",
    "MISCELANEOS": "Misceláneos",
}

MISCELANEOS_SUBTIPOS = [
    "Misceláneos",
    "Asientos",
    "Equipaje",
    "Decoración luna de miel",
    "Decoración pedida de mano",
    "Decoración cumpleaños",
    "Decoración aniversario",
    "Entradas a tours",
]

RUBROS_CANTIDAD = ["ADULTOS", "NIÑOS", "INFANTES"]
NOMBRES_RUBRO = {"ADULTOS": "Adultos", "NIÑOS": "Niños", "INFANTES": "Infantes"}
SUBTITULOS = {
    "NIÑOS": "de 4 a 11 años",
    "INFANTES": "de 0 a 3 años",
}
CLAVES_CAMPOS = ("adultos", "adultos_ninos", "adultos_ninos_infantes")
RUBRO_DE_CLAVE = {"adultos_ninos": "NIÑOS", "adultos_ninos_infantes": "INFANTES"}

orden_campos = []


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
ventana.geometry("1280x800")
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


encabezado = tk.Frame(ventana, bg=AZUL, height=95)
encabezado.pack(fill="x")
encabezado.pack_propagate(False)

fecha_label = tk.Label(
    encabezado,
    text="",
    font=(FUENTE, 13, "bold"),
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
    font=(FUENTE, 11, "bold"),
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
    font=(FUENTE, 18, "bold"),
    bg=AZUL,
    fg=BLANCO,
)
titulo.place(relx=0.5, rely=0.35, anchor="center")


servicios = []
personas = {}
resumen_filas = {}
estado = {"activos": None, "pendiente": None, "foco": None, "desglose": False}


# ------------------------------------------------------------- utilidades
def cantidad(rubro):
    caja = personas.get(rubro)
    if caja is None:
        return 0
    try:
        return int(caja.get().strip() or "0")
    except ValueError:
        return 0


def rubros_activos():
    return ["ADULTOS"] + [r for r in ("NIÑOS", "INFANTES") if cantidad(r) > 0]


def tipo_incluido(servicio, rubro):
    if rubro == "ADULTOS":
        return True
    if rubro not in rubros_activos():
        return False
    marca = servicio["checks"].get(rubro)
    return True if marca is None else bool(marca[0].get())


def nombre_servicio(servicio):
    if servicio["subtipo"] is not None:
        return servicio["subtipo"].get().strip() or NOMBRES_VISTA[servicio["base"]]
    return NOMBRES_VISTA[servicio["base"]]


def dinero(valor):
    return f"$ {valor:,.2f}"


def quetzales(valor):
    return f"Q {valor * FACTOR_CONVERSION:,.2f}"


def programar_calculo(event=None):
    if estado["pendiente"] is not None:
        try:
            ventana.after_cancel(estado["pendiente"])
        except Exception:
            pass
    estado["pendiente"] = ventana.after(250, lambda: calcular(silencioso=True))


def boton_plano(padre, texto, comando, fondo, fondo_hover, color, fuente, padx=14, pady=7):
    boton = tk.Label(
        padre,
        text=texto,
        font=fuente,
        bg=fondo,
        fg=color,
        padx=padx,
        pady=pady,
        cursor="hand2",
    )
    boton.bind("<Enter>", lambda event: boton.config(bg=fondo_hover))
    boton.bind("<Leave>", lambda event: boton.config(bg=fondo))
    boton.bind("<Button-1>", lambda event: comando())
    return boton


# ------------------------------------------------------------- estructura
contenedor = tk.Frame(ventana, bg=BLANCO)
contenedor.pack(fill="both", expand=True, padx=20, pady=(12, 6))
contenedor.grid_columnconfigure(0, weight=1)
contenedor.grid_rowconfigure(0, weight=1)

zona_tabla = tk.Frame(contenedor, bg=BLANCO)
zona_tabla.grid(row=0, column=0, sticky="nsew")

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

pagina = tk.Frame(canvas_tabla, bg=BLANCO)
canvas_tabla_window = canvas_tabla.create_window((0, 0), window=pagina, anchor="nw")


def ajustar_ancho_tabla(event):
    canvas_tabla.itemconfig(canvas_tabla_window, width=event.width)


def actualizar_scroll_tabla(event=None):
    canvas_tabla.configure(scrollregion=canvas_tabla.bbox("all"))


canvas_tabla.bind("<Configure>", ajustar_ancho_tabla)
pagina.bind("<Configure>", actualizar_scroll_tabla)


def crear_seccion(titulo, nota=None):
    marco = tk.Frame(pagina, bg=SECCION, padx=18, pady=14)
    marco.pack(fill="x", pady=(0, 12), padx=(0, 12))
    cabeza = tk.Frame(marco, bg=SECCION)
    cabeza.pack(fill="x", pady=(0, 8))
    tk.Label(
        cabeza,
        text=titulo,
        font=(FUENTE, 10, "bold"),
        bg=SECCION,
        fg=AZUL,
    ).pack(side="left")
    if nota:
        tk.Label(
            cabeza,
            text=nota,
            font=(FUENTE, 9),
            bg=SECCION,
            fg=GRIS_TEXTO,
        ).pack(side="left", padx=(12, 0))
    return marco


# ------------------------------------------------------------- personas
personas_frame = crear_seccion("PERSONAS")
personas_fila = tk.Frame(personas_frame, bg=SECCION)
personas_fila.pack(fill="x")


def validar_personas(texto):
    return texto == "" or (texto.isdigit() and len(texto) <= 2)


validar_personas_cmd = ventana.register(validar_personas)


def al_cambiar_personas(event=None):
    activos = tuple(rubros_activos())
    if activos != estado["activos"]:
        estado["activos"] = activos
        actualizar_columnas()
        actualizar_filas_resumen()
        actualizar_orden_campos()
    for rubro, fila in resumen_filas.items():
        fila["cantidad"].config(text=f"× {cantidad(rubro)}")
    programar_calculo()


for columna, rubro in enumerate(RUBROS_CANTIDAD):
    bloque = tk.Frame(personas_fila, bg=SECCION)
    bloque.grid(row=0, column=columna, sticky="w", padx=(0, 36))
    tk.Label(
        bloque,
        text=NOMBRES_RUBRO[rubro],
        font=(FUENTE, 11, "bold"),
        bg=SECCION,
        fg=TEXTO,
    ).grid(row=0, column=0, sticky="w")
    tk.Label(
        bloque,
        text=SUBTITULOS.get(rubro, "mayores de 11 años"),
        font=(FUENTE, 8),
        bg=SECCION,
        fg=GRIS_TEXTO,
    ).grid(row=1, column=0, sticky="w")
    caja = tk.Spinbox(
        bloque,
        from_=0,
        to=99,
        width=4,
        font=(FUENTE, 12, "bold"),
        justify="center",
        relief="flat",
        bd=0,
        bg=BLANCO,
        fg=TEXTO,
        buttonbackground=SECCION,
        highlightthickness=2,
        highlightbackground=BORDE,
        highlightcolor=AZUL,
        insertbackground=AZUL,
        validate="key",
        validatecommand=(validar_personas_cmd, "%P"),
        command=al_cambiar_personas,
    )
    caja.delete(0, tk.END)
    caja.insert(0, "1" if rubro == "ADULTOS" else "0")
    caja.grid(row=0, column=1, rowspan=2, padx=(12, 0))
    caja.bind("<KeyRelease>", al_cambiar_personas, add="+")
    caja.bind("<FocusIn>", lambda event: event.widget.selection_range(0, tk.END), add="+")
    caja.bind("<Return>", lambda event: siguiente_campo(event))
    caja.bind("<KP_Enter>", lambda event: siguiente_campo(event))
    personas[rubro] = caja


# ------------------------------------------------------------- servicios
servicios_frame = crear_seccion(
    "SERVICIOS",
    "Escribe el monto total de cada grupo · Diseñador: precio por persona"
    " · En Misceláneos marca ☑ para incluir niños o infantes",
)
servicios_grid = tk.Frame(servicios_frame, bg=SECCION)
servicios_grid.pack(fill="x")
servicios_grid.grid_columnconfigure(0, weight=1, minsize=250)
for numero_columna in (1, 2, 3):
    servicios_grid.grid_columnconfigure(numero_columna, minsize=160)
servicios_grid.grid_columnconfigure(4, minsize=40)

encabezados_servicios = {}
for numero_columna, (clave, texto, ancla) in enumerate(
    (
        ("nombre", "Servicio", "w"),
        ("adultos", "Adultos", "e"),
        ("adultos_ninos", "Adultos + niños", "e"),
        ("adultos_ninos_infantes", "Adultos + niños + infantes", "e"),
    )
):
    etiqueta = tk.Label(
        servicios_grid,
        text=texto,
        font=(FUENTE, 9, "bold"),
        bg=SECCION,
        fg=GRIS_TEXTO,
        anchor=ancla,
        padx=10,
        pady=4,
    )
    etiqueta.grid(row=0, column=numero_columna, sticky="nsew")
    encabezados_servicios[clave] = etiqueta


def actualizar_columnas():
    activos = rubros_activos()
    hay_ninos = "NIÑOS" in activos
    hay_infantes = "INFANTES" in activos
    if hay_ninos:
        encabezados_servicios["adultos_ninos"].grid()
    else:
        encabezados_servicios["adultos_ninos"].grid_remove()
    encabezados_servicios["adultos_ninos_infantes"].config(
        text="Adultos + niños + infantes" if hay_ninos else "Adultos + infantes"
    )
    if hay_infantes:
        encabezados_servicios["adultos_ninos_infantes"].grid()
    else:
        encabezados_servicios["adultos_ninos_infantes"].grid_remove()
    for servicio in servicios:
        actualizar_fila_servicio(servicio)


def actualizar_fila_servicio(servicio):
    activos = rubros_activos()
    for clave, rubro in RUBRO_DE_CLAVE.items():
        celda = servicio["celdas"][clave]
        if rubro in activos:
            celda.grid()
        else:
            celda.grid_remove()
        entrada = servicio["entradas"][clave]
        if rubro in servicio["checks"]:
            entrada.config(state="normal" if tipo_incluido(servicio, rubro) else "disabled")


def color_fila(servicio):
    return RESALTE if estado["foco"] is servicio else servicio["color"]


def pintar_fila(servicio):
    color = color_fila(servicio)
    for widget in servicio["fondo"]:
        widget.config(bg=color)
    for marca in servicio["checks"].values():
        marca[1].config(activebackground=color)


def resaltar(servicio, clave):
    anterior = estado["foco"]
    estado["foco"] = servicio
    if anterior is not None and anterior is not servicio and anterior in servicios:
        pintar_fila(anterior)
    pintar_fila(servicio)
    for clave_encabezado, etiqueta in encabezados_servicios.items():
        activa = clave_encabezado == clave
        etiqueta.config(bg=RESALTE if activa else SECCION, fg=AZUL if activa else GRIS_TEXTO)
    servicio["entradas"][clave].config(bg=FOCO)


def quitar_resalte(servicio, clave):
    servicio["entradas"][clave].config(bg=BLANCO)
    if estado["foco"] is servicio:
        estado["foco"] = None
        if servicio in servicios:
            pintar_fila(servicio)
    for etiqueta in encabezados_servicios.values():
        etiqueta.config(bg=SECCION, fg=GRIS_TEXTO)


def crear_entrada_monto(padre, servicio, clave):
    entrada = tk.Entry(
        padre,
        font=(FUENTE, 11),
        justify="right",
        width=12,
        relief="flat",
        bd=0,
        bg=BLANCO,
        fg=TEXTO,
        highlightthickness=2,
        highlightbackground=BORDE,
        highlightcolor=AZUL,
        insertbackground=AZUL,
        disabledbackground=DESACTIVADO,
        disabledforeground="#A0A7B1",
    )
    entrada.insert(0, "$ 0.00")
    entrada.bind("<KeyPress>", limpiar_espacios_al_borrar, add="+")
    entrada.bind("<KeyRelease>", programar_calculo, add="+")
    entrada.bind(
        "<FocusIn>",
        lambda event: (resaltar(servicio, clave), event.widget.selection_range(0, tk.END)),
        add="+",
    )
    entrada.bind(
        "<FocusOut>",
        lambda event: (formatear_moneda(event.widget), quitar_resalte(servicio, clave)),
        add="+",
    )
    entrada.bind("<Return>", lambda event: siguiente_campo(event))
    entrada.bind("<KP_Enter>", lambda event: siguiente_campo(event))
    servicio["entradas"][clave] = entrada
    return entrada


def crear_fila_servicio(base, fijo=False):
    servicio = {
        "base": base,
        "fijo": fijo,
        "porcentaje": PORCENTAJES[base],
        "modo": MODO_CAPTURA.get(base, "total"),
        "celdas": {},
        "entradas": {},
        "checks": {},
        "subtipo": None,
        "fondo": [],
        "orden_celdas": [],
        "color": BLANCO,
    }

    celda_nombre = tk.Frame(servicios_grid, bg=BLANCO, padx=10, pady=6)
    servicio["fondo"].append(celda_nombre)
    servicio["orden_celdas"].append(celda_nombre)
    if base == "MISCELANEOS":
        subtipo = ttk.Combobox(
            celda_nombre,
            values=MISCELANEOS_SUBTIPOS,
            font=(FUENTE, 10),
            state="readonly",
            width=26,
        )
        subtipo.set(MISCELANEOS_SUBTIPOS[0])
        subtipo.bind("<<ComboboxSelected>>", programar_calculo)
        subtipo.pack(anchor="w")
        servicio["subtipo"] = subtipo
    else:
        nombre = tk.Label(
            celda_nombre,
            text=NOMBRES_VISTA[base],
            font=(FUENTE, 10, "bold"),
            bg=BLANCO,
            fg=TEXTO,
            anchor="w",
        )
        nombre.pack(anchor="w")
        servicio["fondo"].append(nombre)
        if servicio["modo"] == "persona":
            nota = tk.Label(
                celda_nombre,
                text="precio por persona",
                font=(FUENTE, 8),
                bg=BLANCO,
                fg=GRIS_TEXTO,
                anchor="w",
            )
            nota.pack(anchor="w")
            servicio["fondo"].append(nota)

    for clave in CLAVES_CAMPOS:
        celda = tk.Frame(servicios_grid, bg=BLANCO, padx=8, pady=6)
        servicio["fondo"].append(celda)
        servicio["orden_celdas"].append(celda)
        servicio["celdas"][clave] = celda
        rubro = RUBRO_DE_CLAVE.get(clave)
        if base == "MISCELANEOS" and rubro:
            variable = tk.BooleanVar(value=False)
            marca = tk.Checkbutton(
                celda,
                variable=variable,
                command=lambda s=servicio: al_cambiar_inclusion(s),
                bg=BLANCO,
                activebackground=BLANCO,
                selectcolor=BLANCO,
                highlightthickness=0,
                bd=0,
                cursor="hand2",
            )
            marca.pack(side="left", padx=(0, 4))
            servicio["fondo"].append(marca)
            servicio["checks"][rubro] = (variable, marca)
        crear_entrada_monto(celda, servicio, clave).pack(side="right", ipady=4)

    celda_quitar = tk.Frame(servicios_grid, bg=BLANCO, padx=4, pady=6)
    servicio["fondo"].append(celda_quitar)
    servicio["orden_celdas"].append(celda_quitar)
    if not fijo:
        quitar = tk.Label(
            celda_quitar,
            text="✕",
            font=(FUENTE, 11),
            bg=BLANCO,
            fg=GRIS_ICONO,
            padx=6,
            pady=1,
            cursor="hand2",
        )
        quitar.bind("<Enter>", lambda event: quitar.config(fg=CORINTO, bg=PELIGRO_SUAVE))
        quitar.bind(
            "<Leave>",
            lambda event: quitar.config(fg=GRIS_ICONO, bg=color_fila(servicio)),
        )
        quitar.bind("<Button-1>", lambda event: quitar_servicio(servicio))
        quitar.pack()
        servicio["fondo"].append(quitar)

    servicios.append(servicio)
    return servicio


def posicionar_servicios():
    for indice, servicio in enumerate(servicios, start=1):
        servicio["color"] = BLANCO if indice % 2 else ZEBRA
        for numero_columna, celda in enumerate(servicio["orden_celdas"]):
            celda.grid(row=indice, column=numero_columna, sticky="nsew")
        pintar_fila(servicio)
    boton_agregar_servicio.grid(
        row=len(servicios) + 1, column=0, columnspan=5, sticky="w", pady=(12, 0)
    )
    actualizar_columnas()
    actualizar_scroll_tabla()


def al_cambiar_inclusion(servicio):
    actualizar_fila_servicio(servicio)
    actualizar_orden_campos()
    programar_calculo()


def agregar_servicio_tipo(base):
    servicio = crear_fila_servicio(base)
    posicionar_servicios()
    actualizar_orden_campos()
    servicio["entradas"]["adultos"].focus()
    programar_calculo()
    return servicio


def quitar_servicio(servicio):
    if servicio not in servicios or servicio["fijo"]:
        return
    servicios.remove(servicio)
    if estado["foco"] is servicio:
        estado["foco"] = None
    for celda in servicio["orden_celdas"]:
        celda.destroy()
    posicionar_servicios()
    actualizar_orden_campos()
    programar_calculo()


def abrir_menu_servicios():
    usados = {servicio["base"] for servicio in servicios}
    menu = tk.Menu(
        ventana,
        tearoff=0,
        font=(FUENTE, 10),
        bg=BLANCO,
        fg=TEXTO,
        activebackground=RESALTE,
        activeforeground=AZUL,
        bd=0,
    )
    for base in CONCEPTOS_DISPONIBLES:
        if base == "MISCELANEOS" or base not in usados:
            menu.add_command(
                label=f"   {NOMBRES_VISTA[base]}   ",
                command=lambda b=base: agregar_servicio_tipo(b),
            )
    try:
        menu.tk_popup(
            boton_agregar_servicio.winfo_rootx(),
            boton_agregar_servicio.winfo_rooty() + boton_agregar_servicio.winfo_height(),
        )
    finally:
        menu.grab_release()


boton_agregar_servicio = boton_plano(
    servicios_grid,
    "＋  Agregar servicio",
    abrir_menu_servicios,
    BOTON_SUAVE,
    BOTON_SUAVE_HOVER,
    AZUL,
    (FUENTE, 10, "bold"),
)

crear_fila_servicio("BOLETOS NETOS", fijo=True)
crear_fila_servicio("DISEÑADOR", fijo=True)


def actualizar_orden_campos():
    orden_campos.clear()
    for rubro in RUBROS_CANTIDAD:
        orden_campos.append(personas[rubro])
    activos = rubros_activos()
    for servicio in servicios:
        for clave in CLAVES_CAMPOS:
            rubro = RUBRO_DE_CLAVE.get(clave)
            if rubro is None or (rubro in activos and tipo_incluido(servicio, rubro)):
                orden_campos.append(servicio["entradas"][clave])


def siguiente_campo(event):
    widget_actual = event.widget
    if widget_actual in orden_campos and widget_actual not in personas.values():
        formatear_moneda(widget_actual)

    try:
        indice = orden_campos.index(widget_actual)
    except ValueError:
        return "break"

    if indice < len(orden_campos) - 1:
        siguiente = orden_campos[indice + 1]
        siguiente.focus()
        try:
            siguiente.selection_range(0, tk.END)
        except Exception:
            pass
    else:
        calcular()

    return "break"


# ------------------------------------------------------------- desglose
desglose_frame = crear_seccion("DESGLOSE")


def alternar_desglose():
    estado["desglose"] = not estado["desglose"]
    if estado["desglose"]:
        boton_desglose.config(text="▾  Ocultar desglose")
        desglose_tabla.pack(fill="x", pady=(10, 0))
    else:
        boton_desglose.config(text="▸  Ver desglose")
        desglose_tabla.pack_forget()
    actualizar_scroll_tabla()


boton_desglose = boton_plano(
    desglose_frame,
    "▸  Ver desglose",
    alternar_desglose,
    SECCION,
    BOTON_SUAVE,
    AZUL,
    (FUENTE, 10, "bold"),
    padx=6,
    pady=3,
)
boton_desglose.pack(anchor="w")

desglose_tabla = tk.Frame(desglose_frame, bg=BLANCO)
desglose_tabla.grid_columnconfigure(0, weight=1, minsize=240)
for numero_columna in range(1, 5):
    desglose_tabla.grid_columnconfigure(numero_columna, minsize=130)

ENCABEZADOS_DESGLOSE = (
    "Concepto",
    "Costo neto total",
    "Costo neto por persona",
    "PVP total",
    "PVP por persona",
)


def construir_desglose(grupos, totales):
    for widget in desglose_tabla.winfo_children():
        widget.destroy()

    for numero_columna, texto in enumerate(ENCABEZADOS_DESGLOSE):
        tk.Label(
            desglose_tabla,
            text=texto,
            font=(FUENTE, 9, "bold"),
            bg=AZUL,
            fg=BLANCO,
            anchor="w" if numero_columna == 0 else "e",
            padx=10,
            pady=6,
        ).grid(row=0, column=numero_columna, sticky="nsew")

    if not grupos:
        tk.Label(
            desglose_tabla,
            text="Todavía no hay montos para mostrar.",
            font=(FUENTE, 10),
            bg=BLANCO,
            fg=GRIS_TEXTO,
            anchor="w",
            padx=10,
            pady=10,
        ).grid(row=1, column=0, columnspan=5, sticky="nsew")
        return

    fila = 1
    for nombre, renglones in grupos:
        tk.Label(
            desglose_tabla,
            text=nombre,
            font=(FUENTE, 10, "bold"),
            bg=SECCION,
            fg=AZUL,
            anchor="w",
            padx=10,
            pady=4,
        ).grid(row=fila, column=0, columnspan=5, sticky="nsew", pady=(6, 0))
        fila += 1
        for rubro, numero, valores in renglones:
            tk.Label(
                desglose_tabla,
                text=f"{NOMBRES_RUBRO[rubro]} ({numero})",
                font=(FUENTE, 10),
                bg=BLANCO,
                fg=TEXTO,
                anchor="w",
                padx=24,
                pady=3,
            ).grid(row=fila, column=0, sticky="nsew")
            for numero_columna, valor in enumerate(valores, start=1):
                tk.Label(
                    desglose_tabla,
                    text=dinero(valor),
                    font=(FUENTE, 10, "bold" if numero_columna >= 3 else "normal"),
                    bg=BLANCO,
                    fg=CORINTO if numero_columna >= 3 else TEXTO,
                    anchor="e",
                    padx=10,
                    pady=3,
                ).grid(row=fila, column=numero_columna, sticky="nsew")
            fila += 1

    tk.Label(
        desglose_tabla,
        text="TOTAL",
        font=(FUENTE, 10, "bold"),
        bg=CORINTO,
        fg=BLANCO,
        anchor="w",
        padx=10,
        pady=6,
    ).grid(row=fila, column=0, sticky="nsew", pady=(8, 0))
    for numero_columna, valor in enumerate(totales, start=1):
        tk.Label(
            desglose_tabla,
            text=dinero(valor),
            font=(FUENTE, 10, "bold"),
            bg=CORINTO,
            fg=BLANCO,
            anchor="e",
            padx=10,
            pady=6,
        ).grid(row=fila, column=numero_columna, sticky="nsew", pady=(8, 0))


# ------------------------------------------------------------- resumen
resumen = tk.Frame(contenedor, bg=SECCION, padx=22, pady=18)
resumen.grid(row=0, column=1, sticky="ns", padx=(4, 0))


def etiqueta_resumen(texto, tamano=9, color=GRIS_TEXTO, negrita=False, padre=None):
    return tk.Label(
        padre or resumen,
        text=texto,
        font=(FUENTE, tamano, "bold" if negrita else "normal"),
        bg=SECCION,
        fg=color,
        anchor="w",
        justify="left",
    )


etiqueta_resumen("RESUMEN", 10, AZUL, True).pack(anchor="w")

etiqueta_resumen("Total PVP").pack(anchor="w", pady=(14, 0))
total_pvp_label = etiqueta_resumen("$ 0.00", 24, CORINTO, True)
total_pvp_label.pack(anchor="w")
total_pvp_q_label = etiqueta_resumen("Q 0.00", 11)
total_pvp_q_label.pack(anchor="w")

descuento_cabeza = tk.Frame(resumen, bg=SECCION)
descuento_cabeza.pack(anchor="w", pady=(14, 0))
etiqueta_resumen("Total con descuento", padre=descuento_cabeza).pack(side="left")
etiqueta_resumen("  un solo pago en efectivo", 8, CORINTO, padre=descuento_cabeza).pack(
    side="left"
)
total_descuento_label = etiqueta_resumen("$ 0.00", 20, CORINTO, True)
total_descuento_label.pack(anchor="w")
total_descuento_q_label = etiqueta_resumen("Q 0.00", 11)
total_descuento_q_label.pack(anchor="w")

tk.Frame(resumen, bg=BORDE, height=1).pack(fill="x", pady=16)

etiqueta_resumen("POR PERSONA", 10, AZUL, True).pack(anchor="w")
por_persona = tk.Frame(resumen, bg=SECCION)
por_persona.pack(fill="x", pady=(8, 0))
por_persona.grid_columnconfigure(1, weight=1)
por_persona.grid_columnconfigure(2, weight=1)
etiqueta_resumen("PVP", 8, GRIS_TEXTO, True, por_persona).grid(
    row=0, column=1, sticky="e", padx=(14, 0)
)
etiqueta_resumen("Con descuento", 8, GRIS_TEXTO, True, por_persona).grid(
    row=0, column=2, sticky="e", padx=(14, 0)
)

for indice, rubro in enumerate(RUBROS_CANTIDAD):
    fila_base = 1 + indice * 3
    nombre = etiqueta_resumen(NOMBRES_RUBRO[rubro], 10, TEXTO, True, por_persona)
    numero = etiqueta_resumen("× 0", 9, GRIS_TEXTO, False, por_persona)
    pvp = etiqueta_resumen("$ 0.00", 11, TEXTO, True, por_persona)
    descuento = etiqueta_resumen("$ 0.00", 11, TEXTO, True, por_persona)
    pvp_q = etiqueta_resumen("Q 0.00", 8, GRIS_TEXTO, False, por_persona)
    descuento_q = etiqueta_resumen("Q 0.00", 8, GRIS_TEXTO, False, por_persona)
    pvp_total = etiqueta_resumen("Total $ 0.00", 8, GRIS_TEXTO, False, por_persona)
    descuento_total = etiqueta_resumen("Total $ 0.00", 8, GRIS_TEXTO, False, por_persona)
    ubicaciones = (
        (nombre, fila_base, 0, "w", 10),
        (numero, fila_base + 1, 0, "nw", 0),
        (pvp, fila_base, 1, "e", 10),
        (descuento, fila_base, 2, "e", 10),
        (pvp_q, fila_base + 1, 1, "e", 0),
        (descuento_q, fila_base + 1, 2, "e", 0),
        (pvp_total, fila_base + 2, 1, "e", 0),
        (descuento_total, fila_base + 2, 2, "e", 0),
    )
    for widget, fila_grid, columna_grid, pegado, espacio in ubicaciones:
        widget.grid(
            row=fila_grid,
            column=columna_grid,
            sticky=pegado,
            padx=(14, 0) if columna_grid else 0,
            pady=(espacio, 0) if espacio else 0,
        )
    resumen_filas[rubro] = {
        "widgets": [w[0] for w in ubicaciones],
        "cantidad": numero,
        "pvp": pvp,
        "pvp_q": pvp_q,
        "pvp_total": pvp_total,
        "descuento": descuento,
        "descuento_q": descuento_q,
        "descuento_total": descuento_total,
    }


def actualizar_filas_resumen():
    activos = rubros_activos()
    for rubro, fila in resumen_filas.items():
        for widget in fila["widgets"]:
            if rubro in activos:
                widget.grid()
            else:
                widget.grid_remove()


botones_frame = tk.Frame(resumen, bg=SECCION)
botones_frame.pack(side="bottom", fill="x", pady=(18, 0))

boton_calcular = tk.Button(
    botones_frame,
    text="Calcular",
    command=lambda: calcular(),
    font=(FUENTE, 11, "bold"),
    bg=AZUL,
    fg=BLANCO,
    activebackground="#00548F",
    activeforeground=BLANCO,
    relief="flat",
    bd=0,
    cursor="hand2",
    pady=8,
)
boton_calcular.pack(side="left", fill="x", expand=True, padx=(0, 6))

boton_limpiar = tk.Button(
    botones_frame,
    text="Limpiar",
    command=lambda: limpiar(),
    font=(FUENTE, 11, "bold"),
    bg=BLANCO,
    fg=CORINTO,
    activebackground=PELIGRO_SUAVE,
    activeforeground=CORINTO,
    relief="flat",
    bd=0,
    highlightthickness=1,
    highlightbackground=CORINTO,
    cursor="hand2",
    pady=8,
)
boton_limpiar.pack(side="left", fill="x", expand=True, padx=(6, 0))


# ------------------------------------------------------------- cálculo
def totales_servicio(servicio, cantidades):
    adultos = cantidades["ADULTOS"]
    ninos = cantidades["NIÑOS"] if tipo_incluido(servicio, "NIÑOS") else 0
    infantes = cantidades["INFANTES"] if tipo_incluido(servicio, "INFANTES") else 0
    entradas = servicio["entradas"]
    por_persona_modo = servicio["modo"] == "persona"

    monto_adultos = obtener_monto(entradas["adultos"])
    base_adultos = monto_adultos * adultos if por_persona_modo else monto_adultos

    if ninos:
        monto = obtener_monto(entradas["adultos_ninos"])
        base_adultos_ninos = monto * (adultos + ninos) if por_persona_modo else monto
    else:
        base_adultos_ninos = base_adultos

    if infantes:
        monto = obtener_monto(entradas["adultos_ninos_infantes"])
        base_combinado = (
            monto * (adultos + ninos + infantes) if por_persona_modo else monto
        )
    else:
        base_combinado = base_adultos_ninos

    totales = {
        "ADULTOS": base_adultos,
        "NIÑOS": (base_adultos_ninos - base_adultos) if ninos else 0.0,
        "INFANTES": (base_combinado - base_adultos_ninos) if infantes else 0.0,
    }
    if por_persona_modo and totales["INFANTES"] <= 0:
        totales["INFANTES"] = 0.0
    return totales


def campo_invalido(servicio):
    for entrada in servicio["entradas"].values():
        try:
            obtener_monto(entrada)
        except ValueError:
            return entrada
    return None


def calcular(silencioso=False):
    estado["pendiente"] = None
    cantidades = {rubro: cantidad(rubro) for rubro in RUBROS_CANTIDAD}
    if sum(cantidades.values()) < 1:
        if not silencioso:
            messagebox.showerror(
                "Dato incorrecto",
                "Debe haber al menos una persona en el presupuesto.",
            )
            personas["ADULTOS"].focus()
        return

    montos = {}
    for servicio in servicios:
        try:
            montos[id(servicio)] = totales_servicio(servicio, cantidades)
        except ValueError:
            if not silencioso:
                messagebox.showerror(
                    "Dato incorrecto",
                    f"El valor ingresado en {nombre_servicio(servicio)} no es válido.",
                )
                campo = campo_invalido(servicio)
                if campo is not None:
                    campo.focus()
            return

    activos = rubros_activos()
    pvp_por_rubro = {rubro: 0.0 for rubro in RUBROS_CANTIDAD}
    totales = [0.0, 0.0, 0.0, 0.0]
    grupos = []
    for servicio in servicios:
        renglones = []
        for rubro in activos:
            if not tipo_incluido(servicio, rubro):
                continue
            numero = cantidades[rubro]
            costo_total = montos[id(servicio)][rubro]
            costo_persona = costo_total / numero if numero else 0.0
            pvp_total = costo_total / servicio["porcentaje"]
            pvp_persona = pvp_total / numero if numero else 0.0
            if numero:
                pvp_por_rubro[rubro] += pvp_persona
            valores = (costo_total, costo_persona, pvp_total, pvp_persona)
            for posicion, valor in enumerate(valores):
                totales[posicion] += valor
            if costo_total:
                renglones.append((rubro, numero, valores))
        if renglones:
            grupos.append((nombre_servicio(servicio), renglones))

    total_pvp = total_descuento = 0.0
    for rubro, fila in resumen_filas.items():
        monto_pvp = pvp_por_rubro[rubro]
        monto_descuento = monto_pvp / 1.05
        subtotal_pvp = monto_pvp * cantidades[rubro]
        subtotal_descuento = monto_descuento * cantidades[rubro]
        total_pvp += subtotal_pvp
        total_descuento += subtotal_descuento
        fila["cantidad"].config(text=f"× {cantidades[rubro]}")
        fila["pvp"].config(text=dinero(monto_pvp))
        fila["pvp_q"].config(text=quetzales(monto_pvp))
        fila["pvp_total"].config(text=f"Total {dinero(subtotal_pvp)}")
        fila["descuento"].config(text=dinero(monto_descuento))
        fila["descuento_q"].config(text=quetzales(monto_descuento))
        fila["descuento_total"].config(text=f"Total {dinero(subtotal_descuento)}")

    total_pvp_label.config(text=dinero(total_pvp))
    total_pvp_q_label.config(text=quetzales(total_pvp))
    total_descuento_label.config(text=dinero(total_descuento))
    total_descuento_q_label.config(text=quetzales(total_descuento))
    construir_desglose(grupos, totales)
    actualizar_scroll_tabla()


def limpiar():
    for rubro, caja in personas.items():
        caja.delete(0, tk.END)
        caja.insert(0, "1" if rubro == "ADULTOS" else "0")

    for servicio in list(servicios):
        if not servicio["fijo"]:
            servicios.remove(servicio)
            for celda in servicio["orden_celdas"]:
                celda.destroy()
    estado["foco"] = None
    for servicio in servicios:
        for entrada in servicio["entradas"].values():
            entrada.config(state="normal")
            entrada.delete(0, tk.END)
            entrada.insert(0, "$ 0.00")

    estado["activos"] = None
    posicionar_servicios()
    al_cambiar_personas()
    calcular(silencioso=True)
    personas["ADULTOS"].focus()


# ------------------------------------------------------------- arranque
footer = tk.Label(
    ventana,
    text=f"Los datos ingresados son temporales y no se almacenan permanentemente.  ·  Versión {VERSION_APP}",
    font=(FUENTE, 9),
    bg=BLANCO,
    fg=GRIS_TEXTO,
)
footer.pack(pady=(0, 10))

posicionar_servicios()
al_cambiar_personas()
calcular(silencioso=True)


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
        final.paste(base.crop((0, cy, cx, cy + alto_canvas)), (0, cy))
        final.paste(
            base.crop((cx + ancho_canvas, cy, base.width, cy + alto_canvas)),
            (cx + ancho_canvas, cy),
        )
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
    entorno = {
        k: v for k, v in os.environ.items()
        if not k.startswith("_PYI") and k != "_MEIPASS2"
    }
    entorno["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    subprocess.Popen(
        [ruta_instalador, "/SILENT", "/NORESTART", "/CLOSEAPPLICATIONS"],
        env=entorno,
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


personas["ADULTOS"].focus()
ventana.after(2500, iniciar_revision_actualizacion)
ventana.mainloop()
