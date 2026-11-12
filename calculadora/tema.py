"""Tokens de diseño: color, tipografía y espaciado.

Toda la interfaz toma sus valores de aquí; no se escriben colores ni tamaños sueltos.
Contrastes verificados contra WCAG 2.1 AA (texto 4.5:1, bordes e iconos 3:1).
"""

FAMILIA = "Segoe UI"


class Color:
    MARCA = "#003D6B"  # azul Dream & Travel: títulos, acción principal, foco
    MARCA_HOVER = "#00528F"
    MARCA_TEXTO_SUAVE = "#C9D7E6"  # texto secundario sobre la banda azul (7.6:1)
    ACENTO = "#960018"  # corinto: solo totales y acciones destructivas
    ACENTO_SUAVE = "#FBE9EB"

    LIENZO = "#EEF2F6"  # fondo de la ventana, detrás de las tarjetas
    FONDO = "#FFFFFF"  # tarjetas y campos
    SUPERFICIE = "#F4F6F9"  # encabezados de tabla y zonas secundarias
    SUPERFICIE_ALTERNA = "#FAFBFC"  # filas pares
    SUAVE = "#E6EEF7"  # botones secundarios
    SUAVE_HOVER = "#D3E2F1"
    RESALTE = "#E3EEF9"  # fila y columna activas
    FOCO_CAMPO = "#F3F8FE"  # fondo del campo que se está editando

    TEXTO = "#1F2937"
    TEXTO_SECUNDARIO = "#525B68"  # 6.3:1 sobre SUPERFICIE, 5.9:1 sobre LIENZO
    ICONO = "#6B7686"  # 4.6:1 sobre FONDO
    BORDE_CAMPO = "#8A94A3"  # 3.1:1 sobre FONDO
    DIVISOR = "#DDE3EA"  # decorativo
    BORDE_TARJETA = "#E1E6EC"  # contorno suave de las tarjetas

    DESACTIVADO_FONDO = "#ECEFF3"
    DESACTIVADO_TEXTO = "#6E7681"
    EXITO = "#1E7A4C"  # 5.6:1 sobre FONDO
    PELIGRO = "#C62828"  # rojo de aviso, 5.6:1 sobre FONDO


class Tipo:
    """Escala tipográfica (puntos): 9 · 10 · 11 · 16."""

    NOTA = (FAMILIA, 9)
    NOTA_FUERTE = (FAMILIA, 9, "bold")
    CUERPO = (FAMILIA, 10)
    CUERPO_FUERTE = (FAMILIA, 10, "bold")
    DATO = (FAMILIA, 11)
    DATO_FUERTE = (FAMILIA, 11, "bold")
    TITULO_APP = (FAMILIA, 16, "bold")
    CIFRA = (FAMILIA, 16, "bold")  # precios por persona y totales del resumen
    ICONO = (FAMILIA, 11)
    EMOJI = ("Segoe UI Emoji", 12)


class Espacio:
    """Escala de espaciado en píxeles lógicos (se multiplica por la escala de pantalla)."""

    XS = 4
    S = 8
    M = 12
    L = 16
    XL = 24


class Radio:
    """Radio de las esquinas en píxeles lógicos."""

    TARJETA = 14
    CONTROL = 8


_escala = {"factor": 1.0}


def configurar_escala(raiz):
    """Ajusta los píxeles a la escala de Windows (100 %, 125 %, 150 %...)."""
    try:
        pixeles_por_punto = float(raiz.tk.call("tk", "scaling"))
    except (AttributeError, TypeError, ValueError):
        return
    _escala["factor"] = max(1.0, pixeles_por_punto / (96 / 72))


def px(valor):
    return int(round(valor * _escala["factor"]))
