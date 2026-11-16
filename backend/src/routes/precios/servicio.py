"""
El cotizador (ADR-017): lee el pedido del lead y las reglas de la base, llama al motor puro (`cotizacion.cotizar`) y prepara lo
que se guarda en el lead. Victoria y el resto del sistema piden precios SOLO por aquí.

Si leer una regla falla (base caída), se cotiza sin esa regla, es decir, al precio de lista: nunca se inventa un descuento y nunca
se cobra menos de lo normal por un error. Queda en el log.
"""
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.routes.ventas.origen import costo_unitario

from .cotizacion import (
    LINEA_OFERTA,
    LINEA_PRODUCTO,
    Cotizacion,
    DatosCotizacion,
    ItemOferta,
    LineaInvalida,
    LineaPedido,
    OfertaPrecio,
    ProductoPrecio,
    Regateo,
    TransferenciaNegocio,
    cotizar,
)
from .reglas import AjustesPiso, Escala, dinero, dinero_opcional
from .repository import PreciosRepository, vigente

logger = logging.getLogger(__name__)

_SIN_CAMBIO = object()


def producto_precio(producto: Dict[str, Any], escalas: Optional[List[Dict[str, Any]]] = None) -> ProductoPrecio:
    """Fila de `productos_bot` (como la lee el repositorio de Victoria) -> lo que el motor necesita."""
    return ProductoPrecio(
        sku=producto["sku"],
        nombre=producto.get("nombre") or producto["sku"],
        precio=dinero(producto["precio"]),
        costo=costo_unitario(producto),
        envio_incluido=bool(producto.get("envio_incluido", True)),
        transferencia_tipo=producto.get("transferencia_tipo") or None,
        transferencia_valor=dinero_opcional(producto.get("transferencia_valor")),
        regateo_tipo=producto.get("regateo_tipo") or None,
        regateo_valor=dinero_opcional(producto.get("regateo_valor")),
        envio_gratis_desde_unidades=producto.get("envio_gratis_desde_unidades") or None,
        envio_gratis_desde_monto=dinero_opcional(producto.get("envio_gratis_desde_monto")),
        escalas=tuple(Escala(int(e["cantidad"]), dinero(e["precio_total"])) for e in (escalas or [])),
    )


def oferta_precio(oferta: Dict[str, Any]) -> OfertaPrecio:
    return OfertaPrecio(
        id=int(oferta["id"]),
        nombre=oferta["nombre"],
        precio=dinero(oferta["precio"]),
        items=tuple(ItemOferta(i["producto_sku"], int(i.get("cantidad") or 1), i.get("variante") or None) for i in oferta.get("items") or []),
        envio_incluido=bool(oferta.get("envio_incluido", True)),
        regateo_tipo=oferta.get("regateo_tipo") or None,
        regateo_valor=dinero_opcional(oferta.get("regateo_valor")),
        transferencia_tipo=oferta.get("transferencia_tipo") or None,
        transferencia_valor=dinero_opcional(oferta.get("transferencia_valor")),
    )


def lineas_del_lead(lead: Dict[str, Any]) -> List[LineaPedido]:
    """Las líneas del pedido. Un lead de antes (o de un solo producto) no tiene `lineas`: su producto y cantidad son la línea."""
    guardadas = lead.get("lineas")
    if isinstance(guardadas, list) and guardadas:
        return [LineaPedido.desde_json(l) for l in guardadas]
    if lead.get("producto_sku"):
        return [
            LineaPedido(
                tipo=LINEA_PRODUCTO, sku=lead["producto_sku"], cantidad=int(lead.get("cantidad") or 1),
                variante=lead.get("producto_variante") or None,
            )
        ]
    return []


def ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


