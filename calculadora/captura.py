"""Captura de la ventana completa (incluida la parte con scroll) al portapapeles."""

import io
import time

from PIL import Image, ImageGrab

MAX_PIEZAS = 200
PAUSA_REDIBUJO_S = 0.12


def copiar_imagen_portapapeles(imagen):
    import win32clipboard

    salida = io.BytesIO()
    imagen.convert("RGB").save(salida, "BMP")
    datos = salida.getvalue()[14:]  # CF_DIB no lleva la cabecera de archivo BMP
    salida.close()
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, datos)
    finally:
        win32clipboard.CloseClipboard()


def _refrescar(ventana):
    ventana.update_idletasks()
    ventana.update()
    time.sleep(PAUSA_REDIBUJO_S)


def _caja_ventana(ventana):
    x, y = ventana.winfo_rootx(), ventana.winfo_rooty()
    return (x, y, x + ventana.winfo_width(), y + ventana.winfo_height())


def _capturar(ventana):
    return ImageGrab.grab(bbox=_caja_ventana(ventana), all_screens=True).convert("RGB")


def capturar_contenido_completo(ventana, lienzo):
    """Devuelve una imagen de la ventana con todo el contenido del lienzo desplegado.

    Recorre el lienzo con scroll, captura cada tramo y los une. Lo que queda fuera
    del lienzo (encabezado, panel lateral y pie) se toma de la primera captura.
    """
    maximizada = False
    _, _, derecha, abajo = _caja_ventana(ventana)
    if ventana.state() == "normal" and (
        derecha > ventana.winfo_screenwidth() or abajo > ventana.winfo_screenheight()
    ):
        ventana.state("zoomed")
        maximizada = True
        _refrescar(ventana)

    posicion_scroll = lienzo.yview()[0]
    try:
        lienzo.configure(scrollregion=lienzo.bbox("all"))
        lienzo.yview_moveto(0)
        _refrescar(ventana)
        x0, y0, _, _ = _caja_ventana(ventana)
        base = _capturar(ventana)
        cx = lienzo.winfo_rootx() - x0
        cy = lienzo.winfo_rooty() - y0
        ancho = lienzo.winfo_width()
        alto = lienzo.winfo_height()
        region = lienzo.bbox("all")
        if not region or region[3] - region[1] <= alto:
            return base

        origen = region[1]
        alto_total = region[3] - region[1]
        piezas = [(0, base.crop((cx, cy, cx + ancho, cy + alto)))]
        tope = 0
        while tope + alto < alto_total and len(piezas) < MAX_PIEZAS:
            lienzo.yview_moveto((tope + alto) / alto_total)
            _refrescar(ventana)
            nuevo_tope = int(round(lienzo.canvasy(0))) - origen
            if nuevo_tope <= tope:
                break
            piezas.append((nuevo_tope, _capturar(ventana).crop((cx, cy, cx + ancho, cy + alto))))
            tope = nuevo_tope

        inferior = base.crop((0, cy + alto, base.width, base.height))
        final = Image.new(
            "RGB",
            (base.width, cy + alto_total + inferior.height),
            base.getpixel((1, cy + 2)),
        )
        final.paste(base.crop((0, 0, base.width, cy)), (0, 0))
        final.paste(base.crop((0, cy, cx, cy + alto)), (0, cy))
        final.paste(base.crop((cx + ancho, cy, base.width, cy + alto)), (cx + ancho, cy))
        for tope_pieza, pieza in piezas:
            final.paste(pieza, (cx, cy + tope_pieza))
        final.paste(inferior, (0, cy + alto_total))
        return final
    finally:
        lienzo.yview_moveto(posicion_scroll)
        if maximizada:
            ventana.state("normal")
        _refrescar(ventana)
