"""Ventana principal de la calculadora."""

import ctypes
import os
import queue
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

from . import actualizador, captura
from .calculo import (
    ServicioCapturado,
    calcular_presupuesto,
    dinero,
    leer_monto,
    diferencia_total,
    formato_quetzales,
    precios_por_persona,
    redondear_cercano,
    tipos_activos,
)
from .componentes import Ayuda, Boton, Campo, Tarjeta
from .config import (
    ADULTOS,
    CLAVE_ADULTOS,
    CLAVE_ADULTOS_NINOS,
    CLAVE_ADULTOS_NINOS_INFANTES,
    CLAVES_MONTO,
    EDADES_TIPO,
    INFANTES,
    MODO_CAPTURA,
    MODO_PERSONA,
    MODO_TOTAL,
    NINOS,
    NOMBRES_SERVICIO,
    NOMBRES_TIPO,
    PROPORCION_COSTO,
    SERVICIO_MISCELANEOS,
    SERVICIOS_FIJOS,
    SERVICIOS_OPCIONALES,
    SUBTIPOS_MISCELANEOS,
    TIPO_DE_CLAVE,
    TIPOS_PERSONA,
    VERSION_APP,
)
from .tema import Color, Espacio, Tipo, configurar_escala, px

TITULO_PRESUPUESTO = "PRESUPUESTO PARA ADULTOS Y NIÑOS F1"
MONTO_VACIO = "$ 0.00"

RETARDO_CALCULO_MS = 250
RETARDO_CAPTURA_MS = 150
DURACION_CONFIRMACION_MS = 1200
RETARDO_REVISION_ACTUALIZACION_MS = 2500
SONDEO_MS = 100

ENCABEZADOS_DESGLOSE = (
    "Concepto",
    "Costo neto total",
    "Costo neto por persona",
    "PVP total",
    "PVP por persona",
)


def ruta_recurso(nombre):
    """Ruta de un archivo incluido (logo, ícono), tanto en desarrollo como en el .exe."""
    base = getattr(sys, "_MEIPASS", None) or Path(__file__).resolve().parent.parent
    return os.path.join(base, nombre)


def activar_dpi():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass  # fuera de Windows o en versiones sin soporte


def descripcion_grupo(clave, incluye_ninos):
    if clave == CLAVE_ADULTOS:
        return "Monto de los adultos"
    if clave == CLAVE_ADULTOS_NINOS:
        return "Monto de adultos + niños"
    return "Monto de adultos + niños + infantes" if incluye_ninos else "Monto de adultos + infantes"


def preparar_edicion_monto(evento):
    """Al borrar, quita '$' y comas para editar el número sin formato."""
    if evento.keysym not in ("BackSpace", "Delete"):
        return
    campo = evento.widget
    texto = campo.get()
    if "$" not in texto and "," not in texto:
        return
    habia_seleccion = campo.selection_present()
    posicion = campo.index(tk.INSERT)
    limpio = texto.replace("$", "").replace(",", "").replace(" ", "")
    campo.delete(0, tk.END)
    campo.insert(0, limpio)
    if habia_seleccion:
        campo.selection_range(0, tk.END)
    else:
        campo.icursor(min(posicion, len(limpio)))


def formatear_monto(campo):
    try:
        valor = leer_monto(campo.get())
    except ValueError:
        return  # se deja el texto para que el usuario lo corrija
    campo.delete(0, tk.END)
    campo.insert(0, dinero(valor))


def crear_entrada_monto(contenedor, ancho=11):
    return tk.Entry(
        contenedor,
        font=Tipo.DATO,
        justify="right",
        width=ancho,
        bg=Color.FONDO,
        fg=Color.TEXTO,
        insertbackground=Color.MARCA,
        disabledbackground=Color.DESACTIVADO_FONDO,
        disabledforeground=Color.DESACTIVADO_TEXTO,
    )


class CampoInvalido(ValueError):
    def __init__(self, campo):
        super().__init__("monto no válido")
        self.campo = campo


