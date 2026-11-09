from decimal import Decimal

from marshmallow import EXCLUDE, Schema, fields, validate


class AnuncioSchema(Schema):
    """Un anuncio visto (o vinculado de antemano), con su producto y su rendimiento en el periodo."""

    id_anuncio = fields.Str(data_key="idAnuncio")
    producto_sku = fields.Str(data_key="productoSku", allow_none=True)
    producto_nombre = fields.Str(data_key="productoNombre", allow_none=True)
    nombre_vinculo = fields.Str(data_key="nombreVinculo", allow_none=True)
    titulo = fields.Str(allow_none=True)
    texto = fields.Str(allow_none=True)
    url_anuncio = fields.Str(data_key="urlAnuncio", allow_none=True)
    tipo_origen = fields.Str(data_key="tipoOrigen", allow_none=True)
    tipo_media = fields.Str(data_key="tipoMedia", allow_none=True)
    imagen_url = fields.Str(data_key="imagenUrl", allow_none=True)
    miniatura_url = fields.Str(data_key="miniaturaUrl", allow_none=True)
    primera_llegada = fields.Str(data_key="primeraLlegada", allow_none=True)
    ultima_llegada = fields.Str(data_key="ultimaLlegada", allow_none=True)
    llegadas = fields.Int()
    conversaciones = fields.Int()
    ventas = fields.Int()
    ingresos = fields.Str()
    ganancia = fields.Str()
    ventas_sin_costo = fields.Int(data_key="ventasSinCosto")


class VentasPorOrigenSchema(Schema):
    conversaciones = fields.Int()
    ventas = fields.Int()
    ingresos = fields.Str()
    ganancia = fields.Str()


class ResumenSchema(Schema):
    anuncio = fields.Nested(VentasPorOrigenSchema)
    directo = fields.Nested(VentasPorOrigenSchema)
    llegadas = fields.Int()
    anuncios_activos = fields.Int(data_key="anunciosActivos")
    anuncios_sin_vincular = fields.Int(data_key="anunciosSinVincular")


class VincularInputSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    sku = fields.Str(required=True, validate=validate.Length(min=1, max=64))
    nombre = fields.Str(load_default=None, allow_none=True, validate=validate.Length(max=120))
    reasignar = fields.Bool(load_default=False)


class VinculoSchema(Schema):
    id_anuncio = fields.Str(data_key="idAnuncio")
    producto_sku = fields.Str(data_key="productoSku")
    producto_nombre = fields.Str(data_key="productoNombre")


anuncio_schema = AnuncioSchema()
resumen_schema = ResumenSchema()
vincular_input_schema = VincularInputSchema()
vinculo_schema = VinculoSchema()


def _dinero(valor) -> str:
    """Dinero siempre como texto con 2 decimales. Los importes vienen de la base como Decimal: se formatean sin pasar por float."""
    return format(Decimal(str(valor if valor is not None else 0)).quantize(Decimal("0.01")), "f")


def preparar_anuncio(fila: dict) -> dict:
    """Fechas a ISO y dinero a texto con 2 decimales (el dinero nunca viaja como número decimal impreciso)."""
    salida = dict(fila)
    for campo in ("primera_llegada", "ultima_llegada"):
        valor = salida.get(campo)
        salida[campo] = valor.isoformat() if valor else None
    for campo in ("ingresos", "ganancia"):
        salida[campo] = _dinero(salida.get(campo))
    return salida


def preparar_resumen(resumen: dict) -> dict:
    salida = dict(resumen)
    for origen in ("anuncio", "directo"):
        bloque = dict(salida[origen])
        bloque["ingresos"] = _dinero(bloque.get("ingresos"))
        bloque["ganancia"] = _dinero(bloque.get("ganancia"))
        salida[origen] = bloque
    return salida
