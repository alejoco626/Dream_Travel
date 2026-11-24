"""Fechas en formato dd/mm/aaaa y cálculo de la fecha de pago."""

import calendar
from datetime import date, timedelta

FORMATO = "%d/%m/%Y"
DIAS_ANTES_DE_CANCELACION = 15
ANIOS_MAXIMOS_A_FUTURO = 3  # una fecha más lejana casi seguro tiene el año mal escrito


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


def revisar_fecha(texto, nombre, hoy):
    """Devuelve (fecha, error). Error None si la fecha está bien o vacía (fecha None)."""
    texto = texto.strip()
    if not texto:
        return None, None
    digitos = "".join(c for c in texto if c.isdigit())
    if len(digitos) < 8:
        return None, f"La {nombre} está incompleta: escríbela como dd/mm/aaaa."
    fecha = leer_fecha(texto)
    if fecha is None:
        return None, f"La {nombre} no existe: revisa el día y el mes."
    if fecha.year > hoy.year + ANIOS_MAXIMOS_A_FUTURO:
        return None, f"Revisa el año de la {nombre}."
    return fecha, None


def revisar_fechas(texto_viaje, texto_cancelacion, hoy):
    """Revisa las dos fechas y calcula la fecha de pago.

    Devuelve un dict con: texto, tono ("neutro", "exito", "peligro" o "error"),
    campo (el campo con el error: "viaje" o "cancelacion") e incompleta (el error es
    solo que falta terminar de escribir).
    """
    viaje, error = revisar_fecha(texto_viaje, "fecha de viaje", hoy)
    if error:
        return {"texto": error, "tono": "error", "campo": "viaje", "incompleta": "incompleta" in error}
    cancelacion, error = revisar_fecha(texto_cancelacion, "fecha de cancelación del hotel", hoy)
    if error:
        return {"texto": error, "tono": "error", "campo": "cancelacion", "incompleta": "incompleta" in error}
    if viaje is not None and viaje < hoy:
        return {"texto": "La fecha de viaje ya pasó.", "tono": "error", "campo": "viaje"}
    if viaje is None or cancelacion is None:
        return {"texto": "Escribe las dos fechas para ver la fecha de pago.", "tono": "neutro", "campo": None}
    if cancelacion > viaje:
        return {
            "texto": "La cancelación del hotel no puede ser después del viaje.",
            "tono": "error",
            "campo": "cancelacion",
        }
    if cancelacion < hoy:
        return {
            "texto": "La fecha de cancelación del hotel ya pasó: la reserva ya no es reembolsable.",
            "tono": "error",
            "campo": "cancelacion",
        }
    pago, holgada = fecha_de_pago(viaje, cancelacion)
    if pago < hoy:
        return {
            "texto": f"Fecha de pago: {formato_fecha(pago)} (ya pasó: hay que pagar hoy)",
            "tono": "peligro",
            "campo": None,
        }
    return {"texto": f"Fecha de pago: {formato_fecha(pago)}", "tono": "exito" if holgada else "peligro", "campo": None}


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
