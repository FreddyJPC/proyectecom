from marshmallow import EXCLUDE, Schema, fields, validate


class VentaSchema(Schema):
    """Lo que la pantalla necesita saber de una venta tras cobrarla o cancelarla."""

    id = fields.Int()
    estado = fields.Str()
    total = fields.Str(allow_none=True)
    cobrada = fields.Bool()
    cobrada_en = fields.Str(data_key="cobradaEn", allow_none=True)
    cobrada_por = fields.Str(data_key="cobradaPor", allow_none=True)
    nota_cobro = fields.Str(data_key="notaCobro", allow_none=True)
    cancelada_en = fields.Str(data_key="canceladaEn", allow_none=True)
    cancelada_por = fields.Str(data_key="canceladaPor", allow_none=True)
    motivo_cancelacion = fields.Str(data_key="motivoCancelacion", allow_none=True)
    stock_devuelto = fields.Int(data_key="stockDevuelto")
    producto_sigue_agotado = fields.Bool(data_key="productoSigueAgotado")
    puede_cobrar = fields.Bool(data_key="puedeCobrar")
    puede_deshacer_cobro = fields.Bool(data_key="puedeDeshacerCobro")
    puede_cancelar = fields.Bool(data_key="puedeCancelar")


class CobrarInputSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    nota = fields.Str(load_default=None, allow_none=True, validate=validate.Length(max=500))


class CancelarInputSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    motivo = fields.Str(load_default=None, allow_none=True, validate=validate.Length(max=500))


venta_schema = VentaSchema()
cobrar_input_schema = CobrarInputSchema()
cancelar_input_schema = CancelarInputSchema()
