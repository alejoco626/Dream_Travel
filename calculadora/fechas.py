"""Fechas en formato dd/mm/aaaa y cálculo de la fecha de pago."""

import calendar
from datetime import date, timedelta

FORMATO = "%d/%m/%Y"
DIAS_ANTES_DE_CANCELACION = 15


def formato_fecha(fecha):
    return fecha.strftime(FORMATO)


def leer_fecha(texto):
    """'25/12/2026' -> date(2026, 12, 25). None si la fecha no está completa o no existe."""
    partes = texto.strip().split("/")
    if len(partes) != 3 or not all(p.isdigit() for p in partes) or len(partes[2]) != 4:
        return None
    dia, mes, anio = (int(p) for p in partes)
    try:
        return date(anio, mes, dia)
    except ValueError:
        return None


def con_diagonales(texto):
    """Toma los dígitos escritos y los acomoda como dd/mm/aaaa: '25122026' -> '25/12/2026'."""
    digitos = "".join(c for c in texto if c.isdigit())[:8]
    partes = [digitos[:2], digitos[2:4], digitos[4:]]
    return "/".join(parte for parte in partes if parte)


def restar_meses(fecha, meses):
    """Mismo día N meses antes; si ese mes es más corto, el último día del mes (31/03 -> 28/02)."""
    total = fecha.year * 12 + (fecha.month - 1) - meses
    anio, mes = divmod(total, 12)
    mes += 1
    return date(anio, mes, min(fecha.day, calendar.monthrange(anio, mes)[1]))


def fecha_de_pago(fecha_viaje, fecha_cancelacion):
    """Devuelve (fecha de pago, holgada).

    Si el viaje es más de un mes después de la cancelación del hotel, se paga un mes
    antes del viaje (holgada=True). Si no, 15 días antes de la cancelación del hotel.
    """
    un_mes_antes_del_viaje = restar_meses(fecha_viaje, 1)
    if un_mes_antes_del_viaje > fecha_cancelacion:
        return un_mes_antes_del_viaje, True
    return fecha_cancelacion - timedelta(days=DIAS_ANTES_DE_CANCELACION), False
