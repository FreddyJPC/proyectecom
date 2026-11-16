"""
Reglas de alerta de anuncios (ADR-017, plan v2.0 §6.4). PURAS: reciben lo ya leído y devuelven las alertas. Las decide el CÓDIGO
con los umbrales del dueño; la IA no interviene. Solo R1 y R2 pueden pedir pausar (son HECHOS: no hay qué vender); las de gasto
solo avisan (pausar por rendimiento podría apagar un anuncio que sí vende).
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional

ACTIVO = "ACTIVE"
ESTADOS_CON_PROBLEMA = {"DISAPPROVED", "WITH_ISSUES", "PENDING_BILLING_INFO"}


@dataclass(frozen=True)
class Alerta:
    regla: str
    objeto: str
    mensaje: str
    id_anuncio: Optional[str] = None
    pausar: bool = False


@dataclass(frozen=True)
class Umbrales:
    stock_bajo: int = 5
    gasto_sin_venta: Decimal = Decimal("0")  # 0 = apagada
    costo_conversacion: Decimal = Decimal("0")  # en dólares; 0 = apagada
    minimo_conversaciones: int = 10


def _nombre(anuncio: Dict[str, Any]) -> str:
    return f"«{anuncio.get('nombre') or anuncio['id_anuncio']}»"


def evaluar(
    anuncios: List[Dict[str, Any]],
    productos: Dict[str, Dict[str, Any]],
    ofertas: Dict[int, Dict[str, Any]],
    metricas: Dict[str, Dict[str, Any]],
    ventas: Dict[str, Dict[str, Any]],
    umbrales: Umbrales,
) -> List[Alerta]:
    """`anuncios`: copia de Meta con su vínculo (producto_sku u oferta_id). `ofertas`: con `vendible` (bool) y `motivo` y `skus`.
    `metricas`: por anuncio, gasto y conversaciones del periodo. `ventas`: por anuncio, ventas y ganancia (None si falta un costo)."""
    alertas: List[Alerta] = []
    for anuncio in anuncios:
        id_anuncio = anuncio["id_anuncio"]
        nombre = _nombre(anuncio)
        estado = anuncio.get("estado_efectivo")

        if estado in ESTADOS_CON_PROBLEMA:
            alertas.append(Alerta("R8", id_anuncio, f"Meta marcó el anuncio {nombre} como {estado}: revísalo en el Administrador de anuncios.", id_anuncio))
        if estado != ACTIVO:
            continue

        sku, oferta_id = anuncio.get("producto_sku"), anuncio.get("oferta_id")
        if not sku and not oferta_id:
            alertas.append(Alerta("R7", id_anuncio, f"El anuncio {nombre} está activo pero no tiene producto ni oferta vinculada: Victoria no sabrá qué vender.", id_anuncio))
        skus = [sku] if sku else list((ofertas.get(oferta_id) or {}).get("skus") or [])

        sin_producto = [s for s in skus if not (productos.get(s) or {}).get("activo", False)]
        if sin_producto:
            nombres = ", ".join((productos.get(s) or {}).get("nombre") or s for s in sin_producto)
            alertas.append(
                Alerta("R1", id_anuncio, f"El anuncio {nombre} sigue activo pero {nombres} está agotado o pausado: estás pagando clics de algo que no se vende.", id_anuncio, pausar=True)
            )
        if oferta_id:
            oferta = ofertas.get(oferta_id)
            if oferta is not None and not oferta.get("vendible", False):
                alertas.append(
                    Alerta("R2", id_anuncio, f"El anuncio {nombre} promociona «{oferta.get('nombre')}», que {oferta.get('motivo') or 'ya no está disponible'}.", id_anuncio, pausar=True)
                )
        for s in skus:
            fila = productos.get(s) or {}
            stock = fila.get("stock_ultimo")
            if fila.get("activo") and stock is not None and 0 < int(stock) <= umbrales.stock_bajo:
                alertas.append(Alerta("R3", f"{id_anuncio}:{s}", f"Quedan {stock} unidades de {fila.get('nombre') or s} y el anuncio {nombre} sigue activo.", id_anuncio))

        datos = metricas.get(id_anuncio) or {}
        gasto = Decimal(str(datos.get("gasto") or 0))
        conversaciones = int(datos.get("conversaciones") or 0)
        vendido = ventas.get(id_anuncio) or {}
        n_ventas = int(vendido.get("ventas") or 0)
        if umbrales.gasto_sin_venta > 0 and n_ventas == 0 and gasto >= umbrales.gasto_sin_venta:
            alertas.append(Alerta("R4", id_anuncio, f"El anuncio {nombre} gastó ${gasto:.2f} y no trajo ninguna venta.", id_anuncio))
        if umbrales.costo_conversacion > 0 and conversaciones >= umbrales.minimo_conversaciones:
            costo = (gasto / conversaciones).quantize(Decimal("0.01"))
            if costo > umbrales.costo_conversacion:
                alertas.append(
                    Alerta("R5", id_anuncio, f"Cada conversación del anuncio {nombre} cuesta ${costo:.2f} (tu límite: ${umbrales.costo_conversacion:.2f}).", id_anuncio)
                )
        ganancia = vendido.get("ganancia")
        if n_ventas > 0 and ganancia is not None and gasto > 0:
            costo_venta = (gasto / n_ventas).quantize(Decimal("0.01"))
            ganancia_venta = (Decimal(str(ganancia)) / n_ventas).quantize(Decimal("0.01"))
            if costo_venta > ganancia_venta:
                alertas.append(
                    Alerta("R6", id_anuncio, f"El anuncio {nombre} cuesta ${costo_venta:.2f} por venta y cada venta deja ${ganancia_venta:.2f}: está perdiendo plata.", id_anuncio)
                )
    return alertas


def alerta_de_regateo(por_producto: List[Dict[str, Any]], porcentaje: int, minimo_ventas: int = 5) -> List[Alerta]:
    """R9: productos cuyo porcentaje de ventas con rebaja por regateo llega al umbral. `por_producto`: sku, nombre, ventas, con_regateo."""
    if porcentaje <= 0:
        return []
    salida = []
    for fila in por_producto:
        ventas, con = int(fila.get("ventas") or 0), int(fila.get("con_regateo") or 0)
        if ventas >= minimo_ventas and con * 100 >= porcentaje * ventas:
            salida.append(
                Alerta("R9", fila["sku"], f"{con} de {ventas} ventas de {fila.get('nombre') or fila['sku']} se cerraron con rebaja por regateo: revisa el precio o el límite.")
            )
    return salida
