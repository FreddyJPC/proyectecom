from marshmallow import EXCLUDE, Schema, fields, validate


class SkuMonitoreadoInputSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    sku = fields.Str(data_key="sku", required=True, validate=validate.Length(min=1))
    umbral_stock_minimo = fields.Int(
        data_key="umbralStockMinimo", load_default=5, validate=validate.Range(min=0)
    )


class SkuMonitoreadoResponseSchema(Schema):
    sku = fields.Str()
    umbral_stock_minimo = fields.Int(data_key="umbralStockMinimo")
    activo = fields.Bool()
    ultimo_stock = fields.Int(data_key="ultimoStock", allow_none=True)
    ultimo_precio = fields.Str(data_key="ultimoPrecio", allow_none=True)
    ultimo_snapshot_en = fields.Str(data_key="ultimoSnapshotEn", allow_none=True)


sku_monitoreado_input_schema = SkuMonitoreadoInputSchema()
skus_monitoreados_response_schema = SkuMonitoreadoResponseSchema(many=True)
