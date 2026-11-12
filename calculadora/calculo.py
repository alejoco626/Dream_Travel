"""Lógica del presupuesto, independiente de la interfaz."""

from dataclasses import dataclass, field

from .config import (
    ADULTOS,
    CLAVE_ADULTOS,
    CLAVE_ADULTOS_NINOS,
    CLAVE_ADULTOS_NINOS_INFANTES,
    DIVISOR_DESCUENTO_EFECTIVO,
    INFANTES,
    MODO_PERSONA,
    NINOS,
    TIPO_CAMBIO_GTQ,
    TIPOS_PERSONA,
)


def leer_monto(texto):
    """Convierte '$ 1,250.00' en 1250.0. Vacío vale 0. Lanza ValueError si no es número."""
    if not texto.strip():
        return 0.0
    return float(texto.replace("$", "").replace(",", "").strip())


def dinero(valor):
    return f"$ {valor:,.2f}"


def quetzales(valor):
    return f"Q {valor * TIPO_CAMBIO_GTQ:,.2f}"


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


def costos_por_tipo(servicio, cantidades):
    """Reparte el costo del servicio entre adultos, niños e infantes.

    Los montos son acumulados: el costo de los niños es (adultos + niños) - adultos
    y el de los infantes es (adultos + niños + infantes) - (adultos + niños).
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

    costos = {
        ADULTOS: base_adultos,
        NINOS: (base_adultos_ninos - base_adultos) if ninos else 0.0,
        INFANTES: (base_combinada - base_adultos_ninos) if infantes else 0.0,
    }
    if por_persona and costos[INFANTES] <= 0:
        costos[INFANTES] = 0.0
    return costos


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


def redondear_arriba(valor):
    """Sube al siguiente entero si hay centavos: 301.01 -> 302, 301.00 -> 301."""
    centavos = round(valor * 100)
    return float(-(-centavos // 100))


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


def precios_por_persona(presupuesto, cantidades, redondear):
    """Con redondeo, cada precio por persona ($ y Q) sube al siguiente entero y los
    totales se calculan a partir de esos precios redondeados."""
    ajustar = redondear_arriba if redondear else (lambda valor: valor)
    precios = PreciosPorPersona()
    total_pvp_q = total_descuento_q = 0.0
    for tipo in TIPOS_PERSONA:
        numero = cantidades[tipo]
        pvp = ajustar(presupuesto.pvp_persona[tipo])
        descuento = ajustar(presupuesto.descuento_persona[tipo])
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


def diferencia_por_persona(precio_adulto, precio_nuevo, cantidades):
    """(precio adulto - precio nuevo) x adultos, repartido entre todas las personas.

    Devuelve (diferencia total, diferencia por persona).
    """
    total = (precio_adulto - precio_nuevo) * cantidades[ADULTOS]
    personas = sum(cantidades.values())
    return total, (total / personas if personas else 0.0)
