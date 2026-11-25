"""Lógica del presupuesto, independiente de la interfaz."""

import math
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from .config import (
    ADULTOS,
    CLAVE_ADULTOS,
    CLAVE_ADULTOS_NINOS,
    CLAVE_ADULTOS_NINOS_INFANTES,
    DIVISOR_DESCUENTO_EFECTIVO,
    INFANTES,
    MODO_PERSONA,
    MODO_REPARTO,
    NINOS,
    PESOS_REPARTO,
    TIPO_CAMBIO_GTQ,
    TIPOS_PERSONA,
)


def leer_monto(texto):
    """Convierte '$ 1,250.00' en 1250.0. Vacío vale 0. Lanza ValueError si no es número."""
    if not texto.strip():
        return 0.0
    valor = float(texto.replace("$", "").replace(",", "").strip())
    if not math.isfinite(valor):  # float() acepta "nan" e "inf", que romperían los totales
        raise ValueError("monto no válido")
    return valor


def dinero(valor):
    return f"$ {valor:,.2f}"


def tipos_activos(cantidades):
    """Adultos siempre; niños e infantes solo si hay al menos uno."""
    return [ADULTOS] + [t for t in (NINOS, INFANTES) if cantidades.get(t, 0) > 0]


@dataclass(frozen=True)
class ServicioCapturado:
    nombre: str
    proporcion_costo: float
    modo: str
    montos: dict
    tipos_incluidos: frozenset


@dataclass(frozen=True)
class Renglon:
    tipo: str
    cantidad: int
    costo_total: float
    costo_persona: float
    pvp_total: float
    pvp_persona: float

    @property
    def valores(self):
        return (self.costo_total, self.costo_persona, self.pvp_total, self.pvp_persona)


@dataclass
class Presupuesto:
    servicios: list = field(default_factory=list)  # [(nombre, [Renglon])]
    pvp_persona: dict = field(default_factory=dict)
    descuento_persona: dict = field(default_factory=dict)
    subtotal_pvp: dict = field(default_factory=dict)
    subtotal_descuento: dict = field(default_factory=dict)
    total_pvp: float = 0.0
    total_descuento: float = 0.0
    totales_columnas: tuple = (0.0, 0.0, 0.0, 0.0)


CLAVE_TOTAL = "total"


def costos_repartidos(total, tipos_incluidos, cantidades):
    """Reparte un total según el peso de cada persona (PESOS_REPARTO).

    Solo cuentan los tipos incluidos que tienen personas; la suma siempre da el total.
    """
    partes = {
        tipo: PESOS_REPARTO[tipo] * cantidades[tipo]
        for tipo in TIPOS_PERSONA
        if tipo in tipos_incluidos and cantidades.get(tipo, 0) > 0
    }
    suma = sum(partes.values())
    costos = {tipo: 0.0 for tipo in TIPOS_PERSONA}
    if suma > 0:
        for tipo, peso in partes.items():
            costos[tipo] = total * peso / suma
    return costos


def costos_por_tipo(servicio, cantidades):
    """Reparte el costo del servicio entre adultos, niños e infantes.

    Con "Repartir monto" divide el total por pesos. Si no, resta las cotizaciones
    acumuladas (ver costos_cotizados). Un costo negativo no puede ser un precio: si la
    cotización con más personas salió más barata que la anterior, se toma 0 (la página
    lo avisa).
    """
    if servicio.modo == MODO_REPARTO:
        return costos_repartidos(servicio.montos[CLAVE_TOTAL], servicio.tipos_incluidos, cantidades)
    return {tipo: max(0.0, costo) for tipo, costo in costos_cotizados(servicio, cantidades).items()}


def costos_cotizados(servicio, cantidades):
    """Costos tal como salen de restar las cotizaciones acumuladas (pueden ser negativos).

    Los montos son acumulados: el costo de los niños es (adultos + niños) - adultos
    y el de los infantes es (adultos + niños + infantes) - (adultos + niños). En el
    Diseñador cada monto es por persona y se multiplica por las personas de ese grupo.
    """
    adultos = cantidades[ADULTOS]
    ninos = cantidades[NINOS] if NINOS in servicio.tipos_incluidos else 0
    infantes = cantidades[INFANTES] if INFANTES in servicio.tipos_incluidos else 0
    por_persona = servicio.modo == MODO_PERSONA
    montos = servicio.montos

    base_adultos = montos[CLAVE_ADULTOS] * adultos if por_persona else montos[CLAVE_ADULTOS]

    if ninos:
        monto = montos[CLAVE_ADULTOS_NINOS]
        base_adultos_ninos = monto * (adultos + ninos) if por_persona else monto
    else:
        base_adultos_ninos = base_adultos

    if infantes:
        monto = montos[CLAVE_ADULTOS_NINOS_INFANTES]
        base_combinada = monto * (adultos + ninos + infantes) if por_persona else monto
    else:
        base_combinada = base_adultos_ninos

    return {
        ADULTOS: base_adultos,
        NINOS: (base_adultos_ninos - base_adultos) if ninos else 0.0,
        INFANTES: (base_combinada - base_adultos_ninos) if infantes else 0.0,
    }


