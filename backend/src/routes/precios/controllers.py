"""
API de precios y ofertas (ADR-017): lo que el dueño configura desde el panel.

- GET/PUT /precios/productos/<sku>  -> «Precios y descuentos» de un producto (transferencia, regateo, escalas, envío gratis).
- GET/PUT /precios/negocio          -> precio por transferencia por defecto para todos los productos.
- GET/POST /precios/ofertas, GET/PUT /precios/ofertas/<id> -> combos y promociones.
- PUT /precios/ofertas/<id>/anuncios/<id_anuncio> -> vincula un anuncio a la oferta (Victoria la ofrece a quien llegue por él).

Dinero siempre como texto («25.00»). Un precio que deja la venta bajo el margen mínimo responde 409 con el motivo y solo se guarda
si se reenvía con `confirmarBajoMargen: true` (en una oferta: `bajoMargenAutorizado`).
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from flask import g, jsonify, request

from src.routes.ajustes.services import AjustesService
from src.routes.anuncios.servicio import validar_id_anuncio
from src.routes.anuncios.exceptions import AnuncioInvalidoError
from src.routes.ventas.origen import costo_unitario

from . import precios_bp
from .reglas import AjustesPiso, dinero, piso_del_pedido
from .repository import PreciosRepository, vigente
from .servicio import ahora_utc
from .validacion import validar_oferta, validar_reglas_producto

logger = logging.getLogger(__name__)


def _usuario() -> Optional[str]:
    return (getattr(g, "usuario", None) or {}).get("email")


def _texto(valor) -> Optional[str]:
    return None if valor is None else f"{dinero(valor):.2f}"


def _iso(valor) -> Optional[str]:
    return valor.isoformat() if isinstance(valor, datetime) else None


def _ajustes() -> Optional[AjustesPiso]:
    try:
        a = AjustesService().obtener_ajustes()
        return AjustesPiso(a.confirmado, a.margen_minimo_pct, a.envio_estimado, a.otros_costos_fijos, a.otros_costos_pct)
    except Exception:
        logger.exception("No se pudieron leer los Ajustes para el control de margen")
        return None


def _producto_completo(sku: str) -> Optional[Dict[str, Any]]:
    from src.routes.whatsapp.repository import ProductoBotRepository  # perezoso: evita ciclos al arrancar

    return ProductoBotRepository.obtener_por_sku(sku)


def _cuerpo() -> Dict[str, Any]:
    datos = request.get_json(force=True, silent=True)
    return datos if isinstance(datos, dict) else {}


# ------------------------------------------------------------------ producto
def _reglas_dto(producto: Dict[str, Any], escalas, ajustes: Optional[AjustesPiso]) -> Dict[str, Any]:
    costo = costo_unitario(producto)
    return {
        "sku": producto["sku"],
        "nombre": producto["nombre"],
        "precio": _texto(producto["precio"]),
        "costo": _texto(costo),
        "precioMinimo": _texto(piso_del_pedido([costo], ajustes)),
        "margenConfirmado": bool(ajustes and ajustes.confirmado),
        "envioIncluido": bool(producto.get("envio_incluido", True)),
        "maxUnidades": int(producto.get("max_unidades_por_pedido") or 1),
        "transferenciaTipo": producto.get("transferencia_tipo"),
        "transferenciaValor": _texto(producto.get("transferencia_valor")),
        "regateoTipo": producto.get("regateo_tipo"),
        "regateoValor": _texto(producto.get("regateo_valor")),
        "envioGratisDesdeUnidades": producto.get("envio_gratis_desde_unidades"),
        "envioGratisDesdeMonto": _texto(producto.get("envio_gratis_desde_monto")),
        "escalas": [{"cantidad": e["cantidad"], "precioTotal": _texto(e["precio_total"])} for e in escalas],
    }


@precios_bp.get("/productos/<sku>")
def reglas_de_producto(sku: str):
    producto = _producto_completo(sku)
    if producto is None:
        return jsonify(error="Ese producto no existe."), 404
    escalas = PreciosRepository.escalas_de([sku]).get(sku, [])
    return jsonify(_reglas_dto(producto, escalas, _ajustes())), 200


@precios_bp.put("/productos/<sku>")
def guardar_reglas_de_producto(sku: str):
    producto = _producto_completo(sku)
    if producto is None:
        return jsonify(error="Ese producto no existe."), 404
    entrada = _cuerpo()
    ajustes = _ajustes()
    resultado = validar_reglas_producto(entrada, producto, costo_unitario(producto), ajustes)
    if not resultado.valido:
        return jsonify(error="Revisa los datos marcados.", errores=resultado.errores), 422
    if resultado.bajo_margen and not entrada.get("confirmarBajoMargen"):
        return jsonify(error="Algún precio queda bajo tu margen mínimo.", bajoMargen=resultado.bajo_margen), 409
    PreciosRepository.guardar_reglas_de_producto(sku, resultado.datos, resultado.escalas)
    logger.info("Reglas de precio de %s guardadas por %s", sku, _usuario())
    producto = _producto_completo(sku)
    return jsonify(_reglas_dto(producto, PreciosRepository.escalas_de([sku]).get(sku, []), ajustes)), 200


# ------------------------------------------------------------------ negocio
@precios_bp.get("/negocio")
def transferencia_del_negocio():
    datos = PreciosRepository.transferencia_negocio()
    return jsonify(transferenciaTipo=datos.get("tipo"), transferenciaValor=_texto(datos.get("valor"))), 200


@precios_bp.put("/negocio")
def guardar_transferencia_del_negocio():
    entrada = _cuerpo()
    tipo = (entrada.get("transferenciaTipo") or None)
    if tipo is None:
        PreciosRepository.guardar_transferencia_negocio(None, None)
        return jsonify(transferenciaTipo=None, transferenciaValor=None), 200
    if tipo not in ("porcentaje", "monto"):
        return jsonify(error="Elige porcentaje o monto.", errores={"transferenciaTipo": ["Tipo no válido."]}), 422
    try:
        valor = dinero(Decimal(str(entrada.get("transferenciaValor")).replace(",", ".")))
    except Exception:
        return jsonify(error="Escribe un número.", errores={"transferenciaValor": ["Escribe un número."]}), 422
    if valor <= 0 or (tipo == "porcentaje" and valor >= 100):
        return jsonify(error="Valor fuera de rango.", errores={"transferenciaValor": ["Debe ser mayor que 0 (y menor que 100 si es %)."]}), 422
    PreciosRepository.guardar_transferencia_negocio(tipo, valor)
    logger.info("Precio por transferencia del negocio guardado por %s", _usuario())
    return jsonify(transferenciaTipo=tipo, transferenciaValor=_texto(valor)), 200


# ------------------------------------------------------------------ ofertas
def _oferta_dto(oferta: Dict[str, Any], ventas: Dict[int, Dict[str, Any]], anuncios: Dict[int, list], ajustes) -> Dict[str, Any]:
    items = oferta.get("items") or []
    lista = sum((dinero(i["precio"]) * int(i["cantidad"]) for i in items), Decimal("0"))
    resumen = ventas.get(oferta["id"], {})
    ahora = ahora_utc()
    if oferta["estado"] != "activa":
        situacion = oferta["estado"]
    elif oferta.get("hasta") and ahora >= oferta["hasta"]:
        situacion = "vencida"
    elif oferta.get("desde") and ahora < oferta["desde"]:
        situacion = "programada"
    elif oferta.get("cupo") is not None and int(resumen.get("ventas", 0)) >= int(oferta["cupo"]):
        situacion = "sin_cupo"
    else:
        situacion = "vigente"
    return {
        "id": oferta["id"],
        "nombre": oferta["nombre"],
        "descripcion": oferta.get("descripcion"),
        "textoAnuncio": oferta.get("texto_anuncio"),
        "precio": _texto(oferta["precio"]),
        "precioLista": _texto(lista),
        "ahorro": _texto(max(lista - dinero(oferta["precio"]), Decimal("0"))),
        "envioIncluido": oferta.get("envio_incluido", True),
        "desde": _iso(oferta.get("desde")),
        "hasta": _iso(oferta.get("hasta")),
        "cupo": oferta.get("cupo"),
        "maximoPorCliente": oferta.get("maximo_por_cliente"),
        "visibilidad": oferta["visibilidad"],
        "regateoTipo": oferta.get("regateo_tipo"),
        "regateoValor": _texto(oferta.get("regateo_valor")),
        "transferenciaTipo": oferta.get("transferencia_tipo"),
        "transferenciaValor": _texto(oferta.get("transferencia_valor")),
        "bajoMargenAutorizado": oferta.get("bajo_margen_autorizado", False),
        "estado": oferta["estado"],
        "situacion": situacion,
        "vigente": situacion == "vigente" and vigente(oferta, ahora),
        "items": [
            {
                "productoSku": i["producto_sku"],
                "productoNombre": i.get("producto_nombre"),
                "cantidad": i["cantidad"],
                "variante": i.get("variante"),
                "precio": _texto(i["precio"]),
                "productoActivo": bool(i.get("activo", True)),
            }
            for i in items
        ],
        "anuncios": anuncios.get(oferta["id"], []),
        "ventas": int(resumen.get("ventas", 0)),
        "ingreso": _texto(resumen.get("ingreso", 0)),
        "creadaEn": _iso(oferta.get("creada_en")),
    }


def _contexto_ofertas(ofertas):
    ids = [o["id"] for o in ofertas]
    return PreciosRepository.resumen_ventas_ofertas(), PreciosRepository.anuncios_de_ofertas(ids)


@precios_bp.get("/ofertas")
def listar_ofertas():
    archivadas = request.args.get("archivadas") in ("1", "true")
    ofertas = PreciosRepository.ofertas(incluir_archivadas=archivadas)
    ventas, anuncios = _contexto_ofertas(ofertas)
    ajustes = _ajustes()
    return jsonify(ofertas=[_oferta_dto(o, ventas, anuncios, ajustes) for o in ofertas]), 200


@precios_bp.get("/ofertas/<int:oferta_id>")
def ver_oferta(oferta_id: int):
    oferta = PreciosRepository.oferta(oferta_id)
    if oferta is None:
        return jsonify(error="Esa oferta no existe."), 404
    ventas, anuncios = _contexto_ofertas([oferta])
    return jsonify(_oferta_dto(oferta, ventas, anuncios, _ajustes())), 200


def _validar(entrada: Dict[str, Any], es_nueva: bool, actual: Optional[Dict[str, Any]] = None):
    skus = {str((i or {}).get("productoSku") or "").strip() for i in (entrada.get("items") or []) if isinstance(i, dict)}
    if actual is not None and "items" not in entrada:
        skus |= {i["producto_sku"] for i in actual.get("items") or []}
    productos = {s: p for s in skus if s and (p := _producto_completo(s)) is not None}
    costos = {s: costo_unitario(p) for s, p in productos.items()}
    if actual is not None and "precio" not in entrada:
        entrada = {**entrada, "precio": actual["precio"]}
    if actual is not None and "items" not in entrada:
        entrada = {
            **entrada,
            "items": [{"productoSku": i["producto_sku"], "cantidad": i["cantidad"], "variante": i.get("variante")} for i in actual["items"]],
        }
    if actual is not None and "bajoMargenAutorizado" not in entrada:
        entrada = {**entrada, "bajoMargenAutorizado": actual.get("bajo_margen_autorizado", False)}
    return validar_oferta(entrada, productos, costos, _ajustes(), es_nueva)


@precios_bp.post("/ofertas")
def crear_oferta():
    entrada = _cuerpo()
    resultado = _validar(entrada, es_nueva=True)
    if not resultado.valido:
        return jsonify(error="Revisa los datos marcados.", errores=resultado.errores), 422
    if resultado.bajo_margen:
        return jsonify(error="El precio queda bajo tu margen mínimo.", bajoMargen=resultado.bajo_margen), 409
    oferta_id = PreciosRepository.crear_oferta(resultado.datos, resultado.items, _usuario())
    logger.info("Oferta %s creada por %s", oferta_id, _usuario())
    return ver_oferta(oferta_id)[0], 201


@precios_bp.put("/ofertas/<int:oferta_id>")
def actualizar_oferta(oferta_id: int):
    actual = PreciosRepository.oferta(oferta_id)
    if actual is None:
        return jsonify(error="Esa oferta no existe."), 404
    entrada = _cuerpo()
    resultado = _validar(entrada, es_nueva=False, actual=actual)
    if not resultado.valido:
        return jsonify(error="Revisa los datos marcados.", errores=resultado.errores), 422
    if resultado.bajo_margen:
        return jsonify(error="El precio queda bajo tu margen mínimo.", bajoMargen=resultado.bajo_margen), 409
    datos = {k: v for k, v in resultado.datos.items()}
    PreciosRepository.actualizar_oferta(oferta_id, datos, resultado.items if "items" in entrada else None)
    logger.info("Oferta %s actualizada por %s", oferta_id, _usuario())
    return ver_oferta(oferta_id)


@precios_bp.put("/ofertas/<int:oferta_id>/anuncios/<id_anuncio>")
def vincular_anuncio_a_oferta(oferta_id: int, id_anuncio: str):
    try:
        id_anuncio = validar_id_anuncio(id_anuncio)
    except AnuncioInvalidoError as exc:
        return jsonify(error=str(exc)), 422
    oferta = PreciosRepository.oferta(oferta_id)
    if oferta is None:
        return jsonify(error="Esa oferta no existe."), 404
    actual = PreciosRepository.vinculo_de_anuncio(id_anuncio)
    entrada = _cuerpo()
    if actual is not None and actual.get("oferta_id") != oferta_id and not entrada.get("reasignar"):
        return jsonify(error="Ese anuncio ya está vinculado a otro producto u oferta.", vinculadoA=actual.get("producto_sku") or actual.get("oferta_id")), 409
    nombre = (str(entrada.get("nombre") or "").strip()[:120]) or None
    PreciosRepository.vincular_anuncio_a_oferta(id_anuncio, oferta_id, nombre)
    logger.info("Anuncio %s vinculado a la oferta %s por %s", id_anuncio, oferta_id, _usuario())
    return jsonify(idAnuncio=id_anuncio, ofertaId=oferta_id, ofertaNombre=oferta["nombre"]), 200
