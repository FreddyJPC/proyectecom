"""
Conexión con Meta (ADR-016, docs/PLAN_META_ADS.md): estado de la configuración y el botón «Preparar Meta».

«Preparar Meta» le pide a Meta el dataset (el buzón donde se reciben las compras) de la cuenta de WhatsApp, con el token que vive en el
servidor, y guarda su número. Así nadie tiene que ver ni copiar el token. Repetirlo es seguro: según la documentación de Meta, si el dataset
ya existe devuelve el mismo. Esta ruta NUNCA devuelve el token ni lo escribe en un error.
"""
import logging

from flask import g, jsonify

from src.integrations.meta import MetaRechazoError, MetaRespuestaDudosaError
from src.integrations.meta import factory as meta_factory
from src.config.parametros import parametros

from . import meta_bp
from .repository import MetaRepository

logger = logging.getLogger(__name__)


def _cliente_para_dataset():
    """Separado para poder cambiarlo en las pruebas."""
    return meta_factory.get_cliente_para_dataset()


def _usuario():
    return (getattr(g, "usuario", None) or {}).get("email")


def _jsonable(fila: dict) -> dict:
    return {
        "id": fila["id"],
        "ventaId": fila["venta_id"],
        "estado": fila["estado"],
        "motivo": fila.get("motivo"),
        "valor": str(fila["valor"]),  # el dinero viaja siempre como texto
        "moneda": fila["moneda"],
        "intentos": fila["intentos"],
        "creadoEn": fila["creado_en"].isoformat() if fila.get("creado_en") else None,
        "enviadoEn": fila["enviado_en"].isoformat() if fila.get("enviado_en") else None,
    }


@meta_bp.get("/estado")
def estado():
    dataset = meta_factory.dataset_id()
    return (
        jsonify(
            tokenConfigurado=meta_factory.token_configurado(),
            cuentaWhatsappConfigurada=meta_factory.cuenta_whatsapp_configurada(),
            datasetId=dataset,
            listo=bool(meta_factory.token_configurado() and meta_factory.cuenta_whatsapp_configurada() and dataset),
            avisosActivos=bool(parametros.valor("meta.activo")),
            eventos=MetaRepository.resumen_eventos(),
            ultimosEventos=[_jsonable(f) for f in MetaRepository.ultimos_eventos()],
        ),
        200,
    )


@meta_bp.post("/preparar")
def preparar():
    cliente, ausentes = _cliente_para_dataset()
    if cliente is None:
        return jsonify(error="Falta configurar en el servidor: " + ", ".join(ausentes) + "."), 409
    try:
        dataset_id = cliente.obtener_o_crear_dataset()
    except MetaRechazoError as exc:
        logger.warning("Meta no entregó el dataset: %s", exc)
        return jsonify(error=str(exc)), 502
    except MetaRespuestaDudosaError as exc:
        logger.warning("Respuesta dudosa de Meta al pedir el dataset: %s", exc)
        return jsonify(error=f"{exc}. Puedes volver a intentarlo: pedir el dataset es seguro de repetir."), 502
    MetaRepository.guardar_dataset_id(dataset_id)
    logger.info("Dataset de Meta preparado por %s (id %s)", _usuario() or "desconocido", dataset_id)
    return jsonify(datasetId=dataset_id), 200


# ---------------------------------------------------------------------------
# Anuncios de Meta (ADR-017): cuenta publicitaria, tablero, leer ahora, pausar a mano y alertas.
# ---------------------------------------------------------------------------
from datetime import timedelta  # noqa: E402
from decimal import Decimal  # noqa: E402

from flask import request  # noqa: E402

from src.integrations.meta.marketing import normalizar_cuenta  # noqa: E402
from src.jobs.meta_anuncios import MetaAnunciosService  # noqa: E402
from src.jobs.meta_anuncios.repository import TableroRepository  # noqa: E402
from src.jobs.meta_anuncios.service import hoy_ecuador  # noqa: E402

_DIAS_TABLERO = (1, 7, 14, 30)


def _servicio_anuncios() -> MetaAnunciosService:
    """Separado para poder cambiarlo en las pruebas."""
    return MetaAnunciosService()


def _d(valor) -> Decimal:
    return Decimal(str(valor or 0)).quantize(Decimal("0.01"))


def _dinero(valor) -> str:
    return f"{_d(valor):.2f}"


def _division(a: Decimal, b) -> str:
    return f"{(a / Decimal(b)).quantize(Decimal('0.01')):.2f}" if b else None


@meta_bp.get("/cuenta")
def cuenta_publicitaria():
    return jsonify(cuentaPublicitaria=meta_factory.cuenta_publicitaria(), lecturaActiva=bool(parametros.valor("meta.anuncios_activo"))), 200


@meta_bp.put("/cuenta")
def guardar_cuenta_publicitaria():
    datos = request.get_json(force=True, silent=True) or {}
    texto = str(datos.get("cuentaPublicitaria") or "").strip()
    if texto and not normalizar_cuenta(texto):
        return jsonify(error="El número de la cuenta publicitaria solo lleva dígitos (puede empezar con act_)."), 422
    cuenta = normalizar_cuenta(texto) or None
    MetaRepository.guardar_cuenta_publicitaria(cuenta)
    logger.info("Cuenta publicitaria de Meta guardada por %s", _usuario())
    return jsonify(cuentaPublicitaria=cuenta), 200


