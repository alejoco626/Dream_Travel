"""Componentes reutilizables de la interfaz: tarjetas, campos y botones redondeados.

Tkinter no dibuja esquinas redondeadas, así que cada componente es un Canvas que
pinta su fondo con rectángulos rectos y cuatro esquinas suavizadas (generadas con
Pillow), lo que mantiene el redibujado rápido al cambiar el tamaño de la ventana.
"""

import tkinter as tk
import tkinter.font as tkfont

from PIL import Image, ImageDraw, ImageTk

from .tema import Color, Espacio, Radio, Tipo, px

RETARDO_AYUDA_MS = 450
SUPERMUESTREO = 4

_esquinas_cache = {}


def _esquinas(radio, relleno, exterior, borde=None, grosor=0):
    """Cuatro imágenes (nw, ne, sw, se) de un cuarto de círculo suavizado."""
    clave = (radio, relleno, exterior, borde, grosor)
    if clave not in _esquinas_cache:
        lado = radio * 2 * SUPERMUESTREO
        imagen = Image.new("RGB", (lado, lado), exterior)
        ImageDraw.Draw(imagen).ellipse(
            (0, 0, lado - 1, lado - 1),
            fill=relleno,
            outline=borde,
            width=grosor * SUPERMUESTREO if borde else 0,
        )
        imagen = imagen.resize((radio * 2, radio * 2), Image.LANCZOS)
        cortes = {
            "nw": (0, 0, radio, radio),
            "ne": (radio, 0, radio * 2, radio),
            "sw": (0, radio, radio, radio * 2),
            "se": (radio, radio, radio * 2, radio * 2),
        }
        _esquinas_cache[clave] = {
            ancla: ImageTk.PhotoImage(imagen.crop(caja)) for ancla, caja in cortes.items()
        }
    return _esquinas_cache[clave]