class FilaServicio:
    """Una fila de la grilla de servicios: nombre, tres montos y botón para quitarla."""

    def __init__(self, app, base, fijo=False):
        self.app = app
        self.base = base
        self.fijo = fijo
        self.proporcion = PROPORCION_COSTO[base]
        self.modo = MODO_CAPTURA.get(base, MODO_TOTAL)
        self.color = Color.FONDO
        self.celdas = {}
        self.entradas = {}
        self.cajas = {}  # clave -> Campo (borde redondeado alrededor de la entrada)
        self.marcas = {}  # tipo de persona -> (BooleanVar, Checkbutton), solo Misceláneos
        self.subtipo = None
        self.boton_quitar = None
        self._columnas = []
        self._fondos = []
        self._construir(app.grid_servicios)

    # -- construcción -------------------------------------------------------
    def _celda(self, grid, padx):
        celda = tk.Frame(grid, bg=self.color, padx=padx, pady=px(Espacio.S))
        self._columnas.append(celda)
        self._fondos.append(celda)
        return celda

    def _construir(self, grid):
        celda = self._celda(grid, px(Espacio.M))
        if self.base == SERVICIO_MISCELANEOS:
            self.subtipo = ttk.Combobox(
                celda,
                values=SUBTIPOS_MISCELANEOS,
                font=Tipo.CUERPO,
                state="readonly",
                width=24,
            )
            self.subtipo.set(SUBTIPOS_MISCELANEOS[0])
            self.subtipo.bind("<<ComboboxSelected>>", self.app.programar_calculo)
            self.subtipo.pack(anchor="w")
        else:
            self._texto(celda, NOMBRES_SERVICIO[self.base], Tipo.CUERPO_FUERTE, Color.TEXTO)
            if self.modo == MODO_PERSONA:
                self._texto(celda, "precio por persona", Tipo.NOTA, Color.TEXTO_SECUNDARIO)

        for clave in CLAVES_MONTO:
            celda = self._celda(grid, px(Espacio.S))
            self.celdas[clave] = celda
            tipo = TIPO_DE_CLAVE.get(clave)
            if self.base == SERVICIO_MISCELANEOS and tipo:
                self._crear_marca(celda, tipo)
            self._crear_entrada(celda, clave).pack(side="right")

        celda = self._celda(grid, px(Espacio.XS))
        if not self.fijo:
            self.boton_quitar = Boton(
                celda,
                "✕",
                lambda: self.app.quitar_servicio(self),
                variante="icono",
                ayuda="Quitar servicio",
                padx=px(6),
                pady=px(2),
            )
            self.boton_quitar.pack()

    def _texto(self, padre, texto, fuente, color):
        etiqueta = tk.Label(padre, text=texto, font=fuente, bg=self.color, fg=color, anchor="w")
        etiqueta.pack(anchor="w")
        self._fondos.append(etiqueta)

    def _crear_marca(self, celda, tipo):
        variable = tk.BooleanVar(value=False)
        marca = tk.Checkbutton(
            celda,
            variable=variable,
            command=lambda: self.app.al_cambiar_inclusion(self),
            bg=self.color,
            activebackground=self.color,
            selectcolor=Color.FONDO,
            highlightthickness=px(2),
            highlightcolor=Color.MARCA,
            bd=0,
            cursor="hand2",
        )
        marca.pack(side="left", padx=(0, px(Espacio.XS)))
        Ayuda(marca, f"Incluir {NOMBRES_TIPO[tipo].lower()} en este servicio")
        self.marcas[tipo] = (variable, marca)

    def _crear_entrada(self, celda, clave):
        caja = Campo(celda, crear_entrada_monto)
        entrada = caja.widget
        entrada.insert(0, MONTO_VACIO)
        entrada.bind("<KeyPress>", preparar_edicion_monto, add="+")
        entrada.bind("<KeyRelease>", self.app.programar_calculo, add="+")
        entrada.bind("<FocusIn>", lambda evento: self._al_enfocar(evento, clave), add="+")
        entrada.bind("<FocusOut>", lambda evento: self._al_desenfocar(evento, clave), add="+")
        entrada.bind("<Return>", self.app.siguiente_campo)
        entrada.bind("<KP_Enter>", self.app.siguiente_campo)
        Ayuda(entrada, lambda: descripcion_grupo(clave, self.incluye(NINOS)))
        self.entradas[clave] = entrada
        self.cajas[clave] = caja
        return caja

    def _al_enfocar(self, evento, clave):
        self.app.resaltar(self, clave)
        evento.widget.selection_range(0, tk.END)

    def _al_desenfocar(self, evento, clave):
        formatear_monto(evento.widget)
        self.app.quitar_resalte(self, clave)

    # -- estado -------------------------------------------------------------
    def nombre(self):
        if self.subtipo is not None:
            return self.subtipo.get().strip() or NOMBRES_SERVICIO[self.base]
        return NOMBRES_SERVICIO[self.base]

    def incluye(self, tipo):
        """Niños e infantes cuentan si están activos y, en Misceláneos, si están marcados."""
        if tipo == ADULTOS:
            return True
        if tipo not in self.app.tipos_activos():
            return False
        marca = self.marcas.get(tipo)
        return marca is None or bool(marca[0].get())

    def campos_editables(self):
        return [
            self.entradas[clave]
            for clave in CLAVES_MONTO
            if clave == CLAVE_ADULTOS or self.incluye(TIPO_DE_CLAVE[clave])
        ]

    def capturar(self):
        """Lee los montos que intervienen en el cálculo. Lanza CampoInvalido."""
        incluidos = frozenset(tipo for tipo in TIPOS_PERSONA if self.incluye(tipo))
        usados = {
            CLAVE_ADULTOS: True,
            CLAVE_ADULTOS_NINOS: NINOS in incluidos,
            CLAVE_ADULTOS_NINOS_INFANTES: INFANTES in incluidos,
        }
        montos = {}
        for clave, se_usa in usados.items():
            if not se_usa:
                montos[clave] = 0.0
                continue
            try:
                montos[clave] = leer_monto(self.entradas[clave].get())
            except ValueError:
                raise CampoInvalido(self.entradas[clave]) from None
        return ServicioCapturado(self.nombre(), self.proporcion, self.modo, montos, incluidos)

    def reiniciar_montos(self):
        for clave, entrada in self.entradas.items():
            self.cajas[clave].habilitar(True)
            entrada.delete(0, tk.END)
            entrada.insert(0, MONTO_VACIO)

    # -- presentación ---------------------------------------------------------
    def ubicar(self, fila_grid, color):
        self.color = color
        for columna, celda in enumerate(self._columnas):
            celda.grid(row=fila_grid, column=columna, sticky="nsew")
        self.pintar()

    def pintar(self):
        color = Color.RESALTE if self.app.fila_enfocada is self else self.color
        for widget in self._fondos:
            widget.config(bg=color)
        for _, marca in self.marcas.values():
            marca.config(activebackground=color, highlightbackground=color)
        for caja in self.cajas.values():
            caja.cambiar_fondo(color)
        if self.boton_quitar is not None:
            self.boton_quitar.cambiar_fondo(color)

    def actualizar_columnas(self, activos):
        for clave, tipo in TIPO_DE_CLAVE.items():
            if tipo in activos:
                self.celdas[clave].grid()
            else:
                self.celdas[clave].grid_remove()
            if tipo in self.marcas:
                self.cajas[clave].habilitar(self.incluye(tipo))

    def destruir(self):
        for celda in self._columnas:
            celda.destroy()