@meta_bp.get("/anuncios")
def tablero_de_anuncios():
    try:
        dias = int(request.args.get("dias", 7))
    except ValueError:
        dias = 7
    if dias not in _DIAS_TABLERO:
        dias = 7
    desde = hoy_ecuador() - timedelta(days=dias - 1)
    filas = TableroRepository.anuncios(desde)
    anuncios, total = [], {"gasto": Decimal("0"), "ingreso": Decimal("0"), "ventas": 0, "conversaciones": 0, "ganancia": Decimal("0")}
    ganancia_completa = True
    for f in filas:
        gasto, ingreso, ventas = _d(f["gasto"]), _d(f["ingreso"]), int(f["ventas"])
        ganancia = None if f["ganancia"] is None else _d(f["ganancia"])
        total["gasto"] += gasto
        total["ingreso"] += ingreso
        total["ventas"] += ventas
        total["conversaciones"] += int(f["conversaciones_meta"])
        if ganancia is None:
            ganancia_completa = ganancia_completa and ventas == 0
        else:
            total["ganancia"] += ganancia
        anuncios.append(
            {
                "idAnuncio": f["id_anuncio"], "nombre": f["nombre"], "estado": f["estado"], "estadoEfectivo": f["estado_efectivo"],
                "campana": f["nombre_campana"], "conjunto": f["nombre_conjunto"],
                "presupuestoDiario": None if f["presupuesto_diario"] is None else _dinero(f["presupuesto_diario"]),
                "titulo": f["titulo"], "miniaturaUrl": f["miniatura_url"],
                "productoSku": f["producto_sku"], "productoNombre": f["producto_nombre"],
                "ofertaId": f["oferta_id"], "ofertaNombre": f["oferta_nombre"],
                "gasto": _dinero(gasto), "conversacionesMeta": int(f["conversaciones_meta"]), "conversaciones": int(f["conversaciones"]),
                "impresiones": int(f["impresiones"]), "clics": int(f["clics"]),
                "ventas": ventas, "entregadas": int(f["entregadas"]), "devueltas": int(f["devueltas"]),
                "ingreso": _dinero(ingreso), "descuentos": _dinero(f["descuentos"]),
                "costoPorConversacion": _division(gasto, f["conversaciones_meta"]),
                "costoPorVenta": _division(gasto, ventas),
                "gananciaNeta": None if ganancia is None else _dinero(ganancia - gasto),
                "roas": _division(ingreso, gasto) if gasto > 0 else None,
            }
        )
    ultima = TableroRepository.ultima_lectura()
    return (
        jsonify(
            dias=dias,
            lecturaActiva=bool(parametros.valor("meta.anuncios_activo")),
            ultimaLectura=ultima.isoformat() if ultima else None,
            totales={
                "gasto": _dinero(total["gasto"]), "ingreso": _dinero(total["ingreso"]), "ventas": total["ventas"],
                "conversacionesMeta": total["conversaciones"], "costoPorVenta": _division(total["gasto"], total["ventas"]),
                "gananciaNeta": _dinero(total["ganancia"] - total["gasto"]) if ganancia_completa else None,
            },
            anuncios=anuncios,
            alertas=[
                {"id": a["id"], "regla": a["regla"], "idAnuncio": a["id_anuncio"], "mensaje": a["mensaje"], "creadaEn": a["creada_en"].isoformat()}
                for a in TableroRepository.alertas()
            ],
            acciones=[
                {
                    "id": a["id"], "idAnuncio": a["id_anuncio"], "regla": a["regla"], "motivo": a["motivo"], "resultado": a["resultado"],
                    "detalle": a["detalle"], "creadaPor": a["creada_por"], "creadaEn": a["creada_en"].isoformat(),
                }
                for a in TableroRepository.acciones()
            ],
        ),
        200,
    )


@meta_bp.post("/anuncios/leer")
def leer_anuncios_ahora():
    """«Leer ahora»: corre una pasada del trabajo (respeta el interruptor «Leer mis anuncios de Meta»)."""
    if not parametros.valor("meta.anuncios_activo"):
        return jsonify(error="Enciende «Leer mis anuncios de Meta» en Parámetros para poder leerlos."), 409
    resultado = _servicio_anuncios().ejecutar()
    if resultado.get("estado") == "sin_configurar":
        return jsonify(error="Falta el permiso de anuncios en la app de Meta o la cuenta publicitaria."), 409
    if resultado.get("estado") == "error":
        return jsonify(error=resultado.get("motivo") or "No se pudieron leer los anuncios de Meta."), 502
    return jsonify(resultado), 200


@meta_bp.post("/anuncios/<id_anuncio>/pausar")
def pausar_anuncio(id_anuncio: str):
    if not id_anuncio.isdigit():
        return jsonify(error="ID de anuncio no válido."), 422
    resultado = _servicio_anuncios().pausar_manual(id_anuncio, _usuario())
    if resultado["resultado"] == "sin_configurar":
        return jsonify(error=resultado["mensaje"]), 409
    return jsonify(mensaje=resultado["mensaje"]), 200