def pintar_redondeado(lienzo, ancho, alto, radio, relleno, exterior, borde=None, grosor=0):
    """Dibuja un rectángulo redondeado que ocupa todo el Canvas."""
    lienzo.delete("fondo")
    if ancho < 2 or alto < 2:
        return
    radio = max(1, min(radio, ancho // 2, alto // 2))
    etiqueta = {"tags": "fondo", "outline": "", "width": 0}
    lienzo.create_rectangle(radio, 0, ancho - radio, alto, fill=relleno, **etiqueta)
    lienzo.create_rectangle(0, radio, ancho, alto - radio, fill=relleno, **etiqueta)
    if borde and grosor:
        lienzo.create_rectangle(radio, 0, ancho - radio, grosor, fill=borde, **etiqueta)
        lienzo.create_rectangle(radio, alto - grosor, ancho - radio, alto, fill=borde, **etiqueta)
        lienzo.create_rectangle(0, radio, grosor, alto - radio, fill=borde, **etiqueta)
        lienzo.create_rectangle(ancho - grosor, radio, ancho, alto - radio, fill=borde, **etiqueta)
    esquinas = _esquinas(radio, relleno, exterior, borde if grosor else None, grosor)
    for ancla, x, y in (("nw", 0, 0), ("ne", ancho, 0), ("sw", 0, alto), ("se", ancho, alto)):
        lienzo.create_image(x, y, image=esquinas[ancla], anchor=ancla, tags="fondo")
    lienzo.tag_lower("fondo")


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


class Tarjeta(tk.Canvas):
    """Contenedor con esquinas redondeadas. El contenido va en `self.interior`.

    Toma el tamaño de su contenido. Con `estirar_ancho`/`estirar_alto`, el interior
    ocupa todo el espacio que el contenedor le dé a la tarjeta en esa dirección.
    """

    def __init__(self, padre, color=Color.FONDO, borde=Color.BORDE_TARJETA, padx=None, pady=None,
                 estirar_ancho=True, estirar_alto=False):
        self._exterior = padre.cget("bg")
        super().__init__(padre, bg=self._exterior, highlightthickness=0, bd=0)
        self._color = color
        self._borde = borde
        self._padx = px(Espacio.L) if padx is None else padx
        self._pady = px(Espacio.M) if pady is None else pady
        self._estirar_ancho = estirar_ancho
        self._estirar_alto = estirar_alto
        self.interior = tk.Frame(self, bg=color)
        self._ventana = self.create_window(
            self._padx, self._pady, window=self.interior, anchor="nw"
        )
        self.interior.bind("<Configure>", self._ajustar_a_contenido, add="+")
        self.bind("<Configure>", self._redibujar, add="+")

    def _ajustar_a_contenido(self, _evento=None):
        self.config(
            width=self.interior.winfo_reqwidth() + 2 * self._padx,
            height=self.interior.winfo_reqheight() + 2 * self._pady,
        )

    def _redibujar(self, evento):
        tamano = {}
        if self._estirar_ancho:
            tamano["width"] = max(1, evento.width - 2 * self._padx)
        if self._estirar_alto:
            tamano["height"] = max(1, evento.height - 2 * self._pady)
        if tamano:
            self.itemconfig(self._ventana, **tamano)
        pintar_redondeado(
            self, evento.width, evento.height, px(Radio.TARJETA), self._color,
            self._exterior, self._borde, 1 if self._borde else 0,
        )


class Campo(tk.Canvas):
    """Envuelve un Entry o Spinbox con un borde redondeado que cambia con el foco.

    `crear` recibe el contenedor y devuelve el widget de texto (sin bordes propios).
    """

    def __init__(self, padre, crear, padx=None, pady=None):
        self._exterior = padre.cget("bg")
        super().__init__(padre, bg=self._exterior, highlightthickness=0, bd=0)
        self._padx = px(Espacio.S) if padx is None else padx
        self._pady = px(6) if pady is None else pady
        self.widget = crear(self)
        self.widget.config(relief="flat", bd=0, highlightthickness=0)
        self._activo = True
        self._ventana = self.create_window(0, 0, window=self.widget, anchor="center")
        self.config(
            width=self.widget.winfo_reqwidth() + 2 * self._padx,
            height=self.widget.winfo_reqheight() + 2 * self._pady,
        )
        self.widget.bind("<FocusIn>", lambda _evento: self._pintar(), add="+")
        self.widget.bind("<FocusOut>", lambda _evento: self._pintar(), add="+")
        self.bind("<Configure>", lambda _evento: self._pintar(), add="+")
        self.bind("<Button-1>", lambda _evento: self.widget.focus_set(), add="+")

    def _colores(self):
        if not self._activo:
            return Color.DESACTIVADO_FONDO, Color.DESACTIVADO_FONDO, 1
        if self.focus_get() is self.widget:
            return Color.FOCO_CAMPO, Color.MARCA, 2
        return Color.FONDO, Color.BORDE_CAMPO, 1

    def _pintar(self):
        ancho, alto = self.winfo_width(), self.winfo_height()
        relleno, borde, grosor = self._colores()
        self.widget.config(bg=relleno)
        if isinstance(self.widget, tk.Spinbox):
            self.widget.config(buttonbackground=relleno)
        self.coords(self._ventana, ancho / 2, alto / 2)
        pintar_redondeado(
            self, ancho, alto, px(Radio.CONTROL), relleno, self._exterior, borde, px(grosor)
        )

    def habilitar(self, activo):
        self._activo = activo
        self.widget.config(state="normal" if activo else "disabled")
        self._pintar()

    def cambiar_fondo(self, color):
        """Color de lo que rodea al campo (por ejemplo, la fila resaltada)."""
        self._exterior = color
        self.config(bg=color)
        self._pintar()


# fondo, fondo al pasar el mouse, texto, texto al pasar el mouse, tipografía
VARIANTES = {
    "primario": (Color.MARCA, Color.MARCA_HOVER, Color.FONDO, Color.FONDO, Tipo.DATO_FUERTE),
    "peligro": (Color.ACENTO_SUAVE, "#F6D5DA", Color.ACENTO, Color.ACENTO, Tipo.DATO_FUERTE),
    "suave": (Color.SUAVE, Color.SUAVE_HOVER, Color.MARCA, Color.MARCA, Tipo.CUERPO_FUERTE),
    "enlace": (None, Color.SUAVE, Color.MARCA, Color.MARCA, Tipo.CUERPO_FUERTE),
    "icono": (None, Color.ACENTO_SUAVE, Color.ICONO, Color.ACENTO, Tipo.ICONO),
}


class Boton(tk.Canvas):
    """Botón redondeado accesible con teclado (Tab, Enter y Espacio).

    Las variantes sin fondo propio toman el color de su contenedor y se pueden
    repintar con `cambiar_fondo` (por ejemplo, cuando la fila se resalta).
    """

    def __init__(self, padre, texto, comando, variante="primario", ayuda=None, fuente=None,
                 padx=None, pady=None):
        fondo, fondo_hover, color, color_hover, fuente_variante = VARIANTES[variante]
        self._exterior = padre.cget("bg")
        super().__init__(
            padre, bg=self._exterior, highlightthickness=0, bd=0, cursor="hand2", takefocus=1
        )
        self._fondo_propio = fondo
        self._fondo_hover = fondo_hover
        self._color = color
        self._color_hover = color_hover
        self._comando = comando
        self._fuente = fuente or fuente_variante
        self._padx = px(Espacio.L) if padx is None else padx
        self._pady = px(Espacio.S) if pady is None else pady
        self._encima = False
        self._texto_id = self.create_text(0, 0, text=texto, font=self._fuente, fill=color)
        self._medir(texto)
        self.bind("<Enter>", lambda _evento: self._hover(True), add="+")
        self.bind("<Leave>", lambda _evento: self._hover(False), add="+")
        self.bind("<FocusIn>", lambda _evento: self._pintar(), add="+")
        self.bind("<FocusOut>", lambda _evento: self._pintar(), add="+")
        self.bind("<Configure>", lambda _evento: self._pintar(), add="+")
        for secuencia in ("<Button-1>", "<Return>", "<KP_Enter>", "<space>"):
            self.bind(secuencia, self._activar, add="+")
        self._ayuda = Ayuda(self, ayuda) if ayuda else None

    def _medir(self, texto):
        fuente = tkfont.Font(font=self._fuente)
        self.config(
            width=fuente.measure(texto) + 2 * self._padx,
            height=fuente.metrics("linespace") + 2 * self._pady,
        )

    def _hover(self, encima):
        self._encima = encima
        self._pintar()

    def _pintar(self):
        ancho, alto = self.winfo_width(), self.winfo_height()
        fondo = self._fondo_hover if self._encima else (self._fondo_propio or self._exterior)
        enfocado = self.focus_get() is self
        pintar_redondeado(
            self, ancho, alto, px(Radio.CONTROL), fondo, self._exterior,
            Color.MARCA if enfocado else None, px(2) if enfocado else 0,
        )
        self.itemconfig(self._texto_id, fill=self._color_hover if self._encima else self._color)
        self.coords(self._texto_id, ancho / 2, alto / 2)

    def _activar(self, _evento=None):
        if self._ayuda is not None:
            self._ayuda.ocultar()
        self._comando()
        return "break"

    def cambiar_texto(self, texto, color=None):
        self.itemconfig(self._texto_id, text=texto)
        self._medir(texto)
        if color is not None:
            self._color = color
        self._pintar()

    def cambiar_fondo(self, color):
        self._exterior = color
        self.config(bg=color)
        self._pintar()
