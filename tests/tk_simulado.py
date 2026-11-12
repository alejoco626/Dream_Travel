"""Tkinter simulado para probar la interfaz sin pantalla.

Los widgets guardan sus opciones y su texto; los métodos que no importan para
las pruebas (pack, grid, bind, after...) no hacen nada.
"""

import sys
import types

WIDGETS = []


class Widget:
    def __init__(self, master=None, **opciones):
        self.master = master
        self.kw = dict(opciones)
        self.valor = ""
        self.destruido = False
        WIDGETS.append(self)

    def __getattr__(self, nombre):
        if nombre.startswith("__"):
            raise AttributeError(nombre)
        return lambda *args, **kwargs: None

    def config(self, **opciones):
        self.kw.update(opciones)

    configure = config

    def cget(self, opcion):
        return self.kw.get(opcion)

    def __setitem__(self, clave, valor):
        self.kw[clave] = valor

    def __getitem__(self, clave):
        return self.kw[clave]

    def destroy(self):
        self.destruido = True
        for hijo in self.winfo_children():
            hijo.destroy()

    def winfo_children(self):
        return [w for w in WIDGETS if w.master is self and not w.destruido]

    def get(self):
        return self.valor

    def set(self, valor):
        self.valor = valor

    def insert(self, _indice, texto):
        self.valor = texto + self.valor

    def delete(self, _inicio, _fin=None):
        self.valor = ""

    def winfo_screenwidth(self):
        return 1920

    def winfo_screenheight(self):
        return 1080

    def winfo_reqwidth(self):
        return 0

    def winfo_reqheight(self):
        return 0

    def winfo_width(self):
        return 0

    def winfo_height(self):
        return 0

    def after(self, _ms, _funcion=None):
        return None


class Comodin:
    """Objeto que acepta cualquier llamada (para Pillow y fuentes simuladas)."""

    def __getattr__(self, nombre):
        if nombre.startswith("__"):
            raise AttributeError(nombre)
        return lambda *args, **kwargs: Comodin()

    def __call__(self, *args, **kwargs):
        return Comodin()


class Fuente:
    def __init__(self, *args, **kwargs):
        pass

    def measure(self, texto):
        return 8 * len(texto)

    def metrics(self, _clave):
        return 16


class BooleanVar:
    def __init__(self, value=False):
        self.valor = value

    def get(self):
        return self.valor

    def set(self, valor):
        self.valor = valor


def instalar():
    """Reemplaza tkinter, PIL y win32clipboard por versiones simuladas."""
    errores = []
    tk = types.ModuleType("tkinter")
    for nombre in (
        "Tk", "Toplevel", "Frame", "Label", "Button", "Canvas", "Scrollbar", "PhotoImage",
        "Entry", "Spinbox", "Checkbutton", "Menu",
    ):
        setattr(tk, nombre, type(nombre, (Widget,), {}))
    tk.BooleanVar = BooleanVar
    tk.Misc = types.SimpleNamespace(tkraise=lambda widget: None)
    tk.END = "end"
    tk.INSERT = "insert"
    tk.TclError = type("TclError", (Exception,), {})

    messagebox = types.ModuleType("tkinter.messagebox")
    messagebox.showerror = lambda titulo, mensaje: errores.append((titulo, mensaje))
    messagebox.askyesno = lambda titulo, mensaje: False
    ttk = types.ModuleType("tkinter.ttk")
    ttk.Combobox = type("Combobox", (Widget,), {})
    ttk.Progressbar = type("Progressbar", (Widget,), {})
    ttk.Scrollbar = type("Scrollbar", (Widget,), {})
    ttk.Style = Comodin()
    fuente = types.ModuleType("tkinter.font")
    fuente.Font = Fuente
    tk.font = fuente
    tk.messagebox = messagebox
    tk.ttk = ttk

    pil = types.ModuleType("PIL")
    pil.Image = pil.ImageGrab = pil.ImageDraw = pil.ImageTk = Comodin()
    sys.modules.update(
        {
            "tkinter": tk,
            "tkinter.messagebox": messagebox,
            "tkinter.ttk": ttk,
            "tkinter.font": fuente,
            "PIL": pil,
            "win32clipboard": types.ModuleType("win32clipboard"),
        }
    )
    # Los módulos que importan tkinter se vuelven a cargar con la versión simulada.
    paquete = sys.modules.get("calculadora")
    for nombre in ("interfaz", "componentes", "captura"):
        sys.modules.pop(f"calculadora.{nombre}", None)
        if paquete is not None and hasattr(paquete, nombre):
            delattr(paquete, nombre)
    return tk, errores
