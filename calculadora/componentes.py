"""Componentes reutilizables de la interfaz."""

import tkinter as tk

from .tema import Color, Espacio, Tipo, px

RETARDO_AYUDA_MS = 450


class Ayuda:
    """Texto emergente al pasar el mouse. `texto` puede ser una cadena o una función."""

    def __init__(self, widget, texto):
        self.widget = widget
        self.texto = texto
        self._programada = None
        self._ventana = None
        widget.bind("<Enter>", self._programar, add="+")
        widget.bind("<Leave>", self.ocultar, add="+")
        widget.bind("<ButtonPress>", self.ocultar, add="+")

    def _programar(self, _evento=None):
        self._cancelar()
        self._programada = self.widget.after(RETARDO_AYUDA_MS, self._mostrar)

    def _cancelar(self):
        if self._programada is not None:
            self.widget.after_cancel(self._programada)
            self._programada = None

    def _mostrar(self):
        self._programada = None
        texto = self.texto() if callable(self.texto) else self.texto
        if not texto:
            return
        self._ventana = tk.Toplevel(self.widget)
        self._ventana.wm_overrideredirect(True)
        self._ventana.configure(bg=Color.TEXTO)
        tk.Label(
            self._ventana,
            text=texto,
            font=Tipo.NOTA,
            bg=Color.TEXTO,
            fg=Color.FONDO,
            padx=px(Espacio.S),
            pady=px(Espacio.XS),
        ).pack()
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + px(Espacio.XS)
        self._ventana.wm_geometry(f"+{x}+{y}")

    def ocultar(self, _evento=None):
        self._cancelar()
        if self._ventana is not None:
            self._ventana.destroy()
            self._ventana = None


# fondo, fondo al pasar el mouse, texto, texto al pasar el mouse, tipografía
VARIANTES = {
    "primario": (Color.MARCA, Color.MARCA_HOVER, Color.FONDO, Color.FONDO, Tipo.DATO_FUERTE),
    "peligro": (Color.FONDO, Color.ACENTO_SUAVE, Color.ACENTO, Color.ACENTO, Tipo.DATO_FUERTE),
    "suave": (Color.SUAVE, Color.SUAVE_HOVER, Color.MARCA, Color.MARCA, Tipo.CUERPO_FUERTE),
    "enlace": (None, Color.SUAVE, Color.MARCA, Color.MARCA, Tipo.CUERPO_FUERTE),
    "icono": (None, Color.ACENTO_SUAVE, Color.ICONO, Color.ACENTO, Tipo.ICONO),
}


class Boton(tk.Label):
    """Botón plano accesible con teclado (Tab, Enter y Espacio) y estado hover.

    Las variantes con fondo None toman el color de su contenedor y se pueden
    repintar con `cambiar_fondo` (por ejemplo, cuando la fila se resalta).
    """

    def __init__(self, padre, texto, comando, variante="primario", ayuda=None, fuente=None, **opciones):
        fondo, fondo_hover, color, color_hover, fuente_variante = VARIANTES[variante]
        fuente = fuente or fuente_variante
        self._fondo = fondo or padre.cget("bg")
        self._fondo_hover = fondo_hover
        self._color = color
        self._color_hover = color_hover
        self._comando = comando
        opciones.setdefault("padx", px(Espacio.L))
        opciones.setdefault("pady", px(Espacio.S))
        super().__init__(
            padre,
            text=texto,
            font=fuente,
            bg=self._fondo,
            fg=color,
            cursor="hand2",
            takefocus=1,
            highlightthickness=px(2),
            highlightbackground=self._fondo,
            highlightcolor=Color.MARCA,
            **opciones,
        )
        self.bind("<Enter>", self._entrar, add="+")
        self.bind("<Leave>", self._salir, add="+")
        self.bind("<Button-1>", self._activar, add="+")
        self.bind("<Return>", self._activar, add="+")
        self.bind("<KP_Enter>", self._activar, add="+")
        self.bind("<space>", self._activar, add="+")
        self._ayuda = Ayuda(self, ayuda) if ayuda else None

    def _entrar(self, _evento=None):
        self.config(bg=self._fondo_hover, fg=self._color_hover)

    def _salir(self, _evento=None):
        self.config(bg=self._fondo, fg=self._color)

    def _activar(self, _evento=None):
        if self._ayuda is not None:
            self._ayuda.ocultar()
        self._comando()
        return "break"

    def cambiar_fondo(self, color):
        self._fondo = color
        self.config(bg=color, fg=self._color, highlightbackground=color)