class Calculadora:
    def __init__(self, raiz):
        self.raiz = raiz
        configurar_escala(raiz)
        self.personas = {}
        self.filas = []
        self.fila_enfocada = None
        self.orden_campos = []
        self.resumen_filas = {}
        self.encabezados_servicios = {}
        self._tipos_visibles = None
        self._calculo_pendiente = None
        self._presupuesto = None
        self._precios = None
        self._desglose_visible = False

        self._configurar_ventana()
        self._crear_encabezado()
        self._crear_cuerpo()
        self._crear_personas()
        self._crear_servicios()
        self._crear_desglose()
        self._crear_resumen()
        self._crear_pie()

        for base in SERVICIOS_FIJOS:
            self.filas.append(FilaServicio(self, base, fijo=True))
        self.ubicar_filas()
        self.al_cambiar_personas()
        self.calcular(silencioso=True)

        raiz.bind_all("<Control-Return>", lambda _evento: self.calcular())
        raiz.bind_all("<Control-KP_Enter>", lambda _evento: self.calcular())
        self.personas[ADULTOS].focus()
        raiz.after(RETARDO_REVISION_ACTUALIZACION_MS, self.iniciar_revision_actualizacion)

    # ------------------------------------------------------------ estructura
    def _configurar_ventana(self):
        raiz = self.raiz
        raiz.iconbitmap(ruta_recurso("Logo_Ovalado.ico"))
        raiz.title("Dream & Travel - Calculadora")
        raiz.configure(bg=Color.LIENZO)
        estilo = ttk.Style(raiz)
        estilo.theme_use("clam")
        estilo.configure(
            "TCombobox",
            fieldbackground=Color.FONDO,
            background=Color.FONDO,
            bordercolor=Color.BORDE_CAMPO,
            lightcolor=Color.FONDO,
            darkcolor=Color.FONDO,
            arrowcolor=Color.TEXTO_SECUNDARIO,
            padding=px(4),
        )
        estilo.map(
            "TCombobox",
            bordercolor=[("focus", Color.MARCA)],
            fieldbackground=[("readonly", Color.FONDO)],
            selectbackground=[("readonly", Color.FONDO)],
            selectforeground=[("readonly", Color.TEXTO)],
        )
        for orientacion in ("Vertical", "Horizontal"):
            estilo.configure(
                f"{orientacion}.TScrollbar",
                background=Color.DIVISOR,
                troughcolor=Color.LIENZO,
                bordercolor=Color.LIENZO,
                lightcolor=Color.DIVISOR,
                darkcolor=Color.DIVISOR,
                arrowcolor=Color.TEXTO_SECUNDARIO,
                gripcount=0,
            )
        ancho = min(px(1280), raiz.winfo_screenwidth() - px(40))
        alto = min(px(800), raiz.winfo_screenheight() - px(80))
        raiz.geometry(f"{ancho}x{alto}")
        raiz.minsize(min(px(1000), ancho), min(px(620), alto))

    def _crear_encabezado(self):
        banda = tk.Frame(self.raiz, bg=Color.MARCA, height=px(84))
        banda.pack(fill="x")
        banda.pack_propagate(False)

        self._logo = tk.PhotoImage(file=ruta_recurso("Logo_Letras_Blanco.png")).subsample(3, 3)
        tk.Label(banda, image=self._logo, bg=Color.MARCA).place(
            x=px(Espacio.XL), rely=0.5, anchor="w"
        )
        tk.Label(
            banda, text=TITULO_PRESUPUESTO, font=Tipo.TITULO_APP, bg=Color.MARCA, fg=Color.FONDO
        ).place(relx=0.5, rely=0.5, anchor="center")

        reloj = tk.Frame(banda, bg=Color.MARCA)
        reloj.place(relx=1.0, x=-px(Espacio.XL), rely=0.5, anchor="e")
        self.fecha = tk.Label(reloj, font=Tipo.CUERPO_FUERTE, bg=Color.MARCA, fg=Color.FONDO)
        self.fecha.pack(anchor="e")
        self.hora = tk.Label(reloj, font=Tipo.CUERPO, bg=Color.MARCA, fg=Color.MARCA_TEXTO_SUAVE)
        self.hora.pack(anchor="e")
        self._actualizar_reloj()

    def _actualizar_reloj(self):
        ahora = datetime.now()
        self.fecha.config(text=ahora.strftime("Fecha: %d/%m/%Y"))
        self.hora.config(text=ahora.strftime("Hora: %I:%M %p"))
        hasta_el_minuto = 60_000 - (ahora.second * 1000 + ahora.microsecond // 1000)
        self.raiz.after(hasta_el_minuto + 50, self._actualizar_reloj)

    def _crear_cuerpo(self):
        self.contenedor = tk.Frame(self.raiz, bg=Color.LIENZO)
        self.contenedor.pack(
            fill="both", expand=True, padx=px(Espacio.XL), pady=(px(Espacio.M), px(Espacio.S))
        )
        self.contenedor.grid_columnconfigure(0, weight=1)
        self.contenedor.grid_rowconfigure(0, weight=1)

        zona = tk.Frame(self.contenedor, bg=Color.LIENZO)
        zona.grid(row=0, column=0, sticky="nsew")
        self.lienzo = tk.Canvas(zona, bg=Color.LIENZO, highlightthickness=0)
        barra_vertical = ttk.Scrollbar(zona, orient="vertical", command=self.lienzo.yview)
        self.barra_horizontal = ttk.Scrollbar(
            zona, orient="horizontal", command=self.lienzo.xview
        )
        barra_vertical.pack(side="right", fill="y")
        self.lienzo.pack(side="left", fill="both", expand=True)
        self.lienzo.configure(
            yscrollcommand=barra_vertical.set, xscrollcommand=self.barra_horizontal.set
        )

        self.pagina = tk.Frame(self.lienzo, bg=Color.LIENZO)
        self._ventana_pagina = self.lienzo.create_window((0, 0), window=self.pagina, anchor="nw")
        self.lienzo.bind("<Configure>", self._ajustar_ancho_pagina)
        self.pagina.bind("<Configure>", self.actualizar_scroll)

        self.raiz.bind_all("<MouseWheel>", self._desplazar_con_rueda)
        self.raiz.bind_all("<Button-4>", lambda _evento: self.lienzo.yview_scroll(-1, "units"))
        self.raiz.bind_all("<Button-5>", lambda _evento: self.lienzo.yview_scroll(1, "units"))

    def _ajustar_ancho_pagina(self, evento):
        necesario = self.pagina.winfo_reqwidth()
        self.lienzo.itemconfig(self._ventana_pagina, width=max(evento.width, necesario))
        if necesario > evento.width:
            self.barra_horizontal.pack(side="bottom", fill="x", before=self.lienzo)
        else:
            self.barra_horizontal.pack_forget()

    def _desplazar_con_rueda(self, evento):
        lienzo = self.lienzo
        x = lienzo.winfo_pointerx() - lienzo.winfo_rootx()
        y = lienzo.winfo_pointery() - lienzo.winfo_rooty()
        if not (0 <= x <= lienzo.winfo_width() and 0 <= y <= lienzo.winfo_height()):
            return
        if evento.delta:
            unidades = -int(evento.delta / 120) or (-1 if evento.delta > 0 else 1)
            lienzo.yview_scroll(unidades, "units")

    def actualizar_scroll(self, _evento=None):
        self.lienzo.configure(scrollregion=self.lienzo.bbox("all"))

    def _crear_seccion(self, titulo, nota=None):
        tarjeta = Tarjeta(self.pagina, padx=px(Espacio.L + 4), pady=px(Espacio.L))
        tarjeta.pack(fill="x", pady=(0, px(Espacio.M)), padx=(0, px(Espacio.M)))
        seccion = tarjeta.interior
        cabeza = tk.Frame(seccion, bg=Color.FONDO)
        cabeza.pack(fill="x", pady=(0, px(Espacio.S)))
        tk.Label(
            cabeza, text=titulo, font=Tipo.CUERPO_FUERTE, bg=Color.FONDO, fg=Color.MARCA
        ).pack(side="left")
        if nota:
            tk.Label(
                cabeza, text=nota, font=Tipo.NOTA, bg=Color.FONDO, fg=Color.TEXTO_SECUNDARIO
            ).pack(side="left", padx=(px(Espacio.M), 0))
        return seccion

    # -------------------------------------------------------------- personas
    def _crear_personas(self):
        fila = tk.Frame(self._crear_seccion("PERSONAS"), bg=Color.FONDO)
        fila.pack(fill="x")
        validar = self.raiz.register(lambda texto: texto == "" or (texto.isdigit() and len(texto) <= 2))
        for columna, tipo in enumerate(TIPOS_PERSONA):
            bloque = tk.Frame(fila, bg=Color.FONDO)
            bloque.grid(row=0, column=columna, sticky="w", padx=(0, px(36)))
            tk.Label(
                bloque, text=NOMBRES_TIPO[tipo], font=Tipo.DATO_FUERTE,
                bg=Color.FONDO, fg=Color.TEXTO,
            ).grid(row=0, column=0, sticky="w")
            tk.Label(
                bloque, text=EDADES_TIPO[tipo], font=Tipo.NOTA,
                bg=Color.FONDO, fg=Color.TEXTO_SECUNDARIO,
            ).grid(row=1, column=0, sticky="w")
            contenedor = Campo(
                bloque,
                lambda padre: tk.Spinbox(
                    padre,
                    from_=0,
                    to=99,
                    width=4,
                    font=Tipo.DATO_FUERTE,
                    justify="center",
                    bg=Color.FONDO,
                    fg=Color.TEXTO,
                    insertbackground=Color.MARCA,
                    validate="key",
                    validatecommand=(validar, "%P"),
                    command=self.al_cambiar_personas,
                ),
            )
            caja = contenedor.widget
            caja.delete(0, tk.END)
            caja.insert(0, "1" if tipo == ADULTOS else "0")
            contenedor.grid(row=0, column=1, rowspan=2, padx=(px(Espacio.M), 0))
            caja.bind("<KeyRelease>", self.al_cambiar_personas, add="+")
            caja.bind("<FocusIn>", lambda evento: evento.widget.selection_range(0, tk.END), add="+")
            caja.bind("<Return>", self.siguiente_campo)
            caja.bind("<KP_Enter>", self.siguiente_campo)
            self.personas[tipo] = caja

    def cantidad(self, tipo):
        try:
            return int(self.personas[tipo].get().strip() or "0")
        except ValueError:
            return 0

    def cantidades(self):
        return {tipo: self.cantidad(tipo) for tipo in TIPOS_PERSONA}

    def tipos_activos(self):
        return tipos_activos(self.cantidades())

    def al_cambiar_personas(self, _evento=None):
        activos = tuple(self.tipos_activos())
        if activos != self._tipos_visibles:
            self._tipos_visibles = activos
            self.actualizar_columnas()
            self._actualizar_filas_resumen()
            self.actualizar_orden_campos()
        for tipo, fila in self.resumen_filas.items():
            fila["cantidad"].config(text=f"× {self.cantidad(tipo)}")
        self.programar_calculo()

    # ------------------------------------------------------------- servicios
    def _crear_servicios(self):
        seccion = self._crear_seccion(
            "SERVICIOS",
            "Escribe el monto total de cada grupo · Diseñador: precio por persona"
            " · En Misceláneos marca ☑ para incluir niños o infantes",
        )
        self.grid_servicios = tk.Frame(seccion, bg=Color.FONDO)
        self.grid_servicios.pack(fill="x")
        self.grid_servicios.grid_columnconfigure(0, weight=1, minsize=px(200))
        for columna in (1, 2, 3):
            self.grid_servicios.grid_columnconfigure(columna, minsize=px(150))
        self.grid_servicios.grid_columnconfigure(4, minsize=px(40))

        columnas = (
            ("nombre", "Servicio", "w"),
            (CLAVE_ADULTOS, "Adultos", "e"),
            (CLAVE_ADULTOS_NINOS, "Adultos + niños", "e"),
            (CLAVE_ADULTOS_NINOS_INFANTES, "Adultos + niños + infantes", "e"),
        )
        for columna, (clave, texto, ancla) in enumerate(columnas):
            etiqueta = tk.Label(
                self.grid_servicios,
                text=texto,
                font=Tipo.NOTA_FUERTE,
                bg=Color.FONDO,
                fg=Color.TEXTO_SECUNDARIO,
                anchor=ancla,
                padx=px(Espacio.M),
                pady=px(Espacio.XS),
            )
            etiqueta.grid(row=0, column=columna, sticky="nsew")
            self.encabezados_servicios[clave] = etiqueta

        self.boton_agregar = Boton(
            self.grid_servicios, "＋  Agregar servicio", self.abrir_menu_servicios, "suave"
        )

    def actualizar_columnas(self):
        activos = self.tipos_activos()
        hay_ninos = NINOS in activos
        encabezados = self.encabezados_servicios
        encabezados[CLAVE_ADULTOS_NINOS_INFANTES].config(
            text="Adultos + niños + infantes" if hay_ninos else "Adultos + infantes"
        )
        for clave, tipo in TIPO_DE_CLAVE.items():
            if tipo in activos:
                encabezados[clave].grid()
            else:
                encabezados[clave].grid_remove()
        for fila in self.filas:
            fila.actualizar_columnas(activos)

    def ubicar_filas(self):
        for indice, fila in enumerate(self.filas, start=1):
            fila.ubicar(indice, Color.FONDO if indice % 2 else Color.SUPERFICIE_ALTERNA)
        self.boton_agregar.grid(
            row=len(self.filas) + 1, column=0, columnspan=5, sticky="w", pady=(px(Espacio.M), 0)
        )
        self.actualizar_columnas()
        self.actualizar_scroll()

    def resaltar(self, fila, clave):
        anterior = self.fila_enfocada
        self.fila_enfocada = fila
        if anterior is not None and anterior is not fila and anterior in self.filas:
            anterior.pintar()
        fila.pintar()
        for clave_encabezado, etiqueta in self.encabezados_servicios.items():
            activa = clave_encabezado == clave
            etiqueta.config(
                bg=Color.RESALTE if activa else Color.FONDO,
                fg=Color.MARCA if activa else Color.TEXTO_SECUNDARIO,
            )

    def quitar_resalte(self, fila, clave):
        if self.fila_enfocada is fila:
            self.fila_enfocada = None
            if fila in self.filas:
                fila.pintar()
        for etiqueta in self.encabezados_servicios.values():
            etiqueta.config(bg=Color.FONDO, fg=Color.TEXTO_SECUNDARIO)

    def al_cambiar_inclusion(self, fila):
        fila.actualizar_columnas(self.tipos_activos())
        self.actualizar_orden_campos()
        self.programar_calculo()

    def agregar_servicio(self, base):
        fila = FilaServicio(self, base)
        self.filas.append(fila)
        self.ubicar_filas()
        self.actualizar_orden_campos()
        fila.entradas[CLAVE_ADULTOS].focus()
        self.programar_calculo()
        return fila

    def quitar_servicio(self, fila):
        if fila not in self.filas or fila.fijo:
            return
        self.filas.remove(fila)
        if self.fila_enfocada is fila:
            self.fila_enfocada = None
        fila.destruir()
        self.ubicar_filas()
        self.actualizar_orden_campos()
        self.programar_calculo()

    def abrir_menu_servicios(self):
        usados = {fila.base for fila in self.filas}
        menu = tk.Menu(
            self.raiz,
            tearoff=0,
            font=Tipo.CUERPO,
            bg=Color.FONDO,
            fg=Color.TEXTO,
            activebackground=Color.RESALTE,
            activeforeground=Color.MARCA,
            bd=0,
        )
        for base in SERVICIOS_OPCIONALES:
            if base == SERVICIO_MISCELANEOS or base not in usados:
                menu.add_command(
                    label=f"   {NOMBRES_SERVICIO[base]}   ",
                    command=lambda b=base: self.agregar_servicio(b),
                )
        boton = self.boton_agregar
        try:
            menu.tk_popup(boton.winfo_rootx(), boton.winfo_rooty() + boton.winfo_height())
        finally:
            menu.grab_release()

    # -------------------------------------------------------- navegación
    def actualizar_orden_campos(self):
        self.orden_campos = [self.personas[tipo] for tipo in TIPOS_PERSONA]
        for fila in self.filas:
            self.orden_campos.extend(fila.campos_editables())

    def siguiente_campo(self, evento):
        """Enter pasa al siguiente campo; en el último, calcula."""
        actual = evento.widget
        if actual not in self.personas.values():
            formatear_monto(actual)
        if actual not in self.orden_campos:
            return "break"
        indice = self.orden_campos.index(actual)
        if indice == len(self.orden_campos) - 1:
            self.calcular()
            return "break"
        siguiente = self.orden_campos[indice + 1]
        siguiente.focus()
        siguiente.selection_range(0, tk.END)
        return "break"

    # -------------------------------------------------------------- desglose
    def _crear_desglose(self):
        seccion = self._crear_seccion("DESGLOSE")
        self.boton_desglose = Boton(
            seccion,
            "▸  Ver desglose",
            self.alternar_desglose,
            "enlace",
            padx=px(6),
            pady=px(3),
        )
        self.boton_desglose.pack(anchor="w")
        self.tabla_desglose = tk.Frame(seccion, bg=Color.FONDO)
        self.tabla_desglose.grid_columnconfigure(0, weight=1, minsize=px(220))
        for columna in range(1, 5):
            self.tabla_desglose.grid_columnconfigure(columna, minsize=px(130))

    def alternar_desglose(self):
        self._desglose_visible = not self._desglose_visible
        if self._desglose_visible:
            self.boton_desglose.cambiar_texto("▾  Ocultar desglose")
            self._construir_desglose()
            self.tabla_desglose.pack(fill="x", pady=(px(Espacio.S), 0))
        else:
            self.boton_desglose.cambiar_texto("▸  Ver desglose")
            self.tabla_desglose.pack_forget()
        self.actualizar_scroll()

    def _celda_desglose(self, texto, fila, columna, fuente, fondo, color, ancla="e", **grid):
        tk.Label(
            self.tabla_desglose,
            text=texto,
            font=fuente,
            bg=fondo,
            fg=color,
            anchor=ancla,
            padx=grid.pop("padx_texto", px(Espacio.M)),
            pady=grid.pop("pady_texto", px(Espacio.XS)),
        ).grid(row=fila, column=columna, sticky="nsew", **grid)

    def _construir_desglose(self):
        """Solo se construye cuando el desglose está visible."""
        tabla = self.tabla_desglose
        for widget in tabla.winfo_children():
            widget.destroy()

        for columna, texto in enumerate(ENCABEZADOS_DESGLOSE):
            self._celda_desglose(
                texto, 0, columna, Tipo.NOTA_FUERTE, Color.MARCA, Color.FONDO,
                ancla="w" if columna == 0 else "e", pady_texto=px(6),
            )

        presupuesto = self._presupuesto
        grupos = []
        if presupuesto is not None:
            for nombre, renglones in presupuesto.servicios:
                con_monto = [renglon for renglon in renglones if renglon.costo_total]
                if con_monto:
                    grupos.append((nombre, con_monto))

        if not grupos:
            self._celda_desglose(
                "Todavía no hay montos para mostrar.", 1, 0, Tipo.CUERPO, Color.FONDO,
                Color.TEXTO_SECUNDARIO, ancla="w", columnspan=5, pady_texto=px(10),
            )
            return

        fila = 1
        for nombre, renglones in grupos:
            self._celda_desglose(
                nombre, fila, 0, Tipo.CUERPO_FUERTE, Color.SUPERFICIE, Color.MARCA,
                ancla="w", columnspan=5, pady=(px(6), 0),
            )
            fila += 1
            for renglon in renglones:
                self._celda_desglose(
                    f"{NOMBRES_TIPO[renglon.tipo]} ({renglon.cantidad})", fila, 0, Tipo.CUERPO,
                    Color.FONDO, Color.TEXTO, ancla="w", padx_texto=px(Espacio.XL),
                    pady_texto=px(3),
                )
                for columna, valor in enumerate(renglon.valores, start=1):
                    es_pvp = columna >= 3
                    self._celda_desglose(
                        dinero(valor), fila, columna,
                        Tipo.CUERPO_FUERTE if es_pvp else Tipo.CUERPO, Color.FONDO,
                        Color.ACENTO if es_pvp else Color.TEXTO, pady_texto=px(3),
                    )
                fila += 1

        self._celda_desglose(
            "TOTAL", fila, 0, Tipo.CUERPO_FUERTE, Color.ACENTO, Color.FONDO,
            ancla="w", pady=(px(Espacio.S), 0), pady_texto=px(6),
        )
        for columna, valor in enumerate(presupuesto.totales_columnas, start=1):
            self._celda_desglose(
                dinero(valor), fila, columna, Tipo.CUERPO_FUERTE, Color.ACENTO, Color.FONDO,
                pady=(px(Espacio.S), 0), pady_texto=px(6),
            )

    # --------------------------------------------------------------- resumen
    def _texto_resumen(self, padre, texto, fuente=Tipo.NOTA, color=Color.TEXTO_SECUNDARIO):
        return tk.Label(
            padre, text=texto, font=fuente, bg=Color.FONDO, fg=color,
            anchor="w", justify="left",
        )

    def _crear_resumen(self):
        tarjeta = Tarjeta(
            self.contenedor, padx=px(Espacio.XL), pady=px(Espacio.L),
            estirar_ancho=False, estirar_alto=True,
        )
        tarjeta.grid(row=0, column=1, sticky="ns", padx=(px(Espacio.XS), 0))
        panel = tarjeta.interior
        texto = self._texto_resumen

        # Arriba, lo que más se consulta: el precio por persona (en corinto).
        cabeza = tk.Frame(panel, bg=Color.FONDO)
        cabeza.pack(fill="x")
        texto(cabeza, "POR PERSONA", Tipo.CUERPO_FUERTE, Color.MARCA).pack(side="left")
        self.redondear = tk.BooleanVar(value=True)
        marca = tk.Checkbutton(
            cabeza,
            text="Redondear",
            variable=self.redondear,
            command=lambda: self.calcular(silencioso=True),
            font=Tipo.NOTA_FUERTE,
            bg=Color.FONDO,
            fg=Color.TEXTO_SECUNDARIO,
            activebackground=Color.FONDO,
            selectcolor=Color.FONDO,
            highlightthickness=px(2),
            highlightbackground=Color.FONDO,
            highlightcolor=Color.MARCA,
            bd=0,
            cursor="hand2",
        )
        marca.pack(side="right")
        Ayuda(marca, "Sube cada precio al siguiente entero si tiene centavos (301.01 → 302)")

        tabla = tk.Frame(panel, bg=Color.FONDO)
        tabla.pack(fill="x", pady=(px(Espacio.S), 0))
        tabla.grid_columnconfigure(1, weight=1)
        tabla.grid_columnconfigure(2, weight=1)
        separacion = (px(14), 0)
        texto(tabla, "PVP", Tipo.NOTA_FUERTE).grid(row=0, column=1, sticky="e", padx=separacion)
        texto(tabla, "Con descuento", Tipo.NOTA_FUERTE).grid(
            row=0, column=2, sticky="e", padx=separacion
        )

        for indice, tipo in enumerate(TIPOS_PERSONA):
            fila = 1 + indice * 3
            celdas = {
                "nombre": (texto(tabla, NOMBRES_TIPO[tipo], Tipo.DATO_FUERTE, Color.TEXTO), fila, 0, "w"),
                "cantidad": (texto(tabla, "× 0"), fila + 1, 0, "nw"),
                "pvp": (texto(tabla, MONTO_VACIO, Tipo.CIFRA, Color.ACENTO), fila, 1, "e"),
                "descuento": (texto(tabla, MONTO_VACIO, Tipo.CIFRA, Color.ACENTO), fila, 2, "e"),
                "pvp_q": (texto(tabla, "Q 0.00"), fila + 1, 1, "e"),
                "descuento_q": (texto(tabla, "Q 0.00"), fila + 1, 2, "e"),
                "pvp_total": (texto(tabla, f"Total {MONTO_VACIO}"), fila + 2, 1, "e"),
                "descuento_total": (texto(tabla, f"Total {MONTO_VACIO}"), fila + 2, 2, "e"),
            }
            for widget, fila_grid, columna, pegado in celdas.values():
                widget.grid(
                    row=fila_grid,
                    column=columna,
                    sticky=pegado,
                    padx=separacion if columna else 0,
                    pady=(px(10), 0) if fila_grid == fila else 0,
                )
            self.resumen_filas[tipo] = {clave: celda[0] for clave, celda in celdas.items()}

        tk.Frame(panel, bg=Color.DIVISOR, height=1).pack(fill="x", pady=px(Espacio.M))

        # Totales del grupo (en azul), lado a lado para ahorrar alto.
        texto(panel, "RESUMEN", Tipo.CUERPO_FUERTE, Color.MARCA).pack(anchor="w")
        totales = tk.Frame(panel, bg=Color.FONDO)
        totales.pack(fill="x", pady=(px(Espacio.XS), 0))
        totales.grid_columnconfigure(0, weight=1)
        totales.grid_columnconfigure(1, weight=1)
        texto(totales, "Total PVP").grid(row=0, column=0, sticky="w")
        texto(totales, "Con descuento · efectivo", Tipo.NOTA, Color.ACENTO).grid(
            row=0, column=1, sticky="w", padx=separacion
        )
        self.total_pvp = texto(totales, MONTO_VACIO, Tipo.CIFRA, Color.MARCA)
        self.total_pvp.grid(row=1, column=0, sticky="w")
        self.total_descuento = texto(totales, MONTO_VACIO, Tipo.CIFRA, Color.MARCA)
        self.total_descuento.grid(row=1, column=1, sticky="w", padx=separacion)
        self.total_pvp_q = texto(totales, "Q 0.00")
        self.total_pvp_q.grid(row=2, column=0, sticky="w")
        self.total_descuento_q = texto(totales, "Q 0.00")
        self.total_descuento_q.grid(row=2, column=1, sticky="w", padx=separacion)

        tk.Frame(panel, bg=Color.DIVISOR, height=1).pack(fill="x", pady=px(Espacio.M))
        self._crear_ajuste_adulto(panel)

        botones = tk.Frame(panel, bg=Color.FONDO)
        botones.pack(side="bottom", fill="x", pady=(px(Espacio.M), 0))
        Boton(botones, "Calcular", self.calcular, "primario", ayuda="Ctrl + Enter").pack(
            side="left", fill="x", expand=True, padx=(0, px(6))
        )
        Boton(botones, "Limpiar", self.limpiar, "peligro").pack(
            side="left", fill="x", expand=True, padx=(px(6), 0)
        )

    def _crear_ajuste_adulto(self, panel):
        """Compara el precio adulto calculado con otro precio y muestra la diferencia total."""
        texto = self._texto_resumen
        texto(panel, "AJUSTE DE PRECIO ADULTO", Tipo.CUERPO_FUERTE, Color.MARCA).pack(anchor="w")
        tabla = tk.Frame(panel, bg=Color.FONDO)
        tabla.pack(fill="x", pady=(px(Espacio.XS), 0))
        tabla.grid_columnconfigure(1, weight=1)

        texto(tabla, "Precio adulto actual", Tipo.CUERPO, Color.TEXTO).grid(row=0, column=0, sticky="w")
        self.ajuste_actual = texto(tabla, MONTO_VACIO, Tipo.DATO_FUERTE, Color.TEXTO)
        self.ajuste_actual.grid(row=0, column=1, sticky="e")

        texto(tabla, "Precio adulto nuevo", Tipo.CUERPO, Color.TEXTO).grid(
            row=1, column=0, sticky="w", pady=(px(Espacio.XS), 0)
        )
        campo = Campo(tabla, crear_entrada_monto)
        campo.grid(row=1, column=1, sticky="e", pady=(px(Espacio.XS), 0))
        self.ajuste_nuevo = campo.widget
        self.ajuste_nuevo.bind("<KeyPress>", preparar_edicion_monto, add="+")
        self.ajuste_nuevo.bind("<KeyRelease>", lambda _evento: self._actualizar_ajuste(), add="+")
        self.ajuste_nuevo.bind("<FocusOut>", self._formatear_ajuste, add="+")
        self.ajuste_nuevo.bind("<Return>", self._formatear_ajuste)
        self.ajuste_nuevo.bind("<KP_Enter>", self._formatear_ajuste)
        Ayuda(self.ajuste_nuevo, "Escribe el precio por adulto que quieres ofrecer")

        texto(tabla, "Diferencia total", Tipo.CUERPO_FUERTE, Color.TEXTO).grid(
            row=2, column=0, sticky="w", pady=(px(Espacio.S), 0)
        )
        self.ajuste_diferencia = texto(tabla, "—", Tipo.CIFRA, Color.ACENTO)
        self.ajuste_diferencia.grid(row=2, column=1, sticky="e", pady=(px(Espacio.S), 0))
        self.ajuste_detalle = texto(tabla, "")
        self.ajuste_detalle.grid(row=3, column=0, columnspan=2, sticky="e")

    def _formatear_ajuste(self, _evento=None):
        if self.ajuste_nuevo.get().strip():
            formatear_monto(self.ajuste_nuevo)
        self._actualizar_ajuste()
        return "break"

    def _actualizar_ajuste(self):
        precios = self._precios
        texto_nuevo = self.ajuste_nuevo.get().strip()
        precio_actual = precios.pvp[ADULTOS] if precios else 0.0
        self.ajuste_actual.config(text=dinero(precio_actual))
        try:
            precio_nuevo = leer_monto(texto_nuevo) if texto_nuevo else None
        except ValueError:
            precio_nuevo = None
        if precio_nuevo is None or precios is None:
            self.ajuste_diferencia.config(text="—")
            self.ajuste_detalle.config(text="")
            return
        adultos = self.cantidad(ADULTOS)
        diferencia = diferencia_total(precio_actual, precio_nuevo, self.cantidades())
        if self.redondear.get():
            diferencia = redondear_cercano(diferencia)
        self.ajuste_diferencia.config(text=dinero(diferencia))
        self.ajuste_detalle.config(
            text=f"({dinero(precio_actual)} − {dinero(precio_nuevo)}) × {adultos} adultos"
        )

    def _actualizar_filas_resumen(self):
        activos = self.tipos_activos()
        for tipo, fila in self.resumen_filas.items():
            for widget in fila.values():
                if tipo in activos:
                    widget.grid()
                else:
                    widget.grid_remove()

    def _mostrar_resumen(self, presupuesto, cantidades):
        precios = precios_por_persona(presupuesto, cantidades, self.redondear.get())
        self._precios = precios
        for tipo, fila in self.resumen_filas.items():
            fila["cantidad"].config(text=f"× {cantidades[tipo]}")
            fila["pvp"].config(text=dinero(precios.pvp[tipo]))
            fila["pvp_q"].config(text=formato_quetzales(precios.pvp_q[tipo]))
            fila["pvp_total"].config(text=f"Total {dinero(precios.subtotal_pvp[tipo])}")
            fila["descuento"].config(text=dinero(precios.descuento[tipo]))
            fila["descuento_q"].config(text=formato_quetzales(precios.descuento_q[tipo]))
            fila["descuento_total"].config(
                text=f"Total {dinero(precios.subtotal_descuento[tipo])}"
            )
        self.total_pvp.config(text=dinero(precios.total_pvp))
        self.total_pvp_q.config(text=formato_quetzales(precios.total_pvp_q))
        self.total_descuento.config(text=dinero(precios.total_descuento))
        self.total_descuento_q.config(text=formato_quetzales(precios.total_descuento_q))
        self._actualizar_ajuste()

    # ------------------------------------------------------------------- pie
    def _crear_pie(self):
        tk.Label(
            self.raiz,
            text="Los datos ingresados son temporales y no se almacenan permanentemente."
            f"  ·  Versión {VERSION_APP}",
            font=Tipo.NOTA,
            bg=Color.LIENZO,
            fg=Color.TEXTO_SECUNDARIO,
        ).pack(pady=(0, px(Espacio.S)))
        self.boton_captura = Boton(
            self.raiz,
            "📷",
            self.capturar_pantalla,
            "icono",
            ayuda="Copiar captura de toda la calculadora",
            fuente=Tipo.EMOJI,
            padx=px(6),
            pady=px(2),
        )
        self._ubicar_boton_captura()

    def _ubicar_boton_captura(self):
        self.boton_captura.place(relx=1.0, rely=1.0, x=-px(Espacio.XS), y=-px(Espacio.XS), anchor="se")
        tk.Misc.tkraise(self.boton_captura)  # Canvas.lift mueve figuras, no el widget

    # --------------------------------------------------------------- cálculo
    def programar_calculo(self, _evento=None):
        """Recalcula poco después de la última tecla (cálculo en vivo)."""
        if self._calculo_pendiente is not None:
            self.raiz.after_cancel(self._calculo_pendiente)
        self._calculo_pendiente = self.raiz.after(
            RETARDO_CALCULO_MS, lambda: self.calcular(silencioso=True)
        )

    def calcular(self, silencioso=False):
        self._calculo_pendiente = None
        cantidades = self.cantidades()
        if sum(cantidades.values()) < 1:
            if not silencioso:
                messagebox.showerror(
                    "Dato incorrecto", "Debe haber al menos una persona en el presupuesto."
                )
                self.personas[ADULTOS].focus()
            return

        capturados = []
        for fila in self.filas:
            try:
                capturados.append(fila.capturar())
            except CampoInvalido as error:
                if not silencioso:
                    messagebox.showerror(
                        "Dato incorrecto", f"El valor ingresado en {fila.nombre()} no es válido."
                    )
                    error.campo.focus()
                return

        self._presupuesto = calcular_presupuesto(capturados, cantidades)
        self._mostrar_resumen(self._presupuesto, cantidades)
        if self._desglose_visible:
            self._construir_desglose()
        self.actualizar_scroll()

    def limpiar(self):
        for tipo, caja in self.personas.items():
            caja.delete(0, tk.END)
            caja.insert(0, "1" if tipo == ADULTOS else "0")
        self.ajuste_nuevo.delete(0, tk.END)
        self.redondear.set(True)
        for fila in list(self.filas):
            if fila.fijo:
                fila.reiniciar_montos()
            else:
                self.filas.remove(fila)
                fila.destruir()
        self.fila_enfocada = None
        self._tipos_visibles = None
        self.ubicar_filas()
        self.al_cambiar_personas()
        self.calcular(silencioso=True)
        self.personas[ADULTOS].focus()

    # --------------------------------------------------------------- captura
    def capturar_pantalla(self):
        self.boton_captura.place_forget()
        self.raiz.update()
        self.raiz.after(RETARDO_CAPTURA_MS, self._tomar_captura)

    def _tomar_captura(self):
        exito = False
        try:
            imagen = captura.capturar_contenido_completo(self.raiz, self.lienzo)
            captura.copiar_imagen_portapapeles(imagen)
            exito = True
        except Exception as error:  # portapapeles de Windows y captura de pantalla
            messagebox.showerror("Captura", f"No se pudo capturar la pantalla.\n{error}")
        self._ubicar_boton_captura()
        if exito:
            self.boton_captura.cambiar_texto("✔", Color.EXITO)
            self.raiz.after(
                DURACION_CONFIRMACION_MS,
                lambda: self.boton_captura.cambiar_texto("📷", Color.ICONO),
            )

    # ---------------------------------------------------------- actualización
    def iniciar_revision_actualizacion(self):
        if not getattr(sys, "frozen", False):
            return  # solo el programa instalado se actualiza
        actualizador.limpiar_descargas()
        cola = queue.Queue()
        threading.Thread(target=actualizador.hilo_consultar, args=(cola,), daemon=True).start()
        self.raiz.after(SONDEO_MS, lambda: self._revisar_actualizacion(cola))

    def _revisar_actualizacion(self, cola):
        try:
            info = cola.get_nowait()
        except queue.Empty:
            self.raiz.after(SONDEO_MS, lambda: self._revisar_actualizacion(cola))
            return
        if info and actualizador.es_mas_nueva(info["version"], VERSION_APP):
            if messagebox.askyesno(
                "Actualización disponible",
                f"Hay una versión nueva ({info['version']}).\n"
                f"Tu versión es la {VERSION_APP}.\n\n¿Quieres actualizar ahora?",
            ):
                self._descargar_actualizacion(info)

    def _descargar_actualizacion(self, info):
        cola = queue.Queue()
        dialogo = tk.Toplevel(self.raiz)
        dialogo.title("Actualizando")
        dialogo.configure(bg=Color.FONDO)
        dialogo.resizable(False, False)
        dialogo.transient(self.raiz)
        dialogo.protocol("WM_DELETE_WINDOW", lambda: None)
        tk.Label(
            dialogo,
            text=f"Descargando la versión {info['version']}...",
            font=Tipo.CUERPO_FUERTE,
            bg=Color.FONDO,
            fg=Color.MARCA,
            padx=px(Espacio.XL),
            pady=px(Espacio.L),
        ).pack()
        barra = ttk.Progressbar(dialogo, mode="determinate", length=px(320), maximum=100)
        barra.pack(padx=px(Espacio.XL), pady=(0, px(Espacio.XL)))
        dialogo.grab_set()
        threading.Thread(target=actualizador.hilo_descargar, args=(info, cola), daemon=True).start()

        def revisar():
            resultado = None
            while resultado is None and not cola.empty():
                mensaje = cola.get_nowait()
                if mensaje[0] != "progreso":
                    resultado = mensaje
                elif mensaje[2]:
                    barra["value"] = mensaje[1] * 100 / mensaje[2]
            if resultado is None:
                self.raiz.after(SONDEO_MS, revisar)
                return
            dialogo.grab_release()
            dialogo.destroy()
            if resultado[0] == "error":
                messagebox.showerror(
                    "Actualización", f"No se pudo descargar la actualización.\n{resultado[1]}"
                )
                return
            actualizador.lanzar_instalador(resultado[1])
            self.raiz.destroy()

        self.raiz.after(SONDEO_MS, revisar)


def main():
    activar_dpi()
    raiz = tk.Tk()
    Calculadora(raiz)
    raiz.mainloop()
