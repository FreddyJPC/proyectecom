"""
Forma JSON de la API de leads (camelCase). Las respuestas se arman con funciones `preparar_*` (fechas en ISO, dinero como texto
con dos decimales, nunca float) y lo que entra se valida con esquemas de Marshmallow.
"""
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from marshmallow import EXCLUDE, Schema, fields, validate

from .temperaturas import ETIQUETAS, MOTIVOS_DE_PERDIDA, TEMPERATURAS


def _iso(valor: Optional[datetime]) -> Optional[str]:
    return valor.isoformat() if valor else None


def _dinero(valor) -> Optional[str]:
    return None if valor is None else f"{Decimal(str(valor)):.2f}"


def _nombre(fila: Dict[str, Any]) -> Optional[str]:
    return fila.get("nombre_cliente") or fila.get("contacto_nombre") or fila.get("nombre_perfil")


def preparar_lead(f: Dict[str, Any]) -> Dict[str, Any]:
    ultimo = None
    if f.get("ultimo_contenido") is not None:
        ultimo = {"rol": f["ultimo_rol"], "contenido": f["ultimo_contenido"], "creadoEn": _iso(f["ultimo_en"])}
    return {
        "id": f["id"],
        "contactoId": f["contacto_id"],
        "conversacionId": f["conversacion_id"],
        "canal": f["canal"],
        "idExterno": f["id_externo"],
        "telefono": f.get("telefono"),
        "nombre": _nombre(f),
        "productoSku": f.get("producto_sku"),
        "productoNombre": f.get("producto_nombre"),
        "productoVariante": f.get("producto_variante"),
        "cantidad": f.get("cantidad"),
        "total": _dinero(f.get("total")),
        "etapa": f["etapa"],
        "temperatura": f["temperatura"],
        "temperaturaEtiqueta": ETIQUETAS.get(f["temperatura"], f["temperatura"]),
        "temperaturaMotivo": f.get("temperatura_motivo"),
        "temperaturaOrigen": f.get("temperatura_origen"),
        "temperaturaEn": _iso(f.get("temperatura_en")),
        "temperaturaFijadaHasta": _iso(f.get("temperatura_fijada_hasta")),
        "motivoPerdida": f.get("motivo_perdida"),
        "motivoPerdidaEtiqueta": MOTIVOS_DE_PERDIDA.get(f.get("motivo_perdida") or ""),
        "origen": f["origen"],
        "idAnuncio": f.get("id_anuncio"),
        "tituloAnuncio": f.get("titulo_anuncio"),
        "creadoEn": _iso(f["creado_en"]),
        "actualizadoEn": _iso(f["actualizado_en"]),
        "cerradoEn": _iso(f.get("cerrado_en")),
        "noContactar": bool(f.get("no_contactar")),
        "noContactarMotivo": f.get("no_contactar_motivo"),
        "estadoConversacion": f.get("estado_conversacion"),
        "ultimoMensaje": ultimo,
        "ultimoClienteEn": _iso(f.get("ultimo_cliente_en")),
        # El último mensaje de seguimiento automático que se le envió (empujón o plantilla), si hubo.
        "ultimoSeguimiento": (
            {"tipo": f["seguimiento_tipo"], "enviadoEn": _iso(f.get("seguimiento_en"))} if f.get("seguimiento_tipo") else None
        ),
    }


def preparar_lista(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "items": [preparar_lead(f) for f in r["items"]],
        "total": r["total"],
        "page": r["page"],
        "pageSize": r["page_size"],
    }


def preparar_resumen(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "calientes": r["calientes"],
        "tibios": r["tibios"],
        "frios": r["frios"],
        "valorEnJuego": _dinero(r["valor_en_juego"]),
        "nuevos": r["nuevos"],
        "ganados": r["ganados"],
        "perdidos": r["perdidos"],
        "ingresosGanados": _dinero(r["ingresos_ganados"]),
        "tasaDeCierre": None if r["tasa_de_cierre"] is None else str(r["tasa_de_cierre"]),
        "noContactar": r["no_contactar"],
        "motivosDePerdida": r["motivos_de_perdida"],
    }


def preparar_contacto(c: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if c is None:
        return None
    compras, anuncios = c["compras"], c["anuncios"]
    return {
        "id": c["id"],
        "nombre": c.get("nombre"),
        "telefono": c.get("telefono"),
        "tipo": c.get("tipo"),
        "noContactar": bool(c["no_contactar"]),
        "noContactarMotivo": c.get("no_contactar_motivo"),
        "noContactarEn": _iso(c.get("no_contactar_en")),
        "noContactarPor": c.get("no_contactar_por"),
        "creadoEn": _iso(c["creado_en"]),
        "conversaciones": [
            {"id": x["id"], "canal": x["canal"], "idExterno": x["id_externo"], "estado": x["estado"], "creadaEn": _iso(x["creada_en"])}
            for x in c["conversaciones"]
        ],
        "leads": [
            {
                "id": x["id"], "conversacionId": x["conversacion_id"], "productoNombre": x.get("producto_nombre"),
                "temperatura": x["temperatura"], "etapa": x["etapa"], "total": _dinero(x.get("total")),
                "origen": x["origen"], "creadoEn": _iso(x["creado_en"]), "cerradoEn": _iso(x.get("cerrado_en")),
            }
            for x in c["leads"]
        ],
        "compras": {
            "cantidad": int(compras["compras"] or 0),
            "totalGastado": _dinero(compras["total_gastado"]),
            "ganancia": _dinero(compras["ganancia"]),
            "comprasSinCosto": int(compras["compras_sin_costo"] or 0),
            "ultimaCompra": _iso(compras.get("ultima_compra")),
        },
        "anuncios": {
            "llegadas": int(anuncios["llegadas"] or 0),
            "primera": _iso(anuncios.get("primera")),
            "ultima": _iso(anuncios.get("ultima")),
            "primerAnuncio": (
                {"idAnuncio": c["primer_anuncio"]["id_anuncio"], "titulo": c["primer_anuncio"]["titulo"]}
                if c.get("primer_anuncio") else None
            ),
        },
    }


def preparar_detalle(d: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "lead": preparar_lead(d["lead"]),
        "historial": [
            {
                "id": h["id"], "de": h["de"], "a": h["a"], "origen": h["origen"], "motivo": h["motivo"],
                "usuario": h["usuario"], "creadoEn": _iso(h["creado_en"]),
            }
            for h in d["historial"]
        ],
        "contacto": preparar_contacto(d["contacto"]),
        "seguimientos": [
            {
                "id": x["id"], "tipo": x["tipo"], "estado": x["estado"], "contenido": x.get("contenido"),
                "plantilla": x.get("plantilla"), "error": x.get("error"), "creadoEn": _iso(x["creado_en"]),
                "enviadoEn": _iso(x.get("enviado_en")),
            }
            for x in d.get("seguimientos", [])
        ],
    }


class CambiarTemperaturaInputSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    temperatura = fields.Str(required=True, validate=validate.OneOf(TEMPERATURAS))
    motivo_perdida = fields.Str(data_key="motivoPerdida", allow_none=True, load_default=None, validate=validate.OneOf(tuple(MOTIVOS_DE_PERDIDA)))
    motivo = fields.Str(allow_none=True, load_default=None, validate=validate.Length(max=300))


class NoContactarInputSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    no_contactar = fields.Bool(data_key="noContactar", required=True)
    motivo = fields.Str(allow_none=True, load_default=None, validate=validate.Length(max=300))


cambiar_temperatura_input_schema = CambiarTemperaturaInputSchema()
no_contactar_input_schema = NoContactarInputSchema()
