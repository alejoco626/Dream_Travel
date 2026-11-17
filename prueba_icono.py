import sys, time, tkinter as tk
from PIL import Image, ImageTk
modo = sys.argv[1]
r = tk.Tk(); r.title("Modo " + modo); r.geometry("360x120+%d+40" % (20 + 380 * int(sys.argv[2])))
ico = "icono_calculadora.ico"
if modo in ("bitmap", "ambos"):
    r.iconbitmap(default=ico)
if modo in ("foto", "ambos"):
    im = Image.open(ico); fotos = []
    for t in sorted(im.info["sizes"], reverse=True):
        im.size = t; im.load(); fotos.append(ImageTk.PhotoImage(im.copy().convert("RGBA")))
    r.iconphoto(True, *fotos)
if modo == "foto256":
    im = Image.open(ico); im.size = (256, 256); im.load()
    f = ImageTk.PhotoImage(im.copy().convert("RGBA")); r.iconphoto(True, f)
r.after(25000, r.destroy); r.mainloop()