class CotizadorServicio:
    def __init__(self, productos=None, precios: Optional[PreciosRepository] = None, entregas=None, ajustes=None):
        self._productos = productos
        self._precios = precios or PreciosRepository()
        self._entregas = entregas
        self._ajustes = ajustes

    # Perezosos: así los tests y la simulación pueden pasar los suyos sin armar los reales.
    def _repo_productos(self):
        if self._productos is None:
            from src.routes.whatsapp.repository import ProductoBotRepository

            self._productos = ProductoBotRepository()
        return self._productos

    def _repo_entregas(self):
        if self._entregas is None:
            from src.routes.entregas.repository import EntregaRepository

            self._entregas = EntregaRepository()
        return self._entregas

    def _ajustes_piso(self) -> Optional[AjustesPiso]:
        try:
            if self._ajustes is None:
                from src.routes.ajustes.services import AjustesService

                self._ajustes = AjustesService()
            a = self._ajustes.obtener_ajustes()
            return AjustesPiso(a.confirmado, a.margen_minimo_pct, a.envio_estimado, a.otros_costos_fijos, a.otros_costos_pct)
        except Exception:
            logger.exception("No se pudieron leer los Ajustes: el regateo queda limitado solo por el límite del producto")
            return None

    def _transferencia_negocio(self) -> TransferenciaNegocio:
        try:
            datos = self._precios.transferencia_negocio()
            return TransferenciaNegocio(datos.get("tipo") or None, dinero_opcional(datos.get("valor")))
        except Exception:
            logger.exception("No se pudo leer el precio por transferencia del negocio: se cotiza sin él")
            return TransferenciaNegocio()

    def _escalas(self, skus) -> Dict[str, List[Dict[str, Any]]]:
        try:
            return self._precios.escalas_de(skus)
        except Exception:
            logger.exception("No se pudieron leer las escalas de precio: se cotiza al precio de lista")
            return {}

    def ofertas_de(self, ids) -> Dict[int, Dict[str, Any]]:
        ids = {int(i) for i in ids if i is not None}
        if not ids:
            return {}
        return {int(o["id"]): o for o in self._precios.ofertas(ids, incluir_archivadas=True)}

    def escalas_de_producto(self, sku: str) -> List[Escala]:
        return [Escala(int(e["cantidad"]), dinero(e["precio_total"])) for e in self._escalas([sku]).get(sku, [])]

    def vinculo_de_anuncio(self, id_anuncio: str) -> Optional[Dict[str, Any]]:
        return self._precios.vinculo_de_anuncio(id_anuncio)

    def ofertas_publicas(self, ahora: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Ofertas que Victoria puede ofrecer a cualquier cliente, vigentes ahora."""
        ahora = ahora or ahora_utc()
        return [o for o in self._precios.ofertas_publicas() if vigente(o, ahora)]

    def producto(self, sku: str) -> Optional[Dict[str, Any]]:
        return self._repo_productos().obtener_por_sku(sku)

    def datos(
        self,
        lead: Dict[str, Any],
        lineas: Optional[List[LineaPedido]] = None,
        metodo_pago: Any = _SIN_CAMBIO,
        regateo: Optional[Regateo] = None,
        envio_costo: Any = _SIN_CAMBIO,
        productos: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> DatosCotizacion:
        lineas = list(lineas) if lineas is not None else lineas_del_lead(lead)
        ofertas = self.ofertas_de(l.oferta_id for l in lineas if l.tipo == LINEA_OFERTA)
        skus = {l.sku for l in lineas if l.tipo == LINEA_PRODUCTO}
        for oferta in ofertas.values():
            skus.update(i["producto_sku"] for i in oferta.get("items") or [])
        filas = dict(productos or {})
        for sku in skus:
            if sku not in filas:
                fila = self.producto(sku)
                if fila is not None:
                    filas[sku] = fila
        escalas = self._escalas(filas.keys())
        if envio_costo is _SIN_CAMBIO:
            envio_costo = None
            if lead.get("entrega_opcion_id") is not None:
                opcion = self._repo_entregas().obtener(lead["entrega_opcion_id"])
                envio_costo = dinero(opcion["costo_cliente"]) if opcion else dinero(lead.get("costo_envio") or 0)
        return DatosCotizacion(
            lineas=lineas,
            productos={sku: producto_precio(fila, escalas.get(sku)) for sku, fila in filas.items()},
            ofertas={i: oferta_precio(o) for i, o in ofertas.items()},
            transferencia_negocio=self._transferencia_negocio(),
            ajustes=self._ajustes_piso(),
            envio_opcion_costo=envio_costo,
            regateo=regateo if regateo is not None else Regateo.desde_json(lead.get("regateo")),
            metodo_pago=lead.get("metodo_pago") if metodo_pago is _SIN_CAMBIO else metodo_pago,
        )

    def cotizar(self, lead: Dict[str, Any], **cambios) -> Cotizacion:
        return cotizar(self.datos(lead, **cambios))

    @staticmethod
    def campos(cot: Cotizacion, lineas: List[LineaPedido], regateo: Optional[Regateo] = None) -> Dict[str, Any]:
        """Lo que se guarda en el lead. En un pedido de varias líneas también el resumen (producto principal, unidades)."""
        varias = len(lineas) > 1 or any(l.tipo == LINEA_OFERTA for l in lineas)
        campos: Dict[str, Any] = {
            "lineas": [l.a_json() for l in lineas] if varias else None,
            "cotizacion": cot.a_json(),
            "subtotal": cot.subtotal_a_pagar,
            "total": cot.total,
            "total_transferencia": cot.total_transferencia if cot.hay_precio_por_transferencia else None,
            "costo_envio": cot.envio,
        }
        if regateo is not None:
            campos["regateo"] = regateo.a_json() if (regateo.acordado or regateo.rondas or regateo.contraoferta) else None
        if varias:
            primera = cot.lineas[0]
            campos.update(
                producto_sku=primera.items[0].sku if primera.items else primera.sku,
                producto_nombre=resumen_de_lineas(cot),
                producto_variante=None,
                cantidad=cot.unidades,
            )
        return campos

    def vigencia_de_ofertas(self, cot: Cotizacion, contacto_id: Optional[int], ahora: Optional[datetime] = None) -> Optional[str]:
        """None si todas las ofertas del pedido siguen vendibles; si no, el motivo (vencida, pausada, sin cupo, máximo por cliente)."""
        ids = [l.oferta_id for l in cot.lineas if l.tipo == LINEA_OFERTA]
        if not ids:
            return None
        ahora = ahora or ahora_utc()
        ofertas = self.ofertas_de(ids)
        for linea in cot.lineas:
            if linea.tipo != LINEA_OFERTA:
                continue
            oferta = ofertas.get(linea.oferta_id)
            if oferta is None or not vigente(oferta, ahora):
                return f"La oferta «{linea.nombre}» ya no está disponible (terminó o se pausó)."
            if linea.cantidad > int(oferta.get("maximo_por_cliente") or 1):
                return f"La oferta «{linea.nombre}» se puede llevar como máximo {oferta.get('maximo_por_cliente')} vez/veces por cliente."
            if oferta.get("cupo") is not None and self._precios.ventas_de_oferta(oferta["id"]) >= int(oferta["cupo"]):
                return f"La oferta «{linea.nombre}» ya agotó su cupo."
            if contacto_id is not None and int(oferta.get("maximo_por_cliente") or 1) <= self._precios.ventas_de_oferta(
                oferta["id"], contacto_id
            ):
                return f"Este cliente ya compró la oferta «{linea.nombre}» las veces permitidas."
        return None


def resumen_de_lineas(cot: Cotizacion) -> str:
    partes = [f"{l.cantidad} x {l.nombre}" + (f" ({l.variante})" if l.variante else "") for l in cot.lineas]
    return " + ".join(partes)[:300]


def describir_cotizacion(cot: Cotizacion) -> str:
    """El desglose en palabras para Victoria (sin el mínimo de regateo: ese no se le muestra)."""
    filas = []
    for linea in cot.lineas:
        texto = f"- {linea.cantidad} x {linea.nombre}" + (f" ({linea.variante})" if linea.variante else "") + f": ${linea.precio:.2f}"
        if linea.precio < linea.precio_lista:
            texto += f" (antes ${linea.precio_lista:.2f})"
        if linea.tipo == LINEA_OFERTA:
            texto += " — incluye " + ", ".join(f"{i.cantidad} x {i.nombre}" for i in linea.items)
        filas.append(texto)
    if cot.regateo_vigente:
        filas.append(f"- Precio acordado con el cliente: ${cot.subtotal_contraentrega:.2f}")
    if cot.envio_gratis:
        filas.append("- Envío: GRATIS")
    elif cot.envio > 0:
        filas.append(f"- Envío: ${cot.envio:.2f}")
    elif cot.envio_pendiente:
        filas.append("- Envío: falta elegir la entrega (usa registrar_entrega)")
    filas.append(f"- TOTAL contra entrega: ${cot.total_contraentrega:.2f}")
    if cot.hay_precio_por_transferencia:
        filas.append(f"- TOTAL si paga por transferencia: ${cot.total_transferencia:.2f}")
    return "\n".join(filas)


__all__ = [
    "CotizadorServicio",
    "LineaInvalida",
    "describir_cotizacion",
    "lineas_del_lead",
    "producto_precio",
    "oferta_precio",
    "resumen_de_lineas",
]