def calcular_presupuesto(servicios, cantidades):
    activos = tipos_activos(cantidades)
    pvp_persona = {tipo: 0.0 for tipo in TIPOS_PERSONA}
    totales = [0.0, 0.0, 0.0, 0.0]
    presupuesto = Presupuesto()

    for servicio in servicios:
        costos = costos_por_tipo(servicio, cantidades)
        renglones = []
        for tipo in activos:
            if tipo not in servicio.tipos_incluidos:
                continue
            numero = cantidades[tipo]
            costo_total = costos[tipo]
            pvp_total = costo_total / servicio.proporcion_costo
            renglon = Renglon(
                tipo=tipo,
                cantidad=numero,
                costo_total=costo_total,
                costo_persona=costo_total / numero if numero else 0.0,
                pvp_total=pvp_total,
                pvp_persona=pvp_total / numero if numero else 0.0,
            )
            if numero:
                pvp_persona[tipo] += renglon.pvp_persona
            for posicion, valor in enumerate(renglon.valores):
                totales[posicion] += valor
            renglones.append(renglon)
        presupuesto.servicios.append((servicio.nombre, renglones))

    for tipo in TIPOS_PERSONA:
        descuento = pvp_persona[tipo] / DIVISOR_DESCUENTO_EFECTIVO
        presupuesto.pvp_persona[tipo] = pvp_persona[tipo]
        presupuesto.descuento_persona[tipo] = descuento
        presupuesto.subtotal_pvp[tipo] = pvp_persona[tipo] * cantidades[tipo]
        presupuesto.subtotal_descuento[tipo] = descuento * cantidades[tipo]

    presupuesto.total_pvp = sum(presupuesto.subtotal_pvp.values())
    presupuesto.total_descuento = sum(presupuesto.subtotal_descuento.values())
    presupuesto.totales_columnas = tuple(totales)
    return presupuesto


def formato_quetzales(valor_en_quetzales):
    return f"Q {valor_en_quetzales:,.2f}"


@dataclass
class PreciosPorPersona:
    """Precios que se muestran en el panel, con o sin redondeo."""

    pvp: dict = field(default_factory=dict)
    pvp_q: dict = field(default_factory=dict)
    descuento: dict = field(default_factory=dict)
    descuento_q: dict = field(default_factory=dict)
    subtotal_pvp: dict = field(default_factory=dict)
    subtotal_descuento: dict = field(default_factory=dict)
    total_pvp: float = 0.0
    total_pvp_q: float = 0.0
    total_descuento: float = 0.0
    total_descuento_q: float = 0.0


def pvp_redondeados(presupuesto, cantidades, cuadrar):
    """PVP por persona redondeado al entero más próximo.

    Cada tipo redondea por su cuenta y el error se multiplica por las personas (3 adultos
    con 0.40 de más son 1.20 de más), así que el total puede subir o bajar 1 o 2 dólares.
    Con cuadrar=True el precio del adulto se corrige en 1 o 2 dólares para que el total
    quede lo más cerca posible del total exacto.
    """
    pvp = {tipo: redondear_cercano(presupuesto.pvp_persona[tipo]) for tipo in TIPOS_PERSONA}
    adultos = cantidades[ADULTOS]
    if cuadrar and adultos:
        exacto = sum(presupuesto.pvp_persona[tipo] * cantidades[tipo] for tipo in TIPOS_PERSONA)
        otros = sum(pvp[tipo] * cantidades[tipo] for tipo in TIPOS_PERSONA if tipo != ADULTOS)
        mejor = min(range(-2, 3), key=lambda paso: (abs(exacto - otros - (pvp[ADULTOS] + paso) * adultos), abs(paso)))
        pvp[ADULTOS] = max(0.0, pvp[ADULTOS] + mejor)
    return pvp


def precios_por_persona(presupuesto, cantidades, redondear, cuadrar=False):
    """Con redondeo, cada precio por persona ($ y Q) va al entero más próximo (.50 sube)
    y los totales se calculan a partir de esos precios redondeados."""
    ajustar = redondear_cercano if redondear else (lambda valor: valor)
    pvp_por_tipo = pvp_redondeados(presupuesto, cantidades, cuadrar) if redondear else presupuesto.pvp_persona
    precios = PreciosPorPersona()
    total_pvp_q = total_descuento_q = 0.0
    for tipo in TIPOS_PERSONA:
        numero = cantidades[tipo]
        pvp = pvp_por_tipo[tipo]
        # Con redondeo, el descuento sale del PVP que se ve (PVP redondeado / 1.05).
        descuento = ajustar(pvp / DIVISOR_DESCUENTO_EFECTIVO) if redondear else presupuesto.descuento_persona[tipo]
        precios.pvp[tipo] = pvp
        precios.descuento[tipo] = descuento
        precios.pvp_q[tipo] = ajustar(pvp * TIPO_CAMBIO_GTQ)
        precios.descuento_q[tipo] = ajustar(descuento * TIPO_CAMBIO_GTQ)
        precios.subtotal_pvp[tipo] = pvp * numero
        precios.subtotal_descuento[tipo] = descuento * numero
        total_pvp_q += precios.pvp_q[tipo] * numero
        total_descuento_q += precios.descuento_q[tipo] * numero
    precios.total_pvp = sum(precios.subtotal_pvp.values())
    precios.total_descuento = sum(precios.subtotal_descuento.values())
    if redondear:
        precios.total_pvp_q = total_pvp_q
        precios.total_descuento_q = total_descuento_q
    else:
        precios.total_pvp_q = precios.total_pvp * TIPO_CAMBIO_GTQ
        precios.total_descuento_q = precios.total_descuento * TIPO_CAMBIO_GTQ
    return precios


def redondear_cercano(valor):
    """Entero más próximo; .50 sube: 50.49 -> 50, 50.50 -> 51."""
    return float(Decimal(f"{valor:.2f}").quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def diferencia_total(precio_adulto, precio_nuevo, cantidades):
    """(precio de la calculadora - precio del diseñador) x todas las personas (adultos, niños e infantes)."""
    personas = sum(cantidades[tipo] for tipo in TIPOS_PERSONA)
    return precio_adulto * personas - precio_nuevo * personas
