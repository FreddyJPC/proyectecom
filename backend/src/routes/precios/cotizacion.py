"""
La COTIZACIÓN de un pedido (ADR-017): el único lugar que calcula cuánto paga el cliente.

Recibe las líneas del pedido y las reglas (producto, oferta, negocio) ya leídas, y devuelve el desglose: precio de cada línea,
descuentos con su motivo, envío, total contra entrega, total por transferencia y el mínimo al que se puede regatear. Victoria nunca
calcula: comunica lo que sale de aquí. Lógica PURA con `Decimal`: se prueba con datos, sin base de datos.

Reglas que aplica (ver ADR-017 en PROGRESS.md):
- Sin reglas configuradas, el total es exactamente el de antes (precio × cantidad + envío elegido).
- Regateo y precio por transferencia NO se suman (P2): por transferencia se cobra el menor de los dos.
- El regateo nunca baja del límite del dueño ni del piso de margen.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence

from .reglas import (
    AjustesPiso,
    Escala,
    dinero,
    limite_regateo,
    piso_del_pedido,
    precio_por_cantidad,
    precio_transferencia,
)

LINEA_PRODUCTO = "producto"
LINEA_OFERTA = "oferta"

MOTIVO_ESCALA = "escala"
MOTIVO_OFERTA = "oferta"
MOTIVO_REGATEO = "regateo"
MOTIVO_TRANSFERENCIA = "transferencia"
MOTIVO_ENVIO_GRATIS = "envio_gratis"

CERO = Decimal("0.00")


# ---------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ProductoPrecio:
    sku: str
    nombre: str
    precio: Decimal
    costo: Optional[Decimal] = None
    envio_incluido: bool = True
    transferencia_tipo: Optional[str] = None
    transferencia_valor: Optional[Decimal] = None
    regateo_tipo: Optional[str] = None
    regateo_valor: Optional[Decimal] = None
    envio_gratis_desde_unidades: Optional[int] = None
    envio_gratis_desde_monto: Optional[Decimal] = None
    escalas: Sequence[Escala] = ()


@dataclass(frozen=True)
class ItemOferta:
    sku: str
    cantidad: int = 1
    variante: Optional[str] = None


@dataclass(frozen=True)
class OfertaPrecio:
    id: int
    nombre: str
    precio: Decimal
    items: Sequence[ItemOferta]
    envio_incluido: bool = True
    regateo_tipo: Optional[str] = None
    regateo_valor: Optional[Decimal] = None
    transferencia_tipo: Optional[str] = None
    transferencia_valor: Optional[Decimal] = None


@dataclass(frozen=True)
class LineaPedido:
    tipo: str  # producto | oferta
    cantidad: int = 1
    sku: Optional[str] = None
    oferta_id: Optional[int] = None
    variante: Optional[str] = None

    def a_json(self) -> Dict[str, Any]:
        datos: Dict[str, Any] = {"tipo": self.tipo, "cantidad": self.cantidad}
        if self.tipo == LINEA_PRODUCTO:
            datos["sku"] = self.sku
        else:
            datos["oferta_id"] = self.oferta_id
        if self.variante:
            datos["variante"] = self.variante
        return datos

    @staticmethod
    def desde_json(datos: Dict[str, Any]) -> "LineaPedido":
        tipo = datos.get("tipo") or LINEA_PRODUCTO
        return LineaPedido(
            tipo=tipo,
            cantidad=int(datos.get("cantidad") or 1),
            sku=datos.get("sku") if tipo == LINEA_PRODUCTO else None,
            oferta_id=int(datos["oferta_id"]) if tipo == LINEA_OFERTA and datos.get("oferta_id") is not None else None,
            variante=datos.get("variante") or None,
        )


@dataclass(frozen=True)
class Regateo:
    """Estado del regateo guardado en el lead. `acordado` vale solo si el pedido no cambió desde entonces (`base`)."""

    acordado: Optional[Decimal] = None
    base: Optional[Decimal] = None
    rondas: int = 0
    contraoferta: Optional[Decimal] = None

    def a_json(self) -> Dict[str, Any]:
        return {
            "acordado": None if self.acordado is None else f"{self.acordado:.2f}",
            "base": None if self.base is None else f"{self.base:.2f}",
            "rondas": self.rondas,
            "contraoferta": None if self.contraoferta is None else f"{self.contraoferta:.2f}",
        }

    @staticmethod
    def desde_json(datos: Optional[Dict[str, Any]]) -> "Regateo":
        datos = datos or {}

        def _d(clave):
            return dinero(datos[clave]) if datos.get(clave) not in (None, "") else None

        return Regateo(acordado=_d("acordado"), base=_d("base"), rondas=int(datos.get("rondas") or 0), contraoferta=_d("contraoferta"))


@dataclass(frozen=True)
class TransferenciaNegocio:
    tipo: Optional[str] = None  # porcentaje | monto
    valor: Optional[Decimal] = None


@dataclass
class DatosCotizacion:
    lineas: Sequence[LineaPedido]
    productos: Dict[str, ProductoPrecio]
    ofertas: Dict[int, OfertaPrecio] = field(default_factory=dict)
    transferencia_negocio: TransferenciaNegocio = field(default_factory=TransferenciaNegocio)
    ajustes: Optional[AjustesPiso] = None
    envio_opcion_costo: Optional[Decimal] = None  # costo para el cliente de la entrega elegida (None = aún no elige)
    regateo: Regateo = field(default_factory=Regateo)
    metodo_pago: Optional[str] = None


# ---------------------------------------------------------------------------
# Salida
# ---------------------------------------------------------------------------
@dataclass
class ItemCotizado:
    """Una línea para Rocketfy / `ventas_lineas`: un producto concreto con su cantidad final."""

    sku: str
    nombre: str
    cantidad: int
    variante: Optional[str]
    precio_lista_unitario: Decimal
    oferta_id: Optional[int] = None


@dataclass
class LineaCotizada:
    tipo: str
    nombre: str
    cantidad: int
    precio_lista: Decimal
    precio: Decimal
    motivo: str  # lista | escala | oferta
    precio_transferencia: Optional[Decimal]
    piso_regateo: Decimal  # lo menos que puede quedar esta línea al regatear (= precio si no se regatea)
    costo: Optional[Decimal]
    necesita_envio: bool
    items: List[ItemCotizado]
    sku: Optional[str] = None
    oferta_id: Optional[int] = None
    variante: Optional[str] = None


@dataclass
class Cotizacion:
    lineas: List[LineaCotizada]
    subtotal_lista: Decimal
    subtotal: Decimal  # tras escalas y ofertas, antes de regateo y transferencia
    subtotal_contraentrega: Decimal  # con el regateo, si lo hay
    subtotal_transferencia: Decimal
    envio: Decimal
    envio_gratis: bool
    envio_pendiente: bool  # hay que elegir la entrega y todavía no se eligió
    total_contraentrega: Decimal
    total_transferencia: Decimal
    metodo_pago: Optional[str]
    piso: Optional[Decimal]
    minimo_regateo: Optional[Decimal]  # None = no se puede regatear este pedido
    regateo_vigente: bool

    @property
    def total(self) -> Decimal:
        return self.total_transferencia if self.metodo_pago == "transferencia" else self.total_contraentrega

    @property
    def subtotal_a_pagar(self) -> Decimal:
        return self.subtotal_transferencia if self.metodo_pago == "transferencia" else self.subtotal_contraentrega

    @property
    def hay_precio_por_transferencia(self) -> bool:
        return self.total_transferencia < self.total_contraentrega

    @property
    def items(self) -> List[ItemCotizado]:
        return [item for linea in self.lineas for item in linea.items]

    @property
    def unidades(self) -> int:
        return sum(item.cantidad for item in self.items)

    def descuentos(self) -> List[Dict[str, Any]]:
        """Cada rebaja respecto al precio de lista, con su motivo, para el método de pago actual (para reportes y para el dueño)."""
        salida: List[Dict[str, Any]] = []

        def _sumar(motivo: str, monto: Decimal) -> None:
            if monto > 0:
                salida.append({"motivo": motivo, "monto": f"{monto:.2f}"})

        _sumar(MOTIVO_ESCALA, sum((l.precio_lista - l.precio for l in self.lineas if l.motivo == MOTIVO_ESCALA), CERO))
        _sumar(MOTIVO_OFERTA, sum((l.precio_lista - l.precio for l in self.lineas if l.motivo == MOTIVO_OFERTA), CERO))
        _sumar(MOTIVO_REGATEO, self.subtotal - self.subtotal_contraentrega)
        if self.metodo_pago == "transferencia":
            _sumar(MOTIVO_TRANSFERENCIA, self.subtotal_contraentrega - self.subtotal_transferencia)
        return salida

    def descuento_total(self) -> Decimal:
        return sum((Decimal(d["monto"]) for d in self.descuentos()), CERO)

    def a_json(self) -> Dict[str, Any]:
        def _m(valor: Optional[Decimal]) -> Optional[str]:
            return None if valor is None else f"{valor:.2f}"

        return {
            "lineas": [
                {
                    "tipo": l.tipo,
                    "sku": l.sku,
                    "oferta_id": l.oferta_id,
                    "nombre": l.nombre,
                    "variante": l.variante,
                    "cantidad": l.cantidad,
                    "precio_lista": _m(l.precio_lista),
                    "precio": _m(l.precio),
                    "motivo": l.motivo,
                    "precio_transferencia": _m(l.precio_transferencia),
                    "items": [
                        {
                            "sku": i.sku,
                            "nombre": i.nombre,
                            "cantidad": i.cantidad,
                            "variante": i.variante,
                            "precio_lista_unitario": _m(i.precio_lista_unitario),
                            "oferta_id": i.oferta_id,
                        }
                        for i in l.items
                    ],
                }
                for l in self.lineas
            ],
            "subtotal_lista": _m(self.subtotal_lista),
            "subtotal": _m(self.subtotal),
            "subtotal_contraentrega": _m(self.subtotal_contraentrega),
            "subtotal_transferencia": _m(self.subtotal_transferencia),
            "envio": _m(self.envio),
            "envio_gratis": self.envio_gratis,
            "envio_pendiente": self.envio_pendiente,
            "total_contraentrega": _m(self.total_contraentrega),
            "total_transferencia": _m(self.total_transferencia),
            "metodo_pago": self.metodo_pago,
            "total": _m(self.total),
            "piso": _m(self.piso),
            "minimo_regateo": _m(self.minimo_regateo),
            "regateo_vigente": self.regateo_vigente,
            "descuentos": self.descuentos(),
        }


class LineaInvalida(ValueError):
    """Una línea apunta a un producto u oferta que no se pudo leer."""


# ---------------------------------------------------------------------------
# Cálculo
# ---------------------------------------------------------------------------
def _linea_producto(linea: LineaPedido, datos: DatosCotizacion) -> LineaCotizada:
    producto = datos.productos.get(linea.sku or "")
    if producto is None:
        raise LineaInvalida(f"No hay datos del producto {linea.sku}")
    cantidad = linea.cantidad
    lista = dinero(Decimal(producto.precio) * cantidad)
    precio, escala = precio_por_cantidad(producto.precio, cantidad, producto.escalas)

    # Regla del producto o, si no tiene, la del negocio (la del negocio nunca es «precio fijo»: no sabría de qué producto).
    if producto.transferencia_tipo:
        transferencia = precio_transferencia(precio, cantidad, producto.transferencia_tipo, producto.transferencia_valor)
    else:
        negocio = datos.transferencia_negocio
        transferencia = precio_transferencia(precio, cantidad, negocio.tipo, negocio.valor) if negocio.tipo != "precio" else None

    limite = limite_regateo(lista, cantidad, producto.regateo_tipo, producto.regateo_valor)
    piso_regateo = min(precio, lista - limite) if limite > 0 else precio
    costo = dinero(Decimal(producto.costo) * cantidad) if producto.costo is not None else None
    return LineaCotizada(
        tipo=LINEA_PRODUCTO,
        sku=producto.sku,
        nombre=producto.nombre,
        variante=linea.variante,
        cantidad=cantidad,
        precio_lista=lista,
        precio=precio,
        motivo=MOTIVO_ESCALA if escala is not None else "lista",
        precio_transferencia=transferencia,
        piso_regateo=max(piso_regateo, Decimal("0.01")),
        costo=costo,
        necesita_envio=not producto.envio_incluido,
        items=[ItemCotizado(producto.sku, producto.nombre, cantidad, linea.variante, dinero(producto.precio))],
    )


def _linea_oferta(linea: LineaPedido, datos: DatosCotizacion) -> LineaCotizada:
    oferta = datos.ofertas.get(linea.oferta_id or -1)
    if oferta is None:
        raise LineaInvalida(f"No hay datos de la oferta {linea.oferta_id}")
    veces = linea.cantidad
    precio = dinero(Decimal(oferta.precio) * veces)
    lista = CERO
    costos: List[Optional[Decimal]] = []
    items: List[ItemCotizado] = []
    for item in oferta.items:
        producto = datos.productos.get(item.sku)
        if producto is None:
            raise LineaInvalida(f"No hay datos del producto {item.sku} de la oferta {oferta.id}")
        unidades = item.cantidad * veces
        lista += dinero(Decimal(producto.precio) * unidades)
        costos.append(None if producto.costo is None else dinero(Decimal(producto.costo) * unidades))
        items.append(ItemCotizado(producto.sku, producto.nombre, unidades, item.variante or linea.variante, dinero(producto.precio), oferta.id))
    transferencia = precio_transferencia(precio, veces, oferta.transferencia_tipo, oferta.transferencia_valor)
    limite = limite_regateo(precio, veces, oferta.regateo_tipo, oferta.regateo_valor)
    costo = None if any(c is None for c in costos) else sum(costos, CERO)  # type: ignore[arg-type]
    return LineaCotizada(
        tipo=LINEA_OFERTA,
        oferta_id=oferta.id,
        nombre=oferta.nombre,
        cantidad=veces,
        precio_lista=max(lista, precio),
        precio=precio,
        motivo=MOTIVO_OFERTA if lista > precio else "lista",
        precio_transferencia=transferencia,
        piso_regateo=max(precio - limite, Decimal("0.01")),
        costo=costo,
        necesita_envio=not oferta.envio_incluido,
        items=items,
    )


def _envio_gratis(lineas: List[LineaCotizada], datos: DatosCotizacion, subtotal: Decimal) -> bool:
    """Envío gratis si alguno de los productos que cobran envío aparte cumple su regla (unidades de ese producto o subtotal)."""
    unidades_por_sku: Dict[str, int] = {}
    for linea in lineas:
        for item in linea.items:
            unidades_por_sku[item.sku] = unidades_por_sku.get(item.sku, 0) + item.cantidad
    for linea in lineas:
        if linea.tipo != LINEA_PRODUCTO or not linea.necesita_envio:
            continue
        producto = datos.productos[linea.sku or ""]
        if producto.envio_gratis_desde_unidades and unidades_por_sku.get(producto.sku, 0) >= producto.envio_gratis_desde_unidades:
            return True
        if producto.envio_gratis_desde_monto is not None and subtotal >= Decimal(producto.envio_gratis_desde_monto):
            return True
    return False


def cotizar(datos: DatosCotizacion) -> Cotizacion:
    if not datos.lineas:
        raise LineaInvalida("El pedido no tiene productos")
    lineas = [_linea_producto(l, datos) if l.tipo == LINEA_PRODUCTO else _linea_oferta(l, datos) for l in datos.lineas]

    subtotal_lista = sum((l.precio_lista for l in lineas), CERO)
    subtotal = sum((l.precio for l in lineas), CERO)

    piso = piso_del_pedido([l.costo for l in lineas], datos.ajustes)
    piso_regateo = sum((l.piso_regateo for l in lineas), CERO)
    minimo = max(piso_regateo, piso) if piso is not None else piso_regateo
    minimo_regateo: Optional[Decimal] = minimo if minimo < subtotal else None

    # Un regateo vale solo si el pedido no cambió desde que se acordó y sigue dentro de lo permitido.
    regateo = datos.regateo
    regateo_vigente = (
        regateo.acordado is not None
        and regateo.base == subtotal
        and minimo_regateo is not None
        and minimo_regateo <= regateo.acordado < subtotal
    )
    subtotal_contraentrega = regateo.acordado if regateo_vigente else subtotal  # type: ignore[assignment]

    # P2: regateo y transferencia no se suman; por transferencia se cobra el menor de los dos.
    regla_transferencia = sum(((l.precio_transferencia if l.precio_transferencia is not None else l.precio) for l in lineas), CERO)
    subtotal_transferencia = min(regla_transferencia, subtotal_contraentrega)

    necesita_envio = any(l.necesita_envio for l in lineas)
    envio_gratis = necesita_envio and _envio_gratis(lineas, datos, subtotal_contraentrega)
    if not necesita_envio or envio_gratis or datos.envio_opcion_costo is None:
        envio = CERO
    else:
        envio = dinero(datos.envio_opcion_costo)

    return Cotizacion(
        lineas=lineas,
        subtotal_lista=subtotal_lista,
        subtotal=subtotal,
        subtotal_contraentrega=subtotal_contraentrega,
        subtotal_transferencia=subtotal_transferencia,
        envio=envio,
        envio_gratis=envio_gratis,
        # Aunque el envío salga gratis, el cliente igual elige CÓMO recibe (envío o retiro, y la cobertura de su destino).
        envio_pendiente=necesita_envio and datos.envio_opcion_costo is None,
        total_contraentrega=subtotal_contraentrega + envio,
        total_transferencia=subtotal_transferencia + envio,
        metodo_pago=datos.metodo_pago,
        piso=piso,
        minimo_regateo=minimo_regateo,
        regateo_vigente=regateo_vigente,
    )
